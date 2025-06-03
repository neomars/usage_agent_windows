from flask import Flask, request, jsonify, render_template
import sys
from datetime import datetime, timedelta
from . import sql_ddl  # Relative import
# Ensure this is present, it was in the original code so should be fine.
from . import sql_dml  # Relative import
from . import messages_server as messages # Relative import for server messages
import configparser
import os

# Determine the directory where this script is located for robust file path handling
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_CONFIG_FILENAME = 'db_config.ini' # Define filename centrally
DB_CONFIG_PATH = os.path.join(SCRIPT_DIR, DB_CONFIG_FILENAME)


# --- Database Configuration Loading ---
def load_db_config():
    """Loads database configuration from db_config.ini or uses defaults."""
    config = configparser.ConfigParser()
    db_settings = {
        'host': 'localhost', 'user': None, 'password': None, 'name': 'agent_data_db'
    }

    if os.path.exists(DB_CONFIG_PATH):
        try:
            config.read(DB_CONFIG_PATH)
            if 'database' in config:
                db_settings['host'] = config.get('database', 'host', fallback=db_settings['host'])
                db_settings['user'] = config.get('database', 'user', fallback=None)
                db_settings['password'] = config.get('database', 'password', fallback=None)
                db_settings['name'] = config.get('database', 'name', fallback=db_settings['name'])

                if not db_settings['user'] or not db_settings['password']:
                    # Use message constant from messages_server
                    print(messages.SERVER_DB_CONFIG_KEY_MISSING.format('user', 'password', DB_CONFIG_FILENAME))
            else:
                print(messages.SERVER_DB_CONFIG_SECTION_MISSING.format(DB_CONFIG_FILENAME))
        except configparser.Error as e:
            print(messages.SERVER_DB_CONFIG_PARSING_ERROR.format(DB_CONFIG_FILENAME, e))
    else:
        print(messages.SERVER_DB_CONFIG_FILE_NOT_FOUND.format(DB_CONFIG_FILENAME))
        # Updated guidance on how to run setup_database.py
        print(messages.SERVER_DB_CONFIG_RUN_SETUP_PROMPT.replace("setup_database.py", "server/setup_database.py"))


    return db_settings

# Load DB config at startup
loaded_db_config = load_db_config()
DB_HOST = loaded_db_config['host']
DB_USER = loaded_db_config['user']
DB_PASSWORD = loaded_db_config['password']
DB_NAME = loaded_db_config['name']

# --- Alert Thresholds (Constants) ---
CPU_ALERT_THRESHOLD = 90.0
GPU_ALERT_THRESHOLD = 90.0
OFFLINE_THRESHOLD_MINUTES = 30

# --- Attempt to import MariaDB connector ---
try:
    import mariadb
except ImportError:
    # Use message constants
    print(messages.SERVER_MARIADB_MODULE_IMPORT_ERROR)
    print(messages.SERVER_MARIADB_MODULE_PLEASE_INSTALL)
    mariadb = None

# Flask app initialized considering new path for templates and static files
# SCRIPT_DIR is already defined
TEMPLATE_DIR = os.path.join(SCRIPT_DIR, 'templates')
STATIC_DIR = os.path.join(SCRIPT_DIR, 'static')
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)


# --- Database Connection Function ---
def get_db_connection():
    """Establishes a connection to the MariaDB database."""
    if not mariadb:
        print(messages.SERVER_DB_CONN_UNAVAILABLE_IMPORT)
        return None
    if not DB_USER or not DB_PASSWORD:
        print(messages.SERVER_DB_CONN_UNAVAILABLE_CONFIG)
        return None
    try:
        conn = mariadb.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
        )
        return conn
    except mariadb.Error as e:
        print(messages.SERVER_DB_CONN_ERROR.format(DB_HOST, DB_USER, DB_NAME, e))
        return None

# --- Database Schema Creation Function ---
def create_tables(conn):
    """Creates database tables if they don't already exist using DDL from sql_ddl.py."""
    if not conn:
        print(messages.SERVER_TABLES_CREATE_NO_CONN)
        return
    cursor = None
    try:
        cursor = conn.cursor()
        for table_ddl in sql_ddl.ALL_TABLES_DDL: # Uses relative import: sql_ddl
            cursor.execute(table_ddl)
        conn.commit()
        print(messages.SERVER_TABLES_INIT_SUCCESS)
    except mariadb.Error as e:
        print(messages.SERVER_TABLES_INIT_ERROR.format(e))
        if conn:
            try:
                conn.rollback()
                print(messages.SERVER_TABLES_ROLLBACK_SUCCESS)
            except mariadb.Error as rb_err:
                print(messages.SERVER_TABLES_ROLLBACK_ERROR.format(rb_err))
    except Exception as e:
        print(messages.SERVER_TABLES_UNEXPECTED_ERROR.format(e))
    finally:
        if cursor:
            cursor.close()

