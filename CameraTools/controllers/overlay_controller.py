"""
OverlayController: Manages all visual overlays and grid systems for CameraTools.
Delegates rendering and state to overlay_utils. Handles palette lifecycle and UI events.
"""

import adsk
import adsk.fusion

LOG_MODULE = 'overlay_controller'

from ..utilities import log_utils
log_utils.set_module_logging(LOG_MODULE, False)  # Disable verbose logging for deployment

from ..utilities import overlay_utils, prefs_utils

app = adsk.core.Application.get()
ui = app.userInterface

class OverlayController:
    """
    Manages all visual overlays and grid systems by delegating to overlay_utils global functions.
    """

    def __init__(self):
        self.previous_viewport_width = 0
        self.previous_viewport_height = 0
        self.active_palette = None

    def poll_viewport_size_change(self):
        """
        Check if viewport size changed and repaint overlays if needed.
        """
        viewport = app.activeViewport
        current_width = viewport.width
        current_height = viewport.height
        if (self.previous_viewport_width != current_width or 
            self.previous_viewport_height != current_height):
            self.handle_viewport_size_change(current_width, current_height)
            self.previous_viewport_width = current_width
            self.previous_viewport_height = current_height

    def handle_aspect_ratio_change(self, data, palette=None):
        """
        Handle aspect ratio overlay changes.
        """
        try:
            aspect_ratio = data.get('aspectRatio', 'default')
            preferences = prefs_utils.load_prefs() or {}
            preferences["aspectRatio"] = aspect_ratio
            prefs_utils.save_prefs(preferences)
            overlay_utils.set_aspect_ratio(aspect_ratio)
        except Exception:
            pass

    def handle_update_aspect_ratio(self, data):
        """
        Handle aspect ratio update.
        """
        try:
            aspect_ratio = data.get('aspectRatio', '16:9')
            overlay_utils.set_aspect_ratio(aspect_ratio)
        except Exception:
            pass
    
    def handle_set_grid_overlay(self, data, palette=None):
        """
        Handle grid overlay setting.
        """
        try:
            overlay_type = data.get('type')
            enabled = data.get('enabled', False)
            preferences = prefs_utils.load_prefs() or {}
            if overlay_type == 'halves':
                preferences["gridHalves"] = enabled
            elif overlay_type == 'thirds':
                preferences["gridThirds"] = enabled
            elif overlay_type == 'quarters':
                preferences["gridQuarters"] = enabled
            prefs_utils.save_prefs(preferences)
            overlay_utils.set_grid_overlay(overlay_type, enabled)
        except Exception:
            pass

    def repaint_all_overlays(self):
        """
        Repaint all visual overlays using centralized approach.
        """
        try:
            design = app.activeProduct
            if isinstance(design, adsk.fusion.Design):
                overlay_utils.repaint(design)
        except Exception:
            pass

    def update_eye_level_indicator(self, current_level, target_level):
        """
        Update the eye level drift indicator.
        """
        try:
            overlay_utils.create_eye_level_indicator(current_level, target_level)
        except Exception:
            pass

    def clear_all_overlays(self):
        """
        Clear all overlay graphics and reset global state.
        """
        try:
            overlay_utils.clear_all_custom_graphics()
            overlay_utils.current_aspect_ratio = 'default'
            overlay_utils.halves_enabled = False
            overlay_utils.thirds_enabled = False
            overlay_utils.quarters_enabled = False
        except Exception:
            pass

    def cleanup_for_palette_close(self):
        """
        Cleanup overlay controller for palette close.
        """
        try:
            self.clear_all_overlays()
            self.active_palette = None
        except Exception:
            pass

    def cleanup(self):
        """
        Full cleanup for overlay controller.
        """
        self.cleanup_for_palette_close()

    def initialize_for_palette(self, palette):
        """
        Initialize overlay controller for palette.
        """
        self.active_palette = palette

    def handle_viewport_size_change(self, width, height):
        """
        Handle viewport size changes.
        """
        try:
            self.repaint_all_overlays()
        except Exception:
            pass

# =========================
# SINGLETON INSTANCE
# =========================

_overlay_controller_instance = None

def get_overlay_controller():
    """
    Get the singleton OverlayController instance.
    """
    global _overlay_controller_instance
    if _overlay_controller_instance is None:
        _overlay_controller_instance = OverlayController()
    return _overlay_controller_instance