# Windows Agent & Activity Monitoring Server

This project consists of two main components:
1.  A **Windows Agent** (`agent.py`): A Python script designed to run on Windows machines. It collects various system metrics, logs them locally, and sends them to a central web server.
2.  A **Web Server** (`server.py`): A Python Flask application that receives data from the agent(s), stores it in a MariaDB database, and provides a basic web interface for viewing computer activity and managing computer groups.

## Features

### Windows Agent (`agent.py`)

*   **System Metrics Collection**:
    *   NetBIOS name of the host.
    *   Local IP address.
    *   Free disk space (on C: drive).
    *   CPU utilization (reported if above a configurable threshold).
    *   GPU utilization (NVIDIA GPUs, reported if above a configurable threshold, uses `GPUtil`).
    *   Active window title.
*   **Local Logging**:
    *   Collected data is logged in JSON format to daily rotating files (e.g., `YYMMDDLog_Usage_Windows.log`).
    *   Log folder location is configurable.
*   **Data Transmission**:
    *   Sends data to the configured web server endpoint (`/log_activity`) via HTTP POST request.
*   **Configuration**:
    *   Server address, alert thresholds (CPU/GPU), and log folder are configurable via `config.ini`.
    *   Uses default values if settings are missing.
*   **Messaging**:
    *   User-facing messages (status, errors) are centralized in `messages.py`.

### Web Server (`server.py`)

*   **Data Reception**:
    *   Receives JSON data from agents at the `/log_activity` endpoint.
    *   Validates incoming data.
*   **Database Storage**:
    *   Stores agent information and activity logs in a MariaDB database.
    *   Automatically creates database schema (tables for computers, activity logs, and groups) on first run if they don't exist.
    *   SQL queries are externalized into `sql_ddl.py` (for schema) and `sql_dml.py` (for data operations).
*   **Group Management**:
    *   API endpoints for managing computer groups:
        *   Create new groups (`/api/groups/create`).
        *   List existing groups (`/api/groups`).
        *   Assign/unassign computers to groups (`/api/computers/<netbios_name>/assign_group`).
*   **Web Interface (Dashboard)**:
    *   Basic HTML dashboard (`/`) to display a list of monitored computers, their status (IP, last seen), and assigned group.
    *   (Planned: Alerts view for high CPU/GPU usage and offline computers).
*   **Testing**:
    *   Includes a suite of unit tests for both agent and server functionality, runnable via `run_tests.sh`.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Project Structure

```
.
├── agent.py            # Main script for the Windows agent
├── config.ini          # Configuration file for agent.py
├── messages.py         # User-facing messages for agent.py
├── server.py           # Main script for the Flask web server
├── sql_ddl.py          # SQL Data Definition Language statements (schema) for server.py
├── sql_dml.py          # SQL Data Manipulation Language statements (queries) for server.py
├── run_tests.sh        # Shell script to execute all unit tests
├── tests/                # Directory for all test files
│   ├── test_agent.py     # Unit tests for agent.py
│   └── test_server.py    # Unit tests for server.py
├── templates/            # HTML templates for the server's web interface
│   ├── base.html         # Base HTML layout template
│   └── dashboard.html    # Dashboard page template
├── static/               # Static files (CSS, JS, images) for the web interface
│   └── style.css         # Basic CSS styling
├── README.md             # This file
├── LICENSE               # Project license file (MIT License)
└── requirements_agent.txt # Python dependencies for the agent (to be created)
└── requirements_server.txt# Python dependencies for the server (to be created)
```

## Prerequisites

Before you begin, ensure you have met the following requirements:

*   **Python**: Python 3.7 or higher.
*   **MariaDB**: A running MariaDB server instance.
*   **Operating System**:
    *   The **Agent** (`agent.py`) is designed for Windows.
    *   The **Server** (`server.py`) is cross-platform and can run on Windows, Linux, or macOS (where Python and MariaDB are available).
*   **Pip**: Python package installer, usually included with Python.

## Installation

Follow these steps to set up the project components.

### 1. Clone the Repository

```bash
git clone <repository_url> # Replace <repository_url> with the actual URL
cd <repository_directory>
```

### 2. Agent Setup (on each Windows machine to be monitored)

1.  **Navigate to the project directory.**
2.  **Install Python Dependencies for the Agent:**
    It's recommended to use a virtual environment.
    ```bash
    python -m venv agent_env
    # On Windows
    agent_env\Scripts\activate
    # On Linux/macOS (if setting up agent dev env there)
    # source agent_env/bin/activate
    ```
    Then install the required packages:
    ```bash
    pip install -r requirements_agent.txt
    ```
3.  **Configure the Agent:**
    *   Open the `config.ini` file.
    *   Modify the settings as needed:
        *   `[server]`:
            *   `address`: Set to the IP address or hostname of your server running `server.py`.
        *   `[agent_settings]`:
            *   `cpu_alert_threshold`: Percentage (0-100) for CPU usage alert.
            *   `gpu_alert_threshold`: Percentage (0-100) for GPU usage alert.
            *   `log_folder`: Path to the directory where agent logs will be stored (e.g., `.` for current directory, or `C:\Path\To\AgentLogs`). The agent will attempt to create this folder if it doesn't exist.

