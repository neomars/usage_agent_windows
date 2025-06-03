# server/messages_server.py

# --- Setup Script (setup_database.py) Messages ---
# These are used by setup_database.py when it's run directly.
SETUP_HEADER = "--- Database Setup Script (Server Environment) ---"
SETUP_INTRO_MAIN = "This script will configure 'db_config.ini' with your existing application database details and then attempt to create the necessary tables within that database."
SETUP_INTRO_ASSUMPTION_HEADER = "\nIMPORTANT: This script assumes you have already created a MariaDB database and a dedicated application user with FULL PRIVILEGES on that database."
SETUP_INTRO_ASSUMPTION_DETAIL = "If not, please create them manually or use a separate admin script/tool.\n"
SETUP_PRE_REQUISITE_DB_RUNNING = "Ensure your MariaDB server is running before proceeding.\n"

SETUP_PROMPT_DB_HOST_DEFAULT = 'localhost'
SETUP_PROMPT_DB_NAME_DEFAULT = 'agent_data_db'
SETUP_PROMPT_DB_USER_DEFAULT = 'agent_app_user'

SETUP_ERROR_PASSWORD_EMPTY = "Password cannot be empty. Please try again."
SETUP_ERROR_PASSWORD_MISMATCH = "Passwords do not match. Please try again."

SETUP_SUMMARY_HEADER = "\n--- Summary of Provided Application DB Details ---"
SETUP_SUMMARY_DB_HOST = "  Application DB Host:   {}"
SETUP_SUMMARY_DB_NAME = "  Application DB Name:   {}"
SETUP_SUMMARY_DB_USER = "  Application DB User:   {}"
SETUP_SUMMARY_DB_PASSWORD_SET = "  Application DB Password: [set]"
SETUP_SUMMARY_REVIEW_PROMPT_1 = "\nReview these details carefully. The script will attempt to connect to this database,"
SETUP_SUMMARY_REVIEW_PROMPT_2 = "create the necessary tables, and then write these details to 'db_config.ini'."

SETUP_ABORTED_BY_USER = "Database setup aborted by user."

SETUP_STEP1_HEADER = "\n--- Step 1: Attempting to connect to database '{}' on host '{}' as user '{}' to create tables..."
SETUP_STEP1_CONNECT_SUCCESS = "Successfully connected to database '{}'."
SETUP_STEP1_CREATING_TABLES = "Creating tables if they don't exist..."
SETUP_STEP1_TABLES_SUCCESS = "Tables created/verified successfully in database '{}'."
SETUP_STEP1_ERROR_ROLLBACK = "Transaction rolled back due to error."
SETUP_STEP1_ERROR_ROLLBACK_FAILED = "Error during rollback attempt: {}"
SETUP_STEP1_MARIADB_ERROR = "\nMariaDB Error occurred: {}"
SETUP_STEP1_ERROR_TABLE_CREATION_UNEXPECTED = "An unexpected error occurred during table creation: {}"

SETUP_GUIDANCE_HEADER = "Please ensure:"
SETUP_GUIDANCE_DB_RUNNING = "  1. MariaDB server is running and accessible at '{}'."
SETUP_GUIDANCE_DB_EXISTS = "  2. Database '{}' exists."
SETUP_GUIDANCE_USER_EXISTS_PASSWORD = "  3. User '{}' exists and the provided password is correct."
SETUP_GUIDANCE_USER_PERMISSIONS = "  4. User '{}' has necessary permissions (e.g., CREATE TABLE) on database '{}'."

SETUP_STEP2_HEADER = "\n--- Step 2: Creating database configuration file 'db_config.ini' ---"
SETUP_STEP2_DBCONFIG_CREATED = "'db_config.ini' created successfully."
SETUP_STEP2_DBCONFIG_REMINDER_SECURE = "\nIMPORTANT: Secure the 'db_config.ini' file as it contains database credentials."
SETUP_STEP2_DBCONFIG_REMINDER_GITIGNORE = "Consider adding it to .gitignore if this project is under version control and the file should not be committed."
SETUP_STEP2_ERROR_DBCONFIG_WRITE = "Error writing 'db_config.ini': {}"

SETUP_FINAL_SUCCESS_HEADER = "\n--- Database Configuration Script Completed Successfully! ---"
SETUP_FINAL_SUCCESS_DETAIL = "Setup complete! 'db_config.ini' has been created/updated, and tables have been initialized/verified in database '{}'."
SETUP_FINAL_SUCCESS_NEXT_STEP = "The server (server.py) should now be able to connect to database '{}' on host '{}' using user '{}'."

