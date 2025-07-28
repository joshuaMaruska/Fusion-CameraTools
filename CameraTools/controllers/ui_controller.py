"""
UI Controller - orchestrates all user interface updates, palette communication, and UI state.
Manages timers, UI state, and coordinates between domain controllers and UI.
Uses Fusion-safe custom event timer for high-frequency camera telemetry,
and timer_manager (idle event) for overlay and named view polling.
"""

import adsk
import json
import threading
import time
import traceback

LOG_MODULE = 'ui_controller'

from ..utilities import log_utils
log_utils.set_module_logging(LOG_MODULE, False)  # Disable verbose logging for deployment

app = adsk.core.Application.get()
ui = app.userInterface

# Custom event ID for main-thread UI updates
CT_UI_UPDATE_EVENT_ID = 'CameraTools_UIUpdateEvent'
_ui_update_thread = None
_ui_update_stop_event = None
_ui_update_event_registered = False
_ui_update_event_handler = None

class UIState:
    """Manages UI state for consistency and viewport tracking."""
    def __init__(self):
        self._initialize_defaults()

    def _initialize_defaults(self):
        self.cached_view_names = None
        self.last_document_id = None
        self.previous_viewport_width = 0
        self.previous_viewport_height = 0
        self.viewport_repaint_in_progress = False
        self.ui_update_in_progress = False

    def reset(self):
        self._initialize_defaults()

class UIUpdateEventHandler(adsk.core.CustomEventHandler):
    """Handles periodic UI update events (main thread safe)."""
    def __init__(self):
        super().__init__()
        self._last_named_view_poll = 0

    def notify(self, eventArgs):
        try:
            from .ui_controller import get_ui_controller
            ui_controller = get_ui_controller()
            if not ui_controller.active_palette or not ui_controller.active_palette.isVisible:
                return
            from .camera_controller import get_camera_controller
            from .overlay_controller import get_overlay_controller
            from .view_controller import get_view_controller

            # High frequency polling (30Hz)
            get_camera_controller().send_camera_state_to_ui()

            # Low frequency polling (3Hz)
            now = time.time()
            if now - self._last_named_view_poll > 0.3:  # 3Hz
                get_view_controller().poll_named_views_update()
                get_overlay_controller().poll_viewport_size_change()
                from .eye_level_controller import get_eye_level_controller
                get_eye_level_controller().check_and_apply_passive_correction()
                self._last_named_view_poll = now

        except Exception:
            pass  # Suppress errors for periodic UI update

def register_ui_update_event():
    """Register the custom event for UI updates."""
    global _ui_update_event_registered, _ui_update_event_handler
    if _ui_update_event_registered:
        return
    handler = UIUpdateEventHandler()
    custom_event = app.registerCustomEvent(CT_UI_UPDATE_EVENT_ID)
    custom_event.add(handler)
    _ui_update_event_handler = handler  # Keep a reference!
    _ui_update_event_registered = True

def start_ui_update_timer():
    """Start the background thread for UI update events."""
    global _ui_update_thread, _ui_update_stop_event
    if _ui_update_thread and _ui_update_thread.is_alive():
        return  # Already running
    _ui_update_stop_event = threading.Event()
    def run():
        while _ui_update_stop_event is not None and not _ui_update_stop_event.is_set():
            app.fireCustomEvent(CT_UI_UPDATE_EVENT_ID, '')
            time.sleep(1.0 / 30)  # 30Hz
    _ui_update_thread = threading.Thread(target=run, daemon=True)
    _ui_update_thread.start()

def stop_ui_update_timer():
    """Stop the background UI update thread."""
    global _ui_update_stop_event, _ui_update_thread
    if _ui_update_stop_event:
        _ui_update_stop_event.set()
    _ui_update_thread = None

