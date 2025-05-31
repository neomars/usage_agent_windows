import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta # Added datetime, timedelta

# Add the project root to sys.path to allow importing server.py
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Attempt to import the Flask app from server.py
flask_app_imported = False
server_mariadb_module = None # For creating specific mariadb.Error instances
server_sql_dml_module = None # For referencing DML query strings in tests
try:
    from server import app
    from server import mariadb as server_mariadb_module
    from server import sql_dml as server_sql_dml_module # Import sql_dml from server's context
    flask_app_imported = True
except ImportError as e:
    print(f"Failed to import Flask app, mariadb, or sql_dml from server.py: {e}")
    app = None

# Helper to create a mock MariaDBError for testing
def create_mock_mariadb_error(message, errno):
    if server_mariadb_module and hasattr(server_mariadb_module, 'Error'):
        error = server_mariadb_module.Error(message)
    else:
        error = MagicMock(spec=Exception)
        error.message = message
    error.errno = errno
    return error

class TestServer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not flask_app_imported or not app or not server_sql_dml_module:
            raise unittest.SkipTest("Flask app, sql_dml, or mariadb from server.py failed to import or is None.")
        app.testing = True
        # Define fixed time for tests that need datetime.now() consistency
        cls.mock_now_dt = datetime(2023, 10, 28, 12, 0, 0)
        print("\nFlask app imported successfully for testing.")


    def setUp(self):
        self.client = app.test_client()

    def tearDown(self):
        pass

    # --- Dashboard Alert Tests ---
    @patch('server.render_template')
    @patch('server.datetime') # Mock datetime module in server.py
    @patch('server.get_db_connection')
    def test_dashboard_offline_alert(self, mock_get_db_conn, mock_server_datetime, mock_render_template):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Configure server.datetime.now()
        mock_server_datetime.now.return_value = self.mock_now_dt
        # Ensure timedelta is available if server.py uses server.datetime.timedelta
        mock_server_datetime.timedelta = timedelta

        offline_pc_last_seen = self.mock_now_dt - timedelta(minutes=app.config.get("OFFLINE_THRESHOLD_MINUTES", 30) + 1)
        online_pc_last_seen = self.mock_now_dt - timedelta(minutes=10)

        # Data for SELECT_COMPUTERS_FOR_DASHBOARD
        computers_data = [
            (1, 'OFFLINE_PC', '192.168.1.101', offline_pc_last_seen, 'Test Group', 1),
            (2, 'ONLINE_PC', '192.168.1.102', online_pc_last_seen, 'Test Group', 1)
        ]
        # Data for SELECT_LATEST_ACTIVITY_FOR_COMPUTER (return None to focus on offline)
        latest_activity_data = None

        def execute_side_effect(query, params=None):
            if query == server_sql_dml_module.SELECT_COMPUTERS_FOR_DASHBOARD:
                mock_cursor.fetchall.return_value = computers_data
            elif query == server_sql_dml_module.SELECT_LATEST_ACTIVITY_FOR_COMPUTER:
                mock_cursor.fetchone.return_value = latest_activity_data # No CPU/GPU alerts
            return MagicMock() # Default for other execute calls
        mock_cursor.execute.side_effect = execute_side_effect

        mock_render_template.return_value = "mocked_html" # So the route can complete

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        mock_render_template.assert_called_once()
        args, kwargs = mock_render_template.call_args
        self.assertEqual(args[0], 'dashboard.html')
        self.assertIn('alerts', kwargs)
        alerts = kwargs['alerts']

        self.assertEqual(len(alerts), 1)
        offline_alert_found = any(a['alert_type'] == 'Offline' and a['netbios_name'] == 'OFFLINE_PC' for a in alerts)
        self.assertTrue(offline_alert_found, "Offline alert for OFFLINE_PC not found")

    @patch('server.render_template')
    @patch('server.datetime')
    @patch('server.get_db_connection')
    def test_dashboard_high_cpu_alert(self, mock_get_db_conn, mock_server_datetime, mock_render_template):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_server_datetime.now.return_value = self.mock_now_dt
        mock_server_datetime.timedelta = timedelta

        # Computer data (recently seen)
        cpu_pc_last_seen = self.mock_now_dt - timedelta(minutes=5)
        computers_data = [(1, 'CPU_ALERT_PC', '192.168.1.103', cpu_pc_last_seen, 'Group A', 2)]

        # Latest activity: CPU=95.0 (above threshold), GPU=20.0 (below)
        high_cpu_activity = (95.0, 20.0, self.mock_now_dt - timedelta(minutes=2))

        def execute_side_effect(query, params=None):
            if query == server_sql_dml_module.SELECT_COMPUTERS_FOR_DASHBOARD:
                mock_cursor.fetchall.return_value = computers_data
            elif query == server_sql_dml_module.SELECT_LATEST_ACTIVITY_FOR_COMPUTER and params == (1,): # computer_id 1
                mock_cursor.fetchone.return_value = high_cpu_activity
            else:
                mock_cursor.fetchone.return_value = None
            return MagicMock()
        mock_cursor.execute.side_effect = execute_side_effect
        mock_render_template.return_value = "mocked_html"

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        mock_render_template.assert_called_once()
        args, kwargs = mock_render_template.call_args
        self.assertEqual(args[0], 'dashboard.html')
        self.assertIn('alerts', kwargs)
        alerts = kwargs['alerts']

        # Expect one alert for high CPU
        self.assertEqual(len(alerts), 1, f"Expected 1 alert, got {len(alerts)}: {alerts}")
        cpu_alert = alerts[0]
        self.assertEqual(cpu_alert['alert_type'], 'High CPU Usage')
        self.assertEqual(cpu_alert['netbios_name'], 'CPU_ALERT_PC')
        self.assertIn("CPU at 95.0%", cpu_alert['details'])

    @patch('server.render_template')
    @patch('server.datetime')
    @patch('server.get_db_connection')
    def test_dashboard_high_gpu_alert(self, mock_get_db_conn, mock_server_datetime, mock_render_template):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_server_datetime.now.return_value = self.mock_now_dt
        mock_server_datetime.timedelta = timedelta

        gpu_pc_last_seen = self.mock_now_dt - timedelta(minutes=5)
        computers_data = [(1, 'GPU_ALERT_PC', '192.168.1.104', gpu_pc_last_seen, 'Group B', 3)]
        high_gpu_activity = (20.0, 96.0, self.mock_now_dt - timedelta(minutes=3))

        def execute_side_effect(query, params=None):
            if query == server_sql_dml_module.SELECT_COMPUTERS_FOR_DASHBOARD:
                mock_cursor.fetchall.return_value = computers_data
            elif query == server_sql_dml_module.SELECT_LATEST_ACTIVITY_FOR_COMPUTER and params == (1,):
                mock_cursor.fetchone.return_value = high_gpu_activity
            else:
                mock_cursor.fetchone.return_value = None
            return MagicMock()
        mock_cursor.execute.side_effect = execute_side_effect
        mock_render_template.return_value = "mocked_html"

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        mock_render_template.assert_called_once()
        args, kwargs = mock_render_template.call_args
        self.assertEqual(args[0], 'dashboard.html')
        self.assertIn('alerts', kwargs)
        alerts = kwargs['alerts']

        self.assertEqual(len(alerts), 1, f"Expected 1 alert, got {len(alerts)}: {alerts}")
        gpu_alert = alerts[0]
        self.assertEqual(gpu_alert['alert_type'], 'High GPU Usage')
        self.assertEqual(gpu_alert['netbios_name'], 'GPU_ALERT_PC')
        self.assertIn("GPU at 96.0%", gpu_alert['details'])

    @patch('server.render_template')
    @patch('server.datetime')
    @patch('server.get_db_connection')
    def test_dashboard_no_alerts(self, mock_get_db_conn, mock_server_datetime, mock_render_template):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_server_datetime.now.return_value = self.mock_now_dt
        mock_server_datetime.timedelta = timedelta

        normal_pc_last_seen = self.mock_now_dt - timedelta(minutes=10)
        computers_data = [(1, 'NORMAL_PC', '192.168.1.105', normal_pc_last_seen, 'Group C', 4)]
        normal_activity = (30.0, 40.0, self.mock_now_dt - timedelta(minutes=5)) # Below thresholds

        def execute_side_effect(query, params=None):
            if query == server_sql_dml_module.SELECT_COMPUTERS_FOR_DASHBOARD:
                mock_cursor.fetchall.return_value = computers_data
            elif query == server_sql_dml_module.SELECT_LATEST_ACTIVITY_FOR_COMPUTER and params == (1,):
                mock_cursor.fetchone.return_value = normal_activity
            else:
                mock_cursor.fetchone.return_value = None
            return MagicMock()
        mock_cursor.execute.side_effect = execute_side_effect
        mock_render_template.return_value = "mocked_html"

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        mock_render_template.assert_called_once()
        args, kwargs = mock_render_template.call_args
        self.assertEqual(args[0], 'dashboard.html')
        self.assertIn('alerts', kwargs)
        alerts = kwargs['alerts']
        self.assertEqual(len(alerts), 0, f"Expected 0 alerts, got {len(alerts)}: {alerts}")

    # --- Original tests continue below ---
    # (test_log_activity_success_new_computer, etc.)
    # ... (rest of the TestServer class from previous step) ...
    # Note: The original test methods are assumed to be below this line.
    # For brevity, I'm not reproducing them all here again.
    # Make sure this new code block is inserted correctly into the existing TestServer class.

    # --- /log_activity Tests ---
    @patch('server.get_db_connection')
    def test_log_activity_success_new_computer(self, mock_get_db_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None
        mock_cursor.lastrowid = 1
        payload = {
            "netbios_name": "NEW_PC", "ip_address": "192.168.1.101",
            "timestamp": "2023-10-29T10:00:00", "free_disk_space_gb": 60.2,
            "cpu_usage_percent": 25.5, "gpu_usage_percent": 15.0,
            "active_window_title": "New Test Window"
        }
        response = self.client.post('/log_activity', json=payload)
        response_data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(response_data['message'], 'Data logged successfully')
        self.assertTrue(mock_cursor.execute.call_count >= 2)
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('server.get_db_connection')
    def test_log_activity_success_existing_computer(self, mock_get_db_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        existing_computer_id = 5
        mock_cursor.fetchone.return_value = (existing_computer_id,)
        payload = {
            "netbios_name": "EXISTING_PC", "ip_address": "192.168.1.102",
            "timestamp": "2023-10-29T11:00:00", "free_disk_space_gb": 70.0,
            "cpu_usage_percent": None, "gpu_usage_percent": None,
            "active_window_title": "Existing PC Window"
        }
        response = self.client.post('/log_activity', json=payload)
        response_data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(response_data['message'], 'Data logged successfully')
        self.assertTrue(mock_cursor.execute.call_count >= 2)
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('server.get_db_connection')
    def test_log_activity_bad_payload_missing_key(self, mock_get_db_conn):
        payload = {"ip_address": "192.168.1.100", "timestamp": "2023-10-28T12:00:00"}
        response = self.client.post('/log_activity', json=payload)
        response_data = response.get_json()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response_data['status'], 'error')
        self.assertIn("Missing required key: netbios_name", response_data['message'])
        mock_get_db_conn.assert_not_called()

    def test_log_activity_bad_payload_not_json(self):
        non_json_payload = "This is not a JSON string."
        response = self.client.post('/log_activity', data=non_json_payload, content_type='text/plain')
        response_data = response.get_json()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response_data['status'], 'error')
        self.assertEqual(response_data['message'], 'Invalid JSON payload')

    @patch('server.get_db_connection')
    def test_log_activity_bad_payload_empty_json(self, mock_get_db_conn):
        payload = {}
        response = self.client.post('/log_activity', json=payload)
        response_data = response.get_json()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response_data['status'], 'error')
        self.assertEqual(response_data['message'], 'Invalid JSON payload')
        mock_get_db_conn.assert_not_called()

    # --- /api/groups/create Tests ---
    @patch('server.get_db_connection')
    def test_create_group_success(self, mock_get_db_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        payload = {'name': 'Test Group', 'description': 'A test group'}
        response = self.client.post('/api/groups/create', json=payload)
        response_data = response.get_json()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(response_data['message'], 'Group created successfully')
        self.assertEqual(response_data['group_name'], 'Test Group')
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('server.get_db_connection')
    def test_create_group_duplicate_name(self, mock_get_db_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_db_error = create_mock_mariadb_error("Duplicate entry 'Existing Group' for key 'name'", 1062)
        mock_cursor.execute.side_effect = mock_db_error

        payload = {'name': 'Existing Group'}
        response = self.client.post('/api/groups/create', json=payload)
        response_data = response.get_json()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response_data['status'], 'error')
        self.assertIn("Group name 'Existing Group' already exists", response_data['message'])
        mock_conn.rollback.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('server.get_db_connection')
    def test_create_group_missing_name(self, mock_get_db_conn):
        payload = {'description': 'A group without a name'}
        response = self.client.post('/api/groups/create', json=payload)
        response_data = response.get_json()
        self.assertEqual(response.status_code, 400)
        self.assertIn("Group name is required", response_data['message'])
        mock_get_db_conn.assert_not_called()

    # --- /api/groups Tests ---
    @patch('server.get_db_connection')
    def test_list_groups_success(self, mock_get_db_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [(1, 'Group A', 'Desc A'), (2, 'Group B', None)]

        response = self.client.get('/api/groups')
        response_data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response_data['groups']), 2)
        self.assertEqual(response_data['groups'][0]['name'], 'Group A')
        self.assertEqual(response_data['groups'][1]['description'], '')
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('server.get_db_connection')
    def test_list_groups_empty(self, mock_get_db_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        response = self.client.get('/api/groups')
        response_data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response_data['groups']), 0)
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    # --- /api/computers/<netbios_name>/assign_group Tests ---
    @patch('server.get_db_connection')
    def test_assign_group_success(self, mock_get_db_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.side_effect = [(1,), (10,)]

        payload = {'group_name': 'Test Group'}
        response = self.client.post('/api/computers/TEST_PC/assign_group', json=payload)
        response_data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data['status'], 'success')
        self.assertIn("Computer 'TEST_PC' assigned to group successfully", response_data['message'])
        self.assertEqual(mock_cursor.execute.call_count, 3)
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('server.get_db_connection')
    def test_assign_group_computer_not_found(self, mock_get_db_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        payload = {'group_name': 'Test Group'}
        response = self.client.post('/api/computers/UNKNOWN_PC/assign_group', json=payload)
        response_data = response.get_json()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response_data['status'], 'error')
        self.assertIn("Computer with NetBIOS name 'UNKNOWN_PC' not found", response_data['message'])
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('server.get_db_connection')
    def test_assign_group_group_not_found_by_name(self, mock_get_db_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.side_effect = [(1,), None]

        payload = {'group_name': 'NonExistentGroup'}
        response = self.client.post('/api/computers/TEST_PC/assign_group', json=payload)
        response_data = response.get_json()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response_data['status'], 'error')
        self.assertIn("Group with name 'NonExistentGroup' not found", response_data['message'])
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('server.get_db_connection')
    def test_assign_group_invalid_group_id_fk_error(self, mock_get_db_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = (1,)

        mock_db_error = create_mock_mariadb_error("Simulated FK constraint error for group_id", 1452)

        def execute_side_effect(query, params=None):
            if "UPDATE computers SET group_id" in query:
                if params and params[0] == 999 :
                     raise mock_db_error
            return MagicMock()
        mock_cursor.execute.side_effect = execute_side_effect

        payload = {'group_id': 999}
        response = self.client.post('/api/computers/TEST_PC/assign_group', json=payload)
        response_data = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response_data['status'], 'error')
        self.assertIn("Invalid 'group_id': The specified group does not exist.", response_data['message'])
        mock_conn.rollback.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

if __name__ == '__main__':
    if not flask_app_imported:
        print("Skipping tests as Flask app could not be imported from server.py.")
    else:
        unittest.main()
