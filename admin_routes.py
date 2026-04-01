"""
Admin panel routes for user and permission management
"""

from flask import Blueprint, render_template, request, jsonify, session
from auth_routes import login_required, superadmin_required, permission_required
from admin_models import db, User, UserPermission, ActivityLog, AVAILABLE_PERMISSIONS
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
@login_required
@permission_required('view_admin_panel')
def admin_dashboard():
    """Render admin dashboard"""
    return render_template('admin_dashboard.html', page='admin')

@admin_bp.route('/users')
@login_required
@superadmin_required
def admin_users():
    """Render user management page"""
    return render_template('admin_users.html', page='admin-users')

@admin_bp.route('/activity-logs')
@login_required
@permission_required('view_admin_panel')
def admin_activity():
    """Render activity logs page"""
    return render_template('admin_activity.html', page='admin-activity')

# API Routes

@admin_bp.route('/api/users', methods=['GET'])
@login_required
@superadmin_required
def get_users():
    """Get all users"""
    users = User.query.all()
    return jsonify([user.to_dict() for user in users])

@admin_bp.route('/api/users/<int:user_id>', methods=['GET'])
@login_required
@superadmin_required
def get_user(user_id):
    """Get specific user with permissions"""
    user = User.query.get_or_404(user_id)
    permissions = UserPermission.query.filter_by(user_id=user_id).all()
    
    return jsonify({
        'user': user.to_dict(),
        'permissions': [p.to_dict() for p in permissions]
    })

