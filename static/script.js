const API_URL = window.location.origin; 
const WS_URL = API_URL.replace(/^http/, 'ws');
const authWrapper = document.getElementById('auth-wrapper');

let currentUserRole = "operator"; // Defaults to basic user, updated on login

// --- New Globals ---
let mapInitialized = false;
let map = null;
let trainMarker = null;
let fleetAlertStates = { "train_a": "NORMAL", "train_b": "NORMAL" };
let currentActiveTrain = "train_a";

let currentLang = 'en';

function changeLanguage(lang) {
    currentLang = lang;
    
    // Find all HTML elements with the data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (translations[lang] && translations[lang][key]) {
            el.innerText = translations[lang][key];
        }
    });

    // We have to manually update the dynamic welcome message if they are logged in
    const welcomeDiv = document.getElementById('welcome-message');
    if (welcomeDiv && window.loggedInUser) {
        const badge = currentUserRole === 'admin' ? ' 🛡️' : '';
        welcomeDiv.innerText = `${translations[lang].welcomePrefix} ${window.loggedInUser}${badge}`;
    }
}

// --- UI View Switching ---
function switchView(viewId) {
    document.getElementById('login-view').classList.add('hidden');
    document.getElementById('signup-view').classList.add('hidden');
    document.getElementById(viewId).classList.remove('hidden');
    document.getElementById('login-error').innerText = '';
    document.getElementById('signup-error').innerText = '';
}

function triggerAnimation(element, animClass, duration) {
    element.classList.remove(animClass);
    void element.offsetWidth; 
    element.classList.add(animClass);
    setTimeout(() => element.classList.remove(animClass), duration);
}

