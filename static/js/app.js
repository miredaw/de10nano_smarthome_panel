// IoT Smart Home Monitor - Main JavaScript Application

// Initialize Socket.IO connection
const socket = io();

// Global state
const state = {
    mqttConnected: false,
    sensorData: {
        temperature: null,
        light: null,
        motion: null,
        heating: null,
        sound: null
    },
    alarmStatus: 'DISARMED',
    charts: {}
};

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('Smart Home Monitor initialized');
    
    // Initialize tab navigation
    initializeTabs();
    
    // Initialize control sliders
    initializeSliders();
    
    // Initialize alarm controls
    initializeAlarmControls();
    
    // Initialize charts
    initializeCharts();
    
    // Load initial data
    loadInitialData();
    
    // Initialize Socket.IO listeners
    initializeSocketListeners();
    
    // Set up periodic updates
    setInterval(requestUpdate, 30000); // Request update every 30 seconds
});

// ============================================================================
// Tab Navigation
// ============================================================================

function initializeTabs() {
    const tabs = document.querySelectorAll('.nav-tab');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    // Update active tab button
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // Show corresponding content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');
    
    // Load tab-specific data
    if (tabName === 'sensors') {
        loadSensorHistory('temperature', 24);
        loadSensorHistory('light', 24);
    } else if (tabName === 'alarms') {
        loadAlarmHistory();
    } else if (tabName === 'settings') {
        loadSettings();
    }
}

// ============================================================================
// Socket.IO Listeners
// ============================================================================

function initializeSocketListeners() {
    // Connection status
    socket.on('connection_status', function(data) {
        console.log('Connected to server', data);
        updateMQTTStatus(data.mqtt_status);
        if (data.sensor_cache) {
            updateAllSensors(data.sensor_cache);
        }
    });
    
    socket.on('mqtt_status', function(data) {
        console.log('MQTT status:', data.status);
        updateMQTTStatus(data.status === 'connected');
    });
    
    // Sensor updates
    socket.on('sensor_update', function(data) {
        console.log('Sensor update:', data);
        updateSensor(data.type, data.data);
    });
    
    socket.on('sensor_update_all', function(data) {
        console.log('All sensors update:', data);
        updateAllSensors(data);
    });
    
    // Control updates
    socket.on('control_update', function(data) {
        console.log('Control update:', data);
        updateControl(data.type, data.data);
    });
    
    // Alarm updates
    socket.on('alarm_update', function(data) {
        console.log('Alarm update:', data);
        updateAlarmStatus(data.status);
        loadRecentAlarms(); // Refresh alarms list
    });
    
    socket.on('alarm_acknowledged', function(data) {
        console.log('Alarm acknowledged:', data.alarm_id);
        loadRecentAlarms();
    });
    
    // System updates
    socket.on('system_update', function(data) {
        console.log('System update:', data);
        updateSystemComponent(data.component, data.data);
    });
    
    // Settings updates
    socket.on('setting_updated', function(data) {
        console.log('Setting updated:', data);
        showNotification('Setting updated successfully', 'success');
    });
    
    // Disconnection
    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        updateMQTTStatus(false);
    });
}

// ============================================================================
// Data Loading
// ============================================================================

function loadInitialData() {
    // Load current status
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            updateMQTTStatus(data.mqtt_connected);
            if (data.sensor_cache) {
                updateAllSensors(data.sensor_cache);
            }
        })
        .catch(error => console.error('Error loading status:', error));
    
    // Load recent alarms
    loadRecentAlarms();
}

function requestUpdate() {
    socket.emit('request_update');
}

function loadRecentAlarms() {
    fetch('/api/alarms?limit=5')
        .then(response => response.json())
        .then(data => {
            displayRecentAlarms(data);
        })
        .catch(error => console.error('Error loading alarms:', error));
}

function loadAlarmHistory() {
    fetch('/api/alarms?limit=50')
        .then(response => response.json())
        .then(data => {
            displayAlarmHistory(data);
        })
        .catch(error => console.error('Error loading alarm history:', error));
}

