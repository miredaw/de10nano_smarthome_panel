let allUsers = [];
let availablePermissions = [];
let currentEditUserId = null;
let currentPermUserId = null;
let currentDeleteUserId = null;

document.addEventListener('DOMContentLoaded', function() {
    loadUsers();
    loadAvailablePermissions();
    setupEventListeners();
});

function setupEventListeners() {
    // Create user button
    document.getElementById('createUserBtn').addEventListener('click', showCreateModal);
    
    // Modal close buttons
    document.getElementById('closeModal').addEventListener('click', closeUserModal);
    document.getElementById('cancelBtn').addEventListener('click', closeUserModal);
    document.getElementById('closePermissionsModal').addEventListener('click', closePermissionsModal);
    document.getElementById('closePermBtn').addEventListener('click', closePermissionsModal);
    document.getElementById('closeDeleteModal').addEventListener('click', closeDeleteModal);
    document.getElementById('cancelDeleteBtn').addEventListener('click', closeDeleteModal);
    
    // Form submissions
    document.getElementById('userForm').addEventListener('submit', handleSaveUser);
    document.getElementById('savePermissionsBtn').addEventListener('click', handleSavePermissions);
    document.getElementById('confirmDeleteBtn').addEventListener('click', handleConfirmDelete);
    
    // Search
    document.getElementById('userSearch').addEventListener('input', handleSearch);
    
    // Click outside modal to close
    window.addEventListener('click', function(e) {
        if (e.target.classList.contains('modal')) {
            e.target.classList.remove('show');
        }
    });
}

async function loadUsers() {
    try {
        const response = await fetch('/admin/api/users');
        allUsers = await response.json();
        displayUsers(allUsers);
    } catch (error) {
        console.error('Error loading users:', error);
        document.getElementById('usersTableBody').innerHTML = `
            <tr>
                <td colspan="7" class="error-cell">Error loading users</td>
            </tr>
        `;
    }
}

async function loadAvailablePermissions() {
    try {
        const response = await fetch('/admin/api/permissions/available');
        availablePermissions = await response.json();
    } catch (error) {
        console.error('Error loading permissions:', error);
    }
}

