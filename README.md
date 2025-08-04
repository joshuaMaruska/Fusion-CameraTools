# CameraTools Add-In for Fusion 360

## Overview

**CameraTools** is a modular Fusion 360 add-in that delivers advanced camera and viewport controls through an interactive palette UI. It empowers users to precisely position, orient, and configure the camera for design, presentation, and documentation workflows. CameraTools integrates seamlessly with Fusion 360, providing intuitive sliders, overlays, and named view management—all without interfering with native navigation.

<img src="https://raw.githubusercontent.com/jmaruska/Fusion-CameraTools/refs/heads/main/images/CameraTools-UI.png" width=100% height=100%>

---

## Features Breakdown

### CAMERA TYPE

<img src="https://raw.githubusercontent.com/jmaruska/Fusion-CameraTools/refs/heads/main/images/cameratype@2x.png" width= 350px>

- **Orthographic/Perspective Switch:** Instantly toggle between orthographic and perspective camera types for technical or creative views.


### POSITION
These controls closely mimic Fusion 360’s native viewport navigation. They are **target-centric**: the camera orbits, zooms, and tilts around a fixed target point, allowing you to view your model from different angles while keeping the point of interest centered.

<img src="https://raw.githubusercontent.com/jmaruska/Fusion-CameraTools/refs/heads/main/images/position@2x.png" width= 350px>

- **Distance:** Move the camera closer or farther from the target point.
- **Azimuth:** Rotate the camera horizontally around the target.
- **Inclination:** Tilt the camera up or down for elevation changes.


### ADVANCED
These controls offer a **camera-centric** approach, reversing the standard Fusion workflow. Instead of moving the camera around a fixed target, tools like Dolly, Pan, and Tilt shift the target itself—changing where the camera is looking. This is especially useful for immersive, first-person navigation inside models (such as architectural walkthroughs), giving you precise control over both the camera’s position and its point of focus.

<img src="https://raw.githubusercontent.com/jmaruska/Fusion-CameraTools/refs/heads/main/images/advanced@2x.png" width= 350px>

- **Lock:** Maintain a consistent vertical camera position, ideal for architectural or human-scale views. Enabling the LOCK feature will also affect the Field of View controls making them function more like a telephoto zoom lens where the camera is static, the field of view opens or closes rather than moving the camera to fit the object.
- **Eye-Level:** This numeric entry allows you to specify an eye-height. This is set from the origin, so if your model is offset from 0,0,0, you have to factor that in.
- **Set Target/Eye:** Directly set the camera's eye or target location from the UI. Select a point in your model (construction or model vertex) to use as an absolute position for either camera target or camera eye position.
- **Dolly, Pan, Tilt:** Move the camera or target in absolute terms for precise framing.


### LENS

<img src="https://raw.githubusercontent.com/jmaruska/Fusion-CameraTools/refs/heads/main/images/lens@2x.png" width= 350px>

- **Field of View (FOV):** Adjust the camera's angle for wide or narrow shots.
- **Focal Length:** Fine-tune perspective effects with a logarithmic slider and numeric input.
- **Default Lens:** Instantly reset to Fusion's standard FOV for predictable results.

### VIEWS

<img src="https://raw.githubusercontent.com/jmaruska/Fusion-CameraTools/refs/heads/main/images/views@2x.png" width= 350px>

- **Copy/Paste View:** Save and restore camera states for repeatable setups.
- **Named Views:** Create, select, and manage custom camera views for quick recall.
- **Fit to View:** Frame the entire model in the viewport.
- **Restore View:** Return to the initial camera position.

### OVERLAYS

<img src="https://raw.githubusercontent.com/jmaruska/Fusion-CameraTools/refs/heads/main/images/overlays@2x.png" width= 350px>

- **Aspect Ratio Guides:** Overlay boundaries for common aspect ratios (Current, 16:9, 4:3, 1:1).
- **Grid Overlays:** Display halves, thirds, and quarters to aid composition and alignment.

### UI & Accessibility
- **Dark Mode:** Toggle between light and dark themes for comfortable viewing.
- **Responsive Palette:** Modern, accessible UI with developer tools for debugging.
- **Preferences Saving:** Theme and overlays are stored locally so the palette restores state on next launch.

---

## Getting Started

1. Copy the add-in folder to your Fusion 360 Add-Ins directory.
2. Launch Fusion 360 and enable the add-in from the Scripts and Add-Ins dialog.
3. Open the **Camera Tools** palette from the add-in menu.
4. Use the palette controls to adjust the camera, save views, and apply overlays.

---

## How CameraTools Works

CameraTools operates through a Fusion 360 palette, updating the camera in real time as you adjust controls. All camera changes are routed through a robust controller and utility pipeline, ensuring smooth transitions and accurate state management.

### Data Flow Overview

1. **User Interaction:**  
   The user interacts with sliders, toggles, and buttons in the CameraTools palette UI (HTML/JS).

2. **UI Controller:**  
   UI events are captured and routed to the Python backend via Fusion's palette messaging system.

3. **Camera Controller:**  
   The camera controller receives UI commands, interprets them, and builds a pending camera update dictionary.

4. **Payload Builder:**  
   The controller calls utility functions to build a camera payload, which encodes all camera properties (eye, target, upVector, FOV, cameraType, etc.).