function loadSettings() {
    fetch('/api/settings')
        .then(response => response.json())
        .then(data => {
            displaySettings(data);
        })
        .catch(error => console.error('Error loading settings:', error));
}

function loadSensorHistory(sensorType, hours) {
    fetch(`/api/sensors/history/${sensorType}?hours=${hours}`)
        .then(response => response.json())
        .then(data => {
            updateChart(sensorType, data);
        })
        .catch(error => console.error(`Error loading ${sensorType} history:`, error));
}

// ============================================================================
// UI Updates
// ============================================================================

function updateMQTTStatus(connected) {
    state.mqttConnected = connected;
    
    const statusElement = document.getElementById('mqttStatus');
    const indicator = statusElement.querySelector('.status-indicator');
    const text = statusElement.querySelector('span');
    
    if (connected) {
        indicator.classList.remove('offline');
        indicator.classList.add('online');
        text.textContent = 'MQTT: Connected';
    } else {
        indicator.classList.remove('online');
        indicator.classList.add('offline');
        text.textContent = 'MQTT: Disconnected';
    }
    
    // Update MQTT config status in settings
    const configStatus = document.getElementById('mqttConfigStatus');
    if (configStatus) {
        configStatus.textContent = connected ? 'Connected' : 'Disconnected';
        configStatus.style.color = connected ? 'var(--success-color)' : 'var(--danger-color)';
    }
}

function updateAllSensors(sensorCache) {
    if (sensorCache.temperature) {
        updateSensor('temperature', sensorCache.temperature);
    }
    if (sensorCache.light) {
        updateSensor('light', sensorCache.light);
    }
    if (sensorCache.motion !== undefined) {
        updateSensor('motion', sensorCache.motion);
    }
    if (sensorCache.heating) {
        updateControl('heating', sensorCache.heating);
    }
    if (sensorCache.sound) {
        updateControl('sound', sensorCache.sound);
    }
    if (sensorCache.alarm_status) {
        updateAlarmStatus(sensorCache.alarm_status);
    }
}

function updateSensor(type, data) {
    state.sensorData[type] = data;
    
    if (type === 'temperature') {
        document.getElementById('temperatureValue').textContent = data.value.toFixed(1);
        document.getElementById('temperatureTime').textContent = formatTimestamp(data.timestamp);
    } else if (type === 'light') {
        document.getElementById('lightValue').textContent = Math.round(data.value);
        document.getElementById('lightTime').textContent = formatTimestamp(data.timestamp);
    } else if (type === 'motion') {
        const motionStatus = document.getElementById('motionStatus');
        const motionText = motionStatus.querySelector('span');
        
        if (data.detected) {
            motionStatus.classList.add('active');
            motionText.textContent = 'Motion Detected!';
        } else {
            motionStatus.classList.remove('active');
            motionText.textContent = 'No Motion';
        }
        
        document.getElementById('motionTime').textContent = formatTimestamp(data.timestamp);
    }
}

function updateControl(type, data) {
    if (type === 'heating') {
        const slider = document.getElementById('heatingSlider');
        const display = document.getElementById('heatingDisplay');
        slider.value = data.value;
        display.textContent = Math.round(data.value) + '%';
    } else if (type === 'sound') {
        const slider = document.getElementById('soundSlider');
        const display = document.getElementById('soundDisplay');
        slider.value = data.value;
        display.textContent = Math.round(data.value) + '%';
    }
}

function updateAlarmStatus(status) {
    state.alarmStatus = status;
    
    const badge = document.getElementById('alarmStatusBadge');
    badge.textContent = status;
    badge.setAttribute('data-status', status);
}

function updateSystemComponent(component, data) {
    const statusMap = {
        'wifi': 'wifiStatus',
        'gsm': 'gsmStatus',
        'fpga': 'fpgaStatus',
        'hps': 'hpsStatus'
    };
    
    const elementId = statusMap[component];
    if (elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.classList.remove('online', 'offline');
            element.classList.add(data.status === 'online' ? 'online' : 'offline');
        }
    }
}