class UIController:
    """Unified UI controller - handles all UI orchestration and state."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.ui_state = UIState()
        self.active_palette = None
        self.lock_enabled = False
        self.target_eye_level = None
        self._initialized = True

    # =========================
    # PALETTE LIFECYCLE
    # =========================

    def initialize_for_palette(self, palette):
        """Initialize UI controller for palette."""
        try:
            self.active_palette = palette
            from ..utilities import eye_level_utils
            lock_status = eye_level_utils.get_eye_level_lock_status()
            self.lock_enabled = lock_status['enabled']
            self.target_eye_level = lock_status['target_level']
            if self.lock_enabled:
                self.start_passive_eye_level_lock()
            register_ui_update_event()
            start_ui_update_timer()
        except Exception:
            pass

    def cleanup_for_palette_close(self):
        """Cleanup UI controller for palette close."""
        try:
            stop_ui_update_timer()
            self.ui_state = UIState()
            self.active_palette = None
        except Exception:
            pass

    def cleanup_all_timers(self):
        """Stop all UI timers."""
        try:
            stop_ui_update_timer()
            self.ui_state.reset()
        except Exception:
            pass

    def cleanup(self):
        """Full cleanup for UI controller."""
        try:
            self.cleanup_all_timers()
            self.active_palette = None
        except Exception:
            pass

    # =========================
    # PALETTE COMMUNICATION
    # =========================

    def send_data_to_palette(self, action, data):
        """Send data to palette with error handling."""
        try:
            if self.active_palette and self.active_palette.isVisible:
                payload = {
                    "action": action,
                    "data": data
                }
                self.active_palette.sendInfoToHTML(payload["action"], json.dumps(payload["data"]))
                return True
            return False
        except Exception:
            return False

    # =========================
    # DOCUMENT EVENTS
    # =========================

    def handle_document_activation(self, palette):
        """Handle document activation - coordinate UI updates."""
        try:
            from ..utilities import prefs_utils
            prefs_utils.send_prefs(palette)
            from .camera_controller import get_camera_controller
            camera_controller = get_camera_controller()
            camera_controller.update_distance_bounds()
            from ..utilities import camera_telemetry
            camera_telemetry.send_current_camera_data(palette, force=True)
            from .view_controller import get_view_controller
            view_controller = get_view_controller()
            view_controller.populate_named_views_dropdown(palette)
            self.ui_state.cached_view_names = None
            self.ui_state.last_document_id = None
        except Exception:
            pass

    # =========================
    # VIEWPORT OPERATIONS
    # =========================

    def handle_viewport_repaint(self):
        """Handle viewport repaint - delegate to overlay controller."""
        try:
            if not self.ui_state.viewport_repaint_in_progress:
                self.ui_state.viewport_repaint_in_progress = True
                from .overlay_controller import get_overlay_controller
                overlay_controller = get_overlay_controller()
                overlay_controller.repaint_all_overlays()
                self.ui_state.viewport_repaint_in_progress = False
        except Exception:
            self.ui_state.viewport_repaint_in_progress = False

    # =========================
    # UI PREFERENCES
    # =========================

    def handle_dark_mode_change(self, data):
        """Handle dark mode preference changes."""
        try:
            is_enabled = data.get('enabled')
            from ..utilities import prefs_utils
            preferences = prefs_utils.load_prefs()
            if preferences is None:
                preferences = {}
            preferences["darkMode"] = is_enabled
            prefs_utils.save_prefs(preferences)
        except Exception:
            pass

    # =========================
    # CUSTOM PALETTE CLOSE HANDLING
    # =========================

    def handle_custom_palette_close(self):
        """Handle custom palette close (not standard close button)."""
        try:
            if self.active_palette:
                from ..CameraTools import cleanup_palette_resources
                cleanup_palette_resources()
                self.active_palette.isVisible = False
            return True
        except Exception:
            return False
        
# =========================
# SINGLETON INSTANCE
# =========================

_ui_controller_instance = None

def get_ui_controller():
    """Get the UI controller singleton."""
    global _ui_controller_instance
    if _ui_controller_instance is None:
        _ui_controller_instance = UIController()
    return _ui_controller_instance