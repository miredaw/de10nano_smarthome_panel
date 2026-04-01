// DE10-Nano Smart Home Monitor - Dashboard JavaScript

// ============================================================================
// Carousel Navigation
// ============================================================================

let currentSlide = 1;
const totalSlides = 4;

function showSlide(slideNumber) {
    // Remove active from all slides
    document.querySelectorAll('.carousel-slide').forEach(slide => {
        slide.classList.remove('active');
    });
    
    // Remove active from all dots
    document.querySelectorAll('.carousel-dot').forEach(dot => {
        dot.classList.remove('active');
    });
    
    // Show selected slide
    const targetSlide = document.querySelector(`.carousel-slide[data-slide="${slideNumber}"]`);
    if (targetSlide) {
        targetSlide.classList.add('active');
    }
    
    // Activate corresponding dot
    const dots = document.querySelectorAll('.carousel-dot');
    if (dots[slideNumber - 1]) {
        dots[slideNumber - 1].classList.add('active');
    }
    
    currentSlide = slideNumber;
}

function nextSlide() {
    let next = currentSlide + 1;
    if (next > totalSlides) {
        next = 1;
    }
    showSlide(next);
}

function previousSlide() {
    let prev = currentSlide - 1;
    if (prev < 1) {
        prev = totalSlides;
    }
    showSlide(prev);
}

function goToSlide(slideNumber) {
    showSlide(slideNumber);
}

// Keyboard navigation
document.addEventListener('keydown', function(e) {
    if (e.key === 'ArrowRight') {
        nextSlide();
    } else if (e.key === 'ArrowLeft') {
        previousSlide();
    }
});

// Initialize Socket.IO connection
const socket = io();

// Global state
const state = {
    mqttConnected: false,
    sensorData: {},
    systemArmed: true
};

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('DE10-Nano Dashboard initialized');
    
    // Initialize Socket.IO listeners
    initializeSocketListeners();
    
    // Initialize control buttons
    initializeControls();
    
    // Initialize tab navigation
    initializeTabNavigation();
    
    // Load initial data
    loadInitialData();
    
    // Set up periodic updates
    setInterval(requestUpdate, 30000); // Every 30 seconds
    
    // Update uptime counter
    setInterval(updateUptime, 60000); // Every minute
});

// ============================================================================
// Tab Navigation
// ============================================================================

function initializeTabNavigation() {
    const navPills = document.querySelectorAll('.nav-pill');
    
    navPills.forEach(pill => {
        pill.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    // Update active nav pill
    document.querySelectorAll('.nav-pill').forEach(pill => {
        pill.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // Hide all tab pages
    document.querySelectorAll('.tab-page, .dashboard-content').forEach(page => {
        page.classList.remove('active');
    });
    
    // Show selected tab
    const targetTab = document.getElementById(`${tabName}-tab`);
    if (targetTab) {
        targetTab.classList.add('active');
    }
}

// ============================================================================
// Initialization
// ============================================================================

// ============================================================================
// Socket.IO Listeners
// ============================================================================

function initializeSocketListeners() {
    socket.on('mqtt_status', function(data) {
        console.log('MQTT status:', data.status);
        updateMQTTStatus(data.status === 'connected');
    });

    // Payload from mqtt_handler.py: flat object with keys
    // {temperature, pressure, humidity, light, heating, sound, pir, alarm_flags, timestamp, alarms}
    socket.on('sensor_update', function(data) {
        console.log('Sensor update:', data);
        if (data.temperature !== undefined)
            updateSensorValue('temperature', { value: data.temperature });
        if (data.light !== undefined)
            updateSensorValue('light', { value: data.light });
        if (data.sound !== undefined)
            updateSensorValue('sound', { value: data.sound });
        if (data.pir !== undefined)
            updateSensorValue('motion', { detected: data.pir !== 0 });
        if (data.alarm_flags !== undefined)
            updateAlarmStatus(data.alarm_flags);
    });

    // Payload from mqtt_handler.py: {alarm_type, severity, message, alarm_flags, timestamp, alarms}
    socket.on('alarm_update', function(data) {
        console.log('Alarm update:', data);
        if (data.alarm_flags !== undefined)
            updateAlarmStatus(data.alarm_flags);
    });

    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        updateMQTTStatus(false);
    });
}

// ============================================================================
// Data Loading
// ============================================================================

function loadInitialData() {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            updateMQTTStatus(data.mqtt_connected);
            if (data.sensor_cache) {
                updateAllSensors(data.sensor_cache);
            }
        })
        .catch(error => console.error('Error loading status:', error));
}

