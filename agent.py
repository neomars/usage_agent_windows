import configparser
import time
import os
import socket
import shutil
import json
from datetime import datetime
import messages # Import the new messages module

# --- Attempt to import optional modules ---
try:
    import psutil
except ImportError:
    print(messages.MSG_PSUTIL_NOT_AVAILABLE)
    psutil = None

try:
    import GPUtil
except ImportError:
    print(messages.MSG_GPUTIL_NOT_AVAILABLE)
    GPUtil = None
except Exception as e:
    print(messages.MSG_GPUTIL_INIT_ERROR.format(e))
    GPUtil = None

try:
    import pygetwindow as gw
except ImportError:
    print(messages.MSG_PYGETWINDOW_NOT_AVAILABLE)
    gw = None
except Exception as e:
    print(messages.MSG_PYGETWINDOW_INIT_ERROR.format(e))
    gw = None

try:
    import requests
    requests_available = True
except ImportError:
    print(messages.MSG_REQUESTS_NOT_AVAILABLE)
    requests_available = False
# --- End of imports ---

# --- Data Collection Functions ---
def get_netbios_name():
    """Gets the NetBIOS name of the machine."""
    try:
        return socket.gethostname()
    except Exception as e:
        print(messages.MSG_ERROR_GETTING_NETBIOS.format(e))
        return "N/A"

def get_ip_address():
    """Gets the IP address of the machine."""
    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except socket.gaierror as e:
        print(messages.MSG_ERROR_RESOLVING_IP.format(e))
        return "N/A"
    except Exception as e:
        print(messages.MSG_ERROR_GETTING_IP.format(e))
        return "N/A"

def get_free_disk_space(drive="C:\\"):
    """Gets the free disk space for a given drive. Returns None on error."""
    try:
        total, used, free = shutil.disk_usage(drive)
        return free / (1024**3) # GB
    except FileNotFoundError:
        print(messages.MSG_ERROR_DRIVE_NOT_FOUND.format(drive))
        return None
    except Exception as e:
        print(messages.MSG_ERROR_GETTING_DISK_SPACE.format(drive, e))
        return None

def get_cpu_usage():
    """Gets CPU usage. Returns None if unavailable or error."""
    if not psutil:
        return None
    try:
        return psutil.cpu_percent(interval=1)
    except Exception as e:
        print(messages.MSG_ERROR_GETTING_CPU.format(e))
        return None

def get_gpu_usage():
    """Gets GPU usage for the first NVIDIA GPU. Returns None if unavailable or error."""
    if not GPUtil:
        return None
    try:
        gpus = GPUtil.getGPUs()
        if not gpus:
            # This specific info message is already in messages.py, used in main()
            return None
        return gpus[0].load * 100
    except Exception as e:
        print(messages.MSG_ERROR_GETTING_GPU.format(e))
        return None

def get_active_window_title():
    """Gets active window title. Returns empty string if unavailable or error."""
    if not gw:
        return ""
    try:
        active_window = gw.getActiveWindow()
        return active_window.title if active_window else ""
    except Exception as e:
        print(messages.MSG_ERROR_GETTING_ACTIVE_WINDOW.format(e))
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
        print(messages.MSG_CONFIG_FILE_NOT_FOUND)
        return defaults

    try:
        parser.read(config_file)

        server_address = parser.get('server', 'address', fallback=defaults['server_address'])

        cpu_threshold = parser.getint('agent_settings', 'cpu_alert_threshold', fallback=defaults['cpu_alert_threshold'])
        gpu_threshold = parser.getint('agent_settings', 'gpu_alert_threshold', fallback=defaults['gpu_alert_threshold'])
        log_folder = parser.get('agent_settings', 'log_folder', fallback=defaults['log_folder'])

        # Optional: Print info about defaults being used if specific keys were missing
        # This can be done by comparing parser.has_option with the returned value.
        # For now, the broad error message or file not found is considered sufficient.

        return {
            'server_address': server_address,
            'cpu_alert_threshold': cpu_threshold,
            'gpu_alert_threshold': gpu_threshold,
            'log_folder': log_folder
        }

    except Exception as e:
        print(messages.MSG_CONFIG_ERROR_READING.format(e))
        return defaults


def log_data_to_file(log_path, data_json_string):
    """Appends a JSON string to the specified log file."""
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, 'a') as f:
            f.write(data_json_string + '\n')
    except IOError as e: # More specific for file open/write issues
        print(messages.MSG_LOG_FILE_WRITING_ERROR.format(log_path, e))
    except Exception as e:
        print(messages.MSG_LOG_PATH_ERROR.format(os.path.dirname(log_path), e))


