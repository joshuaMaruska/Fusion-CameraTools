"""
Camera geometry utilities for CameraTools.
Provides pure math functions for converting between camera eye/target/up and azimuth/inclination/distance/FOV.
No Fusion API calls except for reading camera properties.
All transforms are canonicalized to work with arbitrary document up directions.
"""

import math
import adsk
import adsk.fusion
import traceback

LOG_MODULE = 'camera_calculations'

from ..utilities import log_utils
log_utils.set_module_logging(LOG_MODULE, False)  # Set True for debugging

from ..utilities import camera_transforms

# =========================
# BASIC CAMERA MATH
# =========================

def get_distance_from_camera(camera):
    """Returns the Euclidean distance from the camera eye to the camera target."""
    # Simple 3D distance calculation
    return camera.eye.distanceTo(camera.target)

def get_azimuth(camera, transform_vector_func):
    """
    Calculate azimuth (horizontal angle) in canonical space.
    Azimuth is the angle in the XZ plane from the canonical +Z axis, CCW positive.
    """
    # Get vector from eye to target
    v = camera.eye.vectorTo(camera.target)
    v.normalize()
    # Transform to canonical space
    v = transform_vector_func(v)
    # Calculate angle in XZ plane
    azimuth = math.degrees(math.atan2(v.x, v.z))
    # Normalize to [-180, 180]
    azimuth = (azimuth + 360) % 360 - 180
    return round(azimuth, 2)

def get_inclination(camera, transform_vector_func):
    """
    Calculate inclination (vertical angle) in canonical space.
    Inclination is the angle above/below the canonical XZ plane.
    """
    # Get vector from eye to target
    v = camera.eye.vectorTo(camera.target)
    v.normalize()
    # Transform to canonical space
    v = transform_vector_func(v)
    # Calculate vertical angle (asin of Y component)
    return -round(math.degrees(math.asin(v.y)), 2)

# =========================
# CAMERA POSITION SETTERS
# =========================

def set_camera_eye_to_point(app, point):
    """
    Sets the camera eye to the given point, re-levels the up vector, and updates the viewport.
    Ensures eye and target are not coincident.
    """
    viewport = app.activeViewport
    camera = viewport.camera
    target = camera.target
    # Prevent degenerate camera
    if point.isEqualTo(target):
        app.userInterface.messageBox("Eye and target cannot be the same point.")
        return False
    # Set new eye position
    camera.eye = point

    # Get document up direction and normalize
    design = app.activeProduct if app else None
    doc_up = camera_transforms.derive_document_up(design)
    doc_up.normalize()

    # Calculate new view vector and up vector
    view_vec = camera.eye.vectorTo(camera.target)
    view_vec.normalize()
    camera.upVector = corrected_up_vector(view_vec, doc_up)
    # Apply camera update
    viewport.camera = camera
    return True

def set_camera_target_to_point(app, point):
    """
    Sets the camera target to the given point, re-levels the up vector, and updates the viewport.
    Ensures eye and target are not coincident.
    """
    viewport = app.activeViewport
    camera = viewport.camera
    eye = camera.eye
    # Prevent degenerate camera
    if point.isEqualTo(eye):
        app.userInterface.messageBox("Eye and target cannot be the same point.")
        return False
    # Set new target position
    camera.target = point

    # Get document up direction and normalize
    design = app.activeProduct if app else None
    doc_up = camera_transforms.derive_document_up(design)
    doc_up.normalize()

    # Calculate new view vector and up vector
    view_vec = camera.eye.vectorTo(camera.target)
    view_vec.normalize()
    camera.upVector = corrected_up_vector(view_vec, doc_up)
    # Apply camera update
    viewport.camera = camera
    return True

def corrected_up_vector(view_vec, doc_up):
    """
    Returns a normalized up vector that is perpendicular to view_vec and as close as possible to doc_up.
    Uses Gram-Schmidt orthogonalization to project doc_up onto the plane perpendicular to view_vec.
    This ensures the camera horizon remains level after eye/target moves.
    """
    # Copy doc_up for manipulation
    up_vec = doc_up.copy()
    # Project doc_up onto view_vec
    proj = view_vec.copy()
    proj.scaleBy(up_vec.dotProduct(view_vec))
    # Subtract projection to get perpendicular component
    up_vec.subtract(proj)
    # Normalize to unit vector
    up_vec.normalize()
    return up_vec

# =========================
# DOLLY (HORIZONTAL DISTANCE)
# =========================

