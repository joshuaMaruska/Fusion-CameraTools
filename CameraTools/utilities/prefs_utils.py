import os
import sys
import adsk # type: ignore
import json
LOG_MODULE = 'prefs_utils'

from ..utilities import log_utils
log_utils.set_module_logging(LOG_MODULE, False)

app = adsk.core.Application.get()

DEFAULT_PREFS = {
    "darkMode": True,
    "aspectRatio": "default",
    "gridHalves": False,
    "gridThirds": False,
    "gridQuarters": False
}
# This script manages preferences for the CameraTools add-in, including saving and loading preferences to a JSON file.

# Get the path for the preferences file based on the operating system
def get_prefs_path():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        prefs_dir = os.path.join(base, "Autodesk", "CameraTools")
    else:
        base = os.path.expanduser("~/Library/Application Support/Autodesk")
        prefs_dir = os.path.join(base, "CameraTools")
    if not os.path.exists(prefs_dir):
        os.makedirs(prefs_dir)
    return os.path.join(prefs_dir, "prefs.json")

PREFS_PATH = get_prefs_path()

# Save preferences to a JSON file
def save_prefs(prefs):
    try:
        with open(PREFS_PATH, "w") as f:
            json.dump(prefs, f)
            log_utils.log(app,f"✅ Preferences saved to {PREFS_PATH}", level='INFO', module=LOG_MODULE)
    except Exception as e:
        log_utils.log(app, f"❌ Failed to save prefs: {str(e)}", level='ERROR', module=LOG_MODULE)

# Load preferences from a JSON file
def load_prefs():
    try:
        if os.path.exists(PREFS_PATH):
            with open(PREFS_PATH, "r") as f:
                log_utils.log(app,f"✅ Preferences loaded from {PREFS_PATH}", level='INFO', module=LOG_MODULE)
                return json.load(f)
    except Exception as e:
        log_utils.log(app,f"❌ Failed to load prefs: {str(e)}", level='ERROR', module=LOG_MODULE)
        return DEFAULT_PREFS.copy()

def send_prefs(palette=None):
    prefs = load_prefs()
    if prefs is None:
        prefs = DEFAULT_PREFS.copy()
    from ..controllers.ui_controller import get_ui_controller
    ui_controller = get_ui_controller()
    success = ui_controller.send_data_to_palette('loadPrefs', {"prefs": prefs})
    if success:
        log_utils.log(app, f"✅ Preferences sent to palette: {prefs}", level='INFO', module=LOG_MODULE)
        # --- Add this block to sync overlays with prefs ---
        from ..utilities import overlay_utils
        overlay_utils.current_aspect_ratio = prefs.get("aspectRatio", "default")
        overlay_utils.halves_enabled = prefs.get("gridHalves", False)
        overlay_utils.thirds_enabled = prefs.get("gridThirds", False)
        overlay_utils.quarters_enabled = prefs.get("gridQuarters", False)
        overlay_utils.repaint(app.activeProduct)
        # --------------------------------------------------
    else:
        log_utils.log(app, f"❌ Failed to send preferences: palette not visible or not available", level='ERROR', module=LOG_MODULE)