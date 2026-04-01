"""
Admin and User Management Models
"""

from models import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import secrets

class User(db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120))
    role = db.Column(db.String(20), default='user')  # 'superadmin', 'admin', 'user'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    permissions = db.relationship('UserPermission', 
                                 foreign_keys='UserPermission.user_id',
                                 backref='user', 
                                 lazy=True, 
                                 cascade='all, delete-orphan')
    sessions = db.relationship('UserSession', backref='user', lazy=True, cascade='all, delete-orphan')
    activity_logs = db.relationship('ActivityLog', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def has_permission(self, permission_name):
        """Check if user has a specific permission"""
        if self.role == 'superadmin':
            return True
        
        perm = UserPermission.query.filter_by(
            user_id=self.id,
            permission_name=permission_name,
            is_granted=True
        ).first()
        return perm is not None
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class UserPermission(db.Model):
    """User permissions model"""
    __tablename__ = 'user_permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    permission_name = db.Column(db.String(50), nullable=False)  # e.g., 'view_sensors', 'control_alarm'
    is_granted = db.Column(db.Boolean, default=True)
    granted_by = db.Column(db.Integer)  # Store user ID without foreign key constraint
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'permission_name': self.permission_name,
            'is_granted': self.is_granted,
            'granted_at': self.granted_at.isoformat() if self.granted_at else None
        }

class UserSession(db.Model):
    """Track user sessions"""
    __tablename__ = 'user_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_token = db.Column(db.String(255), unique=True, nullable=False)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    
    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(32)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active
        }

class ActivityLog(db.Model):
    """Log user activities"""
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    resource = db.Column(db.String(100))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'action': self.action,
            'resource': self.resource,
            'details': self.details,
            'ip_address': self.ip_address,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

# Available permissions
AVAILABLE_PERMISSIONS = [
    {'name': 'view_dashboard', 'description': 'View main dashboard'},
    {'name': 'view_sensors', 'description': 'View sensors page'},
    {'name': 'view_communication', 'description': 'View communication page'},
    {'name': 'view_security', 'description': 'View security page'},
    {'name': 'view_event_logs', 'description': 'View event logs'},
    {'name': 'view_settings', 'description': 'View settings page'},
    {'name': 'control_alarm', 'description': 'Control alarm system'},
    {'name': 'control_heating', 'description': 'Control heating system'},
    {'name': 'control_sound', 'description': 'Control sound system'},
    {'name': 'modify_settings', 'description': 'Modify system settings'},
    {'name': 'view_admin_panel', 'description': 'Access admin panel'},
    {'name': 'manage_users', 'description': 'Manage users (superadmin only)'},
]
