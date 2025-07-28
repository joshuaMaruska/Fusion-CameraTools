"""
overlay_utils.py
Core overlay drawing and state utilities for CameraTools.

- Handles all custom graphics overlays: aspect ratio masks, grid overlays, debug rectangles.
- Maintains global overlay state (aspect ratio, grid enable flags).
- All math is performed in viewport pixel space for overlays.
- No direct UI/controller logic.
"""

import adsk
import adsk.fusion
import math
import traceback

LOG_MODULE = 'overlay_utils'

from ..utilities import log_utils
log_utils.set_module_logging(LOG_MODULE, False)  # Set True for deployment

app = adsk.core.Application.get()
ui = app.userInterface
overlay_cg_group = None

# =========================
# GLOBAL STATE VARIABLES
# =========================

current_aspect_ratio = 'default'
halves_enabled = False
thirds_enabled = False
quarters_enabled = False

HALVES = [0.5]
THIRDS = [1/3, 2/3]
QUARTERS = [0.25, 0.75]

HALVES_COLOR = (0, 255, 255, 128)  # Cyan
THIRDS_COLOR = (255, 128, 0, 64)   # Orange  
QUARTERS_COLOR = (0, 128, 255, 64) # Blue

# =========================
# CORE OVERLAY UTILITIES
# =========================

def get_overlay_cg_group(design):
    """
    Returns the global custom graphics group for overlays, creating it if needed.
    Ensures overlays are drawn in a single group for easy clearing.
    """
    global overlay_cg_group
    if overlay_cg_group is not None:
        try:
            _ = overlay_cg_group.isValid
            return overlay_cg_group
        except:
            overlay_cg_group = None
    overlay_cg_group = design.rootComponent.customGraphicsGroups.add()
    return overlay_cg_group

def clear_overlay_graphics():
    """
    Deletes the global overlay custom graphics group.
    """
    global overlay_cg_group
    if overlay_cg_group is not None:
        try:
            overlay_cg_group.deleteMe()
        except:
            pass
        overlay_cg_group = None
    log_utils.log(app, '🧹 Cleared overlay graphics', level='INFO', module=LOG_MODULE)

def clear_all_custom_graphics():
    """
    Deletes all custom graphics groups from all components and occurrences in the design.
    Used for full overlay reset.
    """
    try:
        if app.activeProduct is None:
            return
        design = app.activeProduct
        if not isinstance(design, adsk.fusion.Design):
            return
        def clear_groups(comp):
            for cg_group in comp.customGraphicsGroups:
                cg_group.deleteMe()
            for occ in comp.occurrences:
                clear_groups(occ.component)
        clear_groups(design.rootComponent)
        log_utils.log(app, '🧹 Cleared all custom graphics', level='INFO', module=LOG_MODULE)
    except Exception as e:
        log_utils.log(app, f'❌ Failed to clear custom graphics: {str(e)}', level='ERROR', module=LOG_MODULE)

# =========================
# ASPECT RATIO UTILITIES
# =========================

def get_aspect_fit_rect(viewport_width, viewport_height, target_aspect):
    """
    Calculates the largest centered rectangle with the target aspect ratio that fits in the viewport.
    Returns (rect_x, rect_y, rect_width, rect_height) in pixel space.
    """
    viewport_aspect = viewport_width / viewport_height
    if viewport_aspect > target_aspect:
        # Pillarbox: fit height, adjust width
        rect_height = viewport_height
        rect_width = rect_height * target_aspect
        rect_x = (viewport_width - rect_width) / 2
        rect_y = 0
    else:
        # Letterbox: fit width, adjust height
        rect_width = viewport_width
        rect_height = rect_width / target_aspect
        rect_x = 0
        rect_y = (viewport_height - rect_height) / 2
    return rect_x, rect_y, rect_width, rect_height

