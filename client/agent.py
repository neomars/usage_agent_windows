import configparser
import platform
import time
import os
import socket
import shutil
import json
# subprocess removed
from datetime import datetime, timedelta, date # Ensure date is also imported
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

# --- Log Cleanup Function ---
def cleanup_old_logs(log_folder_path, retention_days):
    print(messages.MSG_LOG_CLEANUP_STARTED)

    if retention_days < 0:
        print(messages.MSG_LOG_RETENTION_NEGATIVE.format(retention_days))
        return

    try:
        if not os.path.isdir(log_folder_path):
            print(f"Log folder not found: {log_folder_path}") # Or use a message
            return

        log_files_found = False
        today = date.today()

        for filename in os.listdir(log_folder_path):
            if filename.endswith("Log_Usage_Windows.log") and len(filename) == (6 + len("Log_Usage_Windows.log")):
                log_files_found = True
                date_str = filename[:6]
                try:
                    log_file_date = datetime.strptime(date_str, "%y%m%d").date()
                    age_in_days = (today - log_file_date).days

                    if age_in_days > retention_days:
                        file_path_to_delete = os.path.join(log_folder_path, filename)
                        try:
                            os.remove(file_path_to_delete)
                            print(messages.MSG_DELETING_OLD_LOG.format(file_path_to_delete, age_in_days))
                        except OSError as e:
                            print(messages.MSG_ERROR_DELETING_LOG.format(file_path_to_delete, e))

                except ValueError:
                    print(messages.MSG_ERROR_PARSING_LOG_FILENAME.format(filename))

        if not log_files_found:
            print(messages.MSG_NO_LOG_FILES_FOUND.format(log_folder_path))

    except Exception as e:
        print(f"An unexpected error occurred during log cleanup: {e}")

    print(messages.MSG_LOG_CLEANUP_COMPLETED)

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
        'ping_interval_seconds': 60,
        'log_retention_days': 14
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
        ping_interval = parser.getint('agent_settings', 'ping_interval_seconds', fallback=defaults['ping_interval_seconds'])
        log_retention = parser.getint('agent_settings', 'log_retention_days', fallback=defaults['log_retention_days'])

        return {
            'server_address': server_address,
            'cpu_alert_threshold': cpu_threshold,
            'gpu_alert_threshold': gpu_threshold,
            'log_folder': log_folder,
            'disk_space_alert_threshold_gb': disk_threshold,
            'ping_interval_seconds': ping_interval,
            'log_retention_days': log_retention
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
    # Initial "Agent starting up" message
    print(messages.MSG_AGENT_STARTING) # Moved earlier

    app_config = load_app_config()

    # Print loaded configuration
    print(messages.MSG_CONFIG_LOADED_HEADER)
    print(messages.MSG_CONFIG_SERVER_ADDRESS.format(app_config.get('server_address', 'Not configured')))
    print(messages.MSG_CONFIG_CPU_THRESHOLD.format(app_config.get('cpu_alert_threshold', 90)))
    print(messages.MSG_CONFIG_GPU_THRESHOLD.format(app_config.get('gpu_alert_threshold', 90)))
    print(messages.MSG_CONFIG_LOG_FOLDER.format(app_config.get('log_folder', '.')))
    print(messages.MSG_CONFIG_DISK_THRESHOLD.format(app_config.get('disk_space_alert_threshold_gb', 20))) # Using .get for safety, though load_app_config ensures it.
    print(messages.MSG_CONFIG_PING_INTERVAL.format(app_config.get('ping_interval_seconds', 60))) # Using .get for safety
    print(messages.MSG_CONFIG_LOG_RETENTION.format(app_config.get('log_retention_days', 14))) # Using .get for safety
    print(messages.MSG_CONFIG_FOOTER)

    # Perform log cleanup at startup
    log_folder_for_cleanup = app_config.get('log_folder', '.')
    retention_days_for_cleanup = app_config.get('log_retention_days', 14)
    cleanup_old_logs(log_folder_for_cleanup, retention_days_for_cleanup)

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
    # last_windows_update_check_time = None # Line removed
    last_ping_time = None

    while True:
        try:
            # Windows Update Check Logic REMOVED

            # Ping Server Logic (scheduling part)
            try:
                current_ping_interval_seconds = app_config.get('ping_interval_seconds', 60)
                should_send_ping = False
                now_for_ping = datetime.now() # Use a consistent 'now' for this check block

                if last_ping_time is None: # Send on first run
                    should_send_ping = True
                else:
                    if (now_for_ping - last_ping_time).total_seconds() >= current_ping_interval_seconds:
                        should_send_ping = True

                if should_send_ping:
                    print(messages.MSG_ATTEMPTING_SERVER_PING)

                    ping_payload = {
                        "log_type": "ping",
                        "timestamp": now_for_ping.isoformat(),
                        "netbios_name": get_netbios_name(),
                        "ip_address": get_ip_address()
                    }

                    local_ping_status_log = {
                        "event_type": "ping_status",
                        "timestamp": now_for_ping.isoformat(),
                        "server_address": server_address if server_address else "N/A"
                        # "status" will be added based on outcome
                    }

                    # current_log_path is defined later in the loop, so for this specific log:
                    current_log_path_for_ping = os.path.join(app_config.get('log_folder', '.'), now_for_ping.strftime('%y%m%d') + 'Log_Usage_Windows.log')

                    if server_address and requests_available:
                        try:
                            ping_payload_json = json.dumps(ping_payload)

                            if send_data_to_server(server_address, ping_payload_json):
                                local_ping_status_log["status"] = "ok"
                            else:
                                local_ping_status_log["status"] = "false"
                                # Detailed error is already printed to console by send_data_to_server

                        except Exception as e:
                            local_ping_status_log["status"] = "false"
                            # Print a concise error to console for this specific failure context
                            print(f"Error during ping payload preparation or JSON dump: {str(e)}")
                    else:
                        local_ping_status_log["status"] = "false"
                        if not server_address:
                            print(messages.MSG_PING_SKIPPED_NO_SERVER_DETAILS) # Keep console informed
                        elif not requests_available:
                            print(messages.MSG_PING_SKIPPED_NO_REQUESTS_DETAILS) # Keep console informed

                    try:
                        log_data_to_file(current_log_path_for_ping, json.dumps(local_ping_status_log))
                    except Exception as e:
                        print(messages.MSG_ERROR_WRITING_PING_STATUS_LOG.format(str(e)))

                    last_ping_time = now_for_ping # Update last_ping_time after attempt

            except Exception as e:
                # This will now use a message if defined, or fallback to f-string.
                # Assuming a generic scheduling error message might be added later if needed.
                print(f"Error in ping scheduling logic: {e}")

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
