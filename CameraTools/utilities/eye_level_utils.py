"""
eye_level_utils.py
Core eye level utilities for CameraTools.

- No direct camera writes.
- Provides document-aware calculations and payload builders for eye/target level.
- All camera changes are applied by the controller via camera_commands.
- All math is performed in document-up space for consistency.
"""

import adsk
import adsk.fusion
import time

LOG_MODULE = 'eye_level_utils'

from ..utilities import log_utils
from ..utilities.camera_transforms import derive_document_up
from ..utilities import camera_telemetry

log_utils.set_module_logging(LOG_MODULE, False)  # Set True for debugging

app = adsk.core.Application.get()

# =========================
# EYE/TARGET LEVEL PAYLOAD BUILDERS
# =========================

def build_eye_level_payload(target_eye_level, app):
    """
    Build a pending_update dict for the desired eye level.
    Used by controllers to request a change in eye level.
    """
    return {'eyeLevel': target_eye_level}

def build_target_level_payload(target_level, app):
    """
    Build a pending_update dict for the desired target doc-up level.
    Used by controllers to request a change in target level.
    """
    return {'targetLevel': target_level}

def build_eye_and_target_level_payload(eye_level, target_level, app):
    """
    Build a pending_update dict for both eye and target doc-up levels.
    Used by controllers to request simultaneous changes.
    """
    return {'eyeLevel': eye_level, 'targetLevel': target_level}

# =========================
# EYE LEVEL READERS
# =========================

def get_eye_level(camera=None):
    """
    Get current eye level (doc-up projection) for the given camera or active camera.
    Projects the camera's eye point onto the document up vector.
    """
    try:
        if camera is None:
            camera = app.activeViewport.camera
        design = app.activeProduct
        if design is None:
            log_utils.log(app, "❌ No active design/product. get_eye_level aborted.", level='ERROR', module=LOG_MODULE)
            return 0.0
        up_vector = derive_document_up(design)
        # Project eye point onto up vector (dot product)
        return camera.eye.asVector().dotProduct(up_vector)
    except Exception as e:
        log_utils.log(app, f"❌ Exception in get_eye_level: {str(e)}", level='ERROR', module=LOG_MODULE)
        return 0.0

def get_target_level(camera=None):
    """
    Get current target level (doc-up projection) for the given camera or active camera.
    Projects the camera's target point onto the document up vector.
    """
    try:
        if camera is None:
            camera = app.activeViewport.camera
        design = app.activeProduct
        if design is None:
            log_utils.log(app, "❌ No active design/product. get_target_level aborted.", level='ERROR', module=LOG_MODULE)
            return 0.0
        up_vector = derive_document_up(design)
        # Project target point onto up vector (dot product)
        return camera.target.asVector().dotProduct(up_vector)
    except Exception as e:
        log_utils.log(app, f"❌ Exception in get_target_level: {str(e)}", level='ERROR', module=LOG_MODULE)
        return 0.0

# =========================
# EYE LEVEL LOCK STATE MANAGEMENT (Preferences only)
# =========================

def get_eye_level_lock_status():
    """
    Get eye level lock status and target from preferences.
    Returns a dict: {'enabled': bool, 'target_level': float}
    """
    try:
        from . import prefs_utils
        prefs = prefs_utils.load_prefs() or {}
        enabled = prefs.get('eyeLevelLocked', False)
        target = prefs.get('eyeLevelTarget', 0.0)
        return {'enabled': enabled, 'target_level': target}
    except Exception:
        return {'enabled': False, 'target_level': 0.0}

def set_eye_level_lock_state(enabled, target_level_cm=0.0):
    """
    Set eye level lock state and persist to preferences.
    """
    try:
        from . import prefs_utils
        preferences = prefs_utils.load_prefs() or {}
        preferences["eyeLevelLocked"] = bool(enabled)
        preferences["eyeLevelTarget"] = float(target_level_cm)
        prefs_utils.save_prefs(preferences)
        return True
    except Exception:
        return False

def is_eye_level_lock_active():
    """
    Check if eye level lock is currently active.
    """
    return get_eye_level_lock_status().get('enabled', False)