def create_aspect_ratio_mask(design, mode='16:9', color=(0, 0, 0, 64), opacity=1):
    """
    Draws black mask panels outside the aspect-fit rectangle for the given mode.
    Used for letterbox/pillarbox overlays.
    """
    try:
        cgGroup = get_overlay_cg_group(design)
        viewport = app.activeViewport
        width = viewport.width * 2
        height = viewport.height * 2

        aspect_map = {'16:9': 16/9, '4:3': 4/3, '1:1': 1}
        if mode not in aspect_map:
            return

        rect_x, rect_y, rect_w, rect_h = get_aspect_fit_rect(width, height, aspect_map[mode])

        # Top mask (above fit rect)
        if rect_y > 0:
            create_mask_panel(cgGroup, 0, 0, width, -rect_y/2, color, opacity)
        # Bottom mask (below fit rect)
        if rect_y + rect_h < height:
            create_mask_panel(cgGroup, 0, rect_y + rect_h, width, -(height - (rect_y + rect_h/2)), color, opacity)
        # Left mask (left of fit rect)
        if rect_x > 0:
            create_mask_panel(cgGroup, 0, rect_y/2, rect_x/2, -rect_h/2, color, opacity)
        # Right mask (right of fit rect)
        if rect_x + rect_w < width:
            create_mask_panel(cgGroup, rect_x + rect_w, rect_y, width - (rect_x + rect_w/2), -rect_h, color, opacity)
    except Exception as e:
        log_utils.log(app,f'❌ Failed to create aspect ratio mask: {str(e)}', level='ERROR', module=LOG_MODULE)

def create_mask_panel(cgGroup, x, y, w, h, color, opacity):    
    """
    Draws a rectangular mask panel at (x, y) of size (w, h) in screen space.
    Used for aspect ratio overlays.
    """
    coords = [
        0, 0, 0,
        w, 0, 0,
        w, h, 0,
        0, h, 0
    ]
    coordObj = adsk.fusion.CustomGraphicsCoordinates.create(coords)
    indices = [0, 1, 2, 0, 2, 3]
    normals = [0.0, 0.0, 1.0] * 4
    normalIndexList = [0, 1, 2, 0, 2, 3]
    mesh = cgGroup.addMesh(coordObj, indices, normals, normalIndexList)
    mesh.isSelectable = False
    showThrough = adsk.fusion.CustomGraphicsShowThroughColorEffect.create(
        adsk.core.Color.create(*color), opacity
    )
    mesh.color = showThrough
    billBoard = adsk.fusion.CustomGraphicsBillBoard.create(adsk.core.Point3D.create(0,0,0))
    billBoard.billBoardStyle = adsk.fusion.CustomGraphicsBillBoardStyles.ScreenBillBoardStyle 
    mesh.billBoarding = billBoard
    mesh.viewScale = adsk.fusion.CustomGraphicsViewScale.create(1, adsk.core.Point3D.create(0,0,0))
    mesh.viewPlacement = adsk.fusion.CustomGraphicsViewPlacement.create(
        adsk.core.Point3D.create(0,0,0),
        adsk.fusion.ViewCorners.upperLeftViewCorner,
        adsk.core.Point2D.create(x, y)
    )

# =========================
# GRID UTILITIES
# =========================

def create_grid_overlay(design, fractions=None, color=(63,127,255,128), thickness=1):
    """
    Draws grid lines at the specified fractions of the aspect-fit rectangle.
    Used for halves/thirds/quarters overlays.
    """
    cgGroup = get_overlay_cg_group(design)
    if fractions is None:
        return
    try:
        viewport = app.activeViewport
        width = viewport.width * 2
        height = viewport.height * 2

        aspect_map = {'16:9': 16/9, '4:3': 4/3, '1:1': 1}
        aspect = aspect_map.get(current_aspect_ratio, width/height)
        rect_x, rect_y, rect_w, rect_h = get_aspect_fit_rect(width, height, aspect)

        # Vertical lines
        for frac in fractions:
            x = rect_x + rect_w * frac
            create_grid_line_mesh(cgGroup, x, rect_y, 0, -rect_h, thickness, color)
        # Horizontal lines
        for frac in fractions:
            y = rect_y + rect_h * frac
            create_grid_line_mesh(cgGroup, rect_x, y, rect_w, 0, thickness, color)
    except Exception as e:
        log_utils.log(app,f'❌ Failed to create grid overlay: {str(e)}', level='ERROR', module=LOG_MODULE)

