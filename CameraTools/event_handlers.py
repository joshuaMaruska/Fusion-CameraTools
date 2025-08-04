"""
Event handlers for CameraTools - Routes UI events to appropriate controllers.
Clean architecture: UI Events → Event Handlers → Controllers → Utilities

NOTE: Only CameraTools.py should set/clear active_palette_instance.
      This file should only use palette references passed to handlers.

NOTE: Palette close is always triggered via a custom UI button,
      which sends the 'closePalette' event to the event handler.
      This ensures all cleanup logic runs before the palette is hidden.
"""

import adsk  # type: ignore
import json
import traceback

LOG_MODULE = 'event_handlers'

from .utilities import log_utils
log_utils.set_module_logging(LOG_MODULE, False)  # Disable verbose logging for deployment

from .utilities import prefs_utils

app = adsk.core.Application.get()
ui = app.userInterface
event_handlers_list = []

class PaletteIncomingEventHandler(adsk.core.HTMLEventHandler):
    """
    Handles incoming events from the HTML palette and routes them to controllers.
    """
    def __init__(self, palette):
        super().__init__()
        self.palette = palette

    def notify(self, eventArgs):
        """
        Main event dispatcher for palette HTML events.
        Routes actions to appropriate handler methods.
        """
        try:
            event_args = adsk.core.HTMLEventArgs.cast(eventArgs)
            data = event_args.data
            action = event_args.action

            # Action routing map
            action_routing_map = {
                # Palette lifecycle
                'paletteReady': self.handle_palette_ready,
                'closePalette': self.handle_palette_close,

                # UI interaction tracking
                'pauseTelemetry': self.handle_pause_telemetry,
                'resumeTelemetry': self.handle_resume_telemetry,

                # Camera operations
                'updateCameraData': self.handle_sync_update_camera_data,
                'cameraTypeChanged': self.handle_camera_type_change,
                'distanceChanged': self.handle_distance_change,
                'azimuthChanged': self.handle_azimuth_change,
                'inclinationChanged': self.handle_inclination_change,
                'fovChanged': self.handle_fov_change,
                'fusionDefault': self.handle_fusion_default_lens,

                # Advanced camera operations
                'dollyChanged': self.handle_dolly_change,
                'panChanged': self.handle_pan_change,
                'tiltChanged': self.handle_tilt_change,
                'setEye': self.handle_set_eye,
                'setTarget': self.handle_set_target,

                # Eye level operations
                'setEyeLevel': self.handle_eye_level_value_change,
                'lockEyeLevel': self.handle_eye_level_lock,
                'toggleEyeLevelLock': self.handle_eye_level_lock_toggle,
                'updateEyeLevelIndicator': self.handle_eye_level_indicator_update,

                # View operations
                'namedViewSelected': self.handle_named_view_selection,
                'populateNamedViews': self.handle_named_views_population,
                'checkNamedViewSync': self.handle_named_view_sync_check,
                'saveView': self.handle_named_view_save,
                'copyView': self.handle_view_copy,
                'pasteView': self.handle_view_paste,
                'resetView': self.handle_view_reset,
                'fitToView': self.handle_view_fit,

                # Overlay operations
                'aspectRatioChanged': self.handle_aspect_ratio_change,
                'setGridOverlay': self.handle_set_grid_overlay,

                # UI preferences
                'darkModeChanged': self.handle_dark_mode_change,
                'logMessage': self.handle_log_message,
                'htmlTest': self.handle_html_test,
                'response': self.handle_ui_response
            }

            if action in action_routing_map:
                try:
                    action_data = json.loads(data) if data else {}
                    action_routing_map[action](action_data)
                except Exception as e:
                    # Only log errors for debugging
                    log_utils.log(app, f'Error handling action {action}: {e}', level='ERROR', module=LOG_MODULE)
            else:
                log_utils.log(app, f'Unknown action: {action}', level='WARNING', module=LOG_MODULE)

        except Exception as e:
            log_utils.log(app, f'Error in palette event handler notify: {e}', level='ERROR', module=LOG_MODULE)

    # ========== PALETTE LIFECYCLE HANDLERS ==========

    def handle_palette_ready(self, data):
        """
        Initialize controllers and send lock state/preferences to UI when palette is ready.
        """
        try:
            _initialize_controllers_for_palette(self.palette)
            from .controllers.eye_level_controller import get_eye_level_controller
            eye_level_controller = get_eye_level_controller()
            self.palette.sendInfoToHTML('eyeLevelLockStatus', json.dumps({'enabled': eye_level_controller.lock_enabled}))
            prefs_utils.send_prefs(self.palette)
        except Exception as e:
            ui.messageBox(f'Failed to initialize palette:\n{traceback.format_exc()}')

    def handle_palette_close(self, data):
        """
        Cleanup all controllers and state when palette is closed.
        """
        try:
            from .controllers.overlay_controller import get_overlay_controller
            get_overlay_controller().clear_all_overlays()
            from .controllers.eye_level_controller import get_eye_level_controller
            get_eye_level_controller().disable_eye_level_lock()
            from .controllers.camera_controller import get_camera_controller
            get_camera_controller().cleanup_for_palette_close()
            from .controllers.view_controller import get_view_controller
            get_view_controller().cleanup_for_palette_close()
            from .controllers.ui_controller import get_ui_controller
            get_ui_controller()
            if self.palette:
                self.palette.isVisible = False
            cleanup_palette_global()
        except Exception as e:
            ui.messageBox(f'Failed to close palette:\n{traceback.format_exc()}')

    # ========== UI INTERACTION HANDLERS ==========

    def handle_pause_telemetry(self, data):
        """Pause camera telemetry updates."""
        from .controllers.camera_controller import get_camera_controller
        get_camera_controller().telemetry_paused = True

    def handle_resume_telemetry(self, data):
        """Resume camera telemetry updates."""
        from .controllers.camera_controller import get_camera_controller
        get_camera_controller().telemetry_paused = False

    # ========== CAMERA OPERATION HANDLERS ==========

    def handle_sync_update_camera_data(self, data):
        """Send the current camera state to the UI (palette)."""
        from .controllers.camera_controller import get_camera_controller
        get_camera_controller().send_camera_state_to_ui()

    def handle_camera_type_change(self, data):
        value = self._extract_numeric(data, 'cameraType')
        self.handle_camera_property_change('cameraType', value, force=True)

    def handle_distance_change(self, data):
        value = self._extract_numeric(data, 'distance')
        self.handle_camera_property_change('distance', value)

    def handle_azimuth_change(self, data):
        value = self._extract_numeric(data, 'azimuth')
        self.handle_camera_property_change('azimuth', value)

    def handle_inclination_change(self, data):
        value = self._extract_numeric(data, 'inclination')
        self.handle_camera_property_change('inclination', value)

    def handle_set_eye(self, data):
        """Set the camera eye position from a selected construction point."""
        from .controllers.camera_controller import get_camera_controller
        get_camera_controller().handle_set_eye(data, self.palette)

    def handle_set_target(self, data):
        """Set the camera target position from a selected construction point."""
        from .controllers.camera_controller import get_camera_controller
        get_camera_controller().handle_set_target(data, self.palette)

    def handle_dolly_change(self, data):
        value = self._extract_numeric(data, 'dolly')
        self.handle_camera_property_change('dolly', value)

    def handle_pan_change(self, data):
        value = self._extract_numeric(data, 'pan')
        self.handle_camera_property_change('pan', value)

    def handle_tilt_change(self, data):
        value = self._extract_numeric(data, 'tilt')
        self.handle_camera_property_change('tilt', value)

    def handle_fov_change(self, data):
        value = self._extract_numeric(data, 'fov')
        self.handle_camera_property_change('fov', value)

    def handle_camera_property_change(self, property_name, value, force=False):
        """
        Route camera property changes to the camera controller.
        """
        from .controllers.camera_controller import get_camera_controller
        get_camera_controller().handle_camera_property_change(property_name, value, self.palette, force=force)

    def handle_fusion_default_lens(self, data):
        from .controllers.camera_controller import get_camera_controller
        get_camera_controller().handle_fusion_default_lens(data, self.palette)

    def handle_view_fit(self, data):
        from .controllers.camera_controller import get_camera_controller
        get_camera_controller().handle_view_fit(data, self.palette)

    def handle_view_reset(self, data):
        from .controllers.camera_controller import get_camera_controller
        get_camera_controller().handle_view_reset(data, self.palette)

    # ========== HELPERS ==========

    def _extract_numeric(self, data, key=None):
        """
        Extract a float value from data, supporting both dict and direct number.
        """
        if isinstance(data, (int, float)):
            return float(data)
        elif isinstance(data, dict):
            return float(data.get('value', data.get(key, 0)))
        else:
            return float(data)

    # ========== EYE LEVEL HANDLERS ==========

    def handle_eye_level_value_change(self, data):
        from .controllers.eye_level_controller import get_eye_level_controller
        get_eye_level_controller().handle_eye_level_value_change(data, self.palette)

    def handle_eye_level_lock(self, data):
        from .controllers.eye_level_controller import get_eye_level_controller
        get_eye_level_controller().handle_eye_level_lock(data, self.palette)

    def handle_eye_level_lock_toggle(self, data):
        from .controllers.eye_level_controller import get_eye_level_controller
        get_eye_level_controller().handle_eye_level_lock_toggle(data, self.palette)

    def handle_eye_level_indicator_update(self, data):
        from .controllers.eye_level_controller import get_eye_level_controller
        get_eye_level_controller().handle_eye_level_indicator_update(data, self.palette)

    # ========== VIEW HANDLERS ==========

    def handle_named_view_selection(self, data):
        from .controllers.view_controller import get_view_controller
        get_view_controller().handle_named_view_selected(data, self.palette)

    def handle_named_views_population(self, data):
        from .controllers.view_controller import get_view_controller
        get_view_controller().handle_named_views_population(data, self.palette)

    def handle_named_view_sync_check(self, data):
        from .controllers.view_controller import get_view_controller
        get_view_controller().handle_named_view_sync_check(data, self.palette)

    def handle_named_view_save(self, data):
        from .controllers.view_controller import get_view_controller
        get_view_controller().handle_named_view_save(data, self.palette)

    def handle_view_copy(self, data):
        from .controllers.view_controller import get_view_controller
        get_view_controller().handle_view_copy(data, self.palette)

    def handle_view_paste(self, data):
        from .controllers.view_controller import get_view_controller
        get_view_controller().handle_view_paste(data, self.palette)

    # ========== OVERLAY HANDLERS ==========

    def handle_aspect_ratio_change(self, data):
        from .controllers.overlay_controller import get_overlay_controller
        get_overlay_controller().handle_aspect_ratio_change(data, self.palette)

    def handle_set_grid_overlay(self, data):
        from .controllers.overlay_controller import get_overlay_controller
        get_overlay_controller().handle_set_grid_overlay(data, self.palette)

    # ========== UI PREFERENCE HANDLERS ==========

    def handle_dark_mode_change(self, data):
        from .controllers.ui_controller import get_ui_controller
        get_ui_controller().handle_dark_mode_change(data)

    def handle_log_message(self, data):
        """Handle log messages from HTML (currently disabled)."""
        pass  # Disabled to reduce log noise

    def handle_html_test(self, data):
        """Handle HTML test button actions."""
        try:
            from .controllers.overlay_controller import get_overlay_controller
            get_overlay_controller().clear_all_overlays()
            ui.messageBox('HTML test button clicked!')
        except Exception:
            pass  # Suppress errors for test button

    def handle_ui_response(self, data):
        """Handle generic UI responses - usually can be ignored."""
        pass  # Silently ignore UI responses

