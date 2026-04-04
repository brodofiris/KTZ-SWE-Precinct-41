const API_URL = window.location.origin; 
const WS_URL = API_URL.replace(/^http/, 'ws');
const authWrapper = document.getElementById('auth-wrapper');

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
        
        triggerAnimation(authWrapper, 'anim-success', 800);
        errorMsg.style.color = '#2ecc71';
        errorMsg.innerText = "Access Granted...";

        setTimeout(() => {
            authWrapper.classList.add('hidden');
            document.getElementById('dashboard-container').classList.remove('hidden');
            document.body.style.alignItems = 'flex-start'; 
            document.body.style.paddingTop = '40px';
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

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Registration failed");
        }

        errorMsg.style.color = '#2ecc71';
        errorMsg.innerText = "Registration successful! Returning to login...";
        triggerAnimation(authWrapper, 'anim-success', 800);

        setTimeout(() => {
            switchView('login-view');
            document.getElementById('login-user').value = document.getElementById('reg-opnum').value;
            document.getElementById('login-pass').value = '';
        }, 1500);

    } catch (error) {
        triggerAnimation(authWrapper, 'anim-shake', 500);
        errorMsg.style.color = '#e74c3c';
        errorMsg.innerText = error.message;
    }
}

// --- WebSocket Logic ---
function connectWebSocket(token) {
    const output = document.getElementById('telemetry-output');
    const ws = new WebSocket(`${WS_URL}/ws/telemetry?token=${token}`);

    ws.onopen = () => output.innerText = "Connection established. Receiving telemetry...\n\n";
    ws.onclose = () => output.innerText += "\n[SYSTEM] Connection lost to train.";
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.error) {
            output.innerText = `SYSTEM ERROR: ${data.error}\n`;
            return;
        }

        let text = `[${data.timestamp}]\n`;
        text += `STATUS:    ${data.status.system_alert_state}\n`;
        text += `SPEED:     ${data.kinematics.speed_kmh} km/h\n`;
        text += `FUEL:      ${data.engine_and_fuel.fuel_level_liters} L\n`;
        text += `TRACTION:  ${data.electrical.traction_voltage_v} V | ${data.electrical.traction_current_a} A\n`;
        
        output.innerText = text;
    };
}