### 3. Server Setup (on the machine where the server will run)

1.  **Navigate to the project directory.**
2.  **Install Python Dependencies for the Server:**
    It's recommended to use a virtual environment.
    ```bash
    python -m venv server_env
    # On Windows
    server_env\Scripts\activate
    # On Linux/macOS
    # source server_env/bin/activate
    ```
    Then install the required packages:
    ```bash
    pip install -r requirements_server.txt
    ```
3.  **Prepare MariaDB Database and User (Manual Step by DBA)**:
    *   **Important**: Before running the setup script, a MariaDB database and a dedicated application user must be created manually by a Database Administrator.
    *   Connect to your MariaDB server using an admin account (e.g., `root`).
    *   Create the database if it doesn't exist (e.g., `agent_data_db`):
        ```sql
        CREATE DATABASE agent_data_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        ```
    *   Create the application user if it doesn't exist and grant it **all necessary privileges** on the created database. Replace placeholders with your desired username and a strong password. The user should be able to connect from the host where `server.py` will run (e.g., `localhost` or a specific IP).
        ```sql
        CREATE USER 'your_app_user'@'localhost' IDENTIFIED BY 'your_app_password';
        GRANT ALL PRIVILEGES ON agent_data_db.* TO 'your_app_user'@'localhost';
        -- Or, more granularly:
        -- GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, ALTER ON agent_data_db.* TO 'your_app_user'@'localhost';
        FLUSH PRIVILEGES;
        ```
4.  **Run Database Setup Script (for Table Creation & Server Config)**:
    The project includes an interactive script to create the necessary tables within your existing database and to generate the `db_config.ini` file that `server.py` uses.
    1.  **Ensure your MariaDB server is running and accessible.**
    2.  **Run the database setup script from the project root directory:**
        ```bash
        python setup_database.py
        ```
    3.  **Follow the on-screen prompts:**
        *   You will be asked for the details of your **existing** application database setup:
            *   The **MariaDB host** where the application database is located (default: `localhost`).
            *   The **name of the existing application database** (default: `agent_data_db`).
            *   The **username of the existing application user** (default: `agent_app_user`).
            *   The **password for this application user**.
        *   The script will then perform the following actions using these credentials:
            *   Connect to the specified database.
            *   Create all required tables (`computer_groups`, `computers`, `activity_logs`) if they don't already exist, using definitions from `sql_ddl.py`.
            *   Generate a `db_config.ini` file in the project root. This file will store the connection details (host, database name, application username, and password) that `server.py` will use.

5.  **Secure `db_config.ini`:**
    *   The `db_config.ini` file contains sensitive database credentials. Ensure it is appropriately secured and **should not be committed to version control** if you are using Git (consider adding `db_config.ini` to your `.gitignore` file).

The `server.py` application is now configured to read its database connection details from `db_config.ini`.

## Usage

### 1. Running the Server

1.  **Activate the server's virtual environment** (if you created one):
    ```bash
    # On Windows: server_env\Scripts\activate
    # On Linux/macOS: source server_env/bin/activate
    ```
2.  **Navigate to the project directory.**
3.  **Start the Flask server:**
    ```bash
    python server.py
    ```
4.  By default, the server will run on `http://0.0.0.0:5000/`.
    *   It will attempt to create the necessary database tables in your configured MariaDB database on its first run if they don't already exist (using credentials from `db_config.ini`).
    *   You should see output indicating the server is running, e.g., `* Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)`.

### 2. Running the Agent

1.  **Activate the agent's virtual environment** (if you created one):
    ```bash
    # On Windows: agent_env\Scripts\activate
    ```
2.  **Navigate to the project directory.**
3.  **Ensure `config.ini` is correctly configured** (especially the `server_address`).
4.  **Start the agent:**
    ```bash
    python agent.py
    ```
5.  The agent will start collecting system metrics and sending them to the server every 30 seconds.
    *   It will also log this data to files in the configured `log_folder`.
    *   You will see console output from the agent indicating its status and any errors.

### 3. Accessing the Dashboard

*   Once the server is running, open a web browser and navigate to:
    `http://<server_ip_or_hostname>:5000/`
    (e.g., `http://localhost:5000/` if accessing from the same machine as the server).
*   The dashboard will display a list of computers that have reported to the server.

### 4. Using the API (Optional)

The server provides a few API endpoints for group management (primarily for programmatic access or future admin interfaces):

*   **Create a new group:**
    *   `POST /api/groups/create`
    *   JSON Payload: `{"name": "group_name", "description": "Optional description"}`
*   **List all groups:**
    *   `GET /api/groups`
*   **Assign a computer to a group:**
    *   `POST /api/computers/<netbios_name>/assign_group`
    *   JSON Payload: `{"group_name": "target_group_name"}` or `{"group_id": <id_of_group>}`
    *   To unassign, send `{"group_id": null}` or `{"group_name": null}` (or an empty string for group_name).

## Running Tests

This project includes a suite of unit tests for both the agent and server components.

