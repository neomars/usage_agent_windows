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
        # This could be NVMLError, etc.
        print(f"Error getting GPU usage: {e}")
        return None

def get_active_window_title():
    """Gets active window title. Returns empty string if unavailable or error."""
    if not gw:
        return ""
    try:
        active_window = gw.getActiveWindow()
        return active_window.title if active_window else ""
    except Exception as e: # pygetwindow can raise various errors depending on desktop env
        print(f"Error getting active window title: {e}")
        return ""
# --- End of Data Collection Functions ---

# --- Configuration and Logging Functions ---
def read_server_config():
    """Reads server address from config.ini. Returns None on error."""
    parser = configparser.ConfigParser()
    config_file = 'config.ini'
    if not os.path.exists(config_file):
        print(f"Error: Configuration file '{config_file}' not found.")
        return None
    try:
        parser.read(config_file)
        return parser.get('server', 'address')
    except (configparser.NoSectionError, configparser.NoOptionError, Exception) as e:
        print(f"Error reading configuration file '{config_file}': {e}")
        return None

def log_data_to_file(filename, data_json_string):
    """Appends a JSON string to the specified log file."""
    try:
        with open(filename, 'a') as f:
            f.write(data_json_string + '\n')
    except IOError as e:
        print(f"Error writing to log file '{filename}': {e}")

def send_data_to_server(server_address, json_payload):
    """
    Sends the JSON payload to the specified server address.
    Returns True on success (2xx response), False otherwise.
    """
    if not requests_available:
        # This check is technically redundant if main() already checks,
        # but good for function robustness if called from elsewhere.
        # print("Skipping send_data_to_server: requests module not available.")
        return False

    url = f"http://{server_address}/log_activity" # Assumed endpoint
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, data=json_payload, headers=headers, timeout=10)
        response.raise_for_status() # Raises HTTPError for 4xx/5xx responses
        print(f"Data successfully sent to {url} (Status: {response.status_code})")
        return True
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error sending data to {url}: {e}")
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error sending data to {url}: {e}")
    except requests.exceptions.Timeout as e:
        print(f"Timeout sending data to {url}: {e}")
    except requests.exceptions.RequestException as e: # Catch-all for other requests errors
        print(f"Error sending data to {url}: {e}")
    except Exception as e: # Catch any other unexpected errors
        print(f"Unexpected error in send_data_to_server: {e}")
    return False
# --- End of Configuration and Logging Functions ---

# --- Main Application ---
def main():
    """Main function for the agent."""
    server_address = read_server_config()
    # Startup messages
    if not server_address:
        print("Warning: Server address not found in configuration. Data will only be logged locally.")
    else:
        print(f"Server address: {server_address}")
        if not requests_available:
            print("Warning: 'requests' module not installed. Data will not be sent to the server.")

    if GPUtil and not GPUtil.getGPUs(): # One-time check/info if GPUtil is there but no GPUs
        print("Info: GPUtil is loaded, but no NVIDIA GPUs were found. GPU usage will be 'None'.")

    log_file_name = datetime.now().strftime('%y%m%d') + 'Log_Usage_Windows.log'
    print(f"Logging data to: {log_file_name}")

    while True:
        current_time = datetime.now()

        # Update log file name if day changes (for long-running agent)
        new_log_file_name = current_time.strftime('%y%m%d') + 'Log_Usage_Windows.log'
        if new_log_file_name != log_file_name:
            log_file_name = new_log_file_name
            print(f"New day, logging to: {log_file_name}")

        # Collect all data
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
            if cpu_val > 90:
                data_payload["cpu_usage_percent"] = cpu_rounded
            # else it remains None (as per "only include if > 90%, otherwise can be None")
            # For logging purposes, one might want to log the actual value always,
            # and only make it None for *sending*. But current logic matches prompt.

        if gpu_val is not None:
            gpu_rounded = round(gpu_val, 1)
            if gpu_val > 90: # Only include if > 90%
                data_payload["gpu_usage_percent"] = gpu_rounded
            # else it remains None

        # Log data locally
        json_data_for_log = None
        try:
            json_data_for_log = json.dumps(data_payload) # Create JSON for logging
            log_data_to_file(log_file_name, json_data_for_log)
        except TypeError as e:
            print(f"Error serializing data to JSON for logging: {e}. Payload was: {data_payload}")
            # Continue to try sending if server_address is set, as json_data might be fine for sending
            # or use a known safe version if serialization failed.
            # For now, if logging fails serialization, we probably don't send.
            json_data_for_log = None # Ensure it's None if dump failed

        # Send data to server
        if server_address and requests_available and json_data_for_log: # Only send if address, requests, and valid JSON
            # For sending, we might want a different payload if rules for None differ.
            # Current prompt: "cpu_usage_percent: result ... (only include if > 90%, otherwise can be None or omitted)"
            # The payload already reflects this: value is None if not >90.
            # If "omitted" was preferred, we'd need to build a new dict for sending.
            # Sticking to "None" is fine and consistent.
            send_data_to_server(server_address, json_data_for_log)
        elif server_address and requests_available and not json_data_for_log:
            print("Skipping data transmission due to JSON serialization error for logging.")


        # Sleep for the interval
        # psutil.cpu_percent(interval=1) already introduces a 1-second delay.
        # So, time.sleep(30) makes the total cycle time approx. 31 seconds + other processing.
        time.sleep(30)

if __name__ == "__main__":
    main()
