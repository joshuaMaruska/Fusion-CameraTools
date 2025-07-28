import { safeAddEventListener } from './utils.js';

// Palette ready signal
export function sendPaletteReadyWhenAdskAvailable() {
    if (window.adsk && typeof adsk.fusionSendData === 'function') {
        adsk.fusionSendData('paletteReady', '');
    } else {
        setTimeout(sendPaletteReadyWhenAdskAvailable, 50);
    }
}

// Palette close button event listener
export function registerPaletteCloseButton() {
    const closeBtn = document.getElementById('closePaletteButton');
    if (closeBtn) {
        closeBtn.addEventListener('click', function () {
            adsk.fusionSendData('closePalette', JSON.stringify({}));
        });
    }
}

// Dark mode toggle event listener
export function registerDarkModeToggle() {
    const darkModeSwitch = document.getElementById('toggleDarkModeSwitch');
    if (darkModeSwitch) {
        darkModeSwitch.addEventListener('change', function () {
            document.documentElement.classList.toggle('dark-mode', this.checked);
            adsk.fusionSendData('darkModeChanged', JSON.stringify({ enabled: this.checked }));
        });
    }
}

// Initialization function to be called on DOMContentLoaded
export function initPalette() {
    sendPaletteReadyWhenAdskAvailable();
    registerPaletteCloseButton();
    registerDarkModeToggle();
}