function requestUpdate() {
    socket.emit('request_update');
}

// ============================================================================
// UI Updates
// ============================================================================

function updateMQTTStatus(connected) {
    state.mqttConnected = connected;
    const statusDot = document.querySelector('.wifi-status .status-dot');
    if (statusDot) {
        if (connected) {
            statusDot.style.background = '#7fcd91';
            statusDot.style.boxShadow = '0 0 10px #7fcd91';
        } else {
            statusDot.style.background = '#ff4757';
            statusDot.style.boxShadow = '0 0 10px #ff4757';
        }
    }
}

function updateAllSensors(sensorCache) {
    if (sensorCache.temperature) {
        updateSensorValue('temperature', sensorCache.temperature);
    }
    if (sensorCache.light) {
        updateSensorValue('light', sensorCache.light);
    }
    if (sensorCache.motion !== undefined) {
        updateSensorValue('motion', sensorCache.motion);
    }
    if (sensorCache.heating) {
        updateSensorValue('heating', sensorCache.heating);
    }
    if (sensorCache.sound) {
        updateSensorValue('sound', sensorCache.sound);
    }
}

function updateSensorValue(type, data) {
    state.sensorData[type] = data;
    
    switch(type) {
        case 'temperature':
            const tempValue = document.getElementById('tempValue');
            if (tempValue && data.value !== undefined) {
                tempValue.textContent = data.value.toFixed(1);
            }
            break;
            
        case 'light':
            const lightValue = document.getElementById('lightValue');
            if (lightValue && data.value !== undefined) {
                lightValue.textContent = Math.round(data.value);
            }
            break;
            
        case 'motion':
            const motionStatus = document.getElementById('motionStatus');
            if (motionStatus) {
                if (data.detected) {
                    motionStatus.classList.add('active');
                    motionStatus.innerHTML = '<span class="pulse-dot"></span>ACTIVE';
                } else {
                    motionStatus.classList.remove('active');
                    motionStatus.innerHTML = '<span class="dot-green"></span>IDLE';
                }
            }
            break;
            
        case 'sound':
            const soundValue = document.getElementById('soundValue');
            const soundGauge = document.getElementById('soundGauge');
            const noiseLevel = document.getElementById('noiseLevel');
            
            if (soundValue && data.value !== undefined) {
                const value = Math.round(data.value);
                soundValue.textContent = value;
                
                // Update gauge (circle with radius 100, circumference = 2πr = 628)
                if (soundGauge) {
                    const percentage = value / 100;
                    const offset = 628 - (628 * percentage);
                    soundGauge.style.strokeDashoffset = offset;
                }
                
                // Update noise level text
                if (noiseLevel) {
                    if (value < 40) {
                        noiseLevel.textContent = 'Low';
                        noiseLevel.className = 'value green';
                    } else if (value < 70) {
                        noiseLevel.textContent = 'Medium';
                        noiseLevel.className = 'value yellow';
                    } else {
                        noiseLevel.textContent = 'High';
                        noiseLevel.className = 'value red';
                    }
                }
            }
            break;
    }
}