// --- Authentication Logic ---
async function attemptLogin() {
    const user = document.getElementById('login-user').value;
    const pass = document.getElementById('login-pass').value;
    const errorMsg = document.getElementById('login-error');
    errorMsg.innerText = '';
    
    const formData = new URLSearchParams();
    formData.append("username", user);
    formData.append("password", pass);

    try {
        const response = await fetch(`/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData
        });
        
        if (!response.ok) throw new Error("Invalid credentials");
        
        const data = await response.json();
        currentUserRole = data.role;
        triggerAnimation(authWrapper, 'anim-success', 800);
        errorMsg.style.color = '#2ecc71';
        errorMsg.innerText = "Access Granted...";

        setTimeout(() => {
            authWrapper.classList.add('hidden');
            document.getElementById('dashboard-container').classList.remove('hidden');
            document.body.style.alignItems = 'stretch';
            document.body.style.paddingTop = '0';
            
            // Add window.loggedInUser so the translator can access it later
            window.loggedInUser = `${data.first_name} ${data.last_name}`;

            const badge = data.role === 'admin' ? ' 🛡️' : '';
            document.getElementById('welcome-message').innerText = `${translations[currentLang].welcomePrefix} ${window.loggedInUser}${badge}`;
            connectWebSocket(data.access_token);
        }, 800);

    } catch (error) {
        triggerAnimation(authWrapper, 'anim-shake', 500);
        errorMsg.style.color = '#e74c3c';
        errorMsg.innerText = error.message;
    }
}

async function attemptSignUp() {
    const pass1 = document.getElementById('reg-pass').value;
    const pass2 = document.getElementById('reg-pass2').value;
    const errorMsg = document.getElementById('signup-error');
    errorMsg.style.color = '#e74c3c';
    errorMsg.innerText = '';

    if (!document.getElementById('reg-fname').value || !document.getElementById('reg-opnum').value) {
        triggerAnimation(authWrapper, 'anim-shake', 500);
        errorMsg.innerText = "Please fill in all fields.";
        return;
    }
    if (pass1 !== pass2) {
        triggerAnimation(authWrapper, 'anim-shake', 500);
        errorMsg.innerText = "Passwords do not match!";
        return;
    }

    try {
        const response = await fetch('/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                first_name: document.getElementById('reg-fname').value,
                last_name: document.getElementById('reg-lname').value,
                operator_id: document.getElementById('reg-opnum').value,
                password: pass1
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Registration failed");
        }

        errorMsg.style.color = '#2ecc71';
        errorMsg.innerText = "Registration successful! Returning to login...";
        triggerAnimation(authWrapper, 'anim-success', 800);

        setTimeout(() => {
            // FIX: Actually send them to the login screen instead of the dashboard
            switchView('login-view');
            
            // Optional Polish: Pre-fill their username so they don't have to type it again
            document.getElementById('login-user').value = document.getElementById('reg-opnum').value;
            document.getElementById('login-pass').value = ""; // Clear password field    
        }, 1500);

    } catch (error) {
        triggerAnimation(authWrapper, 'anim-shake', 500);
        errorMsg.style.color = '#e74c3c';
        errorMsg.innerText = error.message;
    }
}

// --- WebSocket Logic ---
function connectWebSocket(token) {
    const ws = new WebSocket(`${WS_URL}/ws/telemetry?token=${token}`);

    ws.onopen = () => document.getElementById('val-status').innerText = "CONNECTED - RECEIVING DATA";
    ws.onclose = () => document.getElementById('val-status').innerText = "CONNECTION LOST";
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateCharts(data);
        handleAlerts(data, currentActiveTrain);

        if (data.error) {
            document.getElementById('val-status').innerText = `SYSTEM ERROR: ${data.error}`;
            document.getElementById('panel-alert').className = 'panel alert-panel glow-critical';
            return;
        }

        // SURELY THIS WILL PROPERLY WORK NOW WITHOUT ANY ISSUES RIGHT? RIGHT????
        const speed = data.kinematics?.speed_kmh || 0;
        const engTemp = data.engine_and_fuel?.engine_temperature_c || 0;
        const cabTemp = data.environment?.cabin_temperature_c || 0;
        const fuel = data.engine_and_fuel?.fuel_level_liters || 0;
        const pressMain = data.pneumatics?.main_reservoir_psi || 0;
        const pressBrake = data.pneumatics?.brake_pipe_psi || 0;
        const tracV = data.electrical?.traction_voltage_v || 0;
        const tracA = data.electrical?.traction_current_a || 0;
        const hepKw = data.electrical?.head_end_power_load_kw || 0;
        const status = data.status?.system_alert_state || 'UNKNOWN';
        const fuelRate = data.engine_and_fuel?.fuel_burn_rate_lps || 0;

        document.getElementById('val-speed').innerText = speed.toFixed(0);
        document.getElementById('val-fuel-rate').innerText = fuelRate.toFixed(1);
        document.getElementById('val-engine-temp').innerText = engTemp.toFixed(1);
        document.getElementById('val-cabin-temp').innerText = cabTemp.toFixed(1);
        
        document.getElementById('val-fuel').innerText = `${fuel.toFixed(0)} L`;
        document.getElementById('val-pressure').innerText = `${pressMain.toFixed(0)} PSI`;
        document.getElementById('val-brake').innerText = `${pressBrake.toFixed(0)} PSI`;
        
        document.getElementById('val-voltage').innerText = `${tracV.toFixed(0)} V`;
        document.getElementById('val-current').innerText = `${tracA.toFixed(0)} A`;
        document.getElementById('val-hep').innerText = `${hepKw.toFixed(0)} kW`;
        document.getElementById('val-status').innerText = status;

        // FIX: Update max values based on simulator baselines and random walk limits
        const updateBar = (id, value, max) => {
            const percent = Math.min(100, Math.max(0, (value / max) * 100));
            document.getElementById(id).style.height = `${percent}%`;
        };

        updateBar('bar-fuel', fuel, 15000);        // Max fuel is 15,000 L
        updateBar('bar-pressure', pressMain, 150); // Main reservoir normal max ~145 PSI
        updateBar('bar-brake', pressBrake, 100);   // Brake pipe normal max ~92 PSI
        updateBar('bar-voltage', tracV, 1200);     // Traction V normal max ~1000 V
        updateBar('bar-current', tracA, 1800);     // Traction A normal max ~1500 A
        updateBar('bar-hep', hepKw, 600);          // HEP normal max ~500 kW

        const applyGlow = (panelId, state) => {
            const panel = document.getElementById(panelId);
            panel.classList.remove('glow-warning', 'glow-critical');
            if (state === 'CRITICAL') panel.classList.add('glow-critical');
            if (state === 'WARNING') panel.classList.add('glow-warning');
        };

        // --- TEMPERATURE LOGIC ---
        // Normal range: 75°C - 105°C. Overheat pushes it above 105.
        let tempState = 'NORMAL';
        if (engTemp > 105) tempState = 'CRITICAL';
        else if (engTemp > 100) tempState = 'WARNING';

        // --- FLUIDS & PNEUMATICS LOGIC ---
        // Normal Pressure: 125 - 145. Loss event drops it fast.
        let fluidState = 'NORMAL';
        if (fuel < 1500 || pressMain < 115) fluidState = 'CRITICAL';
        else if (fuel < 3000 || pressMain < 125) fluidState = 'WARNING';

        // --- ELECTRICAL LOGIC ---
        // Normal V: 500-1000. Normal A: 500-1500. 
        // Short circuit causes massive drops (V < 100, A < 50)
        let elecState = 'NORMAL';
        if (tracV < 150 || tracA < 100 || tracV > 1100 || tracA > 1650) elecState = 'CRITICAL';
        else if (tracV < 450 || tracA < 400 || tracV > 1050 || tracA > 1550) elecState = 'WARNING';

        // --- SPEED LOGIC ---
        // Normal operating limit is 160 km/h
        let speedState = 'NORMAL';
        if (speed > 150) speedState = 'CRITICAL';
        else if (speed > 140) speedState = 'WARNING';

        // --- FUEL BURN RATE LOGIC ---
        // Normal burn is < 1.0 L/s. Leak adds 15 - 40 L/s.
        let fuelRateState = 'NORMAL';
        if (fuelRate > 15) fuelRateState = 'CRITICAL';
        else if (fuelRate > 5) fuelRateState = 'WARNING';

        applyGlow('panel-temp', tempState);
        applyGlow('panel-fluid', fluidState);
        applyGlow('panel-electrical', elecState);
        applyGlow('panel-alert', status);
        applyGlow('panel-speed', speedState);
        applyGlow('panel-fuel-rate', fuelRateState);
    };
}

// --- Dashboard Utilities ---
function startClock() {
    const clockEl = document.getElementById('live-clock');
    
    // 1. Define the logic
    const updateTime = () => {
        const now = new Date();
        clockEl.innerText = now.toLocaleString(); 
    };

    // 2. Call it immediately so the screen doesn't wait
    updateTime(); 

    // 3. Start the 1-second interval loop
    setInterval(updateTime, 1000);
}

// --- Theme Toggle Logic ---
function toggleTheme() {
    const body = document.body;
    const btn = document.getElementById('theme-toggle');
    
    // Toggle the class on the body
    body.classList.toggle('dark-theme');
    
    // Check if the class is now active and update icon + storage
    if (body.classList.contains('dark-theme')) {
        btn.innerText = '☀️';
        localStorage.setItem('trainos_theme', 'dark');
    } else {
        btn.innerText = '🌙';
        localStorage.setItem('trainos_theme', 'light');
    }
    updateChartColors();
}

// --- Initialize Theme on Page Load ---
window.addEventListener('DOMContentLoaded', () => {
    
    startClock();
    initCharts();
    // Check if the user previously chose dark mode
    if (localStorage.getItem('trainos_theme') === 'dark') {
        document.body.classList.add('dark-theme');
        const btn = document.getElementById('theme-toggle');
        if (btn) btn.innerText = '☀️';
    }
});


// --- Chart Variables & Configuration ---
const MAX_DATAPOINTS = 60; // 60 seconds of history
let chartKin, chartTemp, chartPneu, chartElec;

// Shared common options for a clean scientific look
const commonChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 0 },
    elements: {
        point: { radius: 0 }, 
        line: { tension: 0.2, borderWidth: 2 }
    },
    plugins: { 
        legend: { 
            labels: { 
                color: '#7f8c8d',
                usePointStyle: true, // Turns the legend icon into a circle
                pointStyle: 'circle' // Explicitly sets the shape
            } 
        } 
    },
    scales: {
        x: { grid: { color: '#e0e0e0' }, ticks: { color: '#7f8c8d' } },
        y: { grid: { color: '#e0e0e0' }, ticks: { color: '#7f8c8d' } }
    }
};

function initCharts() {
    // 1. Kinematics Plot
    chartKin = new Chart(document.getElementById('chart-kinematics'), {
        type: 'line',
        data: { 
            labels: [], 
            datasets: [{ 
                label: 'Speed (km/h)', 
                borderColor: '#3498db', 
                backgroundColor: '#3498db', 
                data: [] 
            }] 
        },
        options: { ...commonChartOptions }
    });

    // 2. Temperature Plot (3 lines)
    chartTemp = new Chart(document.getElementById('chart-temperature'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'Engine (°C)', borderColor: '#e74c3c', backgroundColor: '#e74c3c', data: [] },
                { label: 'Cabin (°C)', borderColor: '#2ecc71', backgroundColor: '#2ecc71', data: [] },
                { label: 'Outside (°C)', borderColor: '#9b59b6', backgroundColor: '#9b59b6', data: [] }
            ]
        },
        options: { ...commonChartOptions }
    });

    // 3. Pneumatics Plot (2 lines)
    chartPneu = new Chart(document.getElementById('chart-pneumatics'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'Main Res (PSI)', borderColor: '#34495e', backgroundColor: '#34495e', data: [] },
                { label: 'Brake Pipe (PSI)', borderColor: '#e67e22', backgroundColor: '#e67e22', data: [] }
            ]
        },
        options: { ...commonChartOptions }
    });

    // 4. Electrical Plot (Dual Y-Axis)
    chartElec = new Chart(document.getElementById('chart-electrical'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'Traction Volts (V)', borderColor: '#f1c40f', backgroundColor: '#f1c40f', data: [], yAxisID: 'y' },
                { label: 'Traction Amps (A)', borderColor: '#1abc9c', backgroundColor: '#1abc9c', data: [], yAxisID: 'y1' }
            ]
        },
        options: {
            ...commonChartOptions,
            scales: {
                x: commonChartOptions.scales.x,
                y: { type: 'linear', display: true, position: 'left', grid: { color: '#e0e0e0' }, ticks: { color: '#7f8c8d' } },
                y1: { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#7f8c8d' } }
            }
        }
    });
}

// --- Dynamic Data Insertion ---
function updateCharts(data) {
    if (!chartKin) return; // Ensure charts are ready

    const timestamp = new Date(data.timestamp).toLocaleTimeString();

    // Helper function to update a specific chart
    const pushData = (chart, newLabel, newValues) => {
        chart.data.labels.push(newLabel);
        if (chart.data.labels.length > MAX_DATAPOINTS) chart.data.labels.shift();

        chart.data.datasets.forEach((dataset, index) => {
            dataset.data.push(newValues[index]);
            if (dataset.data.length > MAX_DATAPOINTS) dataset.data.shift();
        });
        chart.update('none'); // Update without animation
    };

    // Push data to all 4 charts safely handling null values (simulated broken sensors)
    pushData(chartKin, timestamp, [data.kinematics?.speed_kmh || 0]);
    
    pushData(chartTemp, timestamp, [
        data.engine_and_fuel?.engine_temperature_c || 0,
        data.environment?.cabin_temperature_c || 0,
        data.environment?.outside_temperature_c || 0
    ]);

    pushData(chartPneu, timestamp, [
        data.pneumatics?.main_reservoir_psi || 0,
        data.pneumatics?.brake_pipe_psi || 0
    ]);

    pushData(chartElec, timestamp, [
        data.electrical?.traction_voltage_v || 0,
        data.electrical?.traction_current_a || 0
    ]);
}

// --- Dashboard SPA Navigation ---
function switchDashboardView(viewId) {
    // 1. Hide all views
    document.getElementById('main-view').classList.add('hidden');
    document.getElementById('details-view').classList.add('hidden');
    document.getElementById('map-view').classList.add('hidden');
    document.getElementById('alerts-view').classList.add('hidden');
    document.getElementById('controls-view').classList.add('hidden');

    // 2. Show the requested view
    document.getElementById(viewId).classList.remove('hidden');

    // 3. Update active state on navigation buttons dynamically
    document.getElementById('nav-main').classList.remove('active');
    document.getElementById('nav-details').classList.remove('active');
    document.getElementById('nav-map').classList.remove('active');
    document.getElementById('nav-alerts').classList.remove('active');
    document.getElementById('nav-controls').classList.remove('active');
    
    // Construct the nav ID (e.g., 'map-view' -> 'nav-map')
    const navId = 'nav-' + viewId.replace('-view', '');
    document.getElementById(navId).classList.add('active');

    // 4. Handle Leaflet Map rendering quirk
    if (viewId === 'map-view') {
        if (!mapInitialized) {
            initializeMap(); // We will define this below
        } else if (map) {
            // Give the DOM a tiny amount of time to display the block before recalculating size
            setTimeout(() => { map.invalidateSize(); }, 100);
        }
    }
}

function initializeMap() {
    if (mapInitialized) return;

    // Standard Leaflet setup
    map = L.map('map').setView([48.8566, 2.3522], 6); // Default coords (e.g., Paris)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap'
    }).addTo(map);

    // Create a marker for the train
    trainMarker = L.marker([48.8566, 2.3522]).addTo(map);
    
    mapInitialized = true;
}

function handleAlerts(data, trainId) {
    const currentStatus = data.status.system_alert_state;

    // 1. Only log if status is NOT normal AND it is DIFFERENT from the last time we saw THIS train
    if (currentStatus !== "NORMAL" && currentStatus !== fleetAlertStates[trainId]) {
        const tbody = document.getElementById('alert-log-body');
        const timestamp = new Date(data.timestamp).toLocaleTimeString();
        
        const row = document.createElement('tr');
        // Add a class for styling if it's a sensor failure vs a critical emergency
        const alertClass = currentStatus === "SENSOR_FAILURE" ? "warn-text" : "danger-text";
        
        row.innerHTML = `
            <td>${timestamp}</td>
            <td><span class="badge-train">${trainId.toUpperCase().replace('_', ' ')}</span></td>
            <td><span class="${alertClass}">${currentStatus}</span></td>
            <td><button class="btn-ack" onclick="acknowledgeAlert(this)">ACK</button></td>
        `;
        
        if (tbody) tbody.prepend(row);
        
        if (trainId !== currentTrainId) {
            console.warn(`BACKGROUND ALERT: ${trainId} is reporting ${currentStatus}`);
        }
    }

    // 2. IMPORTANT: Update the tracker for this specific train
    fleetAlertStates[trainId] = currentStatus;
}

// --- Theme Updates for Charts ---
// Call this at the end of your existing toggleTheme() function
function updateChartColors() {
    if (!chartKin) return;
    const isDark = document.body.classList.contains('dark-theme');
    const gridColor = isDark ? '#444444' : '#e0e0e0';
    const textColor = isDark ? '#bdc3c7' : '#7f8c8d';

    [chartKin, chartTemp, chartPneu, chartElec].forEach(chart => {
        Object.values(chart.options.scales).forEach(scale => {
            if (scale.grid) scale.grid.color = gridColor;
            if (scale.ticks) scale.ticks.color = textColor;
        });
        chart.options.plugins.legend.labels.color = textColor;
        chart.update('none');
    });
}

function sendCommand(cmdType) {
    // 1. Security Check for Admin-Only Commands
    const restrictedCommands = ['RESET_TRIP', 'CLEAR_FAULTS'];
    
    if (restrictedCommands.includes(cmdType) && currentUserRole !== 'admin') {
        alert("🛑 ACCESS DENIED: Administrator privileges required to execute this command.");
        
        // Optional: Log the unauthorized attempt in the terminal
        const logUl = document.getElementById('command-log');
        if (logUl) {
            logUl.innerHTML += `<li><span style="color: #e74c3c;">[SECURITY]</span> Unauthorized attempt to execute ${cmdType}.</li>`;
        }
        return; // Stop the function from running
    }
    const timestamp = new Date().toLocaleTimeString();
    const log = document.getElementById('command-log');
    
    // 1. Create a log entry
    const entry = document.createElement('li');
    entry.innerHTML = `<span style="color: #3498db;">[${timestamp}]</span> SENDING COMMAND: <strong>${cmdType}</strong>...`;
    log.prepend(entry); // Most recent at top

    // 2. Visual Feedback
    console.log(`Uplink: Transmitting ${cmdType} to Train ECU...`);

    // 3. (Advanced) Send to Backend via WebSocket
    // If your FastAPI was set up to receive data, you would do:
    // ws.send(JSON.stringify({ "command": cmdType, "operator": "Admin" }));
    
    // 4. Confirmation Toast
    if(cmdType === 'EMERGENCY_BRAKE') {
        alert("EMERGENCY BRAKE ACTIVATED. Signal sent to all pneumatic valves.");
    }
}

function clearLocalLogs() {
    if (confirm("Are you sure you want to clear the active event view? Historical data will remain in the system log.")) {
        const tbody = document.getElementById('alert-log-body');
        if (tbody) tbody.innerHTML = '';
    }
}

function downloadLog() {
    // Security Check
    if (currentUserRole !== 'admin') {
        alert("🛑 ACCESS DENIED: Administrator privileges required to download incident reports.");
        return; // Stop the download
    }
    const rows = document.querySelectorAll('#alert-log-body tr');
    let content = "TRAIN OS - INCIDENT REPORT\n==========================\n";
    rows.forEach(row => {
        content += row.innerText.replace(/\t/g, " | ") + "\n";
    });
    
    const blob = new Blob([content], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `incident_log_${new Date().getTime()}.txt`;
    a.click();
}

function switchTrain() {
    currentTrainId = document.getElementById('train-id').value;
    // Clear charts to make the switch visual
    speedChart.data.labels = [];
    speedChart.data.datasets[0].data = [];
    speedChart.update();
    // Reset map focus
    mapInitialized = false; 
}