def get_dolly(camera, doc_up):
    """
    Returns the horizontal distance from eye to target, projected onto the plane perpendicular to doc_up.
    This is the "dolly" distance, ignoring vertical displacement.
    """
    # Get vector from eye to target
    v = camera.eye.vectorTo(camera.target)
    up = doc_up.copy()
    up.normalize()
    # Project v onto up direction
    up_component = up.copy()
    up_component.scaleBy(v.dotProduct(up))
    # Subtract up component to get horizontal component
    v_proj = v.copy()
    v_proj.subtract(up_component)
    # Return length of horizontal component
    return v_proj.length

def get_dolly_from_points(eye, target, doc_up):
    """
    Returns the horizontal distance from eye to target, projected onto the plane perpendicular to doc_up.
    """
    # Get vector from eye to target
    v = eye.vectorTo(target)
    up = doc_up.copy()
    up.normalize()
    # Project v onto up direction
    up_component = up.copy()
    up_component.scaleBy(v.dotProduct(up))
    # Subtract up component to get horizontal component
    v_proj = v.copy()
    v_proj.subtract(up_component)
    # Return length of horizontal component
    return v_proj.length

def set_dolly(camera, horizontal_distance, min_distance=1e-6, app=None):
    """
    Moves the eye in the canonical (Y-up) horizontal (XZ) plane so that the horizontal (XZ) distance from eye to target
    is horizontal_distance, keeping the eye's canonical Y fixed and preserving the inclination (vertical/horizontal ratio).
    Returns new eye and target points.
    """
    try:
        # Get canonical transforms for document up
        design = app.activeProduct if app else None
        doc_up = camera_transforms.derive_document_up(design)
        to_canonical = camera_transforms.get_to_canonical_matrix(doc_up, adsk)
        from_canonical = camera_transforms.get_from_canonical_matrix(doc_up, adsk)

        # Transform eye and target to canonical space
        eye_canon = camera_transforms.transform_point(camera.eye, to_canonical, adsk)
        target_canon = camera_transforms.transform_point(camera.target, to_canonical, adsk)

        # Compute vector from eye to target in canonical space
        v = eye_canon.vectorTo(target_canon)
        v_len = v.length

        # Project onto XZ plane (horizontal)
        horiz = adsk.core.Vector3D.create(v.x, 0, v.z)
        horiz_len = horiz.length
        # If horizontal length is too small, use default direction
        if horiz_len < min_distance:
            horiz = adsk.core.Vector3D.create(1, 0, 0)
            horiz_len = 1.0
        horiz.normalize()

        # Move eye horizontally to achieve desired dolly distance
        new_eye_x = target_canon.x - horiz.x * horizontal_distance
        new_eye_z = target_canon.z - horiz.z * horizontal_distance
        new_eye_y = eye_canon.y  # Preserve Y

        new_eye_canon = adsk.core.Point3D.create(new_eye_x, new_eye_y, new_eye_z)

        # Preserve inclination (vertical/horizontal ratio)
        dy = target_canon.y - eye_canon.y
        inclination = math.atan2(dy, horiz_len)
        new_dy = math.tan(inclination) * horizontal_distance
        new_target_y = new_eye_y + new_dy
        new_target_canon = adsk.core.Point3D.create(target_canon.x, new_target_y, target_canon.z)

        # Transform back to document space
        new_eye = camera_transforms.transform_point(new_eye_canon, from_canonical, adsk)
        new_target = camera_transforms.transform_point(new_target_canon, from_canonical, adsk)

        return new_eye, new_target

    except Exception as e:
        if app:
            log_utils.log(app, f"[DOLLY-CANONICAL-SKATE] Exception: {str(e)}", level='ERROR', module=LOG_MODULE)
        raise

# =========================
# PAN (HORIZONTAL ROTATION)
# =========================

def get_pan(camera, transform_vector_func):
    """Returns the azimuth angle (horizontal rotation) in canonical space."""
    return get_azimuth(camera, transform_vector_func)

