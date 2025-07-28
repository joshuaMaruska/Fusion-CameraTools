"""
View utilities - pure functions for named view operations.
Clean architecture: Uses controllers for orchestration, pure functions only.
Handles named view listing, application, copy/paste, and UI sync.
"""

import adsk
import math
import time
import traceback
LOG_MODULE = 'view_utils'

from ..utilities import log_utils
log_utils.set_module_logging(LOG_MODULE, True)
from ..utilities import camera_transforms
from ..utilities.camera_transforms import derive_document_up

app = adsk.core.Application.get()
ui = app.userInterface

copied_camera_data = None

def _get_camera_controller():
    """
    Returns the singleton camera controller instance.
    """
    from ..controllers.camera_controller import get_camera_controller
    return get_camera_controller()

def get_named_views_list():
    """
    Returns a list of all named views in the current design.
    Each item is a dict: {'index': int, 'name': str}
    """
    try:
        design = app.activeProduct
        if not isinstance(design, adsk.fusion.Design):
            return []
        named_views = design.namedViews
        return [{'index': idx, 'name': view.name} for idx, view in enumerate(named_views)]
    except Exception as e:
        log_utils.log(app, f'❌ Failed to get named views: {str(e)}', level='ERROR', module=LOG_MODULE)
        return []

def apply_named_view_by_index(view_index, palette=None):
    """
    Applies the named view at the given index to the viewport.
    Optionally updates the UI palette after the change.
    """
    try:
        log_utils.log(app, f'apply_named_view_by_index called with index: {view_index}', level='DEBUG', module=LOG_MODULE)
        design = app.activeProduct
        if not isinstance(design, adsk.fusion.Design):
            log_utils.log(app, 'No active design found', level='ERROR', module=LOG_MODULE)
            return False
        named_views = design.namedViews
        if view_index < 0 or view_index >= named_views.count:
            log_utils.log(app, f'Named view index out of range: {view_index}', level='ERROR', module=LOG_MODULE)
            return False
        named_view = named_views.item(view_index)
        log_utils.log(app, f'Applying named view: {named_view.name}', level='DEBUG', module=LOG_MODULE)
        from ..utilities.camera_commands import apply_named_view_camera
        apply_named_view_camera(named_view, app)
        if palette:
            _update_ui_after_view_change(named_view, palette)
        log_utils.log(app, f'Applied named view index: {view_index}', level='INFO', module=LOG_MODULE)
        return True
    except Exception as e:
        log_utils.log(app, f'❌ Exception in apply_named_view_by_index: {str(e)}', level='ERROR', module=LOG_MODULE)
        if palette:
            ui.messageBox(f'❌ Failed to apply named view by index:\n.   Traceback: {traceback.format_exc()}')
        return False

def populate_named_views_dropdown(palette=None):
    """
    Sends the list of named views to the UI palette for dropdown population.
    Throttles updates to avoid excessive UI refreshes.
    """
    global _last_populate_time
    try:
        view_items = get_named_views_list()
        payload = {'namedViews': view_items}
        from ..controllers.ui_controller import get_ui_controller
        ui_controller = get_ui_controller()
        success = ui_controller.send_data_to_palette('populateNamedViews', payload)
        if success:
            log_utils.log(app, 'Named views sent successfully', level='INFO', module=LOG_MODULE)
        else:
            log_utils.log(app, '❌ Failed to send named views: palette not visible or not available', level='ERROR', module=LOG_MODULE)
    except Exception as e:
        log_utils.log(app, f'❌ Failed to populate named views dropdown: {str(e)}', level='ERROR', module=LOG_MODULE)
        ui.messageBox(f'❌ Failed to populate named views dropdown:\n.   Traceback: {traceback.format_exc()}')

def reset_named_view_dropdown(self):
    """
    Tells the JS UI to reset the named view dropdown.
    """
    if self.active_palette:
        self.active_palette.sendInfoToHTML('resetNamedViewDropdown', '{}')

