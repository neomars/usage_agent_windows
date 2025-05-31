import configparser
import time
import os
import socket
import shutil
import json
from datetime import datetime

# --- Attempt to import optional modules ---
try:
    import psutil
except ImportError:
    print("Error: psutil module not found. CPU usage will not be monitored. Please install it using 'pip install psutil'")
    psutil = None

try:
    import GPUtil
except ImportError:
    print("Info: GPUtil module not found. GPU usage will not be monitored. Install with 'pip install GPUtil'")
    GPUtil = None
except Exception as e: # Catch other init errors for GPUtil (e.g. driver issues)
    print(f"Info: GPUtil module could not be initialized ({e}). GPU usage will not be monitored.")
    GPUtil = None

try:
    import pygetwindow as gw
except ImportError:
    print("Info: pygetwindow module not found. Active window title will not be monitored. Install with 'pip install pygetwindow'")
    gw = None
except Exception as e: # Catch other init errors for pygetwindow
    print(f"Info: pygetwindow module could not be initialized ({e}). Active window title will not be monitored.")
    gw = None

try:
    import requests
    requests_available = True
except ImportError:
    print("Info: requests module not found. Data will not be sent to server. Install with 'pip install requests'")
    requests_available = False
# --- End of imports ---

# --- Data Collection Functions ---
# (get_netbios_name, get_ip_address, get_free_disk_space, get_cpu_usage, get_gpu_usage, get_active_window_title remain unchanged)
def get_netbios_name():
    """Gets the NetBIOS name of the machine."""
    try:
        return socket.gethostname()
    except Exception as e:
        print(f"Error getting NetBIOS name: {e}")
        return "N/A"

def get_ip_address():
    """Gets the IP address of the machine."""
    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except socket.gaierror as e:
        print(f"Error resolving hostname to IP address: {e}")
        return "N/A"
    except Exception as e:
        print(f"Error getting IP address: {e}")
        return "N/A"

def get_free_disk_space(drive="C:\\"):
    """Gets the free disk space for a given drive. Returns None on error."""
    try:
        total, used, free = shutil.disk_usage(drive)
        return free / (1024**3) # GB
    except FileNotFoundError:
        print(f"Error: Drive '{drive}' not found.")
        return None
    except Exception as e:
        print(f"Error getting free disk space for drive '{drive}': {e}")
        return None

def get_cpu_usage():
    """Gets CPU usage. Returns None if unavailable or error."""
    if not psutil:
        return None
    try:
        return psutil.cpu_percent(interval=1) # Blocking call for 1 second
    except Exception as e:
        print(f"Error getting CPU usage: {e}")
        return None

def get_gpu_usage():
    """Gets GPU usage for the first NVIDIA GPU. Returns None if unavailable or error."""
    if not GPUtil:
        return None
    try:
        gpus = GPUtil.getGPUs()
        if not gpus:
            return None
        return gpus[0].load * 100 # Percentage
    except Exception as e:
        print(f"Error getting GPU usage: {e}")
        return None

def get_active_window_title():
    """Gets active window title. Returns empty string if unavailable or error."""
    if not gw:
        return ""
    try:
        active_window = gw.getActiveWindow()
        return active_window.title if active_window else ""
    except Exception as e:
        print(f"Error getting active window title: {e}")
        return ""
# --- End of Data Collection Functions ---

# --- Configuration and Logging Functions ---
def load_app_config():
    """
    Reads agent configuration from config.ini.
    Applies defaults for missing settings.
    Returns a dictionary of configuration settings.
    """
    parser = configparser.ConfigParser()
    config_file = 'config.ini'

    defaults = {
        'server_address': None,
        'cpu_alert_threshold': 90,
        'gpu_alert_threshold': 90,
        'log_folder': '.'
    }

    if not os.path.exists(config_file):
        print(f"Warning: Configuration file '{config_file}' not found. Using default settings.")
        return defaults

    try:
        parser.read(config_file)

        # Read server address
        server_address = parser.get('server', 'address', fallback=defaults['server_address'])

        # Read agent settings with fallbacks
        cpu_threshold = parser.getint('agent_settings', 'cpu_alert_threshold', fallback=defaults['cpu_alert_threshold'])
        gpu_threshold = parser.getint('agent_settings', 'gpu_alert_threshold', fallback=defaults['gpu_alert_threshold'])
        log_folder = parser.get('agent_settings', 'log_folder', fallback=defaults['log_folder'])

        return {
            'server_address': server_address,
            'cpu_alert_threshold': cpu_threshold,
            'gpu_alert_threshold': gpu_threshold,
            'log_folder': log_folder
        }

    except Exception as e: # Catch any other error during config parsing
        print(f"Error reading configuration file '{config_file}': {e}. Using default settings.")
        return defaults


