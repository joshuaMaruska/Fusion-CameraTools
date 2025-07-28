"""
CameraController: Orchestrates camera state, UI feedback, and event handling for CameraTools.
Receives UI events, delegates to utilities, manages state, and communicates with the palette.
No direct math or API calls except for orchestration.
"""

import adsk
import threading
import traceback

LOG_MODULE = 'camera_controller'

from ..utilities import log_utils
log_utils.set_module_logging(LOG_MODULE, False)  # Disable verbose logging for deployment

from ..utilities import camera_telemetry, camera_commands, camera_calculations, camera_transforms, view_utils

app = adsk.core.Application.get()
ui = app.userInterface

class CameraController:
    """
    Singleton controller for camera state and UI communication.
    """
    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.initial_camera_state = None
        self.active_palette = None
        self.distance_bounds = None
        self._pending_camera_update = {}
        self._pending_update_timer = None
        self._pending_update_lock = threading.RLock()
        self._initialized = True

    # ========== Palette Lifecycle ==========

    def initialize_for_palette(self, palette):
        """
        Initialize controller for the palette.
        """
        try:
            self.active_palette = palette
            self.record_initial_camera_state()
            self.update_distance_bounds()
            self.send_camera_state_to_ui()
        except Exception:
            pass  # Suppress errors for deployment

    def cleanup_for_palette_close(self):
        """
        Cleanup controller state when palette closes.
        """
        try:
            self.active_palette = None
            self.initial_camera_state = None
            self.distance_bounds = None
            self._pending_camera_update = {}
            if self._pending_update_timer:
                self._pending_update_timer.cancel()
                self._pending_update_timer = None
        except Exception:
            pass

    def cleanup(self):
        """
        Cleanup controller state.
        """
        self.cleanup_for_palette_close()

    # ========== Camera Property Change Handling ==========

    def handle_camera_property_change(self, property_name, value, palette, force=False):
        """
        Handle camera property changes from UI.
        """
        if not palette:
            return
        self.active_palette = palette
        with self._pending_update_lock:
            self._pending_camera_update[property_name] = value

            # --- Eye lock logic: capture eye/target/upVector if FOV/FL is being changed ---
            from ..utilities import eye_level_utils
            eye_lock_active = eye_level_utils.is_eye_level_lock_active()
            fov_or_fl_changing = property_name in ('fov', 'focalLength')
            if eye_lock_active and fov_or_fl_changing:
                camera = app.activeViewport.camera
                self._pending_camera_update['eye'] = {'x': camera.eye.x, 'y': camera.eye.y, 'z': camera.eye.z}
                self._pending_camera_update['target'] = {'x': camera.target.x, 'y': camera.target.y, 'z': camera.target.z}
                self._pending_camera_update['upVector'] = {'x': camera.upVector.x, 'y': camera.upVector.y, 'z': camera.upVector.z}

            self._apply_pending_camera_update(force=force)

    def _apply_pending_camera_update(self, force=False):
        """
        Apply pending camera property changes.
        """
        with self._pending_update_lock:
            try:
                pending_type = self._pending_camera_update.get('cameraType')
                current_type = app.activeViewport.camera.cameraType
                if pending_type is not None and pending_type != current_type:
                    from ..utilities.camera_commands import sanitize_camera_for_type_change
                    sanitize_camera_for_type_change(
                        app.activeViewport.camera, app.activeViewport, app, adsk,
                        target_camera_type=pending_type
                    )
                payload = camera_commands.build_camera_payload(self._pending_camera_update, app)
                camera_commands.apply_camera_state(payload, app, apply_mode="ui")
                self.send_camera_state_to_ui(force=force)
                self._pending_camera_update.clear()
            except Exception:
                pass

    def apply_camera_data_direct(self, camera_data):
        """
        Apply camera data for copy/paste only.
        """
        try:
            payload = camera_commands.build_camera_payload_from_canonical(camera_data, app)
            camera_commands.apply_camera_state(payload, app, apply_mode="direct")
            self.send_camera_state_to_ui(force=True)
            return True
        except Exception:
            return False

    # ========== Other Handlers (Non-property) ==========

    def handle_set_eye(self, data, palette=None):
        """
        Set camera eye position from selected construction point.
        """
        sel = app.userInterface.activeSelections
        if sel.count == 0 or not hasattr(sel.item(0).entity, 'geometry'):
            app.userInterface.messageBox("Select a construction point first.")
            return
        point = sel.item(0).entity.geometry
        from ..utilities.camera_calculations import set_camera_eye_to_point
        set_camera_eye_to_point(app, point)
        self.send_camera_state_to_ui(force=True)

    def handle_set_target(self, data, palette=None):
        """
        Set camera target position from selected construction point.
        """
        sel = app.userInterface.activeSelections
        if sel.count == 0 or not hasattr(sel.item(0).entity, 'geometry'):
            app.userInterface.messageBox("Select a construction point first.")
            return
        point = sel.item(0).entity.geometry
        from ..utilities.camera_calculations import set_camera_target_to_point
        set_camera_target_to_point(app, point)
        self.send_camera_state_to_ui(force=True)

    def handle_view_fit(self, data, palette):
        """
        Fit view to model.
        """
        try:
            app.activeViewport.fit()
            self._delayed_camera_state_to_ui()
        except Exception:
            pass

    def handle_view_reset(self, data, palette):
        """
        Reset view to initial camera state.
        """
        try:
            self._restore_initial_camera_state()
            self._delayed_camera_state_to_ui()
        except Exception:
            pass

    def handle_fusion_default_lens(self, data, palette):
        """
        Reset camera to Fusion default lens.
        """
        try:
            camera_commands.apply_fusion_default_lens(app)
            self._delayed_camera_state_to_ui()
        except Exception:
            pass

    # ========== State Management ==========

    def record_initial_camera_state(self):
        """
        Record initial camera state for reset.
        """
        try:
            camera = app.activeViewport.camera
            self.initial_camera_state = {
                'eye': (camera.eye.x, camera.eye.y, camera.eye.z),
                'target': (camera.target.x, camera.target.y, camera.target.z),
                'upVector': (camera.upVector.x, camera.upVector.y, camera.upVector.z),
                'perspectiveAngle': camera.perspectiveAngle,
                'cameraType': camera.cameraType,
                'isFitView': getattr(camera, 'isFitView', False),
                'isSmoothTransition': getattr(camera, 'isSmoothTransition', False)
            }
        except Exception:
            pass

    def _restore_initial_camera_state(self):
        """
        Restore camera to initial state.
        """
        try:
            if not self.initial_camera_state:
                return
            camera_commands.restore_camera_state(self.initial_camera_state, app)
        except Exception:
            pass

    def update_distance_bounds(self, multiplier=4.0):
        """
        Update camera distance bounds.
        """
        self.distance_bounds = camera_commands.get_distance_bounds(app, multiplier)
        return self.distance_bounds

    def get_distance_bounds(self):
        """
        Get current camera distance bounds.
        """
        if not self.distance_bounds:
            self.update_distance_bounds()
        return self.distance_bounds

    def _delayed_camera_state_to_ui(self, delay=0.15):
        """
        Send camera state to UI after a delay.
        """
        def send():
            constraints = self.get_distance_bounds() or {}
            camera_telemetry.send_camera_state_to_ui(
                self.active_palette, app, adsk, None, None,
                min_distance=constraints.get('min_distance'),
                max_distance=constraints.get('max_distance')
            )
        threading.Timer(delay, send).start()

    def send_camera_state_to_ui(self, eventArgs=None, force=False):
        """
        Send camera state to UI (palette).
        """
        try:
            if force or (self.active_palette and not getattr(self, 'telemetry_paused', False)):
                constraints = self.get_distance_bounds() or {}
                camera_telemetry.send_camera_state_to_ui(
                    self.active_palette, app, adsk, camera_calculations, camera_transforms,
                    min_distance=constraints.get('min_distance'),
                    max_distance=constraints.get('max_distance')
                )
        except Exception:
            pass

# =========================
# SINGLETON INSTANCE
# =========================

_camera_controller_instance = None

def get_camera_controller():
    """
    Get the singleton CameraController instance.
    """
    global _camera_controller_instance
    if _camera_controller_instance is None:
        _camera_controller_instance = CameraController()
    return _camera_controller_instance