# --- Web Page Routes ---
@app.route('/')
def dashboard_page():
    conn = None
    cursor = None
    computer_list = []
    alerts = []
    error_message = None

    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(sql_dml.SELECT_COMPUTERS_FOR_DASHBOARD) # Uses relative import: sql_dml
            rows = cursor.fetchall()
            now = datetime.now()

            for row in rows:
                computer_data = {
                    'id': row[0], 'netbios_name': row[1], 'ip_address': row[2],
                    'last_seen': row[3].strftime('%Y-%m-%d %H:%M:%S') if row[3] else 'Never',
                    'group_name': row[4], 'group_id': row[5]
                }
                computer_list.append(computer_data)

                if row[3]:
                    last_seen_dt = row[3]
                    if now - last_seen_dt > timedelta(minutes=OFFLINE_THRESHOLD_MINUTES):
                        alerts.append({
                            'netbios_name': computer_data['netbios_name'], 'ip_address': computer_data['ip_address'],
                            'alert_type': 'Offline', 'details': f"Last seen: {computer_data['last_seen']}"
                        })
                elif computer_data['last_seen'] == 'Never':
                     alerts.append({
                        'netbios_name': computer_data['netbios_name'], 'ip_address': computer_data['ip_address'],
                        'alert_type': 'Offline', 'details': "Never seen (no activity logs yet)"
                    })

                cursor.execute(sql_dml.SELECT_LATEST_ACTIVITY_FOR_COMPUTER, (computer_data['id'],))
                latest_log = cursor.fetchone()

                if latest_log:
                    cpu_usage, gpu_usage, log_timestamp_dt = latest_log[0], latest_log[1], latest_log[2]
                    log_timestamp = log_timestamp_dt.strftime('%Y-%m-%d %H:%M:%S') if log_timestamp_dt else 'N/A'

                    if cpu_usage is not None and cpu_usage > CPU_ALERT_THRESHOLD:
                        alerts.append({
                            'netbios_name': computer_data['netbios_name'], 'ip_address': computer_data['ip_address'],
                            'alert_type': 'High CPU Usage', 'details': f"CPU at {cpu_usage:.1f}% on {log_timestamp}"
                        })
                    if gpu_usage is not None and gpu_usage > GPU_ALERT_THRESHOLD:
                        alerts.append({
                            'netbios_name': computer_data['netbios_name'], 'ip_address': computer_data['ip_address'],
                            'alert_type': 'High GPU Usage', 'details': f"GPU at {gpu_usage:.1f}% on {log_timestamp}"
                        })
        else:
            error_message = messages.DASHBOARD_DB_CONN_FAILED_ERROR
            print(error_message)

    except mariadb.Error as e:
        error_message = messages.DASHBOARD_DB_FETCH_ERROR.format(e)
        print(error_message)
    except Exception as e:
        error_message = messages.DASHBOARD_UNEXPECTED_FETCH_ERROR.format(e)
        print(error_message)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return render_template('dashboard.html', computers=computer_list, alerts=alerts, error_message=error_message)

# --- API Routes ---
# (Error logging in API routes will use generic messages for now, or can be enhanced with app.logger)
# Make sure 'from datetime import datetime' is at the top of server.py
# from . import sql_dml # Should already exist
# from . import messages_server as messages # Should already exist
# import mariadb # Should already exist

