from flask import Flask, request, jsonify, render_template
import sys
from datetime import datetime, timedelta
import sql_ddl
import sql_dml
import configparser # Added configparser
import os # Added os

# --- Database Configuration Loading ---
def load_db_config():
    """Loads database configuration from db_config.ini or uses defaults."""
    config = configparser.ConfigParser()
    # Define absolute defaults that might be used if file/section/keys are missing
    db_settings = {
        'host': 'localhost',
        'user': None,  # Critical, must be in file
        'password': None, # Critical, must be in file
        'name': 'agent_data_db'
    }

    config_file_path = 'db_config.ini'

    if os.path.exists(config_file_path):
        try:
            config.read(config_file_path)
            if 'database' in config:
                db_settings['host'] = config.get('database', 'host', fallback=db_settings['host'])
                db_settings['user'] = config.get('database', 'user', fallback=None) # No fallback, must exist
                db_settings['password'] = config.get('database', 'password', fallback=None) # No fallback
                db_settings['name'] = config.get('database', 'name', fallback=db_settings['name'])

                if not db_settings['user'] or not db_settings['password']:
                    print(f"Warning: 'user' or 'password' not found in [database] section of '{config_file_path}'.")
            else:
                print(f"Warning: '{config_file_path}' is missing the [database] section. Using internal defaults where possible.")
        except configparser.Error as e:
            print(f"Error parsing '{config_file_path}': {e}. Using internal defaults where possible.")
    else:
        print(f"Warning: Database configuration file '{config_file_path}' not found. Using internal defaults where possible.")
        print("Please run 'python setup_database.py' if you haven't already.")

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
    print("Error: MariaDB connector (python-mariadb) not found. This server requires it.")
    print("Please install it: pip install mariadb")
    mariadb = None

app = Flask(__name__)

# --- Database Connection Function ---
def get_db_connection():
    """Establishes a connection to the MariaDB database."""
    if not mariadb:
        print("Error: MariaDB connector not available (import failed).") # Added more specific message
        return None
    if not DB_USER or not DB_PASSWORD: # Check if critical DB config is missing
        # This message might be redundant if caught at startup, but good for safety
        print("Error: Database user or password is not configured. Cannot connect.")
        return None
    try:
        conn = mariadb.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return conn
    except mariadb.Error as e:
        # More detailed error print, including potentially misconfigured DB_USER/DB_NAME
        print(f"Error connecting to MariaDB (Host: {DB_HOST}, User: {DB_USER}, DB: {DB_NAME}): {e}")
        return None

