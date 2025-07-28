import { safeAddEventListener } from './utils.js';

// Dropdown logic: handles custom dropdowns and outside click closing

export function handleDropdownClicks(e) {
    const target = e.target;
    // Toggle dropdown list visibility
    if (target.classList.contains('dropdown-btn')) {
        const dropdown = target.closest('.hig-dropdown');
        const list = dropdown.querySelector('.dropdown-list');
        const expanded = target.getAttribute('aria-expanded') === 'true';
        if (list) {
            list.style.display = expanded ? 'none' : 'block';
            target.setAttribute('aria-expanded', expanded ? 'false' : 'true');
        }
        e.stopPropagation();
    }
}

// Close dropdowns when clicking outside the palette
export function registerOutsideClickHandler() {
    document.addEventListener('click', function(e) {
        const palette = document.getElementById('cameraToolsPalette');
        if (!palette || !palette.contains(e.target)) {
            document.querySelectorAll('.hig-dropdown').forEach(dropdown => {
                const list = dropdown.querySelector('.dropdown-list');
                const btn = dropdown.querySelector('.dropdown-btn');
                if (list) list.style.display = 'none';
                if (btn) btn.setAttribute('aria-expanded', 'false');
            });
        }
    });
}

export function populateNamedViews(data) {
    console.log('populateNamedViews called with:', data);
    const dropdown = document.getElementById('namedViewsDropdown');
    if (!dropdown || !data || !Array.isArray(data.namedViews)) return;
    console.log('Populating named views dropdown with data:', data.namedViews);
    const list = dropdown.querySelector('.dropdown-list');
    if (!list) return;

    // Clear existing options
    list.innerHTML = '';

    // Optionally add a placeholder
    const placeholder = document.createElement('div');
    placeholder.className = 'dropdown-option';
    placeholder.setAttribute('role', 'option');
    placeholder.setAttribute('aria-selected', 'true');
    placeholder.setAttribute('data-index', '');
    placeholder.textContent = 'Select a Named View';
    list.appendChild(placeholder);

    data.namedViews.forEach((view, idx) => {
        const option = document.createElement('div');
        option.className = 'dropdown-option';
        option.setAttribute('role', 'option');
        option.setAttribute('data-index', idx);
        option.textContent = view.name || `View ${idx + 1}`;
        list.appendChild(option);
    });

    // Re-attach listeners after repopulating
    attachDropdownOptionListeners();
}

export function attachDropdownOptionListeners() {
    // Named Views Dropdown
    const namedViewsDropdown = document.getElementById('namedViewsDropdown');
    if (namedViewsDropdown) {
        const list = namedViewsDropdown.querySelector('.dropdown-list');
        const btn = namedViewsDropdown.querySelector('.dropdown-btn');
        const btnSpan = btn ? btn.querySelector('#namedViewsSelected') : null;
        const options = list ? list.querySelectorAll('.dropdown-option') : [];
        options.forEach(option => {
            option.onclick = function() {
                options.forEach(opt => opt.removeAttribute('aria-selected'));
                option.setAttribute('aria-selected', 'true');
                if (btnSpan) btnSpan.textContent = option.textContent || 'Select a Named View';
                if (list) list.style.display = 'none';
                if (btn) btn.setAttribute('aria-expanded', 'false');
                const viewIndex = option.getAttribute('data-index');
                if (viewIndex !== null && viewIndex !== undefined && viewIndex !== '') {
                    adsk.fusionSendData('namedViewSelected', JSON.stringify({ viewIndex: parseInt(viewIndex) }));
                }
            };
        });
    }

    // Aspect Ratio Dropdown
    const aspectDropdownContainer = document.getElementById('aspectRatioDropdownContainer');
    if (aspectDropdownContainer) {
        const list = aspectDropdownContainer.querySelector('.dropdown-list');
        const btn = aspectDropdownContainer.querySelector('.dropdown-btn');
        const btnSpan = btn ? btn.querySelector('span') : null;
        const options = list ? list.querySelectorAll('.dropdown-option') : [];
        options.forEach(option => {
            option.onclick = function() {
                options.forEach(opt => opt.removeAttribute('aria-selected'));
                option.setAttribute('aria-selected', 'true');
                if (btnSpan) btnSpan.textContent = option.textContent || 'Aspect Ratio';
                if (list) list.style.display = 'none';
                if (btn) btn.setAttribute('aria-expanded', 'false');
                const aspectRatio = option.getAttribute('data-value');
                if (aspectRatio) {
                    adsk.fusionSendData('aspectRatioChanged', JSON.stringify({ aspectRatio }));
                }
            };
        });
    }
}

// Initialization function to be called on DOMContentLoaded
export function initDropdowns() {
    document.addEventListener('click', handleDropdownClicks);
    registerOutsideClickHandler();
    attachDropdownOptionListeners();
}