5. **Camera Application:**  
   The payload is applied to the Fusion camera using a multi-step assignment process to avoid Fusion quirks (such as unwanted reframing when changing FOV or camera type).

6. **Viewport Update:**  
   The viewport is refreshed, overlays are drawn, and the UI is updated to reflect the new camera state.

---

## Module Breakdown

Below is a breakdown of the main modules and files in CameraTools, with a brief comment describing the role of each:

```
CameraTools
├── __init__.py
│    # Python package initializer (required for Fusion add-in structure)
├── CameraTools.html
│    # Main HTML file for the palette UI; defines layout and UI elements
├── CameraTools.manifest
│    # Fusion manifest file; describes the add-in for Fusion 360
├── CameraTools.py
│    # Entry point for the add-in; sets up palette, event handlers, and main loop
├── controllers
│   ├── camera_controller.py
│   │    # Core logic for interpreting UI commands and managing camera state
│   ├── eye_level_controller.py
│   │    # Handles eye-level lock logic and related camera constraints
│   ├── overlay_controller.py
│   │    # Manages overlays (aspect guides, grids) and their drawing logic
│   ├── ui_controller.py
│   │    # Handles palette events and UI logic; routes UI changes to controllers
│   └── view_controller.py
│        # Manages named views, view saving/loading, and view recall
├── event_handlers.py
│    # Sets up Fusion event handlers for palette, commands, and UI events
├── images
│   ├── arrow.svg
│   ├── gridsHalves.svg
│   ├── gridsQuarters.svg
│   ├── gridsThirds.svg
│   ├── uiDark.svg
│   ├── uiLight.svg
│   ├── viewCopy.svg
│   ├── viewPaste.svg
│   └── viewSave.svg
│    # SVG icons for UI buttons, overlays, and palette graphics
├── javascript
│   ├── advanced-ui.js
│   │   # Advanced UI logic for sliders, overlays, and palette controls
│   ├── camera-ui.js
│   │   # Camera-specific UI logic and event handling
│   ├── dropdown.js
│   │   # Dropdown menu logic for palette controls
│   ├── palette.js
│   │   # Palette initialization and Fusion messaging bridge
│   ├── telemetry.js
│   │   # UI telemetry and analytics (optional)
│   └── utils.js
│       # General UI utility functions
├── main.js
│    # Main JS entry point for palette UI; wires up events and controls
├── README.md
│    # Documentation and usage guide for CameraTools
├── resources
│   ├── 16x16.svg
│   ├── 32x32.svg
│   ├── 64x64.svg
│   └── CameraTools_Icons.ai
│    # Icons and design resources for Fusion add-in branding
├── style.css
│    # CSS styles for the palette UI
└── utilities
    ├── camera_calculations.py
    │    # Math functions for camera positioning, spherical transforms, and lens calculations
    ├── camera_commands.py
    │    # Core utility for building/applying camera payloads; handles Fusion quirks
    ├── camera_telemetry.py
    │    # Camera usage analytics and telemetry (optional)
    ├── camera_transforms.py
    │    # Coordinate transforms between Fusion document space and canonical camera space
    ├── eye_level_utils.py
    │    # Eye-level lock logic and helpers
    ├── log_utils.py
    │    # Logging and debugging utilities
    ├── overlay_utils.py
    │    # Overlay drawing and composition guide logic
    ├── prefs_utils.py
    │    # User preferences and settings management
    └── view_utils.py
         # Named view management and view state utilities
```

---

Each module is designed to be modular and maintainable, making it easy to extend CameraTools with new features or UI elements.  
For more details on any module, see the inline comments in the source files.

---

## Engineering Notes & Fusion Workarounds

CameraTools was developed with careful attention to the quirks and limitations of Fusion 360's camera API. Several non-obvious workarounds were implemented to ensure reliable, predictable camera behavior:

- **Multi-Step Camera Assignment:**  
  Changing certain camera properties (like FOV or camera type) in Fusion 360 can cause the camera to unexpectedly reframe, animate, or lose its position. To prevent this, CameraTools applies camera changes in two distinct steps:
  1. First, set the FOV and camera type.
  2. Then, immediately restore the eye, target, and upVector values.
  This sequence ensures the camera remains fixed and avoids unwanted transitions or jumps.

- **Sanitizing Camera Type Changes:**  
  Switching between orthographic and perspective views can leave the camera in an inconsistent state or "stuck" extents. CameraTools always resets to perspective and fits the view before switching to the target camera type, ensuring a clean transition and preventing extents issues.

- **Explicit Eye/Target/UpVector Passing:**  
  When using features like eye-level lock or changing FOV, the current camera position is captured and explicitly passed through the pipeline. This avoids recalculation errors and ensures the camera remains stable during lens changes.

- **Single Refresh After Multi-Step Assignment:**  
  To avoid double transitions or animation artifacts, the viewport is only refreshed once after all camera properties have been set.

- **UI/Controller Layer Responsibility:**  
  The logic for capturing and passing explicit camera positions is handled in the UI/controller layer, keeping the utility pipeline clean and predictable.

These workarounds were discovered through extensive testing and experimentation, and are essential for delivering a professional camera experience in Fusion 360. For more details, see the inline comments in `camera_commands.py` and related modules.

---

## Feedback & Contributions

Questions, suggestions, or bug reports?  
Open an issue or submit a pull request on GitHub!

---
