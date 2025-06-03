import configparser
import platform
import time
import os
import socket
import shutil
import json
import subprocess
from datetime import datetime, timedelta # Ensure timedelta is also imported
import messages_agent as messages # Updated import

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
    config_file = 'config.ini' # Assumes agent.py is run from client/ directory

    defaults = {
        'server_address': None,
        'cpu_alert_threshold': 90,
        'gpu_alert_threshold': 90,
        'log_folder': '.',
        'disk_space_alert_threshold_gb': 20,
        'windows_update_check_interval_hours': 24
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
        disk_threshold = parser.getint('agent_settings', 'disk_space_alert_threshold_gb', fallback=defaults['disk_space_alert_threshold_gb'])
        windows_update_interval = parser.getint('agent_settings', 'windows_update_check_interval_hours', fallback=defaults['windows_update_check_interval_hours'])

        return {
            'server_address': server_address,
            'cpu_alert_threshold': cpu_threshold,
            'gpu_alert_threshold': gpu_threshold,
            'log_folder': log_folder,
            'disk_space_alert_threshold_gb': disk_threshold,
            'windows_update_check_interval_hours': windows_update_interval
        }

    except Exception as e:
        print(messages.MSG_CONFIG_ERROR_READING.format(e))
        return defaults


def log_data_to_file(log_path, data_json_string):
    """Appends a JSON string to the specified log file."""
    try:
        # Ensure log directory exists (e.g., if log_folder is client/logs or ./logs)
        # os.path.dirname will correctly handle paths like '.' or 'logs'
        log_dir = os.path.dirname(log_path)
        if log_dir and not os.path.exists(log_dir): # Check if log_dir is not empty string
             os.makedirs(log_dir, exist_ok=True)
        elif not log_dir and not os.path.exists(log_path) and not os.path.isdir(log_path): # Handle case where log_path is just filename in current dir
             pass # No directory to create if log_dir is empty (current directory)

        with open(log_path, 'a') as f:
            f.write(data_json_string + '\n')
    except IOError as e:
        print(messages.MSG_LOG_FILE_WRITING_ERROR.format(log_path, e))
    except Exception as e:
        print(messages.MSG_LOG_PATH_ERROR.format(log_path, e)) # Changed to log_path for better error


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
        print(messages.MSG_SENDING_DATA_TO_SERVER.format(url, response.status_code))
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
    print(messages.MSG_AGENT_STARTING)
    app_config = load_app_config()

    print(messages.MSG_CONFIG_LOADED_HEADER)
    print(messages.MSG_CONFIG_SERVER_ADDRESS.format(app_config.get('server_address', 'Not configured')))
    print(messages.MSG_CONFIG_CPU_THRESHOLD.format(app_config.get('cpu_alert_threshold', 90)))
    print(messages.MSG_CONFIG_GPU_THRESHOLD.format(app_config.get('gpu_alert_threshold', 90)))
    print(messages.MSG_CONFIG_LOG_FOLDER.format(app_config.get('log_folder', '.')))
    print(messages.MSG_CONFIG_DISK_THRESHOLD.format(app_config.get('disk_space_alert_threshold_gb', 20))) # Using .get for safety, though load_app_config ensures it.
    print(messages.MSG_CONFIG_WINDOWS_UPDATE_INTERVAL.format(app_config.get('windows_update_check_interval_hours', 24))) # Using .get for safety
    print(messages.MSG_CONFIG_FOOTER)

    server_address = app_config.get('server_address')

    if not server_address:
        print(messages.MSG_SERVER_ADDRESS_NOT_CONFIGURED)
    elif not requests_available:
        pass # Message already printed at import time

    if GPUtil and not GPUtil.getGPUs() and GPUtil is not None :
        print(messages.MSG_GPUTIL_NO_GPUS)

    log_folder_base = app_config.get('log_folder', '.')
    initial_log_file_name = datetime.now().strftime('%y%m%d') + 'Log_Usage_Windows.log'
    initial_log_path = os.path.join(log_folder_base, initial_log_file_name)
    # Ensure initial log directory exists before first log message about it
    try:
        if log_folder_base and not os.path.exists(log_folder_base):
            os.makedirs(log_folder_base, exist_ok=True)
    except Exception as e:
        print(messages.MSG_LOG_PATH_ERROR.format(log_folder_base, e))

    print(messages.MSG_LOGGING_TO_FILE.format(initial_log_path))

    last_logged_day_str = ""
    last_windows_update_check_time = None # Initialize here

    while True:
        try:
            # Windows Update Check Logic
            try:
                interval_hours = app_config.get('windows_update_check_interval_hours', 24)
                should_check_updates = False
                now_for_update_check = datetime.now() # Use a consistent 'now' for this block

                if last_windows_update_check_time is None:
                    should_check_updates = True # Check on first run
                else:
                    if (now_for_update_check - last_windows_update_check_time).total_seconds() >= interval_hours * 3600:
                        should_check_updates = True

                if should_check_updates:
                    print(messages.MSG_WINDOWS_UPDATE_CHECK_STARTING)
                    # Correct path assuming agent.py is in client/ and script is also in client/
                    powershell_script_path = os.path.join(os.path.dirname(__file__), 'get_windows_update_status.ps1')

                    process = subprocess.run(
                        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", powershell_script_path],
                        capture_output=True, text=True, check=False, timeout=300 # 5 min timeout
                    )

                    current_log_path_for_wu = os.path.join(app_config.get('log_folder', '.'), datetime.now().strftime('%y%m%d') + 'Log_Usage_Windows.log')


                    if process.returncode == 0:
                        try:
                            update_status_data = json.loads(process.stdout)

                            windows_update_payload = {
                                "log_type": "windows_update",
                                "timestamp": now_for_update_check.isoformat(),
                                "netbios_name": get_netbios_name(),
                                "wsus_server": update_status_data.get("wsusServer"),
                                "last_scan_time": update_status_data.get("lastScanTime"),
                                "pending_security_updates_count": update_status_data.get("pendingSecurityUpdatesCount"),
                                "reboot_pending": update_status_data.get("rebootPending"),
                                "overall_status": update_status_data.get("overallStatus"),
                                "script_error_message": update_status_data.get("errorMessage")
                            }

                            json_wu_payload = json.dumps(windows_update_payload)
                            # Need current_log_path here. It's defined later in the loop.
                            # This means we either pass current_log_path into this section,
                            # or define it earlier. Let's assume current_log_path needs to be
                            # determined based on current_time for the daily log rotation.
                            # For simplicity here, I'll use the 'current_log_path_for_wu'
                            # which uses the 'now_for_update_check' time.
                            log_data_to_file(current_log_path_for_wu, json_wu_payload)

                            server_address_local = app_config.get('server_address') # re-fetch in case it changes? No, app_config is fixed per agent run.
                            if server_address_local and requests_available:
                                send_data_to_server(server_address_local, json_wu_payload)

                            print(messages.MSG_WINDOWS_UPDATE_CHECK_COMPLETED.format(windows_update_payload.get("overall_status")))

                        except json.JSONDecodeError as e:
                            print(messages.MSG_WINDOWS_UPDATE_JSON_ERROR.format(e, process.stdout))
                        except Exception as e:
                            print(messages.MSG_WINDOWS_UPDATE_PROCESSING_ERROR.format(e))
                    else:
                        print(messages.MSG_WINDOWS_UPDATE_SCRIPT_ERROR.format(process.returncode, process.stderr))

                    last_windows_update_check_time = now_for_update_check

            except Exception as e:
                print(messages.MSG_WINDOWS_UPDATE_SCHEDULING_ERROR.format(e))

            # Regular data collection starts here
            current_time = datetime.now() # This current_time is for the main machine/app payloads
            current_day_str = current_time.strftime('%y%m%d')

            log_file_name_only = current_day_str + 'Log_Usage_Windows.log'
            current_log_path = os.path.join(log_folder_base, log_file_name_only)

            if current_day_str != last_logged_day_str and last_logged_day_str != "":
                print(messages.MSG_LOG_FILE_DAILY_CHANGE.format(current_log_path))
            last_logged_day_str = current_day_str

            netbios_name = get_netbios_name()
            ip_address = get_ip_address()
            free_space_gb_val = get_free_disk_space('C:\\') # This returns the raw GB value or None

            # Round the value if it's not None, for consistent representation
            current_free_space_gb_rounded = None
            if free_space_gb_val is not None:
                current_free_space_gb_rounded = round(free_space_gb_val, 2)

            # Determine if it should be included in the payload based on threshold
            payload_free_disk_space_gb = None
            if current_free_space_gb_rounded is not None:
                # disk_space_alert_threshold_gb is already part of app_config
                if current_free_space_gb_rounded < app_config['disk_space_alert_threshold_gb']:
                    payload_free_disk_space_gb = current_free_space_gb_rounded

            try:
                os_name = platform.system()
                os_version = platform.release()
            except Exception as e:
                print(f"Error getting OS info: {e}") # Or use a message from messages_agent.py
                os_name = "N/A"
                os_version = "N/A"

            cpu_val = get_cpu_usage()
            gpu_val = get_gpu_usage()
            active_title = get_active_window_title()

            cpu_alert_threshold = app_config.get('cpu_alert_threshold', 90) # Default 90 if not in config
            gpu_alert_threshold = app_config.get('gpu_alert_threshold', 90) # Default 90 if not in config

            final_cpu_usage = None
            if cpu_val is not None:
                if cpu_val > cpu_alert_threshold:
                    final_cpu_usage = round(cpu_val, 1)

            final_gpu_usage = None
            if gpu_val is not None:
                if gpu_val > gpu_alert_threshold:
                    final_gpu_usage = round(gpu_val, 1)

            machine_payload = {
                "log_type": "machine",
                "timestamp": current_time.isoformat(),
                "netbios_name": netbios_name,
                "ip_address": ip_address,
                "free_disk_space_gb": payload_free_disk_space_gb, # Use the thresholded and rounded value
                "cpu_usage_percent": final_cpu_usage,
                "gpu_usage_percent": final_gpu_usage,
                "os_name": os_name,                               # New field
                "os_version": os_version                          # New field
            }

            application_payload = {
                "log_type": "application",
                "timestamp": current_time.isoformat(),
                "netbios_name": netbios_name,
                "active_window_title": active_title
            }

            # Process and log machine_payload
            json_machine_data_for_log = None
            try:
                json_machine_data_for_log = json.dumps(machine_payload)
                log_data_to_file(current_log_path, json_machine_data_for_log)
            except TypeError as e:
                print(messages.MSG_JSON_SERIALIZATION_ERROR.format("machine data", e, machine_payload))
                json_machine_data_for_log = None # Ensure it's None if serialization fails

            if server_address and requests_available:
                if json_machine_data_for_log:
                    send_data_to_server(server_address, json_machine_data_for_log)
                else:
                    print(messages.MSG_SEND_SKIPPING_JSON_ERROR.format("machine data"))

            # Process and log application_payload
            json_app_data_for_log = None
            try:
                json_app_data_for_log = json.dumps(application_payload)
                log_data_to_file(current_log_path, json_app_data_for_log)
            except TypeError as e:
                print(messages.MSG_JSON_SERIALIZATION_ERROR.format("application data", e, application_payload))
                json_app_data_for_log = None # Ensure it's None

            if server_address and requests_available:
                if json_app_data_for_log:
                    send_data_to_server(server_address, json_app_data_for_log)
                else:
                    print(messages.MSG_SEND_SKIPPING_JSON_ERROR.format("application data"))

            time.sleep(30)
        except Exception as e:
            print(messages.MSG_UNEXPECTED_ERROR_MAIN_LOOP.format(e))
            time.sleep(60)

if __name__ == "__main__":
    main()