def get_eye_level_lock_target():
    """
    Get the current eye level lock target.
    """
    return get_eye_level_lock_status().get('target_level', 0.0)

def disable_eye_level_lock():
    """
    Disable eye level lock and clear target.
    """
    return set_eye_level_lock_state(False, 0.0)

def enable_eye_level_lock(target_level_cm):
    """
    Enable eye level lock with specified target level.
    """
    return set_eye_level_lock_state(True, target_level_cm)

# =========================
# ANIMATION UTILITIES
# =========================

def easeInOutSine(t):
    """
    Easing function for smooth animation (sine curve).
    """
    import math
    return -(math.cos(math.pi * t) - 1) / 2

def easeInOutCubic(t):
    """
    Easing function for smooth animation (cubic curve).
    """
    t *= 2
    if t < 1:
        return t * t * t / 2
    else:
        t -= 2
        return (t * t * t + 2) / 2

def animate_eye_and_target_level(eye_level, target_level, duration=0.1, fps=30, palette=None, camera_calculations=None, camera_transforms=None):
    """
    Animate the camera's eye and target points to the specified levels over a given duration.
    Uses cubic easing for smooth transitions.
    Updates the camera and sends telemetry to the UI palette at each step.
    """
    if camera_transforms is None:
        from ..utilities import camera_transforms

    camera = app.activeViewport.camera
    design = app.activeProduct
    if design is None:
        log_utils.log(app, "❌ No active design/product. Animation aborted.", level='ERROR', module=LOG_MODULE)
        return False
    up_vector = derive_document_up(design)
    start_eye = camera.eye.asVector()
    start_target = camera.target.asVector()
    start_eye_level = start_eye.dotProduct(up_vector)
    start_target_level = start_target.dotProduct(up_vector)
    eye_delta = eye_level - start_eye_level
    target_delta = target_level - start_target_level
    steps = max(1, int(duration * fps / 1000))
    interval = duration / steps

    for i in range(steps):
        t = (i + 1) / steps
        eased_t = easeInOutCubic(t)
        # Interpolate eye and target levels
        new_eye_level = start_eye_level + eye_delta * eased_t
        new_target_level = start_target_level + target_delta * eased_t

        # Move eye along up vector
        eye_offset = up_vector.copy()
        eye_offset.scaleBy(new_eye_level - start_eye_level)
        new_eye = start_eye.copy()
        new_eye.x += eye_offset.x
        new_eye.y += eye_offset.y
        new_eye.z += eye_offset.z

        # Move target along up vector
        target_offset = up_vector.copy()
        target_offset.scaleBy(new_target_level - start_target_level)
        new_target = start_target.copy()
        new_target.x += target_offset.x
        new_target.y += target_offset.y
        new_target.z += target_offset.z

        # Update camera
        camera.eye = adsk.core.Point3D.create(new_eye.x, new_eye.y, new_eye.z)
        camera.target = adsk.core.Point3D.create(new_target.x, new_target.y, new_target.z)
        app.activeViewport.camera = camera
        app.activeViewport.refresh()
        adsk.doEvents()
        
        # Send full camera state to UI with real objects
        camera_telemetry.send_camera_state_to_ui(
            palette, app, adsk, camera_calculations, camera_transforms
        )
    
        time.sleep(interval)

# =========================
# VALIDATION
# =========================

def validate_eye_level_range(eye_level_cm):
    """
    Validate that eye level is within reasonable bounds for the model.
    Checks against the model's bounding box height.
    """
    try:
        design = app.activeProduct
        if isinstance(design, adsk.fusion.Design):
            root_comp = design.rootComponent
            bounding_box = root_comp.boundingBox
            model_height = abs(bounding_box.maxPoint.z - bounding_box.minPoint.z)
            model_center_z = (bounding_box.maxPoint.z + bounding_box.minPoint.z) / 2
            min_eye_level = model_center_z - model_height
            max_eye_level = model_center_z + model_height
            return min_eye_level <= eye_level_cm <= max_eye_level
        else:
            # Fallback for no design context
            return -10000 <= eye_level_cm <= 10000
    except Exception:
        return True