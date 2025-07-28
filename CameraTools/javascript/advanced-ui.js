function safeAddEventListener(id, event, handler) {
    const el = document.getElementById(id);
    if (el) el.addEventListener(event, handler);
}

// Eye Level Lock status sync from backend
function registerEyeLevelLockHandler() {
    if (window.adsk && typeof adsk.fusionSendDataHandler === 'function') {
        adsk.fusionSendDataHandler('eyeLevelLockStatus', function(data) {
            console.log('eyeLevelLockStatus received:', data);
            const lockEyeLevelToggle = document.getElementById('lockEyeLevelToggle');
            if (lockEyeLevelToggle) {
                lockEyeLevelToggle.checked = !!data.enabled;
            }
        });
    } else {
        setTimeout(registerEyeLevelLockHandler, 50);
    }
}

export function registerAdvancedCameraControls() {
    // Eye Level Lock
    const lockEyeLevelToggle = document.getElementById('lockEyeLevelToggle');
    if (lockEyeLevelToggle) {
        lockEyeLevelToggle.addEventListener('change', (event) => {
            adsk.fusionSendData('toggleEyeLevelLock', JSON.stringify({
                enabled: event.target.checked,
                eyeLevel: parseFloat(document.getElementById('eyeLevelValue').value) || 0
            }));
        });
    }

    // Eye Level Numeric Input
    const eyeLevelInput = document.getElementById('eyeLevelValue');
    if (eyeLevelInput) {
        eyeLevelInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                const eyeLevel = parseFloat(event.target.value);
                if (!isNaN(eyeLevel)) {
                    adsk.fusionSendData('setEyeLevel', JSON.stringify({
                        eyeLevel: eyeLevel,
                        locked: document.getElementById('lockEyeLevelToggle').checked,
                        snap: true
                    }));
                    event.target.blur();
                }
            }
        });
        eyeLevelInput.addEventListener('blur', (event) => {
            const eyeLevel = parseFloat(event.target.value);
            if (!isNaN(eyeLevel)) {
                adsk.fusionSendData('setEyeLevel', JSON.stringify({
                    eyeLevel: eyeLevel,
                    locked: document.getElementById('lockEyeLevelToggle').checked,
                    snap: true
                }));
            }
        });
    }

    // Set Eye/Target Buttons
    safeAddEventListener('setEye', 'click', () => {
        adsk.fusionSendData('setEye', JSON.stringify({}));
    });
    safeAddEventListener('setTarget', 'click', () => {
        adsk.fusionSendData('setTarget', JSON.stringify({}));
    });

    // Dolly Controls
    const dollySlider = document.getElementById('dollySlider');
    if (dollySlider) {
        dollySlider.addEventListener('input', (event) => {
            const value = parseFloat(event.target.value);
            adsk.fusionSendData('dollyChanged', JSON.stringify({ value }));
            const dollyValue = document.getElementById('dollyValue');
            if (dollyValue && document.activeElement !== dollyValue) dollyValue.value = value;
        });
    }
    const dollyValue = document.getElementById('dollyValue');
    if (dollyValue) {
        dollyValue.addEventListener('change', (event) => {
            const value = parseFloat(event.target.value);
            adsk.fusionSendData('dollyChanged', JSON.stringify({ value }));
            const dollySlider = document.getElementById('dollySlider');
            if (dollySlider && document.activeElement !== dollySlider) dollySlider.value = value;
        });
    }

    // Pan Controls
    const panSlider = document.getElementById('panSlider');
    if (panSlider) {
        panSlider.addEventListener('input', (event) => {
            const value = parseFloat(event.target.value);
            adsk.fusionSendData('panChanged', JSON.stringify({ value }));
            const panValue = document.getElementById('panValue');
            if (panValue && document.activeElement !== panValue) panValue.value = value;
        });
    }
    const panValue = document.getElementById('panValue');
    if (panValue) {
        panValue.addEventListener('change', (event) => {
            const value = parseFloat(event.target.value);
            adsk.fusionSendData('panChanged', JSON.stringify({ value }));
            const panSlider = document.getElementById('panSlider');
            if (panSlider && document.activeElement !== panSlider) panSlider.value = value;
        });
    }

    // Tilt Controls
    const tiltSlider = document.getElementById('tiltSlider');
    if (tiltSlider) {
        tiltSlider.addEventListener('input', (event) => {
            const value = parseFloat(event.target.value);
            adsk.fusionSendData('tiltChanged', JSON.stringify({ value }));
            const tiltValue = document.getElementById('tiltValue');
            if (tiltValue && document.activeElement !== tiltValue) tiltValue.value = value;
        });
    }
    const tiltValue = document.getElementById('tiltValue');
    if (tiltValue) {
        tiltValue.addEventListener('change', (event) => {
            const value = parseFloat(event.target.value);
            adsk.fusionSendData('tiltChanged', JSON.stringify({ value }));
            const tiltSlider = document.getElementById('tiltSlider');
            if (tiltSlider && document.activeElement !== tiltSlider) tiltSlider.value = value;
        });
    }

    // Eye Level Lock status sync
    registerEyeLevelLockHandler();
}

// For consistency with camera-ui.js
export function initAdvancedUI() {
    registerAdvancedCameraControls();
}