def create_grid_line_mesh(cgGroup, x, y, w, h, thickness, color):
    """
    Draws a vertical or horizontal grid line as a skinny rectangle at (x, y).
    Used for grid overlays.
    """
    if w == 0:  # vertical
        coords = [
            0, 0, 0,
            thickness, 0, 0,
            thickness, h/2, 0,
            0, h/2, 0
        ]
        offset = adsk.core.Point2D.create(x - thickness/2, y)
    else:  # horizontal
        coords = [
            0, -thickness/2, 0,
            w/2, -thickness/2, 0,
            w/2, thickness/2, 0,
            0, thickness/2, 0
        ]
        offset = adsk.core.Point2D.create(x, y)
    coordObj = adsk.fusion.CustomGraphicsCoordinates.create(coords)
    indices = [0, 1, 2, 0, 2, 3]
    normals = [0.0, 0.0, 1.0] * 4
    normalIndexList = [0, 1, 2, 0, 2, 3]
    mesh = cgGroup.addMesh(coordObj, indices, normals, normalIndexList)
    mesh.isSelectable = False
    showThrough = adsk.fusion.CustomGraphicsShowThroughColorEffect.create(
        adsk.core.Color.create(*color), 1
    )
    mesh.color = showThrough
    billBoard = adsk.fusion.CustomGraphicsBillBoard.create(adsk.core.Point3D.create(0,0,0))
    billBoard.billBoardStyle = adsk.fusion.CustomGraphicsBillBoardStyles.ScreenBillBoardStyle 
    mesh.billBoarding = billBoard
    mesh.viewScale = adsk.fusion.CustomGraphicsViewScale.create(1, adsk.core.Point3D.create(0,0,0))
    mesh.viewPlacement = adsk.fusion.CustomGraphicsViewPlacement.create(
        adsk.core.Point3D.create(0,0,0),
        adsk.fusion.ViewCorners.upperLeftViewCorner,
        offset
    )

# =========================
# REPAINT FUNCTION
# =========================

def repaint(design):
    """
    Clears overlays and redraws all enabled overlays (aspect mask, grids).
    Called whenever overlay state changes.
    """
    try:
        clear_overlay_graphics()
        if current_aspect_ratio in ['default', '16:9', '4:3', '1:1']:
            create_aspect_ratio_mask(design, mode=current_aspect_ratio)
        if halves_enabled:
            create_grid_overlay(design, fractions=HALVES, color=HALVES_COLOR)
        if thirds_enabled:
            create_grid_overlay(design, fractions=THIRDS, color=THIRDS_COLOR)
        if quarters_enabled:
            create_grid_overlay(design, fractions=QUARTERS, color=QUARTERS_COLOR)
        log_utils.log(app, '🔄 Repainted overlays successfully', level='INFO', module=LOG_MODULE)
    except Exception as e:
        log_utils.log(app,f'❌ Failed to repaint: {str(e)}', level='ERROR', module=LOG_MODULE)

# =========================
# STATE MANAGEMENT FUNCTIONS
# =========================

def update_aspect_ratio(aspect_ratio):
    """
    Sets the global aspect ratio and repaints overlays.
    """
    global current_aspect_ratio
    current_aspect_ratio = aspect_ratio
    des = app.activeProduct
    if isinstance(des, adsk.fusion.Design):
        repaint(des)

def toggle_grid_halves(enabled):
    """
    Enables/disables halves grid overlay and repaints.
    """
    global halves_enabled
    halves_enabled = enabled
    des = app.activeProduct
    if isinstance(des, adsk.fusion.Design):
        repaint(des)

