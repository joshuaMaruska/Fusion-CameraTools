// Constants
export const SENSOR_WIDTH = 36.0;
export const FOCAL_MIN = 7;
export const FOCAL_MAX = 412;
export const SLIDER_MIN = 0;
export const SLIDER_MAX = 100;
export const DEBOUNCE_MS = 8; // 125 FPS

// Debounce helper
export function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Logging utility
export function sendLogMessage(message) {
    if (window.adsk && typeof adsk.fusionSendData === 'function') {
        adsk.fusionSendData('logMessage', JSON.stringify({ message }));
    }
}

// Safe event listener utility
export function safeAddEventListener(id, event, handler) {
    const el = document.getElementById(id);
    if (el) el.addEventListener(event, handler);
}

// Math utilities
export function fovToFocalLength(fov) {
    return SENSOR_WIDTH / (2 * Math.tan((Math.PI / 180) * fov / 2));
}

export function focalLengthToFov(focalLength) {
    return (2 * Math.atan(SENSOR_WIDTH / (2 * focalLength))) * (180 / Math.PI);
}

export function sliderValueToFocalLength(sliderValue) {
    const minLog = Math.log(FOCAL_MIN);
    const maxLog = Math.log(FOCAL_MAX);
    const scale = (sliderValue - SLIDER_MIN) / (SLIDER_MAX - SLIDER_MIN);
    const logValue = minLog + (maxLog - minLog) * scale;
    return Math.exp(logValue);
}

export function focalLengthToSliderValue(focalLength) {
    const minLog = Math.log(FOCAL_MIN);
    const maxLog = Math.log(FOCAL_MAX);
    const logValue = Math.log(focalLength);
    const scale = (logValue - minLog) / (maxLog - minLog);
    return SLIDER_MIN + scale * (SLIDER_MAX - SLIDER_MIN);
}