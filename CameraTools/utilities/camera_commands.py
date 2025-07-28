"""
CameraCommands Utility

Role: All camera math, transforms, and direct Fusion API calls.
Receives property changes or full camera states, builds payloads, applies to Fusion camera.
Handles all conversions between UI property changes and Fusion's camera API.

NOTE: Fusion's camera API has quirks—certain property changes (like FOV or camera type) can cause the camera to reframe or animate unexpectedly.
To avoid these issues, we use multi-step assignments and explicit value restoration in several places.
"""

import adsk
import math
import time
import traceback

LOG_MODULE = 'camera_commands'

from ..utilities import log_utils
log_utils.set_module_logging(LOG_MODULE, False)  # Set True for debugging
from ..utilities import camera_calculations, camera_transforms

# --- PAYLOAD BUILDERS ---

def build_camera_payload(pending_update, app):
    """
    Builds a camera payload from pending updates and current camera state.
    This function collects all camera properties, applies math transforms, and returns a dict
    suitable for direct application to the Fusion camera.

    NOTE: If explicit eye/target/upVector are present in pending_update (e.g. for eye lock + FOV change),
    those are used directly. Otherwise, spherical math is used to calculate new positions.
    """
    viewport = app.activeViewport
    camera = viewport.camera
    design = app.activeProduct
    if design is None:
        log_utils.log(app, "❌ No active design/product. Camera payload aborted.", level='ERROR', module=LOG_MODULE)
        return None

    # Get canonical transforms for document up
    doc_up = camera_transforms.derive_document_up(design)
    to_canonical = camera_transforms.get_to_canonical_matrix(doc_up, adsk)
    from_canonical = camera_transforms.get_from_canonical_matrix(doc_up, adsk)
    target = camera.target

    # --- Extract or calculate all camera properties ---
    azimuth = pending_update.get('azimuth', camera_calculations.get_azimuth(camera, lambda v: camera_transforms.transform_vector(v, to_canonical, adsk)))
    inclination = pending_update.get('inclination', camera_calculations.get_inclination(camera, lambda v: camera_transforms.transform_vector(v, to_canonical, adsk)))
    distance = pending_update.get('distance', camera_calculations.get_distance_from_camera(camera))
    fov = pending_update.get('fov', math.degrees(camera.perspectiveAngle))
    camera_type = pending_update.get('cameraType', camera.cameraType)

    # --- Calculate new eye position from spherical angles ---
    # If explicit eye/target/upVector are present, use them (for eye lock scenarios)
    if 'eye' in pending_update:
        new_eye = adsk.core.Point3D.create(**pending_update['eye'])
    else:
        new_eye = camera_calculations.new_eye_from_angles(
            target, azimuth, inclination, distance,
            lambda v: camera_transforms.transform_vector(v, from_canonical, adsk), adsk
        )
        if 'eyeLevel' in pending_update:
            new_eye = camera_calculations.apply_eye_level(new_eye, doc_up, pending_update['eyeLevel'])

    if 'target' in pending_update:
        new_target = adsk.core.Point3D.create(**pending_update['target'])
    else:
        new_target = target
        if 'targetLevel' in pending_update:
            new_target = camera_calculations.apply_target_level(target, doc_up, pending_update['targetLevel'])

    if 'upVector' in pending_update:
        up_vec = adsk.core.Vector3D.create(**pending_update['upVector'])
    else:
        up_vec = doc_up

    # --- Apply dolly, pan, tilt if present ---
    # These are absolute, so use set_* functions and pass doc_up as needed
    if 'dolly' in pending_update:
        new_eye, new_target = camera_calculations.set_dolly(camera, pending_update['dolly'], min_distance=1.0, app=app)
    if 'pan' in pending_update:
        new_eye, new_target = camera_calculations.set_pan(camera, pending_update['pan'], app=app)
    if 'tilt' in pending_update:
        new_eye, new_target = camera_calculations.set_tilt(camera, pending_update['tilt'], app=app)

    # --- Build the payload dict for Fusion camera assignment ---
    payload = {
        'eye': {'x': new_eye.x, 'y': new_eye.y, 'z': new_eye.z},
        'target': {'x': new_target.x, 'y': new_target.y, 'z': new_target.z},
        'upVector': {'x': up_vec.x, 'y': up_vec.y, 'z': up_vec.z},
        'perspectiveAngle': math.radians(fov),
        'cameraType': camera_type,
        'isFitView': False,
        'isSmoothTransition': False,
    }
    return payload

