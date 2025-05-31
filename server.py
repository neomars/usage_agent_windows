from flask import Flask, request, jsonify, render_template
import sys
from datetime import datetime, timedelta # Added timedelta
import sql_ddl  # Import DDL statements
import sql_dml  # Import DML statements

# --- MariaDB Configuration ---
DB_HOST = 'localhost'
DB_USER = 'your_db_user'
DB_PASSWORD = 'your_db_password'
DB_NAME = 'agent_data_db'

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
        print(f"Error connecting to MariaDB '{DB_NAME}': {e}")
        return None

# --- Database Schema Creation Function ---
def create_tables(conn):
    """Creates database tables if they don't already exist using DDL from sql_ddl.py."""
    if not conn:
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
    alerts = [] # Initialize alerts list
    error_message = None

    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            # Fetch computer list
            cursor.execute(sql_dml.SELECT_COMPUTERS_FOR_DASHBOARD)
            rows = cursor.fetchall()
            now = datetime.now() # Get current time once for offline checks

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

                # Offline Alert Check
                if row[3]: # If last_seen is not NULL
                    last_seen_dt = row[3] # This is already a datetime object from the DB
                    if now - last_seen_dt > timedelta(minutes=OFFLINE_THRESHOLD_MINUTES):
                        alerts.append({
                            'netbios_name': computer_data['netbios_name'],
                            'ip_address': computer_data['ip_address'],
                            'alert_type': 'Offline',
                            'details': f"Last seen: {computer_data['last_seen']}"
                        })
                elif computer_data['last_seen'] == 'Never': # Explicitly 'Never' means no logs yet
                     alerts.append({
                        'netbios_name': computer_data['netbios_name'],
                        'ip_address': computer_data['ip_address'],
                        'alert_type': 'Offline',
                        'details': "Never seen (no activity logs yet)"
                    })


                # CPU/GPU Alert Check (Strategy A: Query per computer)
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
            error_message = "Database connection failed. Cannot load computer data."
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

        if e.errno == 1062:
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

        if e.errno == 1452 and 'group_id' in str(e).lower():
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
        print("Critical: MariaDB connector not found or failed to import. Server cannot proceed with DB operations.")
        sys.exit("Exiting: MariaDB connector is essential and not available.")

    @app.context_processor
    def inject_current_year():
        return {'current_year': datetime.utcnow().year}

    print(f"Attempting to connect to MariaDB at {DB_HOST} with user {DB_USER} to database {DB_NAME} for schema setup.")
    print("Note: Ensure the database itself ('{DB_NAME}') and user ('{DB_USER}') are created and permissions are granted in MariaDB.")
    print("Using placeholder credentials. Update DB_USER and DB_PASSWORD in server.py if needed.")

    db_conn_startup = None
    try:
        db_conn_startup = get_db_connection()
        if db_conn_startup:
            print("Successfully connected to MariaDB for initial setup.")
            create_tables(db_conn_startup)
        else:
            print("CRITICAL: Failed to connect to MariaDB for initial setup. Tables may not be created.")
            print("Ensure MariaDB is running, accessible, and credentials/database name are correct.")
    except Exception as e:
        print(f"An unexpected error occurred during database setup: {e}")
    finally:
        if db_conn_startup:
            db_conn_startup.close()

    print("Starting Flask web server...")
    app.run(debug=True, host='0.0.0.0', port=5000)