@app.route('/log_activity', methods=['POST'])
def log_activity():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(status="error", message="Invalid JSON payload"), 400

    log_type = data.get('log_type')
    if not log_type:
        return jsonify(status="error", message="Missing 'log_type' field in payload"), 400

    raw_timestamp = data.get('timestamp')
    if not raw_timestamp:
        return jsonify(status="error", message=f"Missing common required key: timestamp for log_type '{log_type}'"), 400

    parsed_timestamp = None
    try:
        # Agent sends ISO format (e.g., "2023-10-27T10:30:00.123456").
        # Replace 'Z' if present (UTC timezone designator) for compatibility with fromisoformat.
        if isinstance(raw_timestamp, str):
            parsed_timestamp = datetime.fromisoformat(raw_timestamp.replace('Z', '+00:00'))
        else: # Should be a string, but good to be safe
            raise ValueError("Timestamp must be a string.")
    except ValueError as e:
        return jsonify(status="error", message=f"Invalid timestamp format: {raw_timestamp}. Expected ISO format. Error: {e}"), 400

    if 'netbios_name' not in data or not str(data['netbios_name']).strip():
        return jsonify(status="error", message=f"Missing or empty common required key: netbios_name for log_type '{log_type}'"), 400

    netbios_name = str(data['netbios_name']).strip()

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(status="error", message="Database connection failed"), 500
        cursor = conn.cursor()

        computer_id = None
        cursor.execute(sql_dml.SELECT_COMPUTER_BY_NETBIOS, (netbios_name,))
        result = cursor.fetchone()

        if log_type == "machine":
            ip_address = data.get('ip_address')
            if not ip_address or not str(ip_address).strip():
                return jsonify(status="error", message="Missing or empty required key 'ip_address' for log_type 'machine'"), 400
            ip_address = str(ip_address).strip()
            os_name = data.get('os_name') # Defaults to None if not present
            os_version = data.get('os_version') # Defaults to None if not present

            if result: # Computer exists
                computer_id = result[0]
                cursor.execute(sql_dml.UPDATE_COMPUTER_LAST_SEEN_IP, (ip_address, parsed_timestamp, os_name, os_version, computer_id))
            else: # New computer
                cursor.execute(sql_dml.INSERT_NEW_COMPUTER, (netbios_name, ip_address, parsed_timestamp, os_name, os_version))
                computer_id = cursor.lastrowid

            if not computer_id:
                if conn: conn.rollback()
                return jsonify(status="error", message="Failed to obtain or create computer ID for 'machine' log"), 500

            # Actual machine data insertion (e.g., into activity_logs) will be handled in a subsequent plan step.
            # For now, this step focuses on updating/creating the computer entry and validating log structure.
            # print(f"Machine log for computer_id {computer_id} acknowledged. Computer record updated/created.") # Old print
            cursor.execute(sql_dml.INSERT_ACTIVITY_LOG, (
                computer_id,
                parsed_timestamp, # This is the datetime object from earlier validation
                data.get('free_disk_space_gb'), # Already rounded by agent or None
                data.get('cpu_usage_percent'),  # Already rounded by agent or None
                data.get('gpu_usage_percent')   # Already rounded by agent or None
                # active_window_title is NOT included here as it will be removed from this table
            ))
            print(f"Machine log for computer_id {computer_id} inserted into activity_logs.")

        elif log_type == "application":
            # active_window_title can be an empty string, so data.get() is fine.
            # No specific validation needed for active_window_title beyond its presence (handled by later DML step).
            # active_window_title = data.get('active_window_title') # This will be used in the INSERT step.

            if result: # Computer exists
                computer_id = result[0]
            else: # Computer not found for an application log
                if conn: conn.rollback()
                return jsonify(status="error", message=f"Computer '{netbios_name}' not found. Application logs require an existing machine record (created by a 'machine' log)."), 404

            if not computer_id: # Should not be reached if logic above is correct
                if conn: conn.rollback()
                return jsonify(status="error", message="Failed to obtain computer ID for 'application' log"), 500

            # Actual application data insertion (e.g., into application_usage_logs) will be handled in a subsequent plan step.
            # print(f"Application log for computer_id {computer_id} acknowledged.") # Old print
            active_window_title = data.get('active_window_title', "") # Ensure active_window_title is fetched

            # Use parsed_timestamp that was validated earlier in the function
            cursor.execute(sql_dml.INSERT_APPLICATION_LOG, (
                computer_id,
                parsed_timestamp, # This is the datetime object from earlier validation
                active_window_title
            ))
            print(f"Application log for computer_id {computer_id} (Active Window: '{active_window_title}') inserted into application_usage_logs.")

    elif log_type == "ping":
        ip_address = data.get('ip_address')
        if not ip_address or not str(ip_address).strip():
            return jsonify(status="error", message="Missing or empty required key 'ip_address' for log_type 'ping'"), 400
        ip_address = str(ip_address).strip()

        # 'netbios_name' and 'parsed_timestamp' are already validated and available.
        # 'result' from SELECT_COMPUTER_BY_NETBIOS is also available.

        computer_id = None
        if not result: # Computer not found, create it
            # INSERT_NEW_COMPUTER expects: netbios_name, ip_address, parsed_timestamp, os_name, os_version
            cursor.execute(sql_dml.INSERT_NEW_COMPUTER, (netbios_name, ip_address, parsed_timestamp, None, None))
            computer_id = cursor.lastrowid
            if not computer_id:
                if conn: conn.rollback()
                return jsonify(status="error", message="Failed to create new computer record from ping"), 500
            print(f"New computer '{netbios_name}' created from ping.")
        else: # Computer exists
            computer_id = result[0]
            cursor.execute(sql_dml.UPDATE_COMPUTER_PING_INFO, (ip_address, parsed_timestamp, computer_id))

        print(f"Ping from computer_id {computer_id} ('{netbios_name}') acknowledged and computer record updated.")
        # Let successful processing fall through to the main commit and success JSON response

        else:
            if conn: conn.rollback()
            return jsonify(status="error", message=f"Unknown log_type: {log_type}"), 400

        conn.commit()
        return jsonify(status="success", message=f"Log type '{log_type}' acknowledged for '{netbios_name}'. Computer record updated/verified. Specific data insertion follows in next steps."), 200

    except mariadb.Error as e:
        if conn:
            try: conn.rollback()
            except mariadb.Error as rb_err: print(messages.API_ROLLBACK_ERROR.format(rb_err)) # Using existing key
        print(messages.API_DB_ERROR_GENERAL.format('/log_activity', e)) # Using existing key
        return jsonify(status="error", message=f"Database error: {str(e)}"), 500
    except ValueError as e: # Catch specific ValueErrors from timestamp parsing or other conversions
        if conn: conn.rollback()
        return jsonify(status="error", message=f"Data validation error: {str(e)}"), 400
    except Exception as e:
        if conn:
            try: conn.rollback()
            except mariadb.Error as rb_err: print(messages.API_ROLLBACK_ERROR.format(rb_err)) # Using existing key
        import traceback
        print(f"Unexpected error in /log_activity: {e}\n{traceback.format_exc()}")
        print(messages.API_UNEXPECTED_ERROR_GENERAL.format('/log_activity', e))
        return jsonify(status="error", message=f"An unexpected server error occurred."), 500 # Avoid sending detailed arbitrary error 'e'
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/api/groups/create', methods=['POST'])
def create_group():
    data = request.get_json()
    if not data or 'name' not in data or not data['name'].strip():
        return jsonify(status="error", message="Group name is required and cannot be empty."), 400
    group_name = data['name'].strip()
    description = data.get('description', '').strip()
    conn = None; cursor = None
    try:
        conn = get_db_connection()
        if not conn: return jsonify(status="error", message="Database connection failed"), 500
        cursor = conn.cursor()
        cursor.execute(sql_dml.INSERT_NEW_GROUP, (group_name, description if description else None))
        conn.commit()
        return jsonify(status="success", message="Group created successfully", group_name=group_name), 201
    except mariadb.Error as e:
        if conn: try: conn.rollback()
                 except mariadb.Error as rb_err: print(messages.API_ROLLBACK_ERROR.format(rb_err))
        if hasattr(e, 'errno') and e.errno == 1062:
            err_msg = f"Group name '{group_name}' already exists." if 'name' in str(e).lower() else f"Duplicate entry: {str(e)}"
            return jsonify(status="error", message=err_msg), 409
        print(messages.API_DB_ERROR_GENERAL.format('/api/groups/create', e))
        return jsonify(status="error", message=f"Database error: {str(e)}"), 500
    except Exception as e:
        if conn: try: conn.rollback()
                 except mariadb.Error as rb_err: print(messages.API_ROLLBACK_ERROR.format(rb_err))
        print(messages.API_UNEXPECTED_ERROR_GENERAL.format('/api/groups/create', e))
        return jsonify(status="error", message=f"An unexpected server error occurred: {str(e)}"), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/api/groups', methods=['GET'])
