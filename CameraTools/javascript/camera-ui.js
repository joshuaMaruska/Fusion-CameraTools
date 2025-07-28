// Camera slider/input event listeners and UI sync helpers
import { safeAddEventListener, fovToFocalLength, focalLengthToFov, focalLengthToSliderValue, sliderValueToFocalLength, SENSOR_WIDTH, FOCAL_MIN, FOCAL_MAX, SLIDER_MIN, SLIDER_MAX } from './utils.js';

function sendCameraAction(control, value) {
    if (window.adsk && typeof adsk.fusionSendData === 'function') {
        let action = '';
        switch (control) {
            case 'distance': action = 'distanceChanged'; break;
            case 'azimuth': action = 'azimuthChanged'; break;
            case 'inclination': action = 'inclinationChanged'; break;
            case 'fov': action = 'fovChanged'; break;
            case 'focalLength': action = 'focalLengthChanged'; break;
            case 'dolly': action = 'dollyChanged'; break;
            case 'pan': action = 'panChanged'; break;
            default: action = 'cameraControlChanged'; // fallback
        }
        adsk.fusionSendData(action, JSON.stringify({ value }));
    }
}

function handleCameraSliderChange(e) {
    const id = e.target.id;
    const value = e.target.value;
    const inputId = id + 'Value';
    const input = document.getElementById(inputId);
    if (input) input.value = value;
    sendCameraAction(id, value);

    // Live sync FL when FOV slider moves
    if (id === 'fov') {
        updateFocalLengthFromFov(parseFloat(value));
    }
}

function handleCameraInputChange(e) {
    const id = e.target.id;
    const value = e.target.value;
    const sliderId = id.replace('Value', '');
    const slider = document.getElementById(sliderId);
    if (slider) slider.value = value;
    sendCameraAction(sliderId, value);
}

function handleFocalLengthSliderChange(e) {
    const value = sliderValueToFocalLength(e.target.value);
    const input = document.getElementById('focalLengthValue');
    if (input) input.value = value.toFixed(0);
    adsk.fusionSendData('focalLengthChanged', JSON.stringify({ value }));
    updateFovFromFocalLength(value);
}

function handleFocalLengthInputChange(e) {
    const value = parseFloat(e.target.value);
    const slider = document.getElementById('focalLength');
    if (slider && !isNaN(value)) slider.value = focalLengthToSliderValue(value);
    adsk.fusionSendData('focalLengthChanged', JSON.stringify({ value }));
    updateFovFromFocalLength(value);
}

function registerCameraTypeSwitch() {
    const cameraTypeSwitch = document.getElementById('cameraTypeSwitch');
    if (cameraTypeSwitch) {
        cameraTypeSwitch.addEventListener('change', function () {
            const cameraType = cameraTypeSwitch.checked ? 1 : 0;
            adsk.fusionSendData('cameraTypeChanged', JSON.stringify({ cameraType }));
        });
    }
}