function updateAlarmStatus(status) {
    state.systemArmed = (status === 'ARMED');
    
    const armedPill = document.getElementById('armedPill');
    const armBtn = document.getElementById('armBtn');
    const disarmBtn = document.getElementById('disarmBtn');
    
    if (state.systemArmed) {
        if (armedPill) {
            armedPill.classList.add('armed');
            armedPill.textContent = '🛡️ ARMED';
        }
        if (armBtn) armBtn.classList.add('active');
        if (disarmBtn) disarmBtn.classList.remove('active');
    } else {
        if (armedPill) {
            armedPill.classList.remove('armed');
            armedPill.textContent = '🛡️ DISARMED';
        }
        if (armBtn) armBtn.classList.remove('active');
        if (disarmBtn) disarmBtn.classList.add('active');
    }
}

function updateUptime() {
    // Simulate uptime increase
    const uptimeEl = document.getElementById('systemUptime');
    if (uptimeEl) {
        const current = parseInt(uptimeEl.textContent) || 127;
        uptimeEl.textContent = current + 1;
    }
    
    const boardUptimeEl = document.getElementById('boardUptime');
    if (boardUptimeEl) {
        // Parse current time and increment
        const match = boardUptimeEl.textContent.match(/(\d+)h (\d+)m/);
        if (match) {
            let hours = parseInt(match[1]);
            let minutes = parseInt(match[2]) + 1;
            if (minutes >= 60) {
                minutes = 0;
                hours++;
            }
            boardUptimeEl.textContent = `${hours}h ${minutes}m`;
        }
    }
}

// ============================================================================
// Control Functions
// ============================================================================

function initializeControls() {
    const armBtn = document.getElementById('armBtn');
    const disarmBtn = document.getElementById('disarmBtn');
    const testAlarmBtn = document.getElementById('testAlarmBtn');
    
    if (armBtn) {
        armBtn.addEventListener('click', function() {
            controlAlarm('arm');
        });
    }
    
    if (disarmBtn) {
        disarmBtn.addEventListener('click', function() {
            controlAlarm('disarm');
        });
    }
    
    if (testAlarmBtn) {
        testAlarmBtn.addEventListener('click', function() {
            testAlarm();
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
            showNotification(`System ${action}ed successfully`, 'success');
            updateAlarmStatus(action === 'arm' ? 'ARMED' : 'DISARMED');
        } else {
            showNotification('Failed to control system', 'error');
        }
    })
    .catch(error => {
        console.error('Error controlling alarm:', error);
        showNotification('Error controlling system', 'error');
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
            
            // Update PWM value temporarily
            const pwmValue = document.getElementById('pwmValue');
            if (pwmValue) {
                pwmValue.textContent = 'ON';
                pwmValue.style.color = '#7fcd91';
                setTimeout(() => {
                    pwmValue.textContent = 'OFF';
                    pwmValue.style.color = '#ff4757';
                }, 3000);
            }
        } else {
            showNotification('Failed to trigger test alarm', 'error');
        }
    })
    .catch(error => {
        console.error('Error triggering test alarm:', error);
        showNotification('Error triggering test alarm', 'error');
    });
}

// ============================================================================
// Utility Functions
// ============================================================================

function showNotification(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    // Create notification element
    const notification = document.createElement('div');
    notification.style.position = 'fixed';
    notification.style.top = '100px';
    notification.style.right = '40px';
    notification.style.padding = '15px 25px';
    notification.style.borderRadius = '12px';
    notification.style.color = 'white';
    notification.style.zIndex = '10000';
    notification.style.boxShadow = '0 6px 12px rgba(0, 0, 0, 0.6)';
    notification.style.fontSize = '14px';
    notification.style.fontWeight = '600';
    notification.style.animation = 'slideIn 0.3s ease';
    notification.textContent = message;
    
    if (type === 'success') {
        notification.style.background = 'linear-gradient(90deg, #7fcd91 0%, #a8e6b5 100%)';
    } else if (type === 'error') {
        notification.style.background = 'linear-gradient(90deg, #ff4757 0%, #ff6b7a 100%)';
    } else {
        notification.style.background = 'linear-gradient(90deg, #6eb6ff 0%, #a8d5ff 100%)';
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

// Real sensor data is received via Socket.IO 'sensor_update' and 'sensor_update_all' events
// from the MQTT handler. No simulation needed.
