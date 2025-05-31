# setup_database.py
import getpass
import configparser
import sys
import os

try:
    import mariadb
except ImportError:
    print("Error: MariaDB connector (python-mariadb) not found.")
    print("Please ensure it is installed for the Python environment this script is using.")
    print("You can typically install it with: pip install mariadb")
    sys.exit(1)

try:
    from sql_ddl import ALL_TABLES_DDL
except ImportError:
    print("Error: Could not import DDL statements from sql_ddl.py.")
    print("Ensure sql_ddl.py is in the project root directory or accessible in PYTHONPATH.")
    sys.exit(1)

def setup_database():
    print("--- Database Setup Script ---")
    print("This script will guide you through setting up the MariaDB database and user for the application.")
    print("You will need credentials for a MariaDB user with privileges to create databases and users (e.g., 'root').")
    print("\nEnsure your MariaDB server is running before proceeding.\n")

    db_host_admin_input = input("Enter MariaDB server host (where the application will connect) [localhost]: ").strip()
    if not db_host_admin_input:
        db_host_admin_input = 'localhost'

    db_user_admin = input(f"Enter MariaDB admin username for host '{db_host_admin_input}' [root]: ").strip()
    if not db_user_admin:
        db_user_admin = 'root'

    db_pass_admin = getpass.getpass(f"Enter password for MariaDB admin user '{db_user_admin}' on '{db_host_admin_input}': ")

    print("\n--- Application Database Details ---")
    app_db_name_default = 'agent_data_db'
    app_db_name = input(f"Enter name for the application database [{app_db_name_default}]: ").strip()
    if not app_db_name:
        app_db_name = app_db_name_default

    app_db_user_default = 'agent_app_user'
    app_db_user = input(f"Enter username for the application user to be created [{app_db_user_default}]: ").strip()
    if not app_db_user:
        app_db_user = app_db_user_default

    # Determine the host for the new application user. Typically 'localhost' if app server is on same machine as DB.
    app_user_host_default = 'localhost'
    app_user_host = input(f"Allow application user '{app_db_user}' to connect from which host? [{app_user_host_default}]: ").strip()
    if not app_user_host:
        app_user_host = app_user_host_default

    while True:
        app_db_pass = getpass.getpass(f"Enter password for new application user '{app_db_user}'@{app_user_host}: ")
        if not app_db_pass:
            print("Password cannot be empty. Please try again.")
            continue
        app_db_pass_confirm = getpass.getpass(f"Confirm password for '{app_db_user}': ")
        if app_db_pass == app_db_pass_confirm:
            break
        else:
            print("Passwords do not match. Please try again.")

    print(f"\n--- Summary of Actions to be Performed ---")
    print(f"  MariaDB Server Host:   {db_host_admin_input}")
    print(f"  Admin User:            {db_user_admin}")
    print(f"  Create Database:       {app_db_name}")
    print(f"  Create App User:       {app_db_user}@{app_user_host}")
    print("  Grant Privileges:      ALL on " + app_db_name + ".* to " + app_db_user + "@" + app_user_host)
    print(f"  Create Tables in:      {app_db_name}")
    print(f"  Write config to:       db_config.ini (with app user credentials for host '{db_host_admin_input}')")

    if input("\nProceed with these actions? (yes/no): ").strip().lower() != 'yes':
        print("Database setup aborted by user.")
        sys.exit(0)

    # 1. Connect as Admin and Create Database/User
    admin_conn = None
    cursor = None
    print(f"\n--- Step 1: Connecting as admin user '{db_user_admin}' to create database and application user ---")
    try:
        admin_conn = mariadb.connect(
            host=db_host_admin_input,
            user=db_user_admin,
            password=db_pass_admin,
            autocommit=False # Use autocommit=False to manage transactions explicitly
        )
        cursor = admin_conn.cursor()

        print(f"Creating database '{app_db_name}' if it does not exist...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {app_db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")

        print(f"Creating application user '{app_db_user}'@'{app_user_host}' if it does not exist...")
        # Need to handle user creation carefully if user already exists with different password or host part
        # For simplicity, CREATE USER IF NOT EXISTS is used.
        # Consider DROP USER IF EXISTS first if you want to ensure a clean setup with the new password.
        cursor.execute(f"CREATE USER IF NOT EXISTS '{app_db_user}'@'{app_user_host}' IDENTIFIED BY '{app_db_pass}'")

        print(f"Granting privileges on '{app_db_name}' to '{app_db_user}'@'{app_user_host}'...")
        cursor.execute(f"GRANT ALL PRIVILEGES ON {app_db_name}.* TO '{app_db_user}'@'{app_user_host}'")

        cursor.execute("FLUSH PRIVILEGES")
        admin_conn.commit()
        print("Database and application user created/verified successfully.")

    except mariadb.Error as e:
        if admin_conn: admin_conn.rollback()
        print(f"MariaDB Error during admin operations: {e}")
        sys.exit(1)
    except Exception as e:
        if admin_conn: admin_conn.rollback()
        print(f"An unexpected error occurred during admin operations: {e}")
        sys.exit(1)
    finally:
        if cursor: cursor.close()
        if admin_conn: admin_conn.close()

    # 2. Connect as App User and Create Tables
    app_conn = None
    app_cursor = None
    print(f"\n--- Step 2: Connecting as application user '{app_db_user}' to create tables in '{app_db_name}' ---")
    try:
        app_conn = mariadb.connect(
            host=db_host_admin_input, # App connects to the same host specified by admin for MariaDB server
            user=app_db_user,
            password=app_db_pass,
            database=app_db_name
        )
        app_cursor = app_conn.cursor()

        print("Creating tables if they don't exist...")
        for ddl_statement in ALL_TABLES_DDL:
            app_cursor.execute(ddl_statement)
        app_conn.commit()
        print("Tables created successfully in database '{app_db_name}'.")

    except mariadb.Error as e:
        if app_conn: app_conn.rollback()
        print(f"MariaDB Error during table creation with app user: {e}")
        sys.exit(1)
    except Exception as e:
        if app_conn: app_conn.rollback()
        print(f"An unexpected error occurred during table creation: {e}")
        sys.exit(1)
    finally:
        if app_cursor: app_cursor.close()
        if app_conn: app_conn.close()

    # 3. Create db_config.ini
    print(f"\n--- Step 3: Creating database configuration file 'db_config.ini' ---")
    config = configparser.ConfigParser()
    config['database'] = {
        'host': db_host_admin_input, # The host where MariaDB server is running
        'name': app_db_name,
        'user': app_db_user,
        'password': app_db_pass
    }

    try:
        with open('db_config.ini', 'w') as configfile:
            config.write(configfile)
        print("'db_config.ini' created successfully.")
        print("\nIMPORTANT: Secure the 'db_config.ini' file as it contains database credentials.")
        print("Consider adding it to .gitignore if this project is under version control and the file should not be committed.")
    except IOError as e:
        print(f"Error writing 'db_config.ini': {e}")
        sys.exit(1)

    print("\n--- Database Setup Completed Successfully! ---")
    print("You may need to update 'server.py' to load its database configuration from 'db_config.ini' instead of hardcoded values.")

if __name__ == "__main__":
    setup_database()