def list_groups():
    conn = None; cursor = None; groups_list = []
    try:
        conn = get_db_connection()
        if not conn: return jsonify(status="error", message="Database connection failed"), 500
        cursor = conn.cursor()
        cursor.execute(sql_dml.SELECT_ALL_GROUPS)
        rows = cursor.fetchall()
        for row in rows: groups_list.append({'id': row[0], 'name': row[1], 'description': row[2] if row[2] is not None else ''})
        return jsonify(groups=groups_list), 200
    except mariadb.Error as e:
        print(messages.API_DB_ERROR_GENERAL.format('/api/groups', e))
        return jsonify(status="error", message=f"Database error: {str(e)}"), 500
    except Exception as e:
        print(messages.API_UNEXPECTED_ERROR_GENERAL.format('/api/groups', e))
        return jsonify(status="error", message=f"An unexpected server error occurred: {str(e)}"), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/api/computers/<string:netbios_name>/assign_group', methods=['POST'])
def assign_computer_to_group(netbios_name):
    data = request.get_json()
    if not data: return jsonify(status="error", message="Invalid JSON payload"), 400
    if 'group_id' not in data and 'group_name' not in data:
        return jsonify(status="error", message="Either 'group_id' or 'group_name' must be provided."), 400
    conn = None; cursor = None; target_group_id = None
    try:
        conn = get_db_connection()
        if not conn: return jsonify(status="error", message="Database connection failed"), 500
        cursor = conn.cursor()
        cursor.execute(sql_dml.SELECT_COMPUTER_BY_NETBIOS, (netbios_name,))
        computer_result = cursor.fetchone()
        if not computer_result: return jsonify(status="error", message=f"Computer with NetBIOS name '{netbios_name}' not found."), 404
        computer_id = computer_result[0]
        if 'group_id' in data:
            if data['group_id'] is None: target_group_id = None
            else:
                try:
                    target_group_id = int(data['group_id'])
                    if target_group_id <= 0: raise ValueError()
                except ValueError: return jsonify(status="error", message="'group_id' must be a positive integer or null."), 400
        elif 'group_name' in data and data['group_name'] is not None and data['group_name'].strip() != "":
            group_name_to_find = data['group_name'].strip()
            cursor.execute(sql_dml.SELECT_GROUP_BY_NAME, (group_name_to_find,))
            group_result = cursor.fetchone()
            if not group_result: return jsonify(status="error", message=f"Group with name '{group_name_to_find}' not found."), 404
            target_group_id = group_result[0]
        elif ('group_name' in data and (data['group_name'] is None or data['group_name'].strip() == "")): target_group_id = None
        else: return jsonify(status="error", message="Missing group identifier ('group_id' or 'group_name')."), 400
        cursor.execute(sql_dml.UPDATE_COMPUTER_GROUP_ID, (target_group_id, computer_id))
        conn.commit()
        action = "assigned to group" if target_group_id is not None else "unassigned from group"
        return jsonify(status="success", message=f"Computer '{netbios_name}' {action} successfully."), 200
    except mariadb.Error as e:
        if conn: try: conn.rollback()
                 except mariadb.Error as rb_err: print(messages.API_ROLLBACK_ERROR.format(rb_err))
        if hasattr(e, 'errno') and e.errno == 1452 and 'group_id' in str(e).lower():
             return jsonify(status="error", message=f"Invalid 'group_id': The specified group does not exist."), 400
        print(messages.API_DB_ERROR_GENERAL.format(f'/api/computers/.../assign_group', e))
        return jsonify(status="error", message=f"Database error: {str(e)}"), 500
    except Exception as e:
        if conn: try: conn.rollback()
                 except mariadb.Error as rb_err: print(messages.API_ROLLBACK_ERROR.format(rb_err))
        print(messages.API_UNEXPECTED_ERROR_GENERAL.format(f'/api/computers/.../assign_group', e))
        return jsonify(status="error", message=f"An unexpected server error occurred: {str(e)}"), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# --- Main Execution ---
