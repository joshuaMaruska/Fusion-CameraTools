"""
ViewController: Handles all named view operations and synchronization for CameraTools.
Delegates view logic to view_utils. Manages palette lifecycle, UI events, and sync.
"""

import adsk
import traceback

LOG_MODULE = 'view_controller'

from ..utilities import log_utils
log_utils.set_module_logging(LOG_MODULE, False)  # Disable verbose logging for deployment

from ..utilities import view_utils
from ..utilities.view_utils import apply_named_view_by_index

app = adsk.core.Application.get()
ui = app.userInterface

_named_view_selected = False
handlers = []

class NamedViewCameraChangedHandler(adsk.core.CameraEventHandler):
    """Handles Fusion cameraChanged events for named view dropdown reset."""
    def __init__(self, palette):
        super().__init__()
        self.palette = palette

    def notify(self, args):
        global _named_view_selected
        if _named_view_selected:
            _named_view_selected = False
            if self.palette:
                self.palette.sendInfoToHTML('resetNamedViewDropdown', '{}')

def register_camera_changed_handler(palette):
    """Register cameraChanged handler for named view sync."""
    global handlers
    handler = NamedViewCameraChangedHandler(palette)
    app.cameraChanged.add(handler)
    handlers.append(handler)

class ViewController:
    """Unified view controller - handles all view operations and sync."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.active_palette = None
        self._cached_named_views = None
        self._initialized = True

    # =========================
    # PALETTE LIFECYCLE
    # =========================

    def initialize_for_palette(self, palette):
        """Initialize view controller for palette."""
        try:
            self.active_palette = palette
            self.populate_named_views_dropdown(palette)
            register_camera_changed_handler(palette)
            log_utils.log(app, '✅ View controller initialized for palette', level='INFO', module=LOG_MODULE)
        except Exception as e:
            log_utils.log(app, f'❌ Failed to initialize view controller: {str(e)}', level='ERROR', module=LOG_MODULE)

    def cleanup_for_palette_close(self):
        """Cleanup view controller for palette close."""
        try:
            self.active_palette = None
            self._cached_named_views = None
            global handlers
            for handler in handlers:
                app.cameraChanged.remove(handler)
            handlers.clear()
            log_utils.log(app, '✅ View controller cleaned up for palette close', level='INFO', module=LOG_MODULE)
        except Exception as e:
            log_utils.log(app, f'❌ Failed to cleanup view controller: {str(e)}', level='ERROR', module=LOG_MODULE)

    def cleanup(self):
        """Full cleanup for view controller."""
        self.cleanup_for_palette_close()

    # =========================
    # UI EVENT HANDLERS
    # =========================

    def handle_view_copy(self, data, palette=None):
        """Handle view copy operation."""
        try:
            view_utils.copy_view()
            log_utils.log(app, 'View copied successfully', level='INFO', module=LOG_MODULE)
        except Exception as e:
            log_utils.log(app, f'❌ Failed to copy view: {str(e)}', level='ERROR', module=LOG_MODULE)
            ui.messageBox(f'❌ Failed to copy view:\n{traceback.format_exc()}')

    def handle_view_paste(self, data, palette=None):
        """Handle view paste operation."""
        try:
            view_utils.paste_view(palette)
            log_utils.log(app, 'View pasted successfully', level='INFO', module=LOG_MODULE)
        except Exception as e:
            log_utils.log(app, f'❌ Failed to paste view: {str(e)}', level='ERROR', module=LOG_MODULE)
            ui.messageBox(f'❌ Failed to paste view:\n{traceback.format_exc()}')

    def handle_named_view_save(self, data, palette):
        """Handle saving current view as named view."""
        try:
            view_name = view_utils.save_named_view_interactive()
            if view_name:
                self.populate_named_views_dropdown(palette)
                log_utils.log(app, f'Named view saved: {view_name}', level='INFO', module=LOG_MODULE)
        except Exception as e:
            log_utils.log(app, f'❌ Failed to save named view: {str(e)}', level='ERROR', module=LOG_MODULE)
            ui.messageBox(f'❌ Failed to save named view:\n{traceback.format_exc()}')

    def handle_named_view_selected(self, data, palette):
        """Handle named view selection."""
        global _named_view_selected
        _named_view_selected = True
        try:
            view_index = data.get('viewIndex')
            apply_named_view_by_index(view_index, palette)
            log_utils.log(app, f'Named view selected: {view_index}', level='INFO', module=LOG_MODULE)
        except Exception as e:
            log_utils.log(app, f'❌ Failed to handle named view selection: {str(e)}', level='ERROR', module=LOG_MODULE)
            ui.messageBox(f'❌ Failed to handle named view selection:\n{traceback.format_exc()}')

    def handle_named_views_population(self, data, palette):
        """Handle named views dropdown population."""
        try:
            self.populate_named_views_dropdown(palette)
        except Exception as e:
            log_utils.log(app, f'❌ Failed to populate named views: {str(e)}', level='ERROR', module=LOG_MODULE)
            ui.messageBox(f'❌ Failed to populate named views:\n{traceback.format_exc()}')

    def handle_document_activation(self, palette):
        """Handle document activation - refresh named views."""
        try:
            self.populate_named_views_dropdown(palette)
            self._cached_named_views = None
            log_utils.log(app, '✅ Document activation handled - named views refreshed', level='INFO', module=LOG_MODULE)
        except Exception as e:
            log_utils.log(app, f'❌ Failed to handle document activation: {str(e)}', level='ERROR', module=LOG_MODULE)

    def poll_named_views_update(self, palette=None):
        """Poll for named views update and refresh dropdown if changed."""
        from ..utilities.view_utils import get_named_views_list
        current_views = get_named_views_list()
        if current_views != self._cached_named_views:
            log_utils.log(app, f'Named views changed: {current_views}', level='INFO', module=LOG_MODULE)
            self._cached_named_views = current_views
            self.populate_named_views_dropdown(palette)

    # =========================
    # SYNC MANAGEMENT
    # =========================

    def _send_updated_views_to_ui(self, views, palette):
        """Send updated views to UI using UIController."""
        try:
            from ..controllers.ui_controller import get_ui_controller
            ui_controller = get_ui_controller()
            payload = {
                "action": "updateNamedViews",
                "views": views
            }
            success = ui_controller.send_data_to_palette('data', payload)
            if not success:
                log_utils.log(app, '❌ Failed to send updated views: palette not visible or not available', level='ERROR', module=LOG_MODULE)
        except Exception as e:
            log_utils.log(app, f'❌ Failed to send views to UI: {str(e)}', level='ERROR', module=LOG_MODULE)

    def populate_named_views_dropdown(self, palette):
        """Populate named views dropdown - delegate to view_utils."""
        try:
            view_utils.populate_named_views_dropdown(palette)
            log_utils.log(app, '✅ Named views dropdown populated', level='INFO', module=LOG_MODULE)
        except Exception as e:
            log_utils.log(app, f'❌ Failed to populate named views dropdown: {str(e)}', level='ERROR', module=LOG_MODULE)

# =========================
# SINGLETON INSTANCE
# =========================

_view_controller_instance = None

def get_view_controller():
    """Get the singleton ViewController instance."""
    global _view_controller_instance
    if _view_controller_instance is None:
        _view_controller_instance = ViewController()
    return _view_controller_instance