function displayRecentAlarms(alarms) {
    const container = document.getElementById('recentAlarmsList');
    
    if (!alarms || alarms.length === 0) {
        container.innerHTML = '<div class="empty-state">No recent alarms</div>';
        return;
    }
    
    container.innerHTML = alarms.map(alarm => `
        <div class="alarm-item ${alarm.severity}">
            <div class="alarm-item-header">
                <span class="alarm-type">${alarm.alarm_type}</span>
                <span class="alarm-time">${formatTimestamp(alarm.timestamp)}</span>
            </div>
            <div class="alarm-message">${alarm.message}</div>
        </div>
    `).join('');
}

function displayAlarmHistory(alarms) {
    const tbody = document.getElementById('alarmsTableBody');
    
    if (!alarms || alarms.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No alarms found</td></tr>';
        return;
    }
    
    tbody.innerHTML = alarms.map(alarm => `
        <tr>
            <td>${formatTimestamp(alarm.timestamp)}</td>
            <td>${alarm.alarm_type}</td>
            <td><span class="severity-badge ${alarm.severity}">${alarm.severity}</span></td>
            <td>${alarm.message}</td>
            <td>${alarm.acknowledged ? '✓ Acknowledged' : 'Pending'}</td>
            <td>
                ${!alarm.acknowledged ? 
                    `<button class="btn btn-sm" onclick="acknowledgeAlarm(${alarm.id})">Acknowledge</button>` : 
                    '-'}
            </td>
        </tr>
    `).join('');
}

function displaySettings(settings) {
    settings.forEach(setting => {
        const inputId = setting.setting_name.replace('_', '');
        const input = document.getElementById(inputId);
        if (input) {
            input.value = setting.value;
        }
    });
}

// ============================================================================
// Control Functions
// ============================================================================

function initializeSliders() {
    const heatingSlider = document.getElementById('heatingSlider');
    const soundSlider = document.getElementById('soundSlider');
    
    heatingSlider.addEventListener('input', function() {
        document.getElementById('heatingDisplay').textContent = this.value + '%';
    });
    
    heatingSlider.addEventListener('change', function() {
        controlHeating(parseFloat(this.value));
    });
    
    soundSlider.addEventListener('input', function() {
        document.getElementById('soundDisplay').textContent = this.value + '%';
    });
    
    soundSlider.addEventListener('change', function() {
        controlSound(parseFloat(this.value));
    });
}

function initializeAlarmControls() {
    document.getElementById('armAlarmBtn').addEventListener('click', function() {
        controlAlarm('arm');
    });
    
    document.getElementById('disarmAlarmBtn').addEventListener('click', function() {
        controlAlarm('disarm');
    });
    
    document.getElementById('testAlarmBtn').addEventListener('click', function() {
        testAlarm();
    });
    
    document.getElementById('refreshAlarmsBtn').addEventListener('click', function() {
        loadRecentAlarms();
    });
    
    const refreshAllBtn = document.getElementById('refreshAllAlarmsBtn');
    if (refreshAllBtn) {
        refreshAllBtn.addEventListener('click', function() {
            loadAlarmHistory();
        });
    }
}

function controlAlarm(action) {
    fetch('/api/control/alarm', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ action })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(`Alarm ${action}ed successfully`, 'success');
        } else {
            showNotification('Failed to control alarm', 'error');
        }
    })
    .catch(error => {
        console.error('Error controlling alarm:', error);
        showNotification('Error controlling alarm', 'error');
    });
}

function testAlarm() {
    fetch('/api/control/test-alarm', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Test alarm triggered', 'success');
        } else {
            showNotification('Failed to trigger test alarm', 'error');
        }
    })
    .catch(error => {
        console.error('Error triggering test alarm:', error);
        showNotification('Error triggering test alarm', 'error');
    });
}

function controlHeating(level) {
    fetch('/api/control/heating', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ level })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Heating level updated');
        } else {
            showNotification('Failed to set heating level', 'error');
        }
    })
    .catch(error => {
        console.error('Error setting heating level:', error);
        showNotification('Error setting heating level', 'error');
    });
}

