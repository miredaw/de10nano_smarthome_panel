"""
MQTT Client Handler for IoT Smart Home Monitor
Subscribes to the two topics published by the HPS C application:

  smarthome/sensors  →  {ts, temp, press, humid, light, heat, sound, pir, alarms}
  smarthome/alarms   →  {ts, msg, alarms}

Alarm flag bits (matching smart_home.h):
  bit 0 = ALARM_TEMP_HIGH
  bit 1 = ALARM_TEMP_LOW
  bit 2 = ALARM_LIGHT_LOW
  bit 3 = ALARM_MOTION
  bit 4 = ALARM_CRITICAL
"""

import paho.mqtt.client as mqtt
import json
import logging
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

logger = logging.getLogger(__name__)

# Alarm flag bitmasks (must match smart_home.h)
ALARM_TEMP_HIGH  = (1 << 0)
ALARM_TEMP_LOW   = (1 << 1)
ALARM_LIGHT_LOW  = (1 << 2)
ALARM_MOTION     = (1 << 3)
ALARM_CRITICAL   = (1 << 4)

ALARM_DESCRIPTIONS = {
    ALARM_TEMP_HIGH : ('temp_high',  'critical', 'High temperature alarm'),
    ALARM_TEMP_LOW  : ('temp_low',   'warning',  'Low temperature alarm'),
    ALARM_LIGHT_LOW : ('light_low',  'warning',  'Low light level alarm'),
    ALARM_MOTION    : ('motion',     'warning',  'Motion detected'),
    ALARM_CRITICAL  : ('critical',   'critical', 'Critical alarm condition'),
}


