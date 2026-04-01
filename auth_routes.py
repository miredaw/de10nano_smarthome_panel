"""
Authentication routes for admin system
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from datetime import datetime, timedelta
from admin_models import db, User, UserSession, ActivityLog

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_active:
            session.clear()
            return redirect(url_for('auth.login'))
        
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission_name):
    """Decorator to require specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            
            user = User.query.get(session['user_id'])
            if not user or not user.is_active:
                return jsonify({'error': 'User not active'}), 403
            
            if not user.has_permission(permission_name):
                return jsonify({'error': 'Permission denied'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def superadmin_required(f):
    """Decorator to require superadmin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        
        user = User.query.get(session['user_id'])
        if not user or user.role != 'superadmin':
            return jsonify({'error': 'Superadmin access required'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET'])
def login():
    """Render login page"""
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@auth_bp.route('/api/auth/login', methods=['POST'])
def api_login():
    """Handle login request"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    user = User.query.filter_by(username=username).first()
    
    if not user or not user.check_password(password):
        # Log failed attempt
        if user:
            activity = ActivityLog(
                user_id=user.id,
                action='login_failed',
                details=f'Failed login attempt for username: {username}',
                ip_address=request.remote_addr
            )
            db.session.add(activity)
            db.session.commit()
        return jsonify({'error': 'Invalid credentials'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is disabled'}), 403
    
    # Update last login
    user.last_login = datetime.utcnow()
    
    # Create session
    session['user_id'] = user.id
    session['username'] = user.username
    session['role'] = user.role
    session.permanent = True
    
    # Create session token
    session_token = UserSession.generate_token()
    user_session = UserSession(
        user_id=user.id,
        session_token=session_token,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent'),
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db.session.add(user_session)
    
    # Log successful login
    activity = ActivityLog(
        user_id=user.id,
        action='login',
        details='Successful login',
        ip_address=request.remote_addr
    )
    db.session.add(activity)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'user': user.to_dict(),
        'redirect': url_for('index')
    })

@auth_bp.route('/api/auth/logout', methods=['POST'])
@login_required
def api_logout():
    """Handle logout request"""
    user_id = session.get('user_id')
    
    if user_id:
        # Log activity
        activity = ActivityLog(
            user_id=user_id,
            action='logout',
            details='User logged out',
            ip_address=request.remote_addr
        )
        db.session.add(activity)
        db.session.commit()
    
    session.clear()
    return jsonify({'success': True, 'redirect': url_for('auth.login')})

@auth_bp.route('/api/auth/current-user', methods=['GET'])
@login_required
def get_current_user():
    """Get current logged in user"""
    user = User.query.get(session['user_id'])
    if user:
        permissions = [p.permission_name for p in user.permissions if p.is_granted]
        return jsonify({
            'user': user.to_dict(),
            'permissions': permissions
        })
    return jsonify({'error': 'User not found'}), 404
