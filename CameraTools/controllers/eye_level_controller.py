"""
EyeLevelController: Orchestrates all eye level operations using eye_level_utils and camera_commands.
No direct camera writes. All camera changes go through the camera pipeline.
Passive lock uses Fusion's cameraChanged event, not polling or threading.
"""

import adsk
import adsk.fusion
import json
import time

LOG_MODULE = 'eye_level_controller'

from ..utilities import log_utils
log_utils.set_module_logging(LOG_MODULE, False)  # Disable verbose logging for deployment

from ..utilities import eye_level_utils, camera_commands

app = adsk.core.Application.get()
ui = app.userInterface
animate_eye_level = True

# =========================
# SUBCLASSES
# =========================

class PassiveEyeLevelCameraHandler(adsk.core.CameraEventHandler):
    """Handles Fusion cameraChanged events for passive eye level correction."""
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

    def notify(self, args):
        self.controller._on_camera_changed(args)

# =========================
# MAIN CONTROLLER
# =========================

class EyeLevelController:
    """Singleton controller for all eye level operations and state."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.lock_enabled = False
        self.target_eye_level = 0.0
        self.active_palette = None
        self.correction_tolerance = 0.1  # 1mm
        self._last_camera_change = 0
        self._camera_event = None
        self._camera_event_handler = None
        self._initialized = True

    # =========================
    # PALETTE LIFECYCLE
    # =========================

    def initialize_for_palette(self, palette):
        """
        Initialize controller for the palette.
        """
        self.active_palette = palette
        self.lock_enabled = False
        self.target_eye_level = 0.0
        palette.sendInfoToHTML('eyeLevelLockStatus', json.dumps({'enabled': False}))

    def cleanup_for_palette_close(self):
        """
        Cleanup controller state when palette closes.
        """
        self.disable_eye_level_lock()
        if self.active_palette:
            self.active_palette.sendInfoToHTML('eyeLevelLockStatus', json.dumps({'enabled': False}))
        self.active_palette = None
        self.lock_enabled = False
        self.target_eye_level = 0.0

    def cleanup(self):
        """
        Cleanup controller state.
        """
        self.cleanup_for_palette_close()

    # =========================
    # UI EVENT HANDLERS
    # =========================

    def handle_eye_level_value_change(self, data, palette=None):
        """
        Handle eye level value changes from UI.
        """
        try:
            if isinstance(data, str):
                data = json.loads(data)
            eye_level_value = float(data.get('eyeLevel', 0.0))
            should_snap = data.get('snap', False)
            self._update_eye_level_overlay(eye_level_value)
            if should_snap and eye_level_value != 0.0:
                self.set_eye_and_target_level(eye_level=eye_level_value, target_level=eye_level_value)
        except Exception:
            pass

    def handle_eye_level_lock_toggle(self, data, palette=None):
        """
        Handle eye level lock toggle from UI.
        """
        try:
            if isinstance(data, str):
                data = json.loads(data)
            is_enabled = data.get('enabled', False)
            target_eye_level = float(data.get('eyeLevel', 0.0))
            success = eye_level_utils.set_eye_level_lock_state(is_enabled, target_eye_level)
            if success:
                self.lock_enabled = is_enabled
                self.target_eye_level = target_eye_level
                if is_enabled:
                    self.start_passive_eye_level_lock()
                else:
                    self.stop_passive_eye_level_lock()
        except Exception:
            pass

    # =========================
    # EYE LEVEL OPERATIONS
    # =========================

    def set_eye_and_target_level(self, eye_level=None, target_level=None):
        """
        Set both eye and target to the specified level.
        """
        try:
            # Animation toggle
            if getattr(self, 'animate_eye_level', True):
                eye_level_utils.animate_eye_and_target_level(eye_level=eye_level, target_level=target_level)
                if eye_level is not None:
                    self.target_eye_level = eye_level
                return True

            # Instant update (existing logic)
            pending_update = {}
            if eye_level is not None:
                pending_update['eyeLevel'] = eye_level
            if target_level is not None:
                pending_update['targetLevel'] = target_level
            if not pending_update:
                return False
            payload = camera_commands.build_camera_payload(pending_update, app)
            camera_commands.apply_camera_state(payload, app, apply_mode="ui")
            if eye_level is not None:
                self.target_eye_level = eye_level
            return True
        except Exception:
            return False

    def disable_eye_level_lock(self):
        """
        Disable eye level lock and clear state.
        """
        eye_level_utils.set_eye_level_lock_state(False, 0.0)
        self.lock_enabled = False
        self.target_eye_level = 0.0
        self.stop_passive_eye_level_lock()

    # =========================
    # PASSIVE LOCK (EVENT-DRIVEN)
    # =========================

    def start_passive_eye_level_lock(self):
        """
        Attach cameraChanged event for passive correction.
        """
        try:
            self._detach_camera_event()
            self._camera_event_handler = PassiveEyeLevelCameraHandler(self)
            self._camera_event = app.cameraChanged
            self._camera_event.add(self._camera_event_handler)
        except Exception:
            pass

    def stop_passive_eye_level_lock(self):
        """
        Detach cameraChanged event.
        """
        self._detach_camera_event()

    def _detach_camera_event(self):
        if (
            hasattr(self, '_camera_event') and self._camera_event is not None and
            hasattr(self, '_camera_event_handler') and self._camera_event_handler is not None
        ):
            try:
                self._camera_event.remove(self._camera_event_handler)
            except Exception:
                pass
            self._camera_event = None
            self._camera_event_handler = None

    def _on_camera_changed(self, args):
        """
        Called on any camera change. Just update the timestamp and schedule correction.
        """
        self._last_camera_change = time.time()

    def check_and_apply_passive_correction(self):
        """
        Should be called periodically (e.g. from main loop or UI tick) to apply correction after navigation.
        """
        if not self.lock_enabled:
            return
        now = time.time()
        # Only correct if it's been >100ms since last camera change
        if now - self._last_camera_change >= 0.1:
            camera = app.activeViewport.camera
            current_eye_level = eye_level_utils.get_eye_level(camera)
            drift = abs(current_eye_level - self.target_eye_level)
            if drift > self.correction_tolerance:
                self.set_eye_and_target_level(eye_level=self.target_eye_level, target_level=self.target_eye_level)
            self._last_camera_change = now

    # =========================
    # OVERLAY/FEEDBACK
    # =========================

    def _update_eye_level_overlay(self, eye_level_value):
        """
        Update overlay (stub for integration).
        """
        try:
            from .overlay_controller import get_overlay_controller
            overlay_controller = get_overlay_controller()
            overlay_controller.current_eye_level_target = eye_level_value
        except Exception:
            pass

    # =========================
    # STATE/HELPERS
    # =========================

    def get_eye_level_lock_status(self):
        """
        Return current eye level lock status.
        """
        return {
            'enabled': self.lock_enabled,
            'target_level': self.target_eye_level
        }

    def is_eye_level_lock_active(self):
        """
        Return True if eye level lock is active.
        """
        return self.lock_enabled

    def get_current_eye_level(self):
        """
        Get the current eye level from the camera.
        """
        try:
            camera = app.activeViewport.camera
            return eye_level_utils.get_eye_level(camera)
        except Exception:
            return 0.0

# =========================
# SINGLETON ACCESSOR
# =========================

_eye_level_controller_instance = None

def get_eye_level_controller():
    """
    Get the singleton EyeLevelController instance.
    """
    global _eye_level_controller_instance
    if _eye_level_controller_instance is None:
        _eye_level_controller_instance = EyeLevelController()
    return _eye_level_controller_instance