export function registerCameraControls() {
    safeAddEventListener('distance', 'input', handleCameraSliderChange);
    safeAddEventListener('distanceValue', 'change', handleCameraInputChange);
    safeAddEventListener('azimuth', 'input', handleCameraSliderChange);
    safeAddEventListener('azimuthValue', 'change', handleCameraInputChange);
    safeAddEventListener('inclination', 'input', handleCameraSliderChange);
    safeAddEventListener('inclinationValue', 'change', handleCameraInputChange);
    safeAddEventListener('dolly', 'input', handleCameraSliderChange);
    safeAddEventListener('dollyValue', 'change', handleCameraInputChange);
    safeAddEventListener('pan', 'input', handleCameraSliderChange);
    safeAddEventListener('panValue', 'change', handleCameraInputChange);
    safeAddEventListener('fov', 'input', handleCameraSliderChange);
    safeAddEventListener('fovValue', 'change', handleCameraInputChange);
    safeAddEventListener('focalLength', 'input', handleFocalLengthSliderChange);
    safeAddEventListener('focalLengthValue', 'change', handleFocalLengthInputChange);
    // Register Lens pane button
    safeAddEventListener('fusionDefault', 'click', () => {
        adsk.fusionSendData('fusionDefault', JSON.stringify({}));
    });
    // Register View pane buttons
    safeAddEventListener('copyView', 'click', () => {
        adsk.fusionSendData('copyView', JSON.stringify({}));
    });
    safeAddEventListener('pasteView', 'click', () => {
        adsk.fusionSendData('pasteView', JSON.stringify({}));
    });
    safeAddEventListener('saveView', 'click', () => {
        adsk.fusionSendData('saveView', JSON.stringify({}));
    });
    safeAddEventListener('fitToView', 'click', () => {
        adsk.fusionSendData('fitToView', JSON.stringify({}));
    });
    safeAddEventListener('resetView', 'click', () => {
        adsk.fusionSendData('resetView', JSON.stringify({}));
    });
    // Register Grid Overlay toggles
    safeAddEventListener('toggleHalves', 'change', function () {
        adsk.fusionSendData('setGridOverlay', JSON.stringify({ type: 'halves', enabled: this.checked }));
    });
    safeAddEventListener('toggleThirds', 'change', function () {
        adsk.fusionSendData('setGridOverlay', JSON.stringify({ type: 'thirds', enabled: this.checked }));
    });
    safeAddEventListener('toggleQuarters', 'change', function () {
        adsk.fusionSendData('setGridOverlay', JSON.stringify({ type: 'quarters', enabled: this.checked }));
    });

    // Focal Length Numeric Input Setup
    const focalLengthValue = document.getElementById('focalLengthValue');
    const focalLengthSlider = document.getElementById('focalLength');
    if (focalLengthValue) {
        focalLengthValue.setAttribute('min', FOCAL_MIN);
        focalLengthValue.setAttribute('max', FOCAL_MAX);
        focalLengthValue.setAttribute('step', '1');
        focalLengthValue.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                const focalLength = parseFloat(event.target.value);
                if (!isNaN(focalLength)) {
                    const clampedFL = Math.max(FOCAL_MIN, Math.min(FOCAL_MAX, focalLength));
                    event.target.value = clampedFL.toFixed(0);
                    if (focalLengthSlider) focalLengthSlider.value = focalLengthToSliderValue(clampedFL);
                    updateFovFromFocalLength(clampedFL);
                }
            }
        });
    }

    // Focal Length Slider Setup
    if (focalLengthSlider) {
        focalLengthSlider.setAttribute('min', SLIDER_MIN);
        focalLengthSlider.setAttribute('max', SLIDER_MAX);
        focalLengthSlider.setAttribute('step', '1');
    }
}

export function initCameraUI() {
    registerCameraControls();
    registerCameraTypeSwitch();
}

// =========================
// Camera UI Sync Helpers
// =========================
export function updateFocalLengthFromFov(fov) {
    const focalLength = fovToFocalLength(fov);
    const focalLengthValue = document.getElementById('focalLengthValue');
    const focalLengthSlider = document.getElementById('focalLength');
    if (!isNaN(focalLength)) {
        if (focalLengthValue) focalLengthValue.value = focalLength.toFixed(0);
        if (focalLengthSlider) focalLengthSlider.value = focalLengthToSliderValue(focalLength);
    }
}
export function updateFovFromFocalLength(focalLength) {
    const fov = focalLengthToFov(focalLength);
    const fovValue = document.getElementById('fovValue');
    const fovSlider = document.getElementById('fov');
    if (!isNaN(fov)) {
        if (fovValue) fovValue.value = fov.toFixed(2);
        if (fovSlider) fovSlider.value = fov.toFixed(2);
        adsk.fusionSendData('fovChanged', JSON.stringify({
            value: fov.toFixed(2),
            userInitiated: true
        }));
    }
}