def build_camera_payload_from_canonical(camera_data, app):
    """
    Builds a camera payload from canonical camera data (for paste).
    Converts canonical coordinates to document coordinates using transforms.
    Used for copy/paste and named view recall.
    """
    design = app.activeProduct
    if design is None:
        log_utils.log(app, "❌ No active design/product. Camera payload aborted.", level='ERROR', module=LOG_MODULE)
        return None
    doc_up = camera_transforms.derive_document_up(design)
    eye_doc = camera_transforms.from_canon_point(adsk.core.Point3D.create(**camera_data['eye']), doc_up, adsk)
    target_doc = camera_transforms.from_canon_point(adsk.core.Point3D.create(**camera_data['target']), doc_up, adsk)
    up_doc = camera_transforms.from_canon_vector(adsk.core.Vector3D.create(**camera_data['upVector']), doc_up, adsk)
    payload = {
        'eye': {'x': eye_doc.x, 'y': eye_doc.y, 'z': eye_doc.z},
        'target': {'x': target_doc.x, 'y': target_doc.y, 'z': target_doc.z},
        'upVector': {'x': up_doc.x, 'y': up_doc.y, 'z': up_doc.z},
        'perspectiveAngle': camera_data['perspectiveAngle'],
        'cameraType': camera_data['cameraType'],
        'isFitView': False,
        'isSmoothTransition': False,
    }
    return payload

# --- CAMERA APPLICATIONS ---

