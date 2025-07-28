// Telemetry pause/resume logic and eye-level lock status sync
import { safeAddEventListener, debounce } from './utils.js';


export function registerTelemetryPauseResumeHooks() {
    let resumeTelemetryTimeout = null;

    function pauseTelemetry() {
        if (!window.cameraTelemetryPaused) {
            window.cameraTelemetryPaused = true;
            if (window.adsk && adsk.fusionSendData) {
                adsk.fusionSendData('pauseTelemetry', JSON.stringify({}));
            }
        }
        if (resumeTelemetryTimeout) {
            clearTimeout(resumeTelemetryTimeout);
            resumeTelemetryTimeout = null;
        }
    }

    function resumeTelemetry() {
        if (window.cameraTelemetryPaused) {
            if (resumeTelemetryTimeout) {
                clearTimeout(resumeTelemetryTimeout);
            }
            // Debounce: wait 150ms before resuming
            resumeTelemetryTimeout = setTimeout(() => {
                window.cameraTelemetryPaused = false;
                if (window.adsk && adsk.fusionSendData) {
                    adsk.fusionSendData('resumeTelemetry', JSON.stringify({}));
                }
            }, 200); // adjust delay as needed
        }
    }

document.querySelectorAll('input[type="range"], input[type="number"], input[type="text"]').forEach(el => {
        el.addEventListener('focus', pauseTelemetry);
        el.addEventListener('mousedown', pauseTelemetry);
        el.addEventListener('touchstart', pauseTelemetry);
        el.addEventListener('blur', resumeTelemetry);
        el.addEventListener('mouseup', resumeTelemetry);
        el.addEventListener('touchend', resumeTelemetry);
        if (el.type === 'number' || el.type === 'text') {
            el.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') resumeTelemetry();
            });
        }
    });
}

// Initialization function to be called on DOMContentLoaded
export function initTelemetry() {
    registerTelemetryPauseResumeHooks();
}
