# messages.py

# --- Configuration Messages ---
MSG_CONFIG_LOADED_HEADER = "--- Agent Configuration ---"
MSG_CONFIG_SERVER_ADDRESS = "Server Address: {}"
MSG_CONFIG_CPU_THRESHOLD = "CPU Alert Threshold: {}%"
MSG_CONFIG_GPU_THRESHOLD = "GPU Alert Threshold: {}%"
MSG_CONFIG_LOG_FOLDER = "Log Folder: {}"
MSG_CONFIG_DISK_THRESHOLD = "Disk Space Alert Threshold (GB): {}"
MSG_CONFIG_PING_INTERVAL = "Server Ping Interval (Seconds): {}"
MSG_CONFIG_LOG_RETENTION = "Log Retention Period (Days): {}"
MSG_CONFIG_FOOTER = "---------------------------"
MSG_CONFIG_FILE_NOT_FOUND = "Warning: Configuration file 'config.ini' not found. Using default settings."
MSG_CONFIG_ERROR_READING = "Error reading 'config.ini': {}. Using default settings."
MSG_SERVER_ADDRESS_MISSING_CONFIG = "Warning: Server address not configured in 'config.ini'. Using default (None)."
MSG_SERVER_ADDRESS_NOT_CONFIGURED = "Warning: Server address not configured. Data transmission will be skipped."

# --- Module Availability Messages ---
MSG_PSUTIL_NOT_AVAILABLE = "Warning: 'psutil' module not found. CPU usage will not be monitored. Please install it using 'pip install psutil'"
MSG_GPUTIL_NOT_AVAILABLE = "Warning: 'GPUtil' module not found. GPU usage will not be monitored. Install with 'pip install GPUtil'"
MSG_GPUTIL_INIT_ERROR = "Warning: GPUtil module could not be initialized ({}). GPU usage will not be monitored."
MSG_GPUTIL_NO_GPUS = "Info: GPUtil is loaded, but no NVIDIA GPUs were found. GPU usage will be 'None'."
MSG_PYGETWINDOW_NOT_AVAILABLE = "Warning: 'pygetwindow' module not found. Active window title will not be monitored. Install with 'pip install pygetwindow'"
MSG_PYGETWINDOW_INIT_ERROR = "Warning: 'pygetwindow' module could not be initialized ({}). Active window title will not be monitored."
MSG_REQUESTS_NOT_AVAILABLE = "Warning: 'requests' module not found. Data will not be sent to server. Install with 'pip install requests'"

# --- Data Collection Error Messages ---
MSG_ERROR_GETTING_NETBIOS = "Error getting NetBIOS name: {}"
MSG_ERROR_GETTING_IP = "Error getting IP address: {}"
MSG_ERROR_RESOLVING_IP = "Error resolving hostname to IP address: {}"
MSG_ERROR_GETTING_DISK_SPACE = "Error getting free disk space for drive '{}': {}"
MSG_ERROR_DRIVE_NOT_FOUND = "Error: Drive '{}' not found."
MSG_ERROR_GETTING_CPU = "Error getting CPU usage: {}"
MSG_ERROR_GETTING_GPU = "Error getting GPU usage: {}"
MSG_ERROR_GETTING_ACTIVE_WINDOW = "Error getting active window title: {}"

# --- Main Loop Status Messages ---
MSG_LOGGING_TO_FILE = "Logging data to: {}"
MSG_LOG_FILE_DAILY_CHANGE = "New day, logging to: {}"
MSG_LOG_FILE_WRITING_ERROR = "Error writing to log file '{}': {}"
MSG_LOG_PATH_ERROR = "Error ensuring log path '{}' exists or writing to file: {}"
MSG_JSON_SERIALIZATION_ERROR = "Error serializing {} to JSON for logging: {}. Payload was: {}"

# --- Data Transmission Messages ---
MSG_SENDING_DATA_TO_SERVER = "Data successfully sent to {} (Status: {})"
MSG_SEND_HTTP_ERROR = "HTTP error sending data to {}: {}"
MSG_SEND_CONNECTION_ERROR = "Connection error sending data to {}: {}"
MSG_SEND_TIMEOUT_ERROR = "Timeout sending data to {}: {}"
MSG_SEND_REQUEST_EXCEPTION = "Error sending data to {}: {}"
MSG_SEND_UNEXPECTED_ERROR = "Unexpected error in send_data_to_server: {}"
MSG_SEND_SKIPPING_JSON_ERROR = "Skipping transmission of {} due to JSON serialization error during logging."

# --- General Error Messages ---
MSG_UNEXPECTED_ERROR_MAIN_LOOP = "An unexpected error occurred in the main loop: {}"

# --- Ping Messages ---
MSG_ATTEMPTING_SERVER_PING = "Attempting server ping..."
MSG_PING_SKIPPED_NO_SERVER_DETAILS = "Ping skipped: Server address not configured."
MSG_PING_SKIPPED_NO_REQUESTS_DETAILS = "Ping skipped: 'requests' module not available."
MSG_ERROR_WRITING_PING_STATUS_LOG = "Error writing ping status to local log: {}"

# --- Log Cleanup Messages ---
MSG_LOG_CLEANUP_STARTED = "Starting cleanup of old log files..."
MSG_LOG_CLEANUP_COMPLETED = "Log cleanup completed."
MSG_DELETING_OLD_LOG = "Deleting old log file: {} (Age: {} days)"
MSG_ERROR_DELETING_LOG = "Error deleting log file {}: {}"
MSG_ERROR_PARSING_LOG_FILENAME = "Could not parse date from log filename: {}"
MSG_NO_LOG_FILES_FOUND = "No log files found in directory: {}"
MSG_LOG_RETENTION_NEGATIVE = "Log retention days is negative ({}). Skipping cleanup."

# --- Agent Startup Messages ---
MSG_AGENT_STARTING = "Agent starting up..."
MSG_AGENT_STOPPING = "Agent shutting down..."

# --- Helper Functions for Messages (Optional) ---
def format_config_value_missing_info(key_name, section_name, default_value):
    return f"Info: Configuration key '{key_name}' in section '[{section_name}]' not found. Using default: '{default_value}'."

def format_config_section_missing_info(section_name):
    return f"Info: Configuration section '[{section_name}]' not found. Using defaults for all its settings."
