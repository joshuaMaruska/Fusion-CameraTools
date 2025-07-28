import { initPalette } from './javascript/palette.js';
import { initDropdowns } from './javascript/dropdown.js';
import { initTelemetry } from './javascript/telemetry.js';
import { initCameraUI, updateFocalLengthFromFov, updateFovFromFocalLength } from './javascript/camera-ui.js';
import { fovToFocalLength, focalLengthToFov, focalLengthToSliderValue, sliderValueToFocalLength } from './javascript/utils.js';
import { initAdvancedUI } from './javascript/advanced-ui.js';
import { attachDropdownOptionListeners } from './javascript/dropdown.js';
import { populateNamedViews } from './javascript/dropdown.js';

let selectedNamedView = null;
let isNamedViewCurrent = false;
let initialCameraState = null;

let userInteracting = {
    distance: false,
    fov: false,
    focalLength: false,
    azimuth: false,
    inclination: false,
    pan: false,
    dolly: false,
    tilt: false
};


attachDropdownOptionListeners();

// =========================
// Fusion 360 -> JS Message Handler
// =========================
function handleIncomingData(action, data) {
    try {
        switch (action) {
            case 'updateCameraData':
                updateCameraData(JSON.parse(data));
                break;
            case 'initialCameraState':
                initialCameraState = JSON.parse(data);
                break;
            case 'populateNamedViews':
                populateNamedViews(JSON.parse(data));
                console.log("Named views populated:", data);
                break;
            case 'resetNamedViewSelection':
                resetNamedViewSelection();
                break;
            case 'resetNamedViewDropdown':
                resetNamedViewDropdown();
                isNamedViewCurrent = false;
                selectedNamedView = null;
                break;
            case 'loadPrefs':
                handleLoadPrefs(JSON.parse(data));
                break;
            case 'updateCameraMode':
                break;
            case 'eyeLevelLockStatus':
                // Telemetry module handles this, so skip here
                break;
            case 'dolly':
                break;
            case 'pan':
                break;
            case 'tilt':
                break;
            case 'data':
                let msg = data;
                if (typeof msg === 'string') {
                    try { msg = JSON.parse(msg); } catch (e) { break; }
                }
                if (msg.action === "loadPrefs") {
                    handleLoadPrefs(msg.prefs ? { prefs: msg.prefs } : msg);
                }
                break;
            case 'testAction':
                break;
            default:
                break;
        }
    } catch (e) {
        console.log(e);
        return 'FAILED';
    }
    return JSON.stringify({ status: 'OK' });
}

window.fusionJavaScriptHandler = {
    handle: function (actionString, dataString) {
        handleIncomingData(actionString, dataString);
    }
};

// =========================
// DOMContentLoaded: UI Setup & Module Initialization
// =========================
document.addEventListener('DOMContentLoaded', function () {
    initPalette();
    initDropdowns();
    initTelemetry();
    initCameraUI();
    initAdvancedUI();
});

// =========================
// The following helpers are still referenced by the message handler
// =========================