def apply_camera_state(payload, app, apply_mode="direct"):
    """
    Apply camera state from a payload.

    - 'direct': two-step assignment for Fusion quirks (copy/paste, named view recall)
      Used when restoring a saved camera state or switching named views.
      This avoids Fusion's tendency to reframe or animate unexpectedly when FOV/type changes.
    - 'ui': single-step assignment for streaming/interactive UI
      Used for live UI changes (sliders, input fields).

    NOTE: For FOV/FL changes with eye lock, we use a two-step assignment even in UI mode:
      1. Set FOV/cameraType first (which may cause Fusion to reframe).
      2. Immediately restore eye/target/upVector to keep the camera fixed.
      This prevents unwanted camera jumps or animations.
    """
    viewport = app.activeViewport
    camera = viewport.camera

    # If camera type is changing, sanitize first to avoid Fusion quirks
    # (Fusion can get "stuck" if switching between ortho/persp without clearing extents)
    if 'cameraType' in payload and payload['cameraType'] != camera.cameraType:
        sanitize_camera_for_type_change(
            camera, viewport, app, adsk,
            target_camera_type=payload['cameraType']
        )

    def to_point3d(val):
        return adsk.core.Point3D.create(**val) if isinstance(val, dict) else val

    def to_vector3d(val):
        return adsk.core.Vector3D.create(**val) if isinstance(val, dict) else val

    if apply_mode == "direct":
        # --- Two-step apply for Fusion quirks ---
        # Step 1: Set FOV and camera type, then assign camera
        # This avoids Fusion's auto-reframing when FOV/type changes
        camera.perspectiveAngle = float(payload['perspectiveAngle'])
        camera.cameraType = int(payload['cameraType'])
        camera.isFitView = False
        camera.isSmoothTransition = False
        viewport.camera = camera

        # Step 2: Set eye, target, upVector, then assign again
        # This restores the desired camera position after FOV/type change
        camera = viewport.camera
        camera.eye = to_point3d(payload['eye'])
        camera.target = to_point3d(payload['target'])
        camera.upVector = to_vector3d(payload['upVector'])
        camera.isFitView = False
        camera.isSmoothTransition = False
        viewport.camera = camera
        viewport.refresh()

        # For orthographic, always fit view after assignment
        if viewport.camera.cameraType == adsk.core.CameraTypes.OrthographicCameraType:
            app.activeViewport.fit()

    else:
        # --- Single-step apply for UI/streaming ---
        # For most UI changes, a single assignment is sufficient.
        # However, for FOV/FL changes with eye lock, Fusion may reframe the camera.
        # To prevent this, we use a two-step assignment (similar to 'direct' mode).
        from ..utilities import eye_level_utils
        eye_lock_active = eye_level_utils.is_eye_level_lock_active()
        fov_or_fl_changing = 'perspectiveAngle' in payload or 'fov' in payload or 'focalLength' in payload
        if eye_lock_active and fov_or_fl_changing:
            # Step 1: Set FOV and camera type
            cached_eye = to_point3d(payload['eye']) if 'eye' in payload else camera.eye
            cached_target = to_point3d(payload['target']) if 'target' in payload else camera.target
            cached_up = to_vector3d(payload['upVector']) if 'upVector' in payload else camera.upVector

            camera.perspectiveAngle = float(payload['perspectiveAngle'])
            camera.cameraType = int(payload['cameraType'])
            camera.isFitView = False
            camera.isSmoothTransition = False
            viewport.camera = camera

            # Step 2: Restore eye/target/upVector
            camera = viewport.camera
            camera.eye = cached_eye
            camera.target = cached_target
            camera.upVector = cached_up
            camera.isFitView = False
            camera.isSmoothTransition = False
            viewport.camera = camera

            # Only refresh once, after both steps
            viewport.refresh()
        else:
            # --- Standard single-step ---
            # For all other UI changes, assign all properties at once
            if 'perspectiveAngle' in payload:
                camera.perspectiveAngle = float(payload['perspectiveAngle'])
            if 'cameraType' in payload:
                camera.cameraType = int(payload['cameraType'])
            if 'isFitView' in payload:
                camera.isFitView = False
            if 'isSmoothTransition' in payload:
                camera.isSmoothTransition = False
            if 'eye' in payload:
                camera.eye = to_point3d(payload['eye'])
            if 'target' in payload:
                camera.target = to_point3d(payload['target'])
            if 'upVector' in payload:
                camera.upVector = to_vector3d(payload['upVector'])
            viewport.camera = camera
            viewport.refresh()

def apply_named_view_camera(named_view, app):
    """
    Directly applies the camera from a named view to the active viewport,
    with sanitization and two-step assignment for FOV/type quirks.

    NOTE: Named views may have different camera types or FOVs than the current view.
    To avoid Fusion's auto-reframing, we sanitize the camera type first,
    then apply the named view's camera properties in two steps.
    """
    viewport = app.activeViewport
    current_camera = viewport.camera
    target_camera = named_view.camera

    # Sanitize if switching camera type
    if target_camera.cameraType != current_camera.cameraType:
        sanitize_camera_for_type_change(
            current_camera, viewport, app, adsk,
            target_camera_type=target_camera.cameraType,
            target_perspective_angle=target_camera.perspectiveAngle,
            target_is_fit_view=target_camera.isFitView
        )

    # --- Two-step apply for Fusion quirks ---
    # Step 1: Set FOV and camera type
    camera = viewport.camera
    camera.perspectiveAngle = target_camera.perspectiveAngle
    camera.cameraType = target_camera.cameraType
    camera.isFitView = False
    camera.isSmoothTransition = False
    viewport.camera = camera

    # Step 2: Set eye, target, upVector
    camera = viewport.camera
    camera.eye = target_camera.eye
    camera.target = target_camera.target
    camera.upVector = target_camera.upVector
    camera.isFitView = False
    camera.isSmoothTransition = False
    viewport.camera = camera
    viewport.refresh()
    
    # For orthographic, always fit view after assignment
    if viewport.camera.cameraType == adsk.core.CameraTypes.OrthographicCameraType:
        app.activeViewport.fit()