# --- Database Schema Creation Function ---
def create_tables(conn):
    """Creates database tables if they don't already exist using DDL from sql_ddl.py."""
    if not conn:
        print("Error: Cannot create tables, no database connection provided.") # More specific
        return
    cursor = None
    try:
        cursor = conn.cursor()
        for table_ddl in sql_ddl.ALL_TABLES_DDL:
            cursor.execute(table_ddl)
        conn.commit()
        print("Database tables initialized/verified successfully using sql_ddl.py.")
    except mariadb.Error as e:
        print(f"Error creating tables using sql_ddl.py: {e}")
        if conn:
            try:
                conn.rollback()
                print("Transaction rolled back due to table creation error.")
            except mariadb.Error as rb_err:
                print(f"Error during rollback: {rb_err}")
    except Exception as e:
        print(f"An unexpected error occurred during table creation: {e}")
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
            cursor.execute(sql_dml.SELECT_COMPUTERS_FOR_DASHBOARD)
            rows = cursor.fetchall()
            now = datetime.now()

            for row in rows:
                computer_data = {
                    'id': row[0],
                    'netbios_name': row[1],
                    'ip_address': row[2],
                    'last_seen': row[3].strftime('%Y-%m-%d %H:%M:%S') if row[3] else 'Never',
                    'group_name': row[4],
                    'group_id': row[5]
                }
                computer_list.append(computer_data)

                if row[3]:
                    last_seen_dt = row[3]
                    if now - last_seen_dt > timedelta(minutes=OFFLINE_THRESHOLD_MINUTES):
                        alerts.append({
                            'netbios_name': computer_data['netbios_name'],
                            'ip_address': computer_data['ip_address'],
                            'alert_type': 'Offline',
                            'details': f"Last seen: {computer_data['last_seen']}"
                        })
                elif computer_data['last_seen'] == 'Never':
                     alerts.append({
                        'netbios_name': computer_data['netbios_name'],
                        'ip_address': computer_data['ip_address'],
                        'alert_type': 'Offline',
                        'details': "Never seen (no activity logs yet)"
                    })

                cursor.execute(sql_dml.SELECT_LATEST_ACTIVITY_FOR_COMPUTER, (computer_data['id'],))
                latest_log = cursor.fetchone()

                if latest_log:
                    cpu_usage = latest_log[0]
                    gpu_usage = latest_log[1]
                    log_timestamp = latest_log[2].strftime('%Y-%m-%d %H:%M:%S') if latest_log[2] else 'N/A'

                    if cpu_usage is not None and cpu_usage > CPU_ALERT_THRESHOLD:
                        alerts.append({
                            'netbios_name': computer_data['netbios_name'],
                            'ip_address': computer_data['ip_address'],
                            'alert_type': 'High CPU Usage',
                            'details': f"CPU at {cpu_usage:.1f}% on {log_timestamp}"
                        })
                    if gpu_usage is not None and gpu_usage > GPU_ALERT_THRESHOLD:
                        alerts.append({
                            'netbios_name': computer_data['netbios_name'],
                            'ip_address': computer_data['ip_address'],
                            'alert_type': 'High GPU Usage',
                            'details': f"GPU at {gpu_usage:.1f}% on {log_timestamp}"
                        })
        else:
            error_message = "Database connection failed. Cannot load computer data. Check server logs and db_config.ini."
            print(error_message)

    except mariadb.Error as e:
        error_message = f"Database error fetching data for dashboard: {e}"
        print(error_message)
    except Exception as e:
        error_message = f"An unexpected error occurred fetching data for dashboard: {e}"
        print(error_message)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return render_template('dashboard.html', computers=computer_list, alerts=alerts, error_message=error_message)

# --- API Routes ---
# (Other API routes remain unchanged but will use the globally configured DB_HOST etc.)
@app.route('/log_activity', methods=['POST'])
def log_activity():
    data = request.get_json(silent=True)

    if not data:
        return jsonify(status="error", message="Invalid JSON payload"), 400

    required_keys = ['netbios_name', 'ip_address', 'timestamp']
    for key in required_keys:
        if key not in data:
            return jsonify(status="error", message=f"Missing required key: {key}"), 400

    conn = None
    cursor = None
    computer_id = None

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(status="error", message="Database connection failed"), 500

        cursor = conn.cursor()

        cursor.execute(sql_dml.SELECT_COMPUTER_BY_NETBIOS, (data['netbios_name'],))
        result = cursor.fetchone()

        if result:
            computer_id = result[0]
            cursor.execute(sql_dml.UPDATE_COMPUTER_LAST_SEEN_IP, (data['ip_address'], computer_id))
        else:
            cursor.execute(sql_dml.INSERT_NEW_COMPUTER, (data['netbios_name'], data['ip_address']))
            computer_id = cursor.lastrowid

        if not computer_id:
            conn.rollback()
            return jsonify(status="error", message="Failed to obtain computer ID"), 500

        cursor.execute(sql_dml.INSERT_ACTIVITY_LOG, (
            computer_id,
            data.get('timestamp'),
            data.get('free_disk_space_gb'),
            data.get('cpu_usage_percent'),
            data.get('gpu_usage_percent'),
            data.get('active_window_title')
        ))

        conn.commit()
        return jsonify(status="success", message="Data logged successfully"), 200

    except mariadb.Error as e:
        if conn:
            try: conn.rollback()
            except mariadb.Error as rb_err: print(f"Error during rollback attempt: {rb_err}")
        print(f"Database error during /log_activity: {e}")
        return jsonify(status="error", message=f"Database error: {str(e)}"), 500
    except Exception as e:
        if conn:
            try: conn.rollback()
            except mariadb.Error as rb_err: print(f"Error during rollback attempt: {rb_err}")
        print(f"Unexpected error during /log_activity: {e}")
        return jsonify(status="error", message=f"An unexpected server error occurred: {str(e)}"), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/api/groups/create', methods=['POST'])