def set_pan(camera, pan_angle_deg, app=None):
    """
    Rotates the target about the eye in the canonical horizontal (XZ) plane by pan_angle_deg.
    Eye remains fixed. Target's canonical Y (height) is preserved.
    Pan is positive CCW when looking down canonical Y (doc-up).
    Returns new eye and target points.
    """
    try:
        # Get canonical transforms for document up
        design = app.activeProduct if app else None
        doc_up = camera_transforms.derive_document_up(design)
        to_canonical = camera_transforms.get_to_canonical_matrix(doc_up, adsk)
        from_canonical = camera_transforms.get_from_canonical_matrix(doc_up, adsk)

        # Transform eye and target to canonical space
        eye_canon = camera_transforms.transform_point(camera.eye, to_canonical, adsk)
        target_canon = camera_transforms.transform_point(camera.target, to_canonical, adsk)

        # Compute vector from eye to target in canonical space
        v = eye_canon.vectorTo(target_canon)
        horiz_x = v.x
        horiz_z = v.z
        radius = math.hypot(horiz_x, horiz_z)  # Distance in XZ plane

        # If radius is too small, use default direction
        min_distance = 1e-6
        if radius < min_distance:
            radius = 1.0
            horiz_x = 1.0
            horiz_z = 0.0

        # Calculate new target position with fixed radius and pan angle
        pan_angle_rad = math.radians(pan_angle_deg + 180)
        new_target_x = eye_canon.x + math.sin(pan_angle_rad) * radius
        new_target_z = eye_canon.z + math.cos(pan_angle_rad) * radius

        # Target's Y (height) is preserved
        new_target_canon = adsk.core.Point3D.create(
            new_target_x,
            target_canon.y,
            new_target_z
        )

        # Transform new target back to document space
        new_target = camera_transforms.transform_point(new_target_canon, from_canonical, adsk)
        new_eye = camera.eye  # eye does not move

        return new_eye, new_target

    except Exception as e:
        if app:
            log_utils.log(app, f"[PAN-CANONICAL] Exception: {str(e)}", level='ERROR', module=LOG_MODULE)
        raise

# =========================
# TILT (VERTICAL ROTATION)
# =========================

def get_tilt(camera, transform_vector_func):
    """Returns the inclination angle (vertical rotation) in canonical space."""
    return get_inclination(camera, transform_vector_func)

def set_tilt(camera, tilt_angle_deg, app=None):
    """
    Sets the camera's tilt (vertical angle) relative to world horizontal (document up).
    Keeps azimuth fixed, rotates view vector up/down.
    Uses canonical transforms to work in any document up orientation.
    Returns new eye and target points.
    """
    try:
        # Clamp tilt to avoid gimbal lock
        tilt_angle_deg = max(min(tilt_angle_deg, 89.999), -89.999)

        # Get canonical transforms for document up
        design = app.activeProduct if app else None
        doc_up = camera_transforms.derive_document_up(design)
        to_canonical = camera_transforms.get_to_canonical_matrix(doc_up, adsk)
        from_canonical = camera_transforms.get_from_canonical_matrix(doc_up, adsk)

        # Transform eye and target to canonical space
        eye_canon = camera_transforms.transform_point(camera.eye, to_canonical, adsk)
        target_canon = camera_transforms.transform_point(camera.target, to_canonical, adsk)

        # Calculate current azimuth in canonical space
        v = eye_canon.vectorTo(target_canon)
        v.normalize()
        azimuth = math.degrees(math.atan2(v.x, v.z))

        # Use the same distance between eye and target
        distance = eye_canon.distanceTo(target_canon)

        # Calculate new target position with fixed azimuth and new tilt (in canonical)
        tilt_rad = math.radians(tilt_angle_deg)
        azimuth_rad = math.radians(azimuth)
        # Spherical to Cartesian conversion for new direction vector
        new_v = adsk.core.Vector3D.create(
            math.cos(tilt_rad) * math.sin(azimuth_rad),  # X component
            math.sin(tilt_rad),                          # Y component (vertical)
            math.cos(tilt_rad) * math.cos(azimuth_rad)   # Z component
        )
        # Scale direction vector by distance and add to eye position
        new_target_canon = adsk.core.Point3D.create(
            eye_canon.x + new_v.x * distance,
            eye_canon.y + new_v.y * distance,
            eye_canon.z + new_v.z * distance
        )

        # Transform new target back to document space
        new_target = camera_transforms.transform_point(new_target_canon, from_canonical, adsk)
        new_eye = camera.eye  # eye does not move

        return new_eye, new_target

    except Exception as e:
        if app:
            log_utils.log(app, f"[TILT-WORLD] Exception: {str(e)}", level='ERROR', module=LOG_MODULE)
        raise

# =========================
# EYE/TARGET LEVEL OPERATIONS
# =========================

def apply_eye_level(new_eye, up_vec, eye_level):
    """
    Moves the eye point along the up vector to achieve the specified eye_level.
    Returns a new Point3D.
    """
    # Convert eye point to vector
    eye_vec = new_eye.asVector()
    # Project onto up vector to get current level
    current_eye_level = eye_vec.dotProduct(up_vec)
    # Calculate offset needed to reach desired level
    delta = eye_level - current_eye_level
    up_offset = up_vec.copy()
    up_offset.scaleBy(delta)
    # Apply offset to eye vector
    eye_vec = adsk.core.Vector3D.create(
        eye_vec.x + up_offset.x,
        eye_vec.y + up_offset.y,
        eye_vec.z + up_offset.z
    )
    # Convert back to point
    return adsk.core.Point3D.create(eye_vec.x, eye_vec.y, eye_vec.z)