def save_named_view_interactive():
    """
    Prompts the user for a named view name, auto-filling with a unique name based on camera type.
    Compensates for Fusion's view extents quirk by re-saving with corrected eye position.
    Returns the view name if saved, or None if cancelled or failed.
    """
    try:
        des = app.activeProduct
        if not isinstance(des, adsk.fusion.Design):
            ui.messageBox('No active Fusion design.')
            return None
        named_views = des.namedViews
        cam = app.activeViewport.camera
        # Determine base name based on camera type
        base_name = "Camera Tools Persp View" if cam.cameraType == adsk.core.CameraTypes.PerspectiveCameraType else "Camera Tools Ortho View"
        # Collect existing names and generate a unique candidate
        existing_names = set(view.name for view in named_views)
        candidate_name = base_name
        suffix = 1
        while candidate_name in existing_names:
            candidate_name = f"{base_name} {suffix}"
            suffix += 1
        # Prompt user with the unique default name
        result, cancelled = ui.inputBox('Name: ', 'Save Named View', candidate_name)
        if cancelled or not result:
            return None
        view_name = result[0] if isinstance(result, list) else result
        log_camera_properties(cam)
        # Save the initial named view
        named_views.add(cam, str(view_name))
        # Find the saved view and log its camera
        saved_cam = None
        for view in named_views:
            if view.name == view_name:
                log_camera_properties(view.camera)
                saved_cam = view.camera
                break
        if saved_cam:
            # Compensate for Fusion's view extents quirk
            fresh_view_extents = saved_cam.viewExtents / 10
            compensated_eye_x = cam.target.x + (cam.eye.x - cam.target.x) * fresh_view_extents
            compensated_eye_y = cam.target.y + (cam.eye.y - cam.target.y) * fresh_view_extents
            compensated_eye_z = cam.target.z + (cam.eye.z - cam.target.z) * fresh_view_extents
            cam.eye = adsk.core.Point3D.create(compensated_eye_x, compensated_eye_y, compensated_eye_z)
            # Remove and re-add the named view with compensated eye
            named_views.itemByName(view_name).deleteMe()
            named_views.add(cam, str(view_name))
            # Log the updated saved view camera properties
            for view in named_views:
                if view.name == view_name:
                    log_camera_properties(view.camera)
        ui.messageBox(f'Saved named view: {view_name}')
        return view_name
    except Exception as e:
        log_utils.log(app, f'❌ Failed to save named view: {str(e)}', level='ERROR', module=LOG_MODULE)
        ui.messageBox(f'Failed to save named view:\n{traceback.format_exc()}')
        return None

def copy_view():
    """
    Copies the current camera view in canonical space for later paste.
    Stores eye, target, upVector, perspectiveAngle, and cameraType.
    """
    global copied_camera_data
    try:
        viewport = app.activeViewport
        camera = viewport.camera
        design = app.activeProduct
        if design is None:
            log_utils.log(app, "❌ No active design/product. Copy aborted.", level='ERROR', module=LOG_MODULE)
            return False
        up_vector = derive_document_up(design)
        copied_camera_data = {
            'eye': {k: getattr(camera_transforms.to_canon_point(camera.eye, up_vector, adsk), k) for k in ('x', 'y', 'z')},
            'target': {k: getattr(camera_transforms.to_canon_point(camera.target, up_vector, adsk), k) for k in ('x', 'y', 'z')},
            'upVector': {k: getattr(camera_transforms.to_canon_vector(camera.upVector, up_vector, adsk), k) for k in ('x', 'y', 'z')},
            'perspectiveAngle': camera.perspectiveAngle,
            'cameraType': camera.cameraType
        }
        log_utils.log(app, "📐 Canonical camera data (Y-up):", level='INFO', module=LOG_MODULE)
        log_copied_camera_data(copied_camera_data)
    except Exception as e:
        log_utils.log(app, f'❌ Failed to copy camera view: {str(e)}', level='ERROR', module=LOG_MODULE)
        ui.messageBox(f'❌ Failed to copy camera view:\n.   Traceback: {traceback.format_exc()}')

def paste_view(palette=None):
    """
    Pastes the previously copied camera view to the viewport.
    Optionally updates the UI palette after the change.
    """
    global copied_camera_data
    try:
        if not copied_camera_data:
            ui.messageBox('No camera view to paste')
            return
        camera_controller = _get_camera_controller()
        success = camera_controller.apply_camera_data_direct(copied_camera_data)
        if success:
            log_utils.log(app, '🔽 Camera view pasted successfully', level='INFO', module=LOG_MODULE)
            log_camera_properties(app.activeViewport.camera)
            if palette:
                camera_mode = 'Orthographic' if copied_camera_data['cameraType'] == adsk.core.CameraTypes.OrthographicCameraType else 'Perspective'
                _send_camera_mode_update(palette, copied_camera_data['cameraType'])
                log_copied_camera_data(copied_camera_data)
        else:
            ui.messageBox('❌ Failed to paste camera view')
    except Exception as e:
        log_utils.log(app, f'❌ Failed to paste camera view: {str(e)}', level='ERROR', module=LOG_MODULE)
        ui.messageBox(f'❌ Failed to paste camera view:\n.   Traceback: {traceback.format_exc()}')

