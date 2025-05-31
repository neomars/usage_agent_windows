from flask import Flask, request, jsonify, render_template # Added render_template
import sys
from datetime import datetime

# --- MariaDB Configuration ---
DB_HOST = 'localhost'
DB_USER = 'your_db_user'
DB_PASSWORD = 'your_db_password'
DB_NAME = 'agent_data_db'

# --- Attempt to import MariaDB connector ---
try:
    import mariadb
except ImportError:
    print("Error: MariaDB connector (python-mariadb) not found. This server requires it.")
    print("Please install it: pip install mariadb")
    mariadb = None
    # Consider sys.exit("MariaDB connector not found. Server cannot start.") for critical DB dependency

app = Flask(__name__) # Flask will look for 'templates' and 'static' folders in the same directory

# --- Database Connection Function ---
def get_db_connection():
    """Establishes a connection to the MariaDB database."""
    if not mariadb:
        # print("Cannot connect to DB: MariaDB connector not available.") # Can be noisy
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
    """Creates database tables if they don't already exist."""
    if not conn:
        # print("Cannot create tables: No database connection.") # Can be noisy
        return
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS computer_groups (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                description TEXT
            ) ENGINE=InnoDB;
        """)
        # print("Table 'computer_groups' checked/created successfully.")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS computers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                netbios_name VARCHAR(255) NOT NULL UNIQUE,
                ip_address VARCHAR(45),
                last_seen DATETIME,
                group_id INT,
                FOREIGN KEY (group_id) REFERENCES computer_groups(id) ON DELETE SET NULL
            ) ENGINE=InnoDB;
        """)
        # print("Table 'computers' checked/created successfully.")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                computer_id INT NOT NULL,
                timestamp DATETIME NOT NULL,
                free_disk_space_gb FLOAT,
                cpu_usage_percent FLOAT,
                gpu_usage_percent FLOAT,
                active_window_title VARCHAR(512),
                FOREIGN KEY (computer_id) REFERENCES computers(id) ON DELETE CASCADE
            ) ENGINE=InnoDB;
        """)
        # print("Table 'activity_logs' checked/created successfully.")
        conn.commit()
        print("Database tables initialized/verified successfully.")
    except mariadb.Error as e:
        print(f"Error creating tables: {e}")
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
    error_message = None

    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            sql = """
                SELECT c.netbios_name, c.ip_address, c.last_seen, IFNULL(g.name, 'N/A') as group_name
                FROM computers c
                LEFT JOIN computer_groups g ON c.group_id = g.id
                ORDER BY c.last_seen DESC, c.netbios_name;
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            for row in rows:
                computer_list.append({
                    'netbios_name': row[0],
                    'ip_address': row[1],
                    'last_seen': row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else 'Never', # Format datetime
                    'group_name': row[3]
                })
        else:
            error_message = "Database connection failed. Cannot load computer data."
            print(error_message) # Log to server console

    except mariadb.Error as e:
        error_message = f"Database error fetching computer data: {e}"
        print(error_message) # Log to server console
    except Exception as e:
        error_message = f"An unexpected error occurred fetching computer data: {e}"
        print(error_message) # Log to server console
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    # The BLAZE_ വർഷം placeholder in base.html will be replaced by current_year from context_processor
    return render_template('dashboard.html', computers=computer_list, error_message=error_message)

# --- API Routes ---
@app.route('/log_activity', methods=['POST'])
def log_activity():
    data = request.get_json()

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

        # Upsert computer
        cursor.execute("SELECT id FROM computers WHERE netbios_name = %s", (data['netbios_name'],))
        result = cursor.fetchone()

        if result:
            computer_id = result[0]
            cursor.execute("""
                UPDATE computers SET ip_address = %s, last_seen = NOW()
                WHERE id = %s
            """, (data['ip_address'], computer_id))
        else:
            cursor.execute("""
                INSERT INTO computers (netbios_name, ip_address, last_seen)
                VALUES (%s, %s, NOW())
            """, (data['netbios_name'], data['ip_address']))
            computer_id = cursor.lastrowid

        if not computer_id:
            conn.rollback()
            return jsonify(status="error", message="Failed to obtain computer ID"), 500

        # Insert activity log
        cursor.execute("""
            INSERT INTO activity_logs (computer_id, timestamp, free_disk_space_gb,
                                     cpu_usage_percent, gpu_usage_percent, active_window_title)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
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

        cursor.execute("""
            INSERT INTO computer_groups (name, description)
            VALUES (%s, %s)
        """, (group_name, description if description else None))

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
        cursor.execute("SELECT id, name, description FROM computer_groups ORDER BY name")
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

        # Find Computer ID
        cursor.execute("SELECT id FROM computers WHERE netbios_name = %s", (netbios_name,))
        computer_result = cursor.fetchone()
        if not computer_result:
            return jsonify(status="error", message=f"Computer with NetBIOS name '{netbios_name}' not found."), 404
        computer_id = computer_result[0]

        # Determine Target Group ID
        if 'group_id' in data:
            if data['group_id'] is None: # Explicitly unassign
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
            cursor.execute("SELECT id FROM computer_groups WHERE name = %s", (group_name_to_find,))
            group_result = cursor.fetchone()
            if not group_result:
                return jsonify(status="error", message=f"Group with name '{group_name_to_find}' not found."), 404
            target_group_id = group_result[0]
        elif ('group_name' in data and (data['group_name'] is None or data['group_name'].strip() == "")):
            target_group_id = None
        else:
            return jsonify(status="error", message="Missing group identifier ('group_id' or 'group_name')."), 400


        # Update computer's group_id
        cursor.execute("UPDATE computers SET group_id = %s WHERE id = %s", (target_group_id, computer_id))
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

    # Add current_year to the default context for all templates
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
            # sys.exit("Exiting: Database connection failed at startup, cannot verify/create tables.")
    except Exception as e:
        print(f"An unexpected error occurred during database setup: {e}")
    finally:
        if db_conn_startup:
            db_conn_startup.close()

    print("Starting Flask web server...")
    app.run(debug=True, host='0.0.0.0', port=5000)
