"""
CameraTools main entry point - handles Fusion 360 lifecycle and palette management.
Clean architecture: Entry point → Controllers → Utilities
"""

import adsk  # type: ignore
import adsk.fusion  # type: ignore
import traceback

LOG_MODULE = 'CameraTools'

from .utilities import log_utils
log_utils.set_module_logging(LOG_MODULE, False)  # Disable verbose logging for deployment

from .event_handlers import PaletteIncomingEventHandler

app = adsk.core.Application.get()
ui = app.userInterface if app else None

# Global variables for Fusion 360 lifecycle
active_palette_instance = None
event_handlers_list = []

# Button configuration
button_properties = {
    'id': 'jm_CameraToolsCommand',
    'display_name': 'CameraTools',
    'description': 'Adjust the viewport camera Field of View and Position',
    'resources': 'resources',
    'palette_id': 'CameraToolsPalette'
}

class CommandCreatedEventHandler(adsk.core.CommandCreatedEventHandler):
    """Handles command creation events for CameraTools button."""
    def __init__(self):
        super().__init__()

    def notify(self, eventArgs):
        eventArgs = adsk.core.CommandCreatedEventArgs.cast(eventArgs)
        command = eventArgs.command
        command.isRepeatable = False
        command.isExecutedWhenPreEmpted = False

class ShowPaletteCommandExecuteHandler(adsk.core.CommandEventHandler):
    """Handles execution of the show palette command."""
    def __init__(self):
        super().__init__()

    def notify(self, eventArgs):
        """Show and initialize the CameraTools palette."""
        global active_palette_instance
        try:
            # Check if palette already exists
            if ui:
                active_palette_instance = ui.palettes.itemById(button_properties['palette_id'])
            else:
                active_palette_instance = None

            if ui and not active_palette_instance:
                # Create palette
                active_palette_instance = ui.palettes.add(
                    button_properties['palette_id'],
                    'Camera Tools',
                    'CameraTools.html',
                    True,   # isResizable
                    False,  # isModal  
                    True,   # isVisible
                    350,    # width
                    420     # height
                )
                active_palette_instance.setMinimumSize(350, 350)
                active_palette_instance.setMaximumSize(350, 1250)
                active_palette_instance.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight

                # Connect event handlers
                palette_close_handler = PaletteCloseEventHandler()
                active_palette_instance.closed.add(palette_close_handler)
                event_handlers_list.append(palette_close_handler)

                palette_incoming_handler = PaletteIncomingEventHandler(active_palette_instance)
                active_palette_instance.incomingFromHTML.add(palette_incoming_handler)
                event_handlers_list.append(palette_incoming_handler)

                # Set global reference for event handlers
                from . import event_handlers
                event_handlers.active_palette_instance = active_palette_instance

            # Show palette and send preferences
            if active_palette_instance:
                active_palette_instance.isVisible = True
                from .utilities import prefs_utils
                prefs_utils.send_prefs(active_palette_instance)
                from .event_handlers import _initialize_controllers_for_palette
                _initialize_controllers_for_palette(active_palette_instance)
        except Exception as e:
            if ui:
                ui.messageBox(f'❌ Failed to show palette:\n{traceback.format_exc()}')

class ShowPaletteCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """Handles creation of the show palette command."""
    def __init__(self):
        super().__init__()

    def notify(self, eventArgs):
        try:
            command = eventArgs.command
            execute_handler = ShowPaletteCommandExecuteHandler()
            command.execute.add(execute_handler)
            event_handlers_list.append(execute_handler)
        except Exception as e:
            if ui:
                ui.messageBox(f'❌ Failed to create show palette command:\n{traceback.format_exc()}')