SETUP_ERROR_MARIADB_MODULE_IMPORT = "Error: MariaDB connector (python-mariadb) not found.\nPlease ensure it is installed for the Python environment this script is using.\nYou can typically install it with: pip install mariadb"
SETUP_ERROR_SQLDDL_IMPORT = "Error: Could not import DDL statements from sql_ddl.py.\nEnsure sql_ddl.py is in the server directory or accessible in PYTHONPATH."


# --- Server Script (server.py) Messages ---
SERVER_MARIADB_MODULE_IMPORT_ERROR = "Error: MariaDB connector (python-mariadb) not found. This server requires it."
SERVER_MARIADB_MODULE_PLEASE_INSTALL = "Please install it: pip install mariadb"
SERVER_EXITING_NO_MARIADB_MODULE = "Exiting: MariaDB connector is essential and not available."

SERVER_DB_CONFIG_FILE_NOT_FOUND = "Warning: Database configuration file 'db_config.ini' (expected in server directory) not found. Using internal defaults where possible."
SERVER_DB_CONFIG_RUN_SETUP_PROMPT = "Please run 'python server/setup_database.py' if you haven't already."
SERVER_DB_CONFIG_SECTION_MISSING = "Warning: 'db_config.ini' is missing the [database] section. Using internal defaults where possible."
SERVER_DB_CONFIG_KEY_MISSING = "Warning: '{}' or '{}' not found in [database] section of 'db_config.ini'." # For user/password
SERVER_DB_CONFIG_PARSING_ERROR = "Error parsing 'db_config.ini': {}. Using internal defaults where possible."

SERVER_DB_CREDENTIALS_MISSING_CRITICAL = "\nCRITICAL: Database user or password is not configured."
SERVER_DB_CREDENTIALS_MISSING_INFO = "These should be loaded from 'db_config.ini'."
SERVER_DB_CREDENTIALS_MISSING_GUIDANCE = "If 'db_config.ini' does not exist or is incomplete, please run 'python server/setup_database.py' first."
SERVER_EXITING_NO_DB_CREDENTIALS = "Exiting: Database credentials not configured."

SERVER_DB_CONN_UNAVAILABLE_IMPORT = "Error: MariaDB connector not available (import failed)."
SERVER_DB_CONN_UNAVAILABLE_CONFIG = "Error: Database user or password is not configured. Cannot connect."
SERVER_DB_CONN_ERROR = "Error connecting to MariaDB (Host: {}, User: {}, DB: {}): {}"

SERVER_TABLES_CREATE_NO_CONN = "Error: Cannot create tables, no database connection provided."
SERVER_TABLES_INIT_SUCCESS = "Database tables initialized/verified successfully using sql_ddl.py."
SERVER_TABLES_INIT_ERROR = "Error creating tables using sql_ddl.py: {}"
SERVER_TABLES_ROLLBACK_SUCCESS = "Transaction rolled back due to table creation error."
SERVER_TABLES_ROLLBACK_ERROR = "Error during rollback: {}"
SERVER_TABLES_UNEXPECTED_ERROR = "An unexpected error occurred during table creation: {}"

SERVER_STARTUP_DB_CONN_ATTEMPT = "Attempting to connect to MariaDB (Host: {}, User: {}, DB: {}) for schema setup."
SERVER_STARTUP_DB_CONN_SUCCESS = "Successfully connected to MariaDB for initial setup."
SERVER_STARTUP_DB_CONN_CRITICAL_FAIL = "CRITICAL: Failed to connect to MariaDB for initial setup. Tables may not be created."
SERVER_STARTUP_DB_CONN_FAIL_GUIDANCE = "Ensure MariaDB is running, accessible, and 'db_config.ini' is correctly configured."
SERVER_STARTUP_UNEXPECTED_DB_SETUP_ERROR = "An unexpected error occurred during database setup: {}"

SERVER_FLASK_STARTING = "Starting Flask web server..."

# Dashboard specific messages (mostly for error states printed to console)
DASHBOARD_DB_CONN_FAILED_ERROR = "Database connection failed. Cannot load computer data. Check server logs and db_config.ini."
DASHBOARD_DB_FETCH_ERROR = "Database error fetching data for dashboard: {}"
DASHBOARD_UNEXPECTED_FETCH_ERROR = "An unexpected error occurred fetching data for dashboard: {}"

# API specific messages (for server-side console logging of errors)
# These are not typically returned in JSON responses but are for server logs.
API_ROLLBACK_ERROR = "Error during rollback attempt: {}" # Generic for API routes
API_DB_ERROR_GENERAL = "Database error during API request [{}]: {}" # Route info, error
API_UNEXPECTED_ERROR_GENERAL = "Unexpected error during API request [{}]: {}" # Route info, error