function displayUsers(users) {
    const tbody = document.getElementById('usersTableBody');
    
    if (users.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="no-data-cell">No users found</td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = users.map(user => `
        <tr>
            <td><strong>${user.username}</strong></td>
            <td>${user.email}</td>
            <td>${user.full_name || '-'}</td>
            <td><span class="role-badge ${user.role}">${user.role}</span></td>
            <td>
                <span class="status-badge ${user.is_active ? 'active' : 'inactive'}">
                    <span class="status-dot"></span>
                    ${user.is_active ? 'Active' : 'Inactive'}
                </span>
            </td>
            <td>${user.last_login ? formatTimestamp(user.last_login) : 'Never'}</td>
            <td>
                <div class="table-actions">
                    <button class="btn-icon-only" onclick="showEditModal(${user.id})" title="Edit">
                        ✏️
                    </button>
                    <button class="btn-icon-only" onclick="showPermissionsModal(${user.id})" title="Permissions">
                        🔑
                    </button>
                    <button class="btn-icon-only" onclick="showDeleteModal(${user.id})" title="Delete">
                        🗑️
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

function handleSearch(e) {
    const searchTerm = e.target.value.toLowerCase();
    const filtered = allUsers.filter(user => 
        user.username.toLowerCase().includes(searchTerm) ||
        user.email.toLowerCase().includes(searchTerm) ||
        (user.full_name && user.full_name.toLowerCase().includes(searchTerm))
    );
    displayUsers(filtered);
}

function showCreateModal() {
    currentEditUserId = null;
    document.getElementById('modalTitle').textContent = 'Create New User';
    document.getElementById('userForm').reset();
    document.getElementById('userId').value = '';
    document.getElementById('modalPassword').required = true;
    document.getElementById('passwordRequired').style.display = 'inline';
    document.getElementById('passwordHint').style.display = 'none';
    document.getElementById('modalIsActive').checked = true;
    document.getElementById('modalError').classList.remove('show');
    document.getElementById('userModal').classList.add('show');
}

async function showEditModal(userId) {
    currentEditUserId = userId;
    document.getElementById('modalTitle').textContent = 'Edit User';
    document.getElementById('modalPassword').required = false;
    document.getElementById('passwordRequired').style.display = 'none';
    document.getElementById('passwordHint').style.display = 'block';
    document.getElementById('modalError').classList.remove('show');
    
    try {
        const response = await fetch(`/admin/api/users/${userId}`);
        const data = await response.json();
        const user = data.user;
        
        document.getElementById('userId').value = user.id;
        document.getElementById('modalUsername').value = user.username;
        document.getElementById('modalEmail').value = user.email;
        document.getElementById('modalFullName').value = user.full_name || '';
        document.getElementById('modalPassword').value = '';
        document.getElementById('modalRole').value = user.role;
        document.getElementById('modalIsActive').checked = user.is_active;
        
        document.getElementById('userModal').classList.add('show');
    } catch (error) {
        console.error('Error loading user:', error);
        alert('Error loading user data');
    }
}

function closeUserModal() {
    document.getElementById('userModal').classList.remove('show');
}

async function handleSaveUser(e) {
    e.preventDefault();
    
    const userId = document.getElementById('userId').value;
    const userData = {
        username: document.getElementById('modalUsername').value,
        email: document.getElementById('modalEmail').value,
        full_name: document.getElementById('modalFullName').value,
        password: document.getElementById('modalPassword').value,
        role: document.getElementById('modalRole').value,
        is_active: document.getElementById('modalIsActive').checked
    };
    
    const errorDiv = document.getElementById('modalError');
    errorDiv.classList.remove('show');
    
    try {
        const url = userId ? `/admin/api/users/${userId}` : '/admin/api/users';
        const method = userId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            closeUserModal();
            loadUsers();
        } else {
            errorDiv.textContent = data.error || 'Failed to save user';
            errorDiv.classList.add('show');
        }
    } catch (error) {
        console.error('Error saving user:', error);
        errorDiv.textContent = 'An error occurred. Please try again.';
        errorDiv.classList.add('show');
    }
}

async function showPermissionsModal(userId) {
    currentPermUserId = userId;
    
    try {
        const [userResponse, permsResponse] = await Promise.all([
            fetch(`/admin/api/users/${userId}`),
            fetch(`/admin/api/users/${userId}/permissions`)
        ]);
        
        const userData = await userResponse.json();
        const permsData = await permsResponse.json();
        
        const user = userData.user;
        const userPermissions = permsData.permissions.map(p => p.permission_name);
        
        document.getElementById('permUserName').textContent = user.username;
        document.getElementById('permUserRole').textContent = user.role;
        document.getElementById('permUserRole').className = `role-badge ${user.role}`;
        
        const permissionsGrid = document.getElementById('permissionsGrid');
        
        if (user.role === 'superadmin') {
            permissionsGrid.innerHTML = `
                <div style="padding: 32px; text-align: center; color: var(--admin-text-secondary);">
                    Superadmins have all permissions by default
                </div>
            `;
        } else {
            permissionsGrid.innerHTML = availablePermissions.map(perm => {
                const hasPermission = userPermissions.includes(perm.name);
                return `
                    <div class="permission-item">
                        <div class="permission-info">
                            <h4>${formatPermissionName(perm.name)}</h4>
                            <p>${perm.description}</p>
                        </div>
                        <label class="permission-toggle">
                            <input type="checkbox" 
                                   data-permission="${perm.name}" 
                                   ${hasPermission ? 'checked' : ''}>
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                `;
            }).join('');
        }
        
        document.getElementById('permissionsModal').classList.add('show');
    } catch (error) {
        console.error('Error loading permissions:', error);
        alert('Error loading permissions');
    }
}

function closePermissionsModal() {
    document.getElementById('permissionsModal').classList.remove('show');
}

async function handleSavePermissions() {
    if (!currentPermUserId) return;
    
    const checkboxes = document.querySelectorAll('#permissionsGrid input[type="checkbox"]');
    const permissions = Array.from(checkboxes)
        .filter(cb => cb.checked)
        .map(cb => cb.dataset.permission);
    
    try {
        const response = await fetch(`/admin/api/users/${currentPermUserId}/permissions/bulk`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ permissions })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            closePermissionsModal();
        } else {
            alert(data.error || 'Failed to save permissions');
        }
    } catch (error) {
        console.error('Error saving permissions:', error);
        alert('An error occurred. Please try again.');
    }
}

function showDeleteModal(userId) {
    currentDeleteUserId = userId;
    const user = allUsers.find(u => u.id === userId);
    
    if (user) {
        document.getElementById('deleteUserName').textContent = user.username;
        document.getElementById('deleteModal').classList.add('show');
    }
}

function closeDeleteModal() {
    document.getElementById('deleteModal').classList.remove('show');
}

async function handleConfirmDelete() {
    if (!currentDeleteUserId) return;
    
    try {
        const response = await fetch(`/admin/api/users/${currentDeleteUserId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            closeDeleteModal();
            loadUsers();
        } else {
            alert(data.error || 'Failed to delete user');
        }
    } catch (error) {
        console.error('Error deleting user:', error);
        alert('An error occurred. Please try again.');
    }
}

function formatPermissionName(name) {
    return name.split('_').map(word => 
        word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}