def create_group():
    data = request.get_json()

    if not data or 'name' not in data or not data['name'].strip():
        return jsonify(status="error", message="Group name is required and cannot be empty."), 400

    group_name = data['name'].strip()
    description = data.get('description', '').strip()

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(status="error", message="Database connection failed"), 500

        cursor = conn.cursor()
        cursor.execute(sql_dml.INSERT_NEW_GROUP, (group_name, description if description else None))
        conn.commit()
        return jsonify(status="success", message="Group created successfully", group_name=group_name), 201

    except mariadb.Error as e:
        if conn:
            try: conn.rollback()
            except mariadb.Error as rb_err: print(f"Error during rollback attempt: {rb_err}")

        if hasattr(e, 'errno') and e.errno == 1062: # Check hasattr for safety
            if 'name' in str(e).lower():
                 return jsonify(status="error", message=f"Group name '{group_name}' already exists."), 409
            else:
                 return jsonify(status="error", message=f"Duplicate entry: {str(e)}"), 409

        print(f"Database error during /api/groups/create: {e}")
        return jsonify(status="error", message=f"Database error: {str(e)}"), 500
    except Exception as e:
        if conn:
            try: conn.rollback()
            except mariadb.Error as rb_err: print(f"Error during rollback attempt: {rb_err}")
        print(f"Unexpected error during /api/groups/create: {e}")
        return jsonify(status="error", message=f"An unexpected server error occurred: {str(e)}"), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/api/groups', methods=['GET'])
def list_groups():
    conn = None
    cursor = None
    groups_list = []

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(status="error", message="Database connection failed"), 500

        cursor = conn.cursor()
        cursor.execute(sql_dml.SELECT_ALL_GROUPS)
        rows = cursor.fetchall()

        for row in rows:
            groups_list.append({
                'id': row[0],
                'name': row[1],
                'description': row[2] if row[2] is not None else ''
            })

        return jsonify(groups=groups_list), 200

    except mariadb.Error as e:
        print(f"Database error during /api/groups: {e}")
        return jsonify(status="error", message=f"Database error: {str(e)}"), 500
    except Exception as e:
        print(f"Unexpected error during /api/groups: {e}")
        return jsonify(status="error", message=f"An unexpected server error occurred: {str(e)}"), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/api/computers/<string:netbios_name>/assign_group', methods=['POST'])
