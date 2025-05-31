import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock, call

# Add the project root to sys.path to allow importing server.py
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Attempt to import the Flask app from server.py
flask_app_imported = False
server_mariadb_module = None # For creating specific mariadb.Error instances
try:
    from server import app
    from server import mariadb as server_mariadb_module # Import mariadb module as used in server.py
    flask_app_imported = True
except ImportError as e:
    print(f"Failed to import Flask app or mariadb from server.py: {e}")
    app = None

# Helper to create a mock MariaDBError for testing
def create_mock_mariadb_error(message, errno):
    if server_mariadb_module and hasattr(server_mariadb_module, 'Error'):
        error = server_mariadb_module.Error(message)
    else: # Fallback if mariadb module itself couldn't be imported via server.py
        error = MagicMock(spec=Exception) # Base Exception
        error.message = message # For debug
    error.errno = errno
    return error

class TestServer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not flask_app_imported or not app:
            raise unittest.SkipTest("Flask app from server.py failed to import or is None.")
        app.testing = True
        print("\nFlask app imported successfully for testing.")

    def setUp(self):
        self.client = app.test_client()

    def tearDown(self):
        pass

    def test_server_home_route_responds(self):
        rule_exists = any(rule.rule == '/' for rule in app.url_map.iter_rules())
        if not rule_exists:
            self.fail("The route '/' is not defined in the Flask app.")
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Computer Activity Dashboard", response.data)

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
        response_data = response.get_json() # Use get_json() for test responses
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
        response_data = response.get_json() # Corrected from json.loads(response.data)
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
        # Corrected assertion: server.py's "if not data:" catches empty dicts first for /log_activity
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
    def test_assign_group_invalid_group_id_fk_error(self, mock_get_db_conn): # Renamed for clarity
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = (1,)

        mock_db_error = create_mock_mariadb_error("Simulated FK constraint error for group_id", 1452)

        # Make the execute call for UPDATE fail with the FK error
        def execute_side_effect(query, params=None):
            if "UPDATE computers SET group_id" in query:
                # Ensure the group_id being set would indeed cause an FK error
                # For this test, params[0] would be the group_id (e.g. 999)
                if params and params[0] == 999 : #The group_id we are testing with
                     raise mock_db_error
            # Allow other execute calls (like SELECT computer) to pass through or be handled by fetchone
            return MagicMock() # Default for other execute calls
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