// Preferences loader (used by handleIncomingData)
function handleLoadPrefs(msg) {
    const prefs = msg.prefs || msg;
    const darkModeSwitch = document.getElementById('toggleDarkModeSwitch');
    if (darkModeSwitch) darkModeSwitch.checked = prefs.darkMode;
    document.documentElement.classList.toggle('dark-mode', prefs.darkMode);
    const aspectDropdown = document.getElementById('aspectRatioDropdown');
    if (aspectDropdown) aspectDropdown.value = prefs.aspectRatio;
    const aspectDropdownContainer = document.getElementById('aspectRatioDropdownContainer');
    if (aspectDropdownContainer) {
        const btn = aspectDropdownContainer.querySelector('.dropdown-btn span');
        const options = aspectDropdownContainer.querySelectorAll('.dropdown-option');
        if (btn && options.length > 0) {
            let found = false;
            options.forEach(opt => {
                if (opt.dataset.value === prefs.aspectRatio) {
                    opt.setAttribute('aria-selected', 'true');
                    btn.textContent = opt.textContent;
                    found = true;
                } else {
                    opt.removeAttribute('aria-selected');
                }
            });
            if (!found && options[0]) {
                options[0].setAttribute('aria-selected', 'true');
                btn.textContent = options[0].textContent;
            }
        }
    }
    const halves = document.getElementById('toggleHalves');
    if (halves) halves.checked = prefs.gridHalves;
    const thirds = document.getElementById('toggleThirds');
    if (thirds) thirds.checked = prefs.gridThirds;
    const quarters = document.getElementById('toggleQuarters');
    if (quarters) quarters.checked = prefs.gridQuarters;
    adsk.fusionSendData('aspectRatioChanged', JSON.stringify({ aspectRatio: prefs.aspectRatio }));
    adsk.fusionSendData('setGridOverlay', JSON.stringify({ type: 'halves', enabled: prefs.gridHalves }));
    adsk.fusionSendData('setGridOverlay', JSON.stringify({ type: 'thirds', enabled: prefs.gridThirds }));
    adsk.fusionSendData('setGridOverlay', JSON.stringify({ type: 'quarters', enabled: prefs.gridQuarters }));
}