1.  **Navigate to the project root directory.**
2.  **Ensure `run_tests.sh` is executable:**
    ```bash
    chmod +x run_tests.sh
    ```
    (This step might only be needed once).
3.  **Execute the test script:**
    ```bash
    bash run_tests.sh
    ```
    Or, if you're in a shell where `./` is in your PATH and the script is executable:
    ```bash
    ./run_tests.sh
    ```
4.  The script will run all tests in `tests/test_agent.py` and `tests/test_server.py` and report whether all test suites passed or if any failures occurred.

## Project Setup and Running

This project consists of a Python Flask backend and a React frontend.

### Backend (Flask Server)

1.  **Navigate to the `server` directory:**
    ```bash
    cd server
    ```

2.  **Create a Python virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Python dependencies:**
    Make sure you have `server/requirements.txt`.
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: If `server/requirements.txt` doesn't exist or is incomplete, it should be created/updated. Key dependencies are Flask and mariadb.)*

4.  **Database Setup:**
    - Ensure MariaDB server is running.
    - Configure database connection details: The `server/setup_database.py` script will guide you through creating `db_config.ini` and setting up tables. Run it from the project root:
        ```bash
        python server/setup_database.py
        ```
    - Follow the prompts. This script assumes you have already created a database and a user with privileges in MariaDB.

5.  **Run the Flask server:**
    From the `server` directory (with virtual environment activated):
    ```bash
    python server.py
    ```
    The server will typically start on `http://localhost:5000`.

### Frontend (React App)

1.  **Navigate to the `frontend` directory:**
    ```bash
    cd frontend
    ```
    *(If you are in the `server` directory from backend setup, you'd do `cd ../frontend`)*

2.  **Install Node.js dependencies:**
    ```bash
    npm install
    ```

3.  **Build the React app for production:**
    ```bash
    npm run build
    ```
    This creates an optimized build in the `frontend/build` directory. The Flask server is configured to serve files from this location.

4.  **Development (Optional):**
    To run the React app in development mode with live reloading (useful when making frontend changes):
    ```bash
    npm start
    ```
    This will typically open the app on `http://localhost:3000`. Note that for API calls to work correctly with the Flask backend, you might need to configure proxy settings in `frontend/package.json` (e.g., `"proxy": "http://localhost:5000"`). For the integrated build served by Flask, this proxy is not needed.

### Accessing the Application

Once both the backend server is running and the frontend has been built (and Flask is serving it):
- Open your browser and navigate to `http://localhost:5000` (or the port your Flask server is running on).


## Server Database Configuration

The server component requires a connection to a MariaDB database. Configuration for this connection is managed through the `server/db_config.ini` file.

### System Prerequisites for `mariadb` Package Installation (Linux)

Before installing the Python requirements for the server (specifically the `mariadb` package), you may need to install several system-level dependencies if they are not already present. These are typically required for compiling the `mariadb` Python package from source on Linux systems.

-   **MariaDB C Connector Development Libraries:** Provides `mariadb_config` and other files needed to compile the connector.
    -   On Debian/Ubuntu: `sudo apt install libmariadb-dev` (or `libmariadbclient-dev`)
    -   On Fedora/RHEL: `sudo dnf install mariadb-connector-c-devel` (or `mariadb-devel`)

-   **Build Tools:** Provides the C compiler (like GCC) and other essential build utilities.
    -   On Debian/Ubuntu: `sudo apt install build-essential`
    -   On Fedora/RHEL: `sudo dnf groupinstall "Development Tools"`

-   **Python Development Headers:** Provides `Python.h` and other headers for your Python version, needed to build Python C extensions.
    -   On Debian/Ubuntu: `sudo apt install python3.x-dev` (replace `x` with your specific Python minor version, e.g., `python3.11-dev`)
    -   On Fedora/RHEL: `sudo dnf install python3.x-devel` (replace `x` with your specific Python minor version, e.g., `python3.11-devel`)

After ensuring these system prerequisites are met, you should be able to successfully install the Python dependencies using `pip install -r server/requirements.txt` within your activated virtual environment.

### `server/db_config.ini`

This file must contain the following details under a `[database]` section:

-   `host`: The hostname or IP address of your MariaDB server.
-   `user`: The username for the database connection.
-   `password`: The password for the specified user.
-   `name`: The name of the database to be used (e.g., `agent_data_db`).

A template `server/db_config.ini` is provided with placeholder values. You **must** replace these placeholders with your actual database credentials.

**Example `server/db_config.ini`:**
```ini
[database]
host = 127.0.0.1
user = my_db_user
password = my_secret_password
name = agent_data_db
```

### Automatic Configuration using `setup_database.py`

Alternatively, you can run the `server/setup_database.py` script:

```bash
python server/setup_database.py
```

This script will interactively prompt you for the database details, attempt to connect to the database, create the necessary tables (if they don't exist), and then automatically generate the `server/db_config.ini` file with the provided information.

### Security Note

Ensure that the `server/db_config.ini` file is secured appropriately. It contains sensitive database credentials. It is highly recommended to add this file to your `.gitignore` file if it's not already included, to prevent accidental commitment of credentials to your repository.

```
# Example .gitignore entry
server/db_config.ini
```