def toggle_grid_thirds(enabled):
    """
    Enables/disables thirds grid overlay and repaints.
    """
    global thirds_enabled
    thirds_enabled = enabled
    des = app.activeProduct
    if isinstance(des, adsk.fusion.Design):
        repaint(des)

def toggle_grid_quarters(enabled):
    """
    Enables/disables quarters grid overlay and repaints.
    """
    global quarters_enabled
    quarters_enabled = enabled
    des = app.activeProduct
    if isinstance(des, adsk.fusion.Design):
        repaint(des)

# =========================
# DEBUG UTILITIES
# =========================

def draw_debug_fit_rect(design, color=(0, 255, 255, 60)):
    """
    Draws a debug rectangle showing the aspect-fit area in the viewport.
    Useful for overlay development.
    """
    try:
        cgGroup = get_overlay_cg_group(design)
        viewport = app.activeViewport
        width = viewport.width * 1
        height = viewport.height * 1

        aspect_map = {'16:9': 16/9, '4:3': 4/3, '1:1': 1}
        aspect = aspect_map.get(current_aspect_ratio, width/height)
        rect_x, rect_y, rect_w, rect_h = get_aspect_fit_rect(width, height, aspect)

        coords = [
            0, 0, 0,
            rect_w, 0, 0,
            rect_w, -rect_h, 0,
            0, -rect_h, 0
        ]
        coordObj = adsk.fusion.CustomGraphicsCoordinates.create(coords)
        indices = [0, 1, 2, 0, 2, 3]
        normals = [0.0, 0.0, 1.0] * 4
        normalIndexList = [0, 1, 2, 0, 2, 3]
        mesh = cgGroup.addMesh(coordObj, indices, normals, normalIndexList)
        mesh.isSelectable = False
        showThrough = adsk.fusion.CustomGraphicsShowThroughColorEffect.create(
            adsk.core.Color.create(*color), 1
        )
        mesh.color = showThrough
        billBoard = adsk.fusion.CustomGraphicsBillBoard.create(adsk.core.Point3D.create(0,0,0))
        billBoard.billBoardStyle = adsk.fusion.CustomGraphicsBillBoardStyles.ScreenBillBoardStyle 
        mesh.billBoarding = billBoard
        mesh.viewScale = adsk.fusion.CustomGraphicsViewScale.create(1, adsk.core.Point3D.create(0,0,0))
        mesh.viewPlacement = adsk.fusion.CustomGraphicsViewPlacement.create(
            adsk.core.Point3D.create(0,0,0),
            adsk.fusion.ViewCorners.upperLeftViewCorner,
            adsk.core.Point2D.create(rect_x*2, rect_y*2)
        )
    except Exception as e:
        log_utils.log(app,f'❌ Failed to draw debug fit rect: {str(e)}', level='ERROR', module=LOG_MODULE)

def set_aspect_ratio(aspect_ratio):
    """
    Sets the aspect ratio and triggers overlay repaint.
    """
    try:
        update_aspect_ratio(aspect_ratio)
        log_utils.log(app,f'Aspect ratio set to: {aspect_ratio}', level='INFO', module=LOG_MODULE)
    except Exception as e:
        log_utils.log(app,f'❌ Failed to set aspect ratio: {str(e)}', level='ERROR', module=LOG_MODULE)

def set_grid_overlay(grid_type, enabled):
    """
    Enables/disables the specified grid overlay and triggers repaint.
    """
    try:
        if grid_type == 'halves':
            toggle_grid_halves(enabled)
        elif grid_type == 'thirds':
            toggle_grid_thirds(enabled)
        elif grid_type == 'quarters':
            toggle_grid_quarters(enabled)
        else:
            log_utils.log(app,f'Unknown grid type: {grid_type}', level='INFO', module=LOG_MODULE)
            return            
    except Exception as e:
        log_utils.log(app,f'❌ Failed to set grid overlay: {str(e)}', level='ERROR', module=LOG_MODULE)