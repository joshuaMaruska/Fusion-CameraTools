"""
CameraTelemetry Utility
Role: Reads raw camera data from the viewport, transforms to canonical, serializes, and sends to UI.
Calls camera_calculations and camera_transforms as needed.
No write/update logic.
"""

import json
import math

LOG_MODULE = 'camera_telemetry'

from ..utilities import log_utils
from ..utilities import eye_level_utils
log_utils.set_module_logging(LOG_MODULE, False)  # Set True for debugging

def gather_camera_state(app, adsk, camera_calculations=None, camera_transforms=None, min_distance=None, max_distance=None):
    """
    Reads the current camera state from Fusion, transforms to canonical coordinates,
    computes all derived properties, and returns a dict suitable for UI serialization.
    """
    # Import utilities if not provided
    if camera_calculations is None:
        from ..utilities import camera_calculations
    if camera_transforms is None:
        from ..utilities import camera_transforms

    viewport = app.activeViewport
    camera = viewport.camera
    design = app.activeProduct

    # Extract raw camera properties
    eye = camera.eye
    target = camera.target
    up = camera.upVector

    # If no design context, abort telemetry
    if design is None:
        log_utils.log(app, "❌ No active design/product. Telemetry aborted.", level='ERROR', module=LOG_MODULE)
        return {}

    # Get canonical transforms for document up
    doc_up = camera_transforms.derive_document_up(design)
    to_canonical = camera_transforms.get_to_canonical_matrix(doc_up, adsk)

    # Transform eye, target, upVector to canonical space
    eye_canon = camera_transforms.transform_point(eye, to_canonical, adsk)
    target_canon = camera_transforms.transform_point(target, to_canonical, adsk)
    up_canon = camera_transforms.transform_vector(up, to_canonical, adsk)

    # Compute derived camera properties in canonical space
    # Azimuth: horizontal angle in XZ plane
    azimuth = camera_calculations.get_azimuth(camera, lambda v: camera_transforms.transform_vector(v, to_canonical, adsk))
    # Inclination: vertical angle above/below XZ plane
    inclination = camera_calculations.get_inclination(camera, lambda v: camera_transforms.transform_vector(v, to_canonical, adsk))
    # Distance: Euclidean distance from eye to target
    distance = eye.distanceTo(target)
    # FOV: field of view in degrees
    fov = math.degrees(camera.perspectiveAngle)
    # Dolly: horizontal distance in document up plane
    dolly = camera_calculations.get_dolly(camera, doc_up)
    # Pan: horizontal rotation in canonical space
    pan = camera_calculations.get_pan(camera, lambda v: camera_transforms.transform_vector(v, to_canonical, adsk))
    # Tilt: vertical rotation in canonical space
    tilt = camera_calculations.get_tilt(camera, lambda v: camera_transforms.transform_vector(v, to_canonical, adsk))

    # Log all computed values for debugging (disabled for production)
    log_utils.log(app, f"Camera state PREPAYLOAD: azimuth={azimuth}, inclination={inclination}, distance={distance}, fov={fov}, dolly={dolly}, pan={pan}, tilt={tilt}", level='DEBUG', module=LOG_MODULE)

    # Build payload for UI
    payload_ui = {
        'cameraType': camera.cameraType,
        'eye': {'x': eye.x, 'y': eye.y, 'z': eye.z},
        "eyeLevel": eye_level_utils.get_eye_level(camera),
        'target': {'x': target.x, 'y': target.y, 'z': target.z},
        'upVector': {'x': up.x, 'y': up.y, 'z': up.z},
        'eye_canonical': {'x': eye_canon.x, 'y': eye_canon.y, 'z': eye_canon.z},
        'target_canonical': {'x': target_canon.x, 'y': target_canon.y, 'z': target_canon.z},
        'upVector_canonical': {'x': up_canon.x, 'y': up_canon.y, 'z': up_canon.z},
        'azimuth': azimuth,
        'inclination': inclination,
        'distance': distance,
        'fov': fov,
        'minDistance': min_distance,
        'maxDistance': max_distance,
        'dolly': dolly,
        'pan': pan,
        'tilt': -tilt,
    }
    return payload_ui

def send_camera_state_to_ui(palette, app, adsk, camera_calculations=None, camera_transforms=None, min_distance=None, max_distance=None):
    """
    Gathers camera state and sends it to the UI palette using the UI controller.
    """
    info = gather_camera_state(app, adsk, camera_calculations, camera_transforms, min_distance, max_distance)
    from ..controllers.ui_controller import get_ui_controller
    ui_controller = get_ui_controller()
    success = ui_controller.send_data_to_palette('updateCameraData', info)
    if not success:
        log_utils.log(app, '❌ Failed to send camera state: palette not visible or not available', level='ERROR', module=LOG_MODULE)