class DocumentActivatedHandler(adsk.core.DocumentEventHandler):
    """Handles document activation events."""
    def __init__(self):
        super().__init__()
        
    def notify(self, eventArgs):
        """Delegate document activation to UI controller if palette is visible."""
        global active_palette_instance
        try:
            if active_palette_instance and active_palette_instance.isVisible:
                from .controllers.ui_controller import get_ui_controller
                ui_controller = get_ui_controller()
                ui_controller.handle_document_activation(active_palette_instance)
        except Exception as e:
            pass  # Suppress errors for document activation

class PaletteCloseEventHandler(adsk.core.UserInterfaceGeneralEventHandler):
    """Handles palette close events."""
    def __init__(self):
        super().__init__()

    def notify(self, eventArgs):
        """Cleanup resources and hide palette when closed."""
        global active_palette_instance
        try:
            cleanup_palette_resources()
            if active_palette_instance:
                active_palette_instance.isVisible = False
            active_palette_instance = None
            from . import event_handlers
            event_handlers.active_palette_instance = None
        except Exception as e:
            if ui:
                ui.messageBox(f'❌ Failed to handle palette close:\n{traceback.format_exc()}')

def cleanup_palette_resources():
    """Clean up palette resources by delegating to all controllers."""
    global active_palette_instance
    try:
        from .controllers.ui_controller import get_ui_controller
        get_ui_controller().cleanup_for_palette_close()
        from .controllers.overlay_controller import get_overlay_controller
        get_overlay_controller().cleanup_for_palette_close()
        from .controllers.eye_level_controller import get_eye_level_controller
        get_eye_level_controller().cleanup_for_palette_close()
        from .controllers.camera_controller import get_camera_controller
        get_camera_controller().cleanup_for_palette_close()
        from .controllers.view_controller import get_view_controller
        get_view_controller().cleanup_for_palette_close()
    except Exception:
        active_palette_instance = None

def cleanup_application():
    """Clean up all application resources and remove UI elements."""
    try:
        cleanup_palette_resources()
        global active_palette_instance
        if ui:
            active_palette_instance = ui.palettes.itemById(button_properties['palette_id'])
            if active_palette_instance:
                active_palette_instance.deleteMe()
                active_palette_instance = None
            command_definition = ui.commandDefinitions.itemById(button_properties['id'])
            if command_definition:
                command_definition.deleteMe()
            addins_panel = ui.allToolbarPanels.itemById('SolidScriptsAddinsPanel')
            if addins_panel:
                control = addins_panel.controls.itemById(button_properties['id'])
                if control:
                    control.deleteMe()
    except Exception as e:
        if ui:
            ui.messageBox(f'❌ Failed to cleanup application:\n{traceback.format_exc()}')

def run(context):
    """Main entry point for the add-in."""
    global app, ui
    ui = None
    try:
        ui = app.userInterface
        cleanup_application()
        show_palette_command_definition = ui.commandDefinitions.itemById(button_properties['id'])
        if not show_palette_command_definition:
            show_palette_command_definition = ui.commandDefinitions.addButtonDefinition(
                button_properties['id'], 
                button_properties['display_name'], 
                button_properties['description'], 
                button_properties['resources']
            )
            command_created_handler = ShowPaletteCommandCreatedHandler()
            show_palette_command_definition.commandCreated.add(command_created_handler)
            event_handlers_list.append(command_created_handler)
        addins_panel = ui.allToolbarPanels.itemById('SolidScriptsAddinsPanel')
        button_control = addins_panel.controls.addCommand(show_palette_command_definition)
        document_activated_handler = DocumentActivatedHandler()
        app.documentActivated.add(document_activated_handler)
        event_handlers_list.append(document_activated_handler)
        if button_control:
            button_control.isPromotedByDefault = True
            button_control.isPromoted = True
    except Exception as e:
        if ui:
            ui.messageBox(f'❌ Failed to start CameraTools:\n{traceback.format_exc()}')

def stop(context):
    """Stop the add-in and clean up resources."""
    try:
        cleanup_application()
    except Exception as e:
        if ui:
            ui.messageBox(f'❌ Failed to stop CameraTools:\n{traceback.format_exc()}')