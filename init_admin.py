"""
Initialize the admin system with default superadmin user
Run this once to set up the admin system
"""

from admin_models import db, User, AVAILABLE_PERMISSIONS
from flask import Flask
import os

def init_admin_system(app):
    """Initialize admin system with default superadmin"""
    
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if superadmin exists
        superadmin = User.query.filter_by(username='admin').first()
        
        if not superadmin:
            # Create default superadmin
            superadmin = User(
                username='admin',
                email='admin@example.com',
                full_name='System Administrator',
                role='superadmin',
                is_active=True
            )
            superadmin.set_password('admin123')  # Change this password!
            
            db.session.add(superadmin)
            db.session.commit()
            
            print("=" * 60)
            print("Admin system initialized successfully!")
            print("=" * 60)
            print("Default superadmin credentials:")
            print("  Username: admin")
            print("  Password: admin123")
            print("=" * 60)
            print("⚠️  IMPORTANT: Change the default password immediately!")
            print("=" * 60)
        else:
            print("Admin system already initialized")

if __name__ == '__main__':
    # Create a minimal Flask app for initialization
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///smarthome.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    init_admin_system(app)