def log_data_to_file(log_path, data_json_string): # Changed 'filename' to 'log_path' for clarity
    """Appends a JSON string to the specified log file."""
    try:
        # Ensure log directory exists (useful if log_folder is not just '.')
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, 'a') as f:
            f.write(data_json_string + '\n')
    except IOError as e:
        print(f"Error writing to log file '{log_path}': {e}")
    except Exception as e: # Catch other errors like permission issues with makedirs
        print(f"Error ensuring log path '{log_path}' exists or writing to file: {e}")


def send_data_to_server(server_address, json_payload):
    """
    Sends the JSON payload to the specified server address.
    Returns True on success (2xx response), False otherwise.
    """
    if not requests_available:
        return False

    url = f"http://{server_address}/log_activity"
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, data=json_payload, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"Data successfully sent to {url} (Status: {response.status_code})")
        return True
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error sending data to {url}: {e}")
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error sending data to {url}: {e}")
    except requests.exceptions.Timeout as e:
        print(f"Timeout sending data to {url}: {e}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending data to {url}: {e}")
    except Exception as e:
        print(f"Unexpected error in send_data_to_server: {e}")
    return False
# --- End of Configuration and Logging Functions ---

# --- Main Application ---
def main():
    """Main function for the agent."""
    app_config = load_app_config()

    # Diagnostic print of loaded configuration
    print(f"--- Agent Configuration ---")
    print(f"Server Address: {app_config.get('server_address', 'Not configured')}")
    print(f"CPU Alert Threshold: {app_config.get('cpu_alert_threshold', 90)}%") # Fallback for print, though load_app_config sets it
    print(f"GPU Alert Threshold: {app_config.get('gpu_alert_threshold', 90)}%") # Fallback for print
    print(f"Log Folder: {app_config.get('log_folder', '.')}")                      # Fallback for print
    print(f"---------------------------")

    server_address = app_config.get('server_address') # Use the loaded server address

    if not server_address:
        print("Warning: Server address not configured in 'config.ini'. Data will only be logged locally.")
    elif not requests_available: # Check this only if server_address is present
        print("Warning: 'requests' module not installed. Data will not be sent to the server.")

    if GPUtil and not GPUtil.getGPUs():
        print("Info: GPUtil is loaded, but no NVIDIA GPUs were found. GPU usage will be 'None'.")

    # Base log folder from config
    log_folder_base = app_config.get('log_folder', '.')


    while True:
        current_time = datetime.now()

        # Construct log file path using log_folder from config
        # Filename itself is still daily
        log_file_name_only = current_time.strftime('%y%m%d') + 'Log_Usage_Windows.log'
        current_log_path = os.path.join(log_folder_base, log_file_name_only)

        # This dynamic check for log_file_path change is now more complex if log_folder_base itself could change
        # Assuming log_folder_base is static for the agent's run once loaded.
        # If log_file_name (path) needs to be printed when it changes (e.g. new day):
        # This simple print might need adjustment if we want to avoid printing it every loop.
        # For now, it's fine, but it will print the full path every time.
        # A static variable to track the last printed path could be used.
        # print(f"Current log file path: {current_log_path}") # Can be noisy

        # Collect all data
        netbios_name = get_netbios_name()
        ip_address = get_ip_address()
        free_space_gb_val = get_free_disk_space('C:\\')
        free_space_gb = round(free_space_gb_val, 2) if free_space_gb_val is not None else None

        # Use loaded thresholds for CPU/GPU data payload decisions
        cpu_val = get_cpu_usage()
        gpu_val = get_gpu_usage()
        active_title = get_active_window_title()

        data_payload = {
            "timestamp": current_time.isoformat(),
            "netbios_name": netbios_name,
            "ip_address": ip_address,
            "free_disk_space_gb": free_space_gb,
            "cpu_usage_percent": None,
            "gpu_usage_percent": None,
            "active_window_title": active_title
        }

        if cpu_val is not None:
            cpu_rounded = round(cpu_val, 1)
            # Use threshold from config for deciding if it's an "alert" level for payload
            if cpu_val > app_config.get('cpu_alert_threshold', 90):
                data_payload["cpu_usage_percent"] = cpu_rounded
            # else it remains None, meaning not high enough to be reported as per original logic for this field

        if gpu_val is not None:
            gpu_rounded = round(gpu_val, 1)
            if gpu_val > app_config.get('gpu_alert_threshold', 90):
                data_payload["gpu_usage_percent"] = gpu_rounded
            # else it remains None

        # Log data locally
        json_data_for_log = None
        try:
            json_data_for_log = json.dumps(data_payload)
            log_data_to_file(current_log_path, json_data_for_log) # Use full path
        except TypeError as e:
            print(f"Error serializing data to JSON for logging: {e}. Payload was: {data_payload}")
            json_data_for_log = None

        # Send data to server
        if server_address and requests_available and json_data_for_log:
            send_data_to_server(server_address, json_data_for_log)
        elif server_address and requests_available and not json_data_for_log:
            print("Skipping data transmission due to JSON serialization error for logging.")

        time.sleep(30)

if __name__ == "__main__":
    main()