def apply_fusion_default_lens(app):
    """
    Applies Fusion's default lens settings to the camera.
    Used to reset the camera to a known default state.
    """
    viewport = app.activeViewport
    camera = viewport.camera
    camera.perspectiveAngle = math.radians(22.62)
    camera.isFitView = False
    camera.isSmoothTransition = False
    viewport.camera = camera
    viewport.refresh()

def restore_camera_state(state, app):
    """
    Restores camera state from a payload.
    Handles camera type changes and applies all camera properties.

    NOTE: Uses two-step assignment to avoid Fusion quirks when restoring saved states.
    """
    viewport = app.activeViewport
    camera = viewport.camera

    # Sanitize if camera type is changing
    if state['cameraType'] != camera.cameraType:
        sanitize_camera_for_type_change(
            camera, viewport, app, adsk,
            target_camera_type=state['cameraType'],
            target_perspective_angle=state['perspectiveAngle'],
            target_is_fit_view=state.get('isFitView', False)
        )

    # Two-step apply for Fusion quirks
    camera = viewport.camera
    camera.perspectiveAngle = state['perspectiveAngle']
    camera.cameraType = state['cameraType']
    camera.isFitView = state.get('isFitView', False)
    camera.isSmoothTransition = state.get('isSmoothTransition', False)
    viewport.camera = camera

    camera = viewport.camera
    camera.eye = adsk.core.Point3D.create(*state['eye'])
    camera.target = adsk.core.Point3D.create(*state['target'])
    camera.upVector = adsk.core.Vector3D.create(*state['upVector'])
    camera.isFitView = state.get('isFitView', False)
    camera.isSmoothTransition = state.get('isSmoothTransition', False)
    viewport.camera = camera
    viewport.refresh()

def get_distance_bounds(app, multiplier=4.0):
    """
    Returns min/max camera distance bounds for the current design.
    Used for UI sliders and camera constraints.
    """
    from ..utilities import camera_calculations
    design = app.activeProduct
    return camera_calculations.distance_bounds_from_design(design, distance_multiplier=multiplier, app=app)

def sanitize_camera_for_type_change(camera, viewport, app, adsk, target_camera_type=None, target_perspective_angle=None, target_is_fit_view=False, palette=None):
    """
    Ensures the camera is in a valid state for type change (e.g., clears extents for ortho/persp switch) and updates UI.

    Fusion's camera API can get "stuck" or behave unpredictably when switching between orthographic and perspective views.
    To avoid this, we always:
      1. Set to perspective and fit view to clear extents.
      2. Switch to the target camera type and apply perspective angle if provided.
      3. Optionally update the UI with the new camera mode.

    This sequence ensures a clean transition and prevents unwanted reframing or extents issues.
    """
    try:
        # Step 1: Set to perspective and fit view to clear extents
        camera.cameraType = adsk.core.CameraTypes.PerspectiveCameraType
        camera.isFitView = True
        camera.isSmoothTransition = False
        viewport.camera = camera
        viewport.refresh()
        time.sleep(0.01)
        # Step 2: Switch to target camera type and apply perspective angle if provided
        if target_camera_type is not None:
            fresh_camera = viewport.camera
            fresh_camera.cameraType = int(target_camera_type)
            if target_perspective_angle is not None:
                fresh_camera.perspectiveAngle = float(target_perspective_angle)
            # Always enforce fitView True for ortho
            fresh_camera.isFitView = True if int(target_camera_type) == adsk.core.CameraTypes.OrthographicCameraType else False
            fresh_camera.isSmoothTransition = False
            viewport.camera = fresh_camera
            viewport.refresh()
            # Optionally update UI with new camera mode
            if palette is not None:
                from ..utilities.view_utils import _send_camera_mode_update
                _send_camera_mode_update(palette, fresh_camera.cameraType)
        return True
    except Exception as e:
        log_utils.log(app, f'❌ Failed to sanitize camera for type change: {str(e)}', level='ERROR', module=LOG_MODULE)
        return False