def send_data_to_server(server_address, json_payload):
    """
    Sends the JSON payload to the specified server address.
    Returns True on success (2xx response), False otherwise.
    """
    if not requests_available: # Should not be called if false, but defensive.
        return False

    url = f"http://{server_address}/log_activity"
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, data=json_payload, headers=headers, timeout=10)
        response.raise_for_status()
        print(messages.MSG_SENDING_DATA_TO_SERVER.format(url, response.status_code)) # Using the more specific success message
        return True
    except requests.exceptions.HTTPError as e:
        print(messages.MSG_SEND_HTTP_ERROR.format(url, e))
    except requests.exceptions.ConnectionError as e:
        print(messages.MSG_SEND_CONNECTION_ERROR.format(url, e))
    except requests.exceptions.Timeout as e:
        print(messages.MSG_SEND_TIMEOUT_ERROR.format(url, e))
    except requests.exceptions.RequestException as e:
        print(messages.MSG_SEND_REQUEST_EXCEPTION.format(url, e))
    except Exception as e:
        print(messages.MSG_SEND_UNEXPECTED_ERROR.format(e))
    return False
# --- End of Configuration and Logging Functions ---

# --- Main Application ---
def main():
    """Main function for the agent."""
    print(messages.MSG_AGENT_STARTING) # Added agent starting message
    app_config = load_app_config()

    print(messages.MSG_CONFIG_LOADED_HEADER)
    print(messages.MSG_CONFIG_SERVER_ADDRESS.format(app_config.get('server_address', 'Not configured')))
    print(messages.MSG_CONFIG_CPU_THRESHOLD.format(app_config.get('cpu_alert_threshold', 90)))
    print(messages.MSG_CONFIG_GPU_THRESHOLD.format(app_config.get('gpu_alert_threshold', 90)))
    print(messages.MSG_CONFIG_LOG_FOLDER.format(app_config.get('log_folder', '.')))
    print(messages.MSG_CONFIG_FOOTER)

    server_address = app_config.get('server_address')

    if not server_address:
        print(messages.MSG_SERVER_ADDRESS_NOT_CONFIGURED)
    elif not requests_available:
        # This message is already printed when requests import fails.
        # Redundant here unless we want to emphasize it again in context of server_address being present.
        # For now, relying on the import-time message.
        pass


    if GPUtil and not GPUtil.getGPUs() and GPUtil is not None : # Check GPUtil is not None before using it
        print(messages.MSG_GPUTIL_NO_GPUS)

    log_folder_base = app_config.get('log_folder', '.')
    # Initial log path for the first message (if any) about where logs are going.
    # This might be slightly off if agent starts exactly at midnight and day changes before first log.
    # But generally ok for an initial print.
    initial_log_file_name = datetime.now().strftime('%y%m%d') + 'Log_Usage_Windows.log'
    initial_log_path = os.path.join(log_folder_base, initial_log_file_name)
    print(messages.MSG_LOGGING_TO_FILE.format(initial_log_path))


    last_logged_day_str = "" # To track when the day changes for logging message

    while True:
        try: # Added try-except for the main loop
            current_time = datetime.now()
            current_day_str = current_time.strftime('%y%m%d')

            log_file_name_only = current_day_str + 'Log_Usage_Windows.log'
            current_log_path = os.path.join(log_folder_base, log_file_name_only)

            if current_day_str != last_logged_day_str and last_logged_day_str != "": # Avoid printing on first ever loop
                print(messages.MSG_LOG_FILE_DAILY_CHANGE.format(current_log_path))
            last_logged_day_str = current_day_str

            # Data Collection
            netbios_name = get_netbios_name()
            ip_address = get_ip_address()
            free_space_gb_val = get_free_disk_space('C:\\')
            free_space_gb = round(free_space_gb_val, 2) if free_space_gb_val is not None else None

            cpu_val = get_cpu_usage()
            gpu_val = get_gpu_usage()
            active_title = get_active_window_title()

            # Prepare data payload
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
                if cpu_val > app_config.get('cpu_alert_threshold', 90):
                    data_payload["cpu_usage_percent"] = cpu_rounded

            if gpu_val is not None:
                gpu_rounded = round(gpu_val, 1)
                if gpu_val > app_config.get('gpu_alert_threshold', 90):
                    data_payload["gpu_usage_percent"] = gpu_rounded

            # Log data locally
            json_data_for_log = None
            try:
                json_data_for_log = json.dumps(data_payload)
                log_data_to_file(current_log_path, json_data_for_log)
            except TypeError as e:
                print(messages.MSG_JSON_SERIALIZATION_ERROR.format(e, data_payload))
                json_data_for_log = None

            # Send data to server
            if server_address and requests_available and json_data_for_log:
                send_data_to_server(server_address, json_data_for_log)
            elif server_address and requests_available and not json_data_for_log:
                print(messages.MSG_SEND_SKIPPING_JSON_ERROR)

            time.sleep(30)
        except Exception as e:
            print(messages.MSG_UNEXPECTED_ERROR_MAIN_LOOP.format(e))
            # Decide on recovery strategy: continue, exit, or wait longer?
            # For now, just print and wait before retrying loop to avoid rapid-fire errors.
            time.sleep(60)


if __name__ == "__main__":
    main()