def _update_ui_after_view_change(named_view, palette):
    """
    Updates the UI palette after a named view change.
    Sends the new camera mode to the palette.
    """
    try:
        viewport = app.activeViewport
        applied_camera = viewport.camera
        camera_mode = 'Orthographic' if applied_camera.cameraType == adsk.core.CameraTypes.OrthographicCameraType else 'Perspective'
        _send_camera_mode_update(palette, applied_camera.cameraType)
    except Exception as e:
        log_utils.log(app, f'❌ Failed to update UI after view change: {str(e)}', level='ERROR', module=LOG_MODULE)

def _send_camera_mode_update(palette, camera_type):
    """
    Sends the camera mode (Perspective/Orthographic) to the UI palette.
    """
    try:
        camera_mode = 'Orthographic' if camera_type == adsk.core.CameraTypes.OrthographicCameraType else 'Perspective'
        payload = {'cameraMode': camera_mode}
        from ..controllers.ui_controller import get_ui_controller
        ui_controller = get_ui_controller()
        success = ui_controller.send_data_to_palette('updateCameraMode', payload)
        if not success:
            log_utils.log(app, '❌ Failed to send camera mode update: palette not visible or not available', level='ERROR', module=LOG_MODULE)
    except Exception as e:
        log_utils.log(app, f'❌ Failed to send camera mode update: {str(e)}', level='ERROR', module=LOG_MODULE)

def log_camera_properties(camera):
    """
    Logs all camera properties for debugging.
    """
    try:
        properties = [
            f"---",
            f"🎥 🎥 🎥 Camera Properties: 🎥 🎥 🎥 ",
            f"Camera Type: {camera.cameraType}",
            f"Eye: ({camera.eye.x:.3f}, {camera.eye.y:.3f}, {camera.eye.z:.3f})",
            f"Target: ({camera.target.x:.3f}, {camera.target.y:.3f}, {camera.target.z:.3f})",
            f"Up Vector: ({camera.upVector.x:.3f}, {camera.upVector.y:.3f}, {camera.upVector.z:.3f})",
            f"Perspective Angle: {math.degrees(camera.perspectiveAngle):.2f}°",
            f"Is Fit View: {getattr(camera, 'isFitView', 'N/A')}",
            f"Is Smooth Transition: {getattr(camera, 'isSmoothTransition', 'N/A')}",
            f"---",
        ]
        for prop in properties:
            log_utils.log(app, prop, level='INFO', module=LOG_MODULE)
    except Exception as e:
        log_utils.log(app, f'❌ Failed to log camera properties: {str(e)}', level='ERROR', module=LOG_MODULE)

def log_copied_camera_data(data):
    """
    Logs all copied camera data for debugging.
    """
    try:
        properties = [
            f"---",
            f"🎥 🎥 🎥 Camera Data: 🎥 🎥 🎥 ",
            f"Camera Type: {data.get('cameraType', 'N/A')}",
            f"Eye: ({data['eye']['x']:.3f}, {data['eye']['y']:.3f}, {data['eye']['z']:.3f})",
            f"Target: ({data['target']['x']:.3f}, {data['target']['y']:.3f}, {data['target']['z']:.3f})",
            f"Up Vector: ({data['upVector']['x']:.3f}, {data['upVector']['y']:.3f}, {data['upVector']['z']:.3f})",
            f"Perspective Angle: {math.degrees(data['perspectiveAngle']):.2f}°",
            f"Is Fit View: {data.get('isFitView', 'N/A')}",
            f"Is Smooth Transition: {data.get('isSmoothTransition', 'N/A')}",
            f"---",
        ]
        for prop in properties:
            log_utils.log(app, prop, level='INFO', module=LOG_MODULE)
    except Exception as e:
        log_utils.log(app, f'❌ Failed to log copied camera data: {str(e)}', level='ERROR', module=LOG_MODULE)