def apply_target_level(target, up_vec, target_level):
    """
    Moves the target point along the up vector to achieve the specified target_level.
    Returns a new Point3D.
    """
    # Convert target point to vector
    target_vec = target.asVector()
    # Project onto up vector to get current level
    current_target_level = target_vec.dotProduct(up_vec)
    # Calculate offset needed to reach desired level
    delta = target_level - current_target_level
    up_offset = up_vec.copy()
    up_offset.scaleBy(delta)
    # Apply offset to target vector
    target_vec = adsk.core.Vector3D.create(
        target_vec.x + up_offset.x,
        target_vec.y + up_offset.y,
        target_vec.z + up_offset.z
    )
    # Convert back to point
    return adsk.core.Point3D.create(target_vec.x, target_vec.y, target_vec.z)

def new_eye_from_angles(target, azimuth, inclination, distance, from_canonical, adsk):
    """
    Calculate new eye position given target, azimuth, inclination, and distance.
    Converts spherical coordinates to Cartesian, then transforms from canonical space.
    """
    # Clamp inclination to avoid gimbal lock
    inclination = max(min(inclination, 89.999), -89.999)
    # Convert angles to radians
    az = math.radians(azimuth)
    inc = math.radians(inclination)
    # Spherical to Cartesian conversion for direction vector
    dir_vec = adsk.core.Vector3D.create(
        math.cos(inc) * math.sin(az),  # X component
        math.sin(inc),                 # Y component (vertical)
        math.cos(inc) * math.cos(az)   # Z component
    )
    # Transform direction vector from canonical to document space
    dir_vec = from_canonical(dir_vec)
    # Calculate new eye position by offsetting from target
    return adsk.core.Point3D.create(
        target.x + dir_vec.x * distance,
        target.y + dir_vec.y * distance,
        target.z + dir_vec.z * distance
    )

# =========================
# FOV/FOCAL LENGTH CONVERSIONS
# =========================

def fov_to_focal_length(fov_deg, sensor_width=36.0):
    """
    Convert field of view (degrees) to focal length (mm) for a given sensor width.
    Uses standard lens formula for 35mm photography.
    """
    # f = sensor_width / (2 * tan(FOV/2))
    return sensor_width / (2 * math.tan(math.radians(fov_deg) / 2))

def focal_length_to_fov(focal_length, sensor_width=36.0):
    """
    Convert focal length (mm) to field of view (degrees) for a given sensor width.
    Uses standard lens formula for 35mm photography.
    """
    # FOV = 2 * atan(sensor_width / (2 * f))
    return math.degrees(2 * math.atan(sensor_width / (2 * focal_length)))

# =========================
# DISTANCE BOUNDS
# =========================

def distance_bounds_from_design(design, distance_multiplier=4.0, app=None):
    """
    Return min/max camera distance based on root component bounding box.
    Uses model diagonal as a reference for reasonable camera distances.
    """
    try:
        if isinstance(design, adsk.fusion.Design):
            root_comp = design.rootComponent
            bounding_box = root_comp.boundingBox
            # Calculate diagonal length of bounding box
            diag = bounding_box.maxPoint.distanceTo(bounding_box.minPoint)
            # Use diagonal to set min/max camera distance
            min_distance = max(diag / distance_multiplier, 1.0)
            max_distance = diag * distance_multiplier
            if app:
                log_utils.log(app, f'📏 Model diagonal: {diag:.1f}cm, distance range: {min_distance:.1f} - {max_distance:.1f}cm', level='INFO', module=LOG_MODULE)
            return {
                'min_distance': min_distance,
                'max_distance': max_distance,
                'diagonal_length': diag,
                'distance_multiplier': distance_multiplier
            }
        else:
            if app:
                log_utils.log(app, '📏 No design context - using default distance range: 10 - 10000cm', level='INFO', module=LOG_MODULE)
            return {
                'min_distance': 10.0,
                'max_distance': 10000.0,
                'diagonal_length': 100.0,
                'distance_multiplier': distance_multiplier
            }
    except Exception as e:
        if app:
            log_utils.log(app, f'❌ Failed to calculate distance multiplier: {str(e)}', level='ERROR', module=LOG_MODULE)
        return {
            'min_distance': 10.0,
            'max_distance': 10000.0,
            'diagonal_length': 100.0,
            'distance_multiplier': distance_multiplier
        }