function controlSound(volume) {
    fetch('/api/control/sound', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ volume })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Sound volume updated');
        } else {
            showNotification('Failed to set sound volume', 'error');
        }
    })
    .catch(error => {
        console.error('Error setting sound volume:', error);
        showNotification('Error setting sound volume', 'error');
    });
}

function acknowledgeAlarm(alarmId) {
    fetch(`/api/alarms/${alarmId}/acknowledge`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Alarm acknowledged', 'success');
            loadAlarmHistory();
        } else {
            showNotification('Failed to acknowledge alarm', 'error');
        }
    })
    .catch(error => {
        console.error('Error acknowledging alarm:', error);
        showNotification('Error acknowledging alarm', 'error');
    });
}

function updateSetting(settingName, value, unit) {
    fetch(`/api/settings/${settingName}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ value: parseFloat(value), unit })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Setting updated successfully', 'success');
        } else {
            showNotification('Failed to update setting', 'error');
        }
    })
    .catch(error => {
        console.error('Error updating setting:', error);
        showNotification('Error updating setting', 'error');
    });
}

// ============================================================================
// Charts
// ============================================================================

function initializeCharts() {
    // Temperature Chart
    const tempCtx = document.getElementById('temperatureChart');
    if (tempCtx) {
        state.charts.temperature = new Chart(tempCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Temperature (°C)',
                    data: [],
                    borderColor: '#EF4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        labels: {
                            color: '#CBD5E1'
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#94A3B8' },
                        grid: { color: '#334155' }
                    },
                    y: {
                        ticks: { color: '#94A3B8' },
                        grid: { color: '#334155' }
                    }
                }
            }
        });
    }
    
    // Light Chart
    const lightCtx = document.getElementById('lightChart');
    if (lightCtx) {
        state.charts.light = new Chart(lightCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Light Level (%)',
                    data: [],
                    borderColor: '#F59E0B',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        labels: {
                            color: '#CBD5E1'
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#94A3B8' },
                        grid: { color: '#334155' }
                    },
                    y: {
                        ticks: { color: '#94A3B8' },
                        grid: { color: '#334155' },
                        min: 0,
                        max: 100
                    }
                }
            }
        });
    }
    
    // Add event listeners for time range selectors
    const tempRange = document.getElementById('tempHistoryRange');
    if (tempRange) {
        tempRange.addEventListener('change', function() {
            loadSensorHistory('temperature', parseInt(this.value));
        });
    }
    
    const lightRange = document.getElementById('lightHistoryRange');
    if (lightRange) {
        lightRange.addEventListener('change', function() {
            loadSensorHistory('light', parseInt(this.value));
        });
    }
}

function updateChart(sensorType, data) {
    const chart = state.charts[sensorType];
    if (!chart) return;
    
    // Sort data by timestamp (oldest first)
    data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    
    // Extract labels and values
    const labels = data.map(item => formatChartTimestamp(item.timestamp));
    const values = data.map(item => item.value);
    
    // Update chart
    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.update();
}

// ============================================================================
// Utility Functions
// ============================================================================

function formatTimestamp(timestamp) {
    if (!timestamp) return 'Never';
    
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    // Less than 1 minute ago
    if (diff < 60000) {
        return 'Just now';
    }
    
    // Less than 1 hour ago
    if (diff < 3600000) {
        const minutes = Math.floor(diff / 60000);
        return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
    }
    
    // Less than 24 hours ago
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
    }
    
    // Format as date and time
    return date.toLocaleString();
}

function formatChartTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function showNotification(message, type = 'info') {
    // Simple notification implementation
    // You can enhance this with a proper toast library
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    // Create a simple notification element
    const notification = document.createElement('div');
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.padding = '16px 24px';
    notification.style.borderRadius = '8px';
    notification.style.color = 'white';
    notification.style.zIndex = '10000';
    notification.style.animation = 'slideIn 0.3s ease';
    notification.textContent = message;
    
    if (type === 'success') {
        notification.style.backgroundColor = '#10B981';
    } else if (type === 'error') {
        notification.style.backgroundColor = '#EF4444';
    } else {
        notification.style.backgroundColor = '#4F46E5';
    }
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// Add CSS animations for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
