"""
Flask Backend for IoT Smart Home Monitor
Main application file with Admin System, SocketIO, and MQTT Integration

Startup order:
  1. Flask + SQLAlchemy + SocketIO initialised
  2. Database tables created, default superadmin created
  3. MQTTHandler instantiated and connected to broker
  4. SocketIO server started (replaces app.run)

MQTT topics consumed (published by HPS C application):
  smarthome/sensors  →  live sensor data every 5 s
  smarthome/alarms   →  alarm notifications (edge-triggered, 5 min cooldown)

SocketIO events emitted to browsers:
  sensor_update   →  full sensor payload on every MQTT sensors message
  alarm_update    →  alarm payload on every MQTT alarms message
  mqtt_status     →  {'status': 'connected'|'disconnected'}
"""

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
from flask_socketio import SocketIO
from dotenv import load_dotenv
import os
import logging
from datetime import datetime, timedelta

from models import db, SensorData, AlarmEvent, SystemStatus, ControlSettings
from admin_models import User, UserPermission, UserSession, ActivityLog
from auth_routes import auth_bp, login_required, permission_required
from admin_routes import admin_bp
from mqtt_handler import MQTTHandler

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flask application
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY']                  = os.getenv('FLASK_SECRET_KEY', 'change-this-secret-key')
app.config['SQLALCHEMY_DATABASE_URI']     = os.getenv('DATABASE_URI', 'sqlite:///smarthome.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME']  = timedelta(days=7)

# ---------------------------------------------------------------------------
# Extensions
# ---------------------------------------------------------------------------
CORS(app, resources={r"/*": {"origins": "*"}})
db.init_app(app)

# SocketIO — use 'threading' async_mode so it works with paho-mqtt's
# background thread without needing gevent or eventlet.
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ---------------------------------------------------------------------------
# Blueprints
# ---------------------------------------------------------------------------
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)

# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------
with app.app_context():
    db.create_all()
    logger.info("Database tables created / verified")

    # Default control settings
    default_settings = [
        {'setting_name': 'temp_threshold_high', 'value': 30.0, 'unit': '°C'},
        {'setting_name': 'temp_threshold_low',  'value': 15.0, 'unit': '°C'},
        {'setting_name': 'light_threshold',     'value': 40.0, 'unit': '%'},
        {'setting_name': 'motion_enabled',      'value': 1.0,  'unit': 'boolean'},
    ]
    for sd in default_settings:
        if not ControlSettings.query.filter_by(setting_name=sd['setting_name']).first():
            db.session.add(ControlSettings(**sd))

    # Default superadmin account
    if not User.query.filter_by(username='admin').first():
        superadmin = User(
            username='admin',
            email='admin@example.com',
            full_name='System Administrator',
            role='superadmin',
            is_active=True
        )
        superadmin.set_password('admin123')
        db.session.add(superadmin)
        logger.info("=" * 60)
        logger.info("Default superadmin created  —  admin / admin123")
        logger.info("⚠️  Change this password immediately after first login!")
        logger.info("=" * 60)

    db.session.commit()
    logger.info("Database initialisation complete")

# ---------------------------------------------------------------------------
# MQTT handler
# Instantiated after the app context so it can call db.session inside
# app_context() blocks when processing incoming messages.
# ---------------------------------------------------------------------------
mqtt_handler = MQTTHandler(app=app, socketio=socketio, db=db)
mqtt_handler.connect()


# ===========================================================================
# SocketIO events
# ===========================================================================