# ========== MODULE-LEVEL FUNCTIONS ==========

def handle_initial_camera_states():
    """
    Handle initial camera states setup - delegate to camera controller.
    """
    try:
        from .controllers.camera_controller import get_camera_controller
        get_camera_controller().handle_initial_camera_states()
    except Exception:
        pass

def check_and_apply_passive_eye_level_correction():
    """
    Check and apply passive eye level correction - delegate to eye level controller.
    """
    try:
        from .controllers.eye_level_controller import get_eye_level_controller
        get_eye_level_controller().check_and_apply_passive_correction()
    except Exception:
        pass

def _initialize_controllers_for_palette(palette_instance):
    """
    Initialize all controllers for palette.
    """
    try:
        from .controllers.ui_controller import get_ui_controller
        get_ui_controller().initialize_for_palette(palette_instance)
        from .controllers.camera_controller import get_camera_controller
        get_camera_controller().initialize_for_palette(palette_instance)
        from .controllers.view_controller import get_view_controller
        get_view_controller().initialize_for_palette(palette_instance)
        from .controllers.eye_level_controller import get_eye_level_controller
        get_eye_level_controller().initialize_for_palette(palette_instance)
        from .controllers.overlay_controller import get_overlay_controller
        get_overlay_controller().initialize_for_palette(palette_instance)
    except Exception:
        pass

def cleanup_event_handlers():
    """
    Clean up event handlers module - delegate to all controllers.
    """
    try:
        from .controllers.camera_controller import get_camera_controller
        from .controllers.eye_level_controller import get_eye_level_controller
        from .controllers.view_controller import get_view_controller
        from .controllers.overlay_controller import get_overlay_controller
        get_camera_controller().cleanup()
        get_eye_level_controller().cleanup()
        get_view_controller().cleanup()
        get_overlay_controller().cleanup()
    except Exception:
        pass

def cleanup_palette_global():
    """
    Global palette cleanup - stop all timers and clear global state.
    """
    try:
        event_handlers_list.clear()
    except Exception:
        pass