def assign_computer_to_group(netbios_name):
    data = request.get_json()

    if not data:
        return jsonify(status="error", message="Invalid JSON payload"), 400

    if 'group_id' not in data and 'group_name' not in data:
        return jsonify(status="error", message="Either 'group_id' or 'group_name' must be provided."), 400

    conn = None
    cursor = None
    computer_id = None
    target_group_id = None

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(status="error", message="Database connection failed"), 500

        cursor = conn.cursor()

        cursor.execute(sql_dml.SELECT_COMPUTER_BY_NETBIOS, (netbios_name,))
        computer_result = cursor.fetchone()
        if not computer_result:
            return jsonify(status="error", message=f"Computer with NetBIOS name '{netbios_name}' not found."), 404
        computer_id = computer_result[0]

        if 'group_id' in data:
            if data['group_id'] is None:
                target_group_id = None
            else:
                try:
                    target_group_id = int(data['group_id'])
                    if target_group_id <= 0:
                         raise ValueError("group_id must be a positive integer if provided.")
                except ValueError:
                    return jsonify(status="error", message="'group_id' must be a positive integer or null."), 400

        elif 'group_name' in data and data['group_name'] is not None and data['group_name'].strip() != "":
            group_name_to_find = data['group_name'].strip()
            cursor.execute(sql_dml.SELECT_GROUP_BY_NAME, (group_name_to_find,))
            group_result = cursor.fetchone()
            if not group_result:
                return jsonify(status="error", message=f"Group with name '{group_name_to_find}' not found."), 404
            target_group_id = group_result[0]
        elif ('group_name' in data and (data['group_name'] is None or data['group_name'].strip() == "")):
            target_group_id = None
        else:
            return jsonify(status="error", message="Missing group identifier ('group_id' or 'group_name')."), 400

        cursor.execute(sql_dml.UPDATE_COMPUTER_GROUP_ID, (target_group_id, computer_id))
        conn.commit()

        action = "assigned to group" if target_group_id is not None else "unassigned from group"
        return jsonify(status="success", message=f"Computer '{netbios_name}' {action} successfully."), 200

    except mariadb.Error as e:
        if conn:
            try: conn.rollback()
            except mariadb.Error as rb_err: print(f"Error during rollback attempt: {rb_err}")

        if hasattr(e, 'errno') and e.errno == 1452 and 'group_id' in str(e).lower():
             return jsonify(status="error", message=f"Invalid 'group_id': The specified group does not exist."), 400

        print(f"Database error during group assignment: {e}")
        return jsonify(status="error", message=f"Database error: {str(e)}"), 500
    except Exception as e:
        if conn:
            try: conn.rollback()
            except mariadb.Error as rb_err: print(f"Error during rollback attempt: {rb_err}")
        print(f"Unexpected error during group assignment: {e}")
        return jsonify(status="error", message=f"An unexpected server error occurred: {str(e)}"), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# --- Main Execution ---
if __name__ == '__main__':
    if not mariadb:
        print("CRITICAL: MariaDB connector (python-mariadb) not found. This server requires it to function.")
        print("Please install it: pip install mariadb")
        sys.exit("Exiting: MariaDB connector is essential and not available.")

    if not DB_USER or not DB_PASSWORD:
        print("\nCRITICAL: Database user or password is not configured.")
        print("These should be loaded from 'db_config.ini'.")
        print("If 'db_config.ini' does not exist or is incomplete, please run 'python setup_database.py' first.")
        sys.exit("Exiting: Database credentials not configured.")

    @app.context_processor
    def inject_current_year():
        return {'current_year': datetime.utcnow().year}

    print(f"Attempting to connect to MariaDB (Host: {DB_HOST}, User: {DB_USER}, DB: {DB_NAME}) for schema setup.")
    # Removed print about placeholder credentials as they are now loaded from file or are None.

    db_conn_startup = None
    try:
        db_conn_startup = get_db_connection()
        if db_conn_startup:
            print("Successfully connected to MariaDB for initial setup.")
            create_tables(db_conn_startup)
        else:
            # get_db_connection() already prints detailed error.
            print("CRITICAL: Failed to connect to MariaDB for initial setup. Tables may not be created.")
            print("Ensure MariaDB is running, accessible, and 'db_config.ini' is correctly configured.")
            # Optionally, exit if table creation is absolutely critical for startup,
            # but server might still run some non-DB routes or API endpoints.
            # sys.exit("Exiting: Database connection failed at startup, cannot verify/create tables.")
    except Exception as e: # Catch any other unexpected error during startup DB interaction
        print(f"An unexpected error occurred during database setup: {e}")
    finally:
        if db_conn_startup:
            db_conn_startup.close()

    print("Starting Flask web server...")
    app.run(debug=True, host='0.0.0.0', port=5000)