// Camera state sync/update helpers (still referenced by message handler)
function updateCameraData(cameraData) {
    // console.log("Received cameraData:", cameraData);
    if (!cameraData) return;

    // Distance
    const distanceSlider = document.getElementById('distance');
    const distanceValue = document.getElementById('distanceValue');
    if (!userInteracting.distance && distanceSlider && document.activeElement !== distanceSlider) {
        const distance = parseFloat(cameraData.distance);
        if (!isNaN(distance)) distanceSlider.value = distance.toFixed(2);
        if (typeof cameraData.minDistance === 'number') distanceSlider.min = cameraData.minDistance;
        if (typeof cameraData.maxDistance === 'number') distanceSlider.max = cameraData.maxDistance;
    }
    if (!userInteracting.distance && distanceValue && document.activeElement !== distanceValue) {
        const distance = parseFloat(cameraData.distance);
        if (!isNaN(distance)) distanceValue.value = distance.toFixed(2);
    }

    // FOV
    const fovSlider = document.getElementById('fov');
    const fovValue = document.getElementById('fovValue');
    if (!userInteracting.fov && fovSlider && document.activeElement !== fovSlider) {
        const fov = parseFloat(cameraData.fov);
        if (!isNaN(fov)) fovSlider.value = fov.toFixed(2);
    }
    if (!userInteracting.fov && fovValue && document.activeElement !== fovValue) {
        const fov = parseFloat(cameraData.fov);
        if (!isNaN(fov)) fovValue.value = fov.toFixed(2);
    }
    
    const focalLengthValue = document.getElementById('focalLengthValue');
        if (!userInteracting.focalLength && focalLengthValue && document.activeElement !== focalLengthValue) {
        updateFocalLengthFromFov(parseFloat(cameraData.fov));
    }

    // Azimuth
    const azimuthSlider = document.getElementById('azimuth');
    const azimuthValue = document.getElementById('azimuthValue');
    if (!userInteracting.azimuth && azimuthSlider && document.activeElement !== azimuthSlider) {
        const azimuth = parseFloat(cameraData.azimuth);
        if (!isNaN(azimuth)) azimuthSlider.value = azimuth.toFixed(2);
    }
    if (!userInteracting.azimuth && azimuthValue && document.activeElement !== azimuthValue) {
        const azimuth = parseFloat(cameraData.azimuth);
        if (!isNaN(azimuth)) azimuthValue.value = azimuth.toFixed(2);
    }

    // Inclination
    const inclinationSlider = document.getElementById('inclination');
    const inclinationValue = document.getElementById('inclinationValue');
    if (!userInteracting.inclination && inclinationSlider && document.activeElement !== inclinationSlider) {
        const inclination = parseFloat(cameraData.inclination);
        if (!isNaN(inclination)) inclinationSlider.value = inclination.toFixed(2);
    }
    if (!userInteracting.inclination && inclinationValue && document.activeElement !== inclinationValue) {
        const inclination = parseFloat(cameraData.inclination);
        if (!isNaN(inclination)) inclinationValue.value = inclination.toFixed(2);
    }

    // Dolly
    const dollySlider = document.getElementById('dollySlider');
    const dollyValue = document.getElementById('dollyValue');
    if (dollySlider && !userInteracting.dolly && document.activeElement !== dollySlider) {
        const dolly = parseFloat(cameraData.dolly);
        if (!isNaN(dolly)) dollySlider.value = dolly.toFixed(2);
        if (typeof cameraData.minDistance === 'number') dollySlider.min = 0.1;
        if (typeof cameraData.maxDistance === 'number') dollySlider.max = cameraData.maxDistance;
    }
    if (dollyValue && !userInteracting.dolly && document.activeElement !== dollyValue) {
        const dolly = parseFloat(cameraData.dolly);
        if (!isNaN(dolly)) dollyValue.value = dolly.toFixed(2);
    }

    // Pan
    const panSlider = document.getElementById('panSlider');
    const panValue = document.getElementById('panValue');
    if (panSlider && !userInteracting.pan && document.activeElement !== panSlider) {
        const pan = parseFloat(cameraData.pan);
        if (!isNaN(pan)) panSlider.value = pan.toFixed(2);
    }
    if (panValue && !userInteracting.pan && document.activeElement !== panValue) {
        const pan = parseFloat(cameraData.pan);
        if (!isNaN(pan)) panValue.value = pan.toFixed(2);
    }

    // Tilt
    const tiltSlider = document.getElementById('tiltSlider');
    const tiltValue = document.getElementById('tiltValue');
    if (tiltSlider && !userInteracting.tilt && document.activeElement !== tiltSlider) {
        const tilt = parseFloat(cameraData.tilt);
        if (!isNaN(tilt)) tiltSlider.value = tilt.toFixed(2);
    }
    if (tiltValue && !userInteracting.tilt && document.activeElement !== tiltValue) {
        const tilt = parseFloat(cameraData.tilt);
        if (!isNaN(tilt)) tiltValue.value = tilt.toFixed(2);
    }

    // Eye Level
    const eyeLevelInput = document.getElementById('eyeLevelValue');
    if (eyeLevelInput && typeof cameraData.eyeLevel === 'number' && document.activeElement !== eyeLevelInput) {
        eyeLevelInput.value = cameraData.eyeLevel.toFixed(2);
    }

    // Camera type switch and control enable/disable
    const cameraTypeSwitch = document.getElementById('cameraTypeSwitch');
    const isPerspective = cameraData.cameraType === 1;
    if (cameraTypeSwitch) cameraTypeSwitch.checked = isPerspective;
    [
        'distance',
        'distanceValue',
        'lockEyeLevelToggle',
        'eyeLevelValue',
        'fov',
        'fovValue',
        'focalLength',
        'focalLengthValue',
        'fusionDefault',
        'dollySlider',
        'dollyValue',
        'panSlider',
        'panValue',
        'tiltSlider',
        'tiltValue',
    ].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.disabled = !isPerspective;
    });
}

// =========================
// Eye Level Update
// =========================
function updateEyeLevelFromCamera(cameraData) {
    const eyeLevelInput = document.getElementById('eyeLevelValue');
    if (
        eyeLevelInput &&
        typeof cameraData.eyeLevel === 'number' &&
        document.activeElement !== eyeLevelInput
    ) {
        eyeLevelInput.value = cameraData.eyeLevel.toFixed(2);
    }
}
// =========================
// Dolly Pan Tilt
// =========================
function handleDolly(data) {
    // This can update UI or just pass to backend
    // For now, just log
    console.log('Dolly event received:', data);
}

function handlePan(data) {
    console.log('Pan event received:', data);
}

function handleTilt(data) {
    console.log('Tilt event received:', data);
}


//# sourceMappingURL=all.js.map