@socketio.on('connect')
def handle_connect():
    """Send the latest cached sensor data to a newly connected browser."""
    cache = mqtt_handler.get_sensor_cache()
    if cache.get('last_updated'):
        # Re-emit the full cache so the page is populated immediately
        socketio.emit('sensor_update', {
            'temperature': cache['temperature'],
            'pressure':    cache['pressure'],
            'humidity':    cache['humidity'],
            'light':       cache['light'],
            'heating':     cache['heating'],
            'sound':       cache['sound'],
            'pir':         cache['pir'],
            'alarm_flags': cache['alarm_flags'],
            'timestamp':   cache['last_updated'],
            'alarms': {
                'temp_high': bool(cache['alarm_flags'] & 0x01),
                'temp_low':  bool(cache['alarm_flags'] & 0x02),
                'light_low': bool(cache['alarm_flags'] & 0x04),
                'motion':    bool(cache['alarm_flags'] & 0x08),
                'critical':  bool(cache['alarm_flags'] & 0x10),
            }
        }, room=request.sid)

    if cache.get('last_alarm'):
        socketio.emit('alarm_update', cache['last_alarm'], room=request.sid)

    # Tell the browser whether MQTT is currently connected
    socketio.emit('mqtt_status',
                  {'status': 'connected' if mqtt_handler.connected else 'disconnected'},
                  room=request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    logger.debug(f"SocketIO client disconnected: {request.sid}")


# ===========================================================================
# Web routes
# ===========================================================================

@app.route('/')
@login_required
def index():
    return render_template('dashboard.html', page='dashboard')

@app.route('/sensors')
@login_required
@permission_required('view_sensors')
def sensors():
    return render_template('sensors.html', page='sensors')

@app.route('/communication')
@login_required
@permission_required('view_communication')
def communication():
    return render_template('communication.html', page='communication')

@app.route('/security')
@login_required
@permission_required('view_security')
def security():
    return render_template('security.html', page='security')

@app.route('/event-logs')
@login_required
@permission_required('view_event_logs')
def event_logs():
    return render_template('event_logs.html', page='event-logs')

@app.route('/settings')
@login_required
@permission_required('view_settings')
def settings_page():
    return render_template('settings.html', page='settings')


# ===========================================================================
# REST API — sensor data
# ===========================================================================

@app.route('/api/status')
@login_required
def get_status():
    """Current system / MQTT status."""
    return jsonify({
        'timestamp':    datetime.utcnow().isoformat(),
        'user':         session.get('username'),
        'role':         session.get('role'),
        'mqtt_connected': mqtt_handler.connected,
    })

@app.route('/api/sensors/latest')
@login_required
@permission_required('view_sensors')
def get_latest_sensors():
    """
    Return the latest sensor values from the MQTT in-memory cache.
    The cache is populated by MQTTHandler._handle_sensors() every time
    the HPS publishes to smarthome/sensors (every MQTT_PUBLISH_INTERVAL seconds).
    """
    cache = mqtt_handler.get_sensor_cache()

    if cache.get('last_updated') is None:
        # Board hasn't published yet — return empty with a flag
        return jsonify({
            'available': False,
            'message': 'No data received from board yet. Check MQTT connection.'
        })

    return jsonify({
        'available':   True,
        'temperature': cache['temperature'],
        'pressure':    cache['pressure'],
        'humidity':    cache['humidity'],
        'light':       cache['light'],
        'heating':     cache['heating'],
        'sound':       cache['sound'],
        'pir':         cache['pir'],
        'motion':      bool(cache['pir']),       # any PIR active
        'alarm_flags': cache['alarm_flags'],
        'timestamp':   cache['last_updated'],
        # Decoded alarm booleans for easy frontend consumption
        'alarms': {
            'temp_high': bool(cache['alarm_flags'] & 0x01),
            'temp_low':  bool(cache['alarm_flags'] & 0x02),
            'light_low': bool(cache['alarm_flags'] & 0x04),
            'motion':    bool(cache['alarm_flags'] & 0x08),
            'critical':  bool(cache['alarm_flags'] & 0x10),
        }
    })

@app.route('/api/sensors/history/<sensor_type>')
@login_required
@permission_required('view_sensors')
def get_sensor_history(sensor_type):
    """Return historical sensor readings from the database."""
    hours      = request.args.get('hours', default=24, type=int)
    start_time = datetime.utcnow() - timedelta(hours=hours)

    readings = SensorData.query.filter(
        SensorData.sensor_type == sensor_type,
        SensorData.timestamp   >= start_time
    ).order_by(SensorData.timestamp.desc()).limit(200).all()

    return jsonify([r.to_dict() for r in readings])


# ===========================================================================
# REST API — alarms
# ===========================================================================

@app.route('/api/alarms')
@login_required
@permission_required('view_security')
def get_alarms():
    """Return alarm events with optional server-side pagination.

    Query params:
      page     – 1-based page number (default 1)
      per_page – rows per page (default 15, max 100)
      severity – filter by severity string
      type     – filter by alarm_type string
    Legacy: limit param still accepted (returns flat list without meta).
    """
    # Legacy flat-list mode
    if 'limit' in request.args and 'page' not in request.args:
        limit  = request.args.get('limit', default=50, type=int)
        alarms = AlarmEvent.query.order_by(AlarmEvent.timestamp.desc()).limit(limit).all()
        return jsonify([a.to_dict() for a in alarms])

    page     = request.args.get('page',     default=1,  type=int)
    per_page = min(request.args.get('per_page', default=15, type=int), 100)
    severity = request.args.get('severity', default='', type=str)
    atype    = request.args.get('type',     default='', type=str)

    q = AlarmEvent.query
    if severity: q = q.filter(AlarmEvent.severity   == severity)
    if atype:    q = q.filter(AlarmEvent.alarm_type == atype)
    q = q.order_by(AlarmEvent.timestamp.desc())

    total   = q.count()
    alarms  = q.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        'items':      [a.to_dict() for a in alarms],
        'total':      total,
        'page':       page,
        'per_page':   per_page,
        'total_pages': max(1, (total + per_page - 1) // per_page),
    })