if __name__ == '__main__':
    if not mariadb:
        print(messages.SERVER_MARIADB_MODULE_IMPORT_ERROR)
        print(messages.SERVER_MARIADB_MODULE_PLEASE_INSTALL)
        sys.exit(messages.SERVER_EXITING_NO_MARIADB_MODULE)

    if not DB_USER or not DB_PASSWORD:
        print(messages.SERVER_DB_CREDENTIALS_MISSING_CRITICAL)
        print(messages.SERVER_DB_CREDENTIALS_MISSING_INFO)
        print(messages.SERVER_DB_CREDENTIALS_MISSING_GUIDANCE.replace("setup_database.py", "server/setup_database.py"))
        sys.exit(messages.SERVER_EXITING_NO_DB_CREDENTIALS)

    @app.context_processor
    def inject_current_year():
        return {'current_year': datetime.utcnow().year}

    print(messages.SERVER_STARTUP_DB_CONN_ATTEMPT.format(DB_HOST, DB_USER, DB_NAME))

    db_conn_startup = None
    try:
        db_conn_startup = get_db_connection()
        if db_conn_startup:
            print(messages.SERVER_STARTUP_DB_CONN_SUCCESS)
            create_tables(db_conn_startup)
        else:
            print(messages.SERVER_STARTUP_DB_CONN_CRITICAL_FAIL)
            print(messages.SERVER_STARTUP_DB_CONN_FAIL_GUIDANCE)
    except Exception as e:
        print(messages.SERVER_STARTUP_UNEXPECTED_DB_SETUP_ERROR.format(e))
    finally:
        if db_conn_startup:
            db_conn_startup.close()

    print(messages.SERVER_FLASK_STARTING)
    app.run(debug=True, host='0.0.0.0', port=5000)
