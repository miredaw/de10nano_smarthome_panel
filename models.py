"""
Database models for IoT Smart Home Monitor
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class SensorData(db.Model):
    """Store sensor readings"""
    __tablename__ = 'sensor_data'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    sensor_type = db.Column(db.String(50), nullable=False)  # temperature, light, motion
    value = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20))
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'sensor_type': self.sensor_type,
            'value': self.value,
            'unit': self.unit
        }

class AlarmEvent(db.Model):
    """Store alarm events"""
    __tablename__ = 'alarm_events'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    alarm_type = db.Column(db.String(50), nullable=False)  # motion, temperature, etc.
    severity = db.Column(db.String(20), nullable=False)  # warning, critical
    message = db.Column(db.Text, nullable=False)
    acknowledged = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'alarm_type': self.alarm_type,
            'severity': self.severity,
            'message': self.message,
            'acknowledged': self.acknowledged
        }

class SystemStatus(db.Model):
    """Store system status information"""
    __tablename__ = 'system_status'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    component = db.Column(db.String(50), nullable=False)  # wifi, gsm, fpga, etc.
    status = db.Column(db.String(20), nullable=False)  # online, offline, error
    details = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'component': self.component,
            'status': self.status,
            'details': self.details
        }

class ControlSettings(db.Model):
    """Store control settings and thresholds"""
    __tablename__ = 'control_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    setting_name = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'setting_name': self.setting_name,
            'value': self.value,
            'unit': self.unit,
            'updated_at': self.updated_at.isoformat()
        }