@app.route('/api/alarms/<int:alarm_id>/acknowledge', methods=['POST'])
@login_required
@permission_required('control_alarm')
def acknowledge_alarm(alarm_id):
    """Mark an alarm as acknowledged."""
    alarm = AlarmEvent.query.get_or_404(alarm_id)
    alarm.acknowledged = True
    db.session.commit()

    db.session.add(ActivityLog(
        user_id=session['user_id'],
        action='acknowledge_alarm',
        resource='alarms',
        details=f'Acknowledged alarm #{alarm_id}',
        ip_address=request.remote_addr
    ))
    db.session.commit()

    return jsonify({'success': True, 'alarm': alarm.to_dict()})


# ===========================================================================
# REST API — settings
# ===========================================================================

@app.route('/api/settings', methods=['GET'])
@login_required
@permission_required('view_settings')
def get_settings():
    settings = ControlSettings.query.all()
    return jsonify([s.to_dict() for s in settings])

@app.route('/api/settings/<setting_name>', methods=['PUT'])
@login_required
@permission_required('modify_settings')
def update_setting(setting_name):
    data    = request.get_json()
    setting = ControlSettings.query.filter_by(setting_name=setting_name).first()
    if not setting:
        setting = ControlSettings(setting_name=setting_name)
        db.session.add(setting)

    setting.value = float(data.get('value', 0))
    setting.unit  = data.get('unit', '')
    db.session.commit()

    db.session.add(ActivityLog(
        user_id=session['user_id'],
        action='update_setting',
        resource='settings',
        details=f'Updated {setting_name} to {setting.value}',
        ip_address=request.remote_addr
    ))
    db.session.commit()

    return jsonify({'success': True, 'setting': setting.to_dict()})


# ===========================================================================
# REST API — control endpoints
# ===========================================================================

@app.route('/api/control/alarm', methods=['POST'])
@login_required
@permission_required('control_alarm')
def control_alarm():
    """Arm or disarm the alarm system."""
    data   = request.get_json()
    action = data.get('action', 'disarm')

    db.session.add(ActivityLog(
        user_id=session['user_id'],
        action='control_alarm',
        resource='alarm',
        details=f'Alarm {action}',
        ip_address=request.remote_addr
    ))
    db.session.commit()

    return jsonify({'success': True, 'action': action})

@app.route('/api/control/test-alarm', methods=['POST'])
@login_required
@permission_required('control_alarm')
def test_alarm():
    """Trigger a test alarm."""
    db.session.add(ActivityLog(
        user_id=session['user_id'],
        action='test_alarm',
        resource='alarm',
        details='Test alarm triggered',
        ip_address=request.remote_addr
    ))
    db.session.commit()

    return jsonify({'success': True, 'message': 'Test alarm triggered'})

@app.route('/api/control/heating', methods=['POST'])
@login_required
@permission_required('control_heating')
def control_heating():
    """Set the heating level."""
    data  = request.get_json()
    level = float(data.get('level', 0))

    db.session.add(ActivityLog(
        user_id=session['user_id'],
        action='control_heating',
        resource='heating',
        details=f'Set heating level to {level}',
        ip_address=request.remote_addr
    ))
    db.session.commit()

    return jsonify({'success': True, 'level': level})

@app.route('/api/control/sound', methods=['POST'])
@login_required
@permission_required('control_sound')
def control_sound():
    """Set the sound volume."""
    data   = request.get_json()
    volume = float(data.get('volume', 0))

    db.session.add(ActivityLog(
        user_id=session['user_id'],
        action='control_sound',
        resource='sound',
        details=f'Set sound volume to {volume}',
        ip_address=request.remote_addr
    ))
    db.session.commit()

    return jsonify({'success': True, 'volume': volume})


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == '__main__':
    host  = os.getenv('FLASK_HOST',  '0.0.0.0')
    port  = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True') == 'True'

    logger.info("=" * 60)
    logger.info(f"Starting Smart Home server on {host}:{port}")
    logger.info("Default admin: admin / admin123  — change immediately!")
    logger.info("SocketIO async_mode: threading")
    logger.info(f"MQTT broker: {mqtt_handler.broker_host}:{mqtt_handler.broker_port}")
    logger.info("=" * 60)

    # use_reloader=False  → prevents Flask from spawning a second watcher process
    #                        that would create a duplicate MQTT client with the same
    #                        client-ID, causing the broker to kick one out (rc=7).
    # allow_unsafe_werkzeug=True → required by Flask-SocketIO when running the
    #                              built-in Werkzeug server with debug=True.
    socketio.run(app, host=host, port=port, debug=debug,
                 use_reloader=False, allow_unsafe_werkzeug=True)