class MQTTHandler:
    def __init__(self, app=None, socketio=None, db=None):
        self.app      = app
        self.socketio = socketio
        self.db       = db
        # Include the process PID in the client-ID so that if the dev-server
        # reloader ever spawns a second process, both clients get distinct IDs
        # and neither will be kicked off the broker.
        self.client   = mqtt.Client(client_id=f"smarthome-flask-{os.getpid()}")
        self.connected = False

        # MQTT broker connection settings (from .env)
        self.broker_host = os.getenv('MQTT_BROKER_HOST', 'localhost')
        self.broker_port = int(os.getenv('MQTT_BROKER_PORT', 1883))
        self.username    = os.getenv('MQTT_USERNAME',    'smarthome')
        self.password    = os.getenv('MQTT_PASSWORD',    'yourpassword')

        # The two topics the HPS C application publishes to
        # (defined as MQTT_TOPIC_SENSORS / MQTT_TOPIC_ALARMS in smart_home.h)
        self.topic_sensors = os.getenv('MQTT_TOPIC_SENSORS', 'smarthome/sensors')
        self.topic_alarms  = os.getenv('MQTT_TOPIC_ALARMS',  'smarthome/alarms')

        # In-memory cache of the most recent values — used by /api/sensors/latest
        self.sensor_cache = {
            'temperature':  None,   # float °C
            'pressure':     None,   # float hPa
            'humidity':     None,   # float %
            'light':        None,   # int 0-1023 (ADC counts)
            'heating':      None,   # int 0-1023
            'sound':        None,   # int 0-1023
            'pir':          None,   # int bitmask (bit0=PIR1, bit1=PIR2)
            'alarm_flags':  0,      # int bitmask
            'last_updated': None,   # ISO timestamp string
            'last_alarm':   None,   # dict from most recent alarm message
        }

        # MQTT client callbacks
        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message    = self._on_message

        # Only set credentials if a username is actually configured.
        # A fresh mosquitto install with allow_anonymous true will reject
        # a username_pw_set() call with rc=5 (not authorised).
        if self.username:
            self.client.username_pw_set(self.username, self.password)

        # Back off between reconnect attempts: start at 5 s, cap at 60 s.
        # Prevents the log from being flooded when the broker is down.
        self.client.reconnect_delay_set(min_delay=5, max_delay=60)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self):
        """Connect to the MQTT broker and start the background thread."""
        try:
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            logger.info(f"MQTT: connecting to {self.broker_host}:{self.broker_port}")
        except Exception as e:
            logger.error(f"MQTT: connection failed — {e}")

    def disconnect(self):
        """Stop the background thread and disconnect cleanly."""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("MQTT: disconnected")

    # ------------------------------------------------------------------
    # paho callbacks
    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info("MQTT: connected to broker")

            # Subscribe to both HPS topics
            client.subscribe(self.topic_sensors)
            client.subscribe(self.topic_alarms)
            logger.info(f"MQTT: subscribed to '{self.topic_sensors}' and '{self.topic_alarms}'")

            if self.socketio:
                self.socketio.emit('mqtt_status', {'status': 'connected'})
        else:
            self.connected = False
            logger.error(f"MQTT: broker rejected connection (rc={rc})")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        logger.warning(f"MQTT: disconnected (rc={rc})")
        if self.socketio:
            self.socketio.emit('mqtt_status', {'status': 'disconnected'})

    def _on_message(self, client, userdata, msg):
        try:
            topic   = msg.topic
            payload = msg.payload.decode('utf-8')
            data    = json.loads(payload)
            logger.debug(f"MQTT ← {topic}: {payload[:120]}")

            if topic == self.topic_sensors:
                self._handle_sensors(data)
            elif topic == self.topic_alarms:
                self._handle_alarm(data)

        except json.JSONDecodeError as e:
            logger.error(f"MQTT: JSON parse error on {msg.topic}: {e}")
        except Exception as e:
            logger.error(f"MQTT: message handler error: {e}")

    # ------------------------------------------------------------------
    # Sensor message handler
    # Payload from build_mqtt_payload() in main_supervisor.c:
    #   {ts, temp, press, humid, light, heat, sound, pir, alarms}
    # ------------------------------------------------------------------

    def _handle_sensors(self, data):
        """Process the combined sensor payload from smarthome/sensors."""

        # Extract all fields using the exact key names from main_supervisor.c
        temp     = float(data.get('temp',   0))
        press    = float(data.get('press',  0))
        humid    = float(data.get('humid',  0))
        light    = int(data.get('light',    0))
        heat     = int(data.get('heat',     0))
        sound    = int(data.get('sound',    0))
        pir      = int(data.get('pir',      0))
        alarms   = int(data.get('alarms',   0))
        ts_epoch = int(data.get('ts',       0))
        ts_iso   = datetime.utcfromtimestamp(ts_epoch).isoformat() if ts_epoch else datetime.utcnow().isoformat()

        # Update in-memory cache
        self.sensor_cache.update({
            'temperature':  temp,
            'pressure':     press,
            'humidity':     humid,
            'light':        light,
            'heating':      heat,
            'sound':        sound,
            'pir':          pir,
            'alarm_flags':  alarms,
            'last_updated': ts_iso,
        })

        # Persist individual sensor rows to the database
        if self.app and self.db:
            with self.app.app_context():
                from models import SensorData, AlarmEvent
                rows = [
                    SensorData(sensor_type='temperature', value=temp,  unit='°C',      timestamp=datetime.utcfromtimestamp(ts_epoch)),
                    SensorData(sensor_type='pressure',    value=press, unit='hPa',     timestamp=datetime.utcfromtimestamp(ts_epoch)),
                    SensorData(sensor_type='humidity',    value=humid, unit='%',       timestamp=datetime.utcfromtimestamp(ts_epoch)),
                    SensorData(sensor_type='light',       value=light, unit='ADC',     timestamp=datetime.utcfromtimestamp(ts_epoch)),
                    SensorData(sensor_type='heating',     value=heat,  unit='ADC',     timestamp=datetime.utcfromtimestamp(ts_epoch)),
                    SensorData(sensor_type='sound',       value=sound, unit='ADC',     timestamp=datetime.utcfromtimestamp(ts_epoch)),
                    SensorData(sensor_type='motion',      value=float(bool(pir)),
                               unit='boolean', timestamp=datetime.utcfromtimestamp(ts_epoch)),
                ]
                self.db.session.bulk_save_objects(rows)

                # Create AlarmEvent rows for any newly set alarm bits
                for bit, (alarm_type, severity, default_msg) in ALARM_DESCRIPTIONS.items():
                    if alarms & bit:
                        alarm_event = AlarmEvent(
                            alarm_type=alarm_type,
                            severity=severity,
                            message=default_msg,
                            timestamp=datetime.utcfromtimestamp(ts_epoch)
                        )
                        self.db.session.add(alarm_event)

                self.db.session.commit()

        # Push live update to all connected browsers via SocketIO
        if self.socketio:
            self.socketio.emit('sensor_update', {
                'temperature': temp,
                'pressure':    press,
                'humidity':    humid,
                'light':       light,
                'heating':     heat,
                'sound':       sound,
                'pir':         pir,
                'alarm_flags': alarms,
                'timestamp':   ts_iso,
                # Convenience decoded alarm booleans for the frontend
                'alarms': {
                    'temp_high':  bool(alarms & ALARM_TEMP_HIGH),
                    'temp_low':   bool(alarms & ALARM_TEMP_LOW),
                    'light_low':  bool(alarms & ALARM_LIGHT_LOW),
                    'motion':     bool(alarms & ALARM_MOTION),
                    'critical':   bool(alarms & ALARM_CRITICAL),
                }
            })

    # ------------------------------------------------------------------
    # Alarm message handler
    # Payload from handle_alarms() in main_supervisor.c:
    #   {ts, msg, alarms}
    # ------------------------------------------------------------------

    def _handle_alarm(self, data):
        """Process a dedicated alarm notification from smarthome/alarms."""

        ts_epoch = int(data.get('ts', 0))
        ts_iso   = datetime.utcfromtimestamp(ts_epoch).isoformat() if ts_epoch else datetime.utcnow().isoformat()
        msg      = data.get('msg',    'Alarm triggered')
        alarms   = int(data.get('alarms', 0))

        self.sensor_cache['last_alarm'] = {
            'message':     msg,
            'alarm_flags': alarms,
            'timestamp':   ts_iso,
        }

        # Determine severity: any CRITICAL or TEMP bit → critical, else warning
        severity = 'critical' if (alarms & (ALARM_TEMP_HIGH | ALARM_CRITICAL)) else 'warning'

        # Determine alarm_type from highest-priority bit
        alarm_type = 'system'
        for bit in (ALARM_CRITICAL, ALARM_TEMP_HIGH, ALARM_TEMP_LOW, ALARM_MOTION, ALARM_LIGHT_LOW):
            if alarms & bit:
                alarm_type = ALARM_DESCRIPTIONS[bit][0]
                break

        # Save to database
        if self.app and self.db:
            with self.app.app_context():
                from models import AlarmEvent
                alarm_event = AlarmEvent(
                    alarm_type=alarm_type,
                    severity=severity,
                    message=msg,
                    timestamp=datetime.utcfromtimestamp(ts_epoch)
                )
                self.db.session.add(alarm_event)
                self.db.session.commit()

        logger.warning(f"MQTT ALARM [{severity}] {msg} (flags=0x{alarms:02X})")

        # Push to browser
        if self.socketio:
            self.socketio.emit('alarm_update', {
                'alarm_type':  alarm_type,
                'severity':    severity,
                'message':     msg,
                'alarm_flags': alarms,
                'timestamp':   ts_iso,
                'alarms': {
                    'temp_high': bool(alarms & ALARM_TEMP_HIGH),
                    'temp_low':  bool(alarms & ALARM_TEMP_LOW),
                    'light_low': bool(alarms & ALARM_LIGHT_LOW),
                    'motion':    bool(alarms & ALARM_MOTION),
                    'critical':  bool(alarms & ALARM_CRITICAL),
                }
            })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_sensor_cache(self):
        """Return the current in-memory sensor cache (used by REST endpoints)."""
        return self.sensor_cache

    def publish(self, topic, message):
        """
        Publish a raw message to any MQTT topic.
        Pass a dict for automatic JSON serialisation.
        """
        if not self.connected:
            logger.error("MQTT publish failed: not connected")
            return False
        try:
            if isinstance(message, dict):
                message = json.dumps(message)
            result = self.client.publish(topic, message)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            logger.error(f"MQTT publish error: {e}")
            return False