@admin_bp.route('/api/users', methods=['POST'])
@login_required
@superadmin_required
def create_user():
    """Create new user"""
    data = request.get_json()
    
    # Validate required fields
    if not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Username, email, and password are required'}), 400
    
    # Check if username or email already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400
    
    # Create user
    user = User(
        username=data['username'],
        email=data['email'],
        full_name=data.get('full_name', ''),
        role=data.get('role', 'user')
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    # Log activity
    activity = ActivityLog(
        user_id=session['user_id'],
        action='create_user',
        resource='users',
        details=f'Created user: {user.username}',
        ip_address=request.remote_addr
    )
    db.session.add(activity)
    db.session.commit()
    
    return jsonify({'success': True, 'user': user.to_dict()}), 201

@admin_bp.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
@superadmin_required
def update_user(user_id):
    """Update user"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    # Prevent superadmin from being demoted by another superadmin
    if user.role == 'superadmin' and data.get('role') != 'superadmin':
        superadmin_count = User.query.filter_by(role='superadmin', is_active=True).count()
        if superadmin_count <= 1:
            return jsonify({'error': 'Cannot demote the last superadmin'}), 400
    
    # Update fields
    if 'email' in data and data['email'] != user.email:
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 400
        user.email = data['email']
    
    if 'full_name' in data:
        user.full_name = data['full_name']
    
    if 'role' in data:
        user.role = data['role']
    
    if 'is_active' in data:
        user.is_active = data['is_active']
    
    if 'password' in data and data['password']:
        user.set_password(data['password'])
    
    db.session.commit()
    
    # Log activity
    activity = ActivityLog(
        user_id=session['user_id'],
        action='update_user',
        resource='users',
        details=f'Updated user: {user.username}',
        ip_address=request.remote_addr
    )
    db.session.add(activity)
    db.session.commit()
    
    return jsonify({'success': True, 'user': user.to_dict()})

@admin_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
@superadmin_required
def delete_user(user_id):
    """Delete user"""
    user = User.query.get_or_404(user_id)
    
    # Prevent deletion of last superadmin
    if user.role == 'superadmin':
        superadmin_count = User.query.filter_by(role='superadmin', is_active=True).count()
        if superadmin_count <= 1:
            return jsonify({'error': 'Cannot delete the last superadmin'}), 400
    
    # Prevent self-deletion
    if user.id == session['user_id']:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    username = user.username
    db.session.delete(user)
    
    # Log activity
    activity = ActivityLog(
        user_id=session['user_id'],
        action='delete_user',
        resource='users',
        details=f'Deleted user: {username}',
        ip_address=request.remote_addr
    )
    db.session.add(activity)
    db.session.commit()
    
    return jsonify({'success': True})

@admin_bp.route('/api/permissions/available', methods=['GET'])
@login_required
@superadmin_required
def get_available_permissions():
    """Get list of available permissions"""
    return jsonify(AVAILABLE_PERMISSIONS)

@admin_bp.route('/api/users/<int:user_id>/permissions', methods=['GET'])
@login_required
@superadmin_required
def get_user_permissions(user_id):
    """Get user permissions"""
    user = User.query.get_or_404(user_id)
    permissions = UserPermission.query.filter_by(user_id=user_id).all()
    
    return jsonify({
        'user_id': user_id,
        'username': user.username,
        'role': user.role,
        'permissions': [p.to_dict() for p in permissions]
    })

@admin_bp.route('/api/users/<int:user_id>/permissions', methods=['POST'])
@login_required
@superadmin_required
def grant_permission(user_id):
    """Grant permission to user"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    permission_name = data.get('permission_name')
    if not permission_name:
        return jsonify({'error': 'Permission name required'}), 400
    
    # Check if permission already exists
    existing = UserPermission.query.filter_by(
        user_id=user_id,
        permission_name=permission_name
    ).first()
    
    if existing:
        existing.is_granted = True
        existing.granted_by = session['user_id']
        existing.granted_at = datetime.utcnow()
    else:
        permission = UserPermission(
            user_id=user_id,
            permission_name=permission_name,
            is_granted=True,
            granted_by=session['user_id']
        )
        db.session.add(permission)
    
    db.session.commit()
    
    # Log activity
    activity = ActivityLog(
        user_id=session['user_id'],
        action='grant_permission',
        resource='permissions',
        details=f'Granted {permission_name} to {user.username}',
        ip_address=request.remote_addr
    )
    db.session.add(activity)
    db.session.commit()
    
    return jsonify({'success': True})

@admin_bp.route('/api/users/<int:user_id>/permissions/<permission_name>', methods=['DELETE'])
@login_required
@superadmin_required
def revoke_permission(user_id, permission_name):
    """Revoke permission from user"""
    user = User.query.get_or_404(user_id)
    permission = UserPermission.query.filter_by(
        user_id=user_id,
        permission_name=permission_name
    ).first()
    
    if permission:
        db.session.delete(permission)
        db.session.commit()
        
        # Log activity
        activity = ActivityLog(
            user_id=session['user_id'],
            action='revoke_permission',
            resource='permissions',
            details=f'Revoked {permission_name} from {user.username}',
            ip_address=request.remote_addr
        )
        db.session.add(activity)
        db.session.commit()
    
    return jsonify({'success': True})

@admin_bp.route('/api/users/<int:user_id>/permissions/bulk', methods=['POST'])
@login_required
@superadmin_required
def bulk_update_permissions(user_id):
    """Bulk update user permissions"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    permissions = data.get('permissions', [])
    
    # Remove all existing permissions
    UserPermission.query.filter_by(user_id=user_id).delete()
    
    # Add new permissions
    for perm_name in permissions:
        permission = UserPermission(
            user_id=user_id,
            permission_name=perm_name,
            is_granted=True,
            granted_by=session['user_id']
        )
        db.session.add(permission)
    
    db.session.commit()
    
    # Log activity
    activity = ActivityLog(
        user_id=session['user_id'],
        action='bulk_update_permissions',
        resource='permissions',
        details=f'Updated permissions for {user.username}',
        ip_address=request.remote_addr
    )
    db.session.add(activity)
    db.session.commit()
    
    return jsonify({'success': True})

@admin_bp.route('/api/activity-logs', methods=['GET'])
@login_required
@permission_required('view_admin_panel')
def get_activity_logs():
    """Get activity logs"""
    limit = request.args.get('limit', default=100, type=int)
    user_id = request.args.get('user_id', type=int)
    action = request.args.get('action')
    
    query = ActivityLog.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    if action:
        query = query.filter_by(action=action)
    
    logs = query.order_by(ActivityLog.timestamp.desc()).limit(limit).all()
    
    return jsonify([log.to_dict() for log in logs])

@admin_bp.route('/api/stats/dashboard', methods=['GET'])
@login_required
@permission_required('view_admin_panel')
def get_admin_stats():
    """Get admin dashboard statistics"""
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    admin_users = User.query.filter_by(role='admin').count()
    superadmin_users = User.query.filter_by(role='superadmin').count()
    
    recent_activities = ActivityLog.query.order_by(
        ActivityLog.timestamp.desc()
    ).limit(10).all()
    
    return jsonify({
        'total_users': total_users,
        'active_users': active_users,
        'admin_users': admin_users,
        'superadmin_users': superadmin_users,
        'recent_activities': [log.to_dict() for log in recent_activities]
    })
