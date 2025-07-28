import adsk
import datetime

LOGGING_ENABLED = True  # MASTER Toggle this to enable/disable logging
INCLUDE_TIMESTAMPS = True  # Toggle this to enable/disable timestamps

LOG_LEVELS = {
    'ALL': 0,  # Special level to log everything
    'DEBUG': 10,
    'INFO': 20,
    'WARNING': 30,
    'ERROR': 40,
    'NONE': 100
}

current_log_level = LOG_LEVELS['ALL']  # Default log level

# Track all modules that log
LOGGED_MODULES = {}

# Optional: Per-module enable/disable
MODULE_LOGGING_ENABLED = {}

# Initialize all modules to enabled
def set_log_level(level):
    global current_log_level
    current_log_level = LOG_LEVELS.get(level.upper(), 20)

# Reset all modules to enabled
def set_timestamps(enabled: bool):
    global INCLUDE_TIMESTAMPS
    INCLUDE_TIMESTAMPS = enabled
    
# Reset all module logging states
def set_module_logging(module, enabled: bool):
    MODULE_LOGGING_ENABLED[module] = enabled
    
# If module is not in the dict, it defaults to True
def log(app, message, level='INFO', module=None):
    if not LOGGING_ENABLED:
        return
    # Special case for message breaks
    if message == '---':
        # Only log if module logging is enabled (or not specified)
        if module is None or MODULE_LOGGING_ENABLED.get(module, True):
            app.log(message)
        return
    if module:
        LOGGED_MODULES[module] = LOGGED_MODULES.get(module, 0) + 1
        if module in MODULE_LOGGING_ENABLED and not MODULE_LOGGING_ENABLED[module]:
            return
        # Append module name to the message
        message = f"{message} -->[from {module}]"
    if LOG_LEVELS[level] < current_log_level:
        return
    if INCLUDE_TIMESTAMPS:
        now = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
        app.log(f'[{now}] {message}')
    else:
        app.log(message)