import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os
import configparser # For NoSectionError, NoOptionError
import datetime # For creating specific datetime objects for mocking
import json # For parsing JSON strings

# Add the project root to sys.path to allow importing agent.py
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from agent import load_app_config, main as agent_main # Import the function and main

class TestAgentConfigLoading(unittest.TestCase):

    @patch('agent.configparser.ConfigParser')
    @patch('agent.os.path.exists')
    def test_load_full_config(self, mock_path_exists, MockConfigParser):
        mock_path_exists.return_value = True
        mock_parser_instance = MagicMock()
        MockConfigParser.return_value = mock_parser_instance

        def get_side_effect(section, option, fallback=None):
            if section == 'server' and option == 'address': return 'testserver.com'
            if section == 'agent_settings' and option == 'log_folder': return '/var/log/agent'
            if fallback is not None: return fallback
            raise configparser.NoOptionError(option, section)

        def getint_side_effect(section, option, fallback=None):
            if section == 'agent_settings' and option == 'cpu_alert_threshold': return 80
            if section == 'agent_settings' and option == 'gpu_alert_threshold': return 75
            if fallback is not None: return fallback
            raise configparser.NoOptionError(option, section)

        mock_parser_instance.get.side_effect = get_side_effect
        mock_parser_instance.getint.side_effect = getint_side_effect
        mock_parser_instance.read.return_value = ['config.ini']

        loaded_config = load_app_config()

        self.assertEqual(loaded_config['server_address'], 'testserver.com')
        self.assertEqual(loaded_config['cpu_alert_threshold'], 80)
        self.assertEqual(loaded_config['gpu_alert_threshold'], 75)
        self.assertEqual(loaded_config['log_folder'], '/var/log/agent')

    @patch('agent.configparser.ConfigParser')
    @patch('agent.os.path.exists')
    def test_load_partial_config_defaults_apply(self, mock_path_exists, MockConfigParser):
        mock_path_exists.return_value = True
        mock_parser_instance = MagicMock()
        MockConfigParser.return_value = mock_parser_instance

        def get_side_effect(section, option, fallback=None):
            if section == 'server' and option == 'address': return 'anotherserver.com'
            if fallback is not None: return fallback
            raise configparser.NoOptionError(option, section)

        def getint_side_effect(section, option, fallback=None):
            if section == 'agent_settings' and option == 'cpu_alert_threshold': return 85
            if fallback is not None: return fallback
            raise configparser.NoOptionError(option, section)

        mock_parser_instance.get.side_effect = get_side_effect
        mock_parser_instance.getint.side_effect = getint_side_effect
        mock_parser_instance.read.return_value = ['config.ini']

        loaded_config = load_app_config()

        self.assertEqual(loaded_config['server_address'], 'anotherserver.com')
        self.assertEqual(loaded_config['cpu_alert_threshold'], 85)
        self.assertEqual(loaded_config['gpu_alert_threshold'], 90)
        self.assertEqual(loaded_config['log_folder'], '.')

    @patch('agent.os.path.exists')
    def test_load_config_file_not_found(self, mock_path_exists):
        mock_path_exists.return_value = False
        loaded_config = load_app_config()
        self.assertIsNone(loaded_config['server_address'])
        self.assertEqual(loaded_config['cpu_alert_threshold'], 90)
        self.assertEqual(loaded_config['gpu_alert_threshold'], 90)
        self.assertEqual(loaded_config['log_folder'], '.')

    @patch('agent.configparser.ConfigParser')
    @patch('agent.os.path.exists')
    def test_load_config_agent_settings_section_missing(self, mock_path_exists, MockConfigParser):
        mock_path_exists.return_value = True
        mock_parser_instance = MagicMock()
        MockConfigParser.return_value = mock_parser_instance

        def get_config_value(section, option, fallback=None, is_int=False):
            if section == 'server' and option == 'address':
                return 'serverfromconfig.com'
            if section == 'agent_settings':
                raise configparser.NoSectionError(section)
            if fallback is not None: return fallback
            raise configparser.NoOptionError(option, section)

        mock_parser_instance.get.side_effect = lambda section, option, fallback=None: get_config_value(section, option, fallback=fallback)
        mock_parser_instance.getint.side_effect = lambda section, option, fallback=None: get_config_value(section, option, fallback=fallback, is_int=True)
        mock_parser_instance.read.return_value = ['config.ini']

        loaded_config = load_app_config()

        self.assertIsNone(loaded_config['server_address'])
        self.assertEqual(loaded_config['cpu_alert_threshold'], 90)
        self.assertEqual(loaded_config['gpu_alert_threshold'], 90)
        self.assertEqual(loaded_config['log_folder'], '.')

class LoopBreak(Exception): pass

class TestAgentMainLogic(unittest.TestCase):

    # Common decorator stack for main loop tests
    def main_loop_test_decorators(func):
        @patch('agent.load_app_config')
        @patch('agent.datetime')
        @patch('agent.log_data_to_file')
        @patch('agent.get_netbios_name', return_value='TestPC')
        @patch('agent.get_ip_address', return_value='127.0.0.1')
        @patch('agent.get_free_disk_space', return_value=50.5)
        # CPU and GPU usage will be patched per test method
        @patch('agent.get_active_window_title', return_value='Test Window')
        @patch('agent.send_data_to_server')
        @patch('agent.time.sleep', side_effect=LoopBreak)
        # We will let json.dumps run with the actual payload
        def wrapper(self, mock_time_sleep, mock_send_data, mock_get_active_window,
                    mock_get_disk, mock_get_ip, mock_get_netbios,
                    mock_log_data_to_file, mock_datetime, mock_load_app_config,
                    *additional_mocks): # For mocks specific to the test (cpu/gpu)

            # Pass all mocks to the decorated function
            args = (self, mock_time_sleep, mock_send_data, mock_get_active_window,
                    mock_get_disk, mock_get_ip, mock_get_netbios,
                    mock_log_data_to_file, mock_datetime, mock_load_app_config) + additional_mocks
            return func(*args)
        return wrapper

    @main_loop_test_decorators
    @patch('agent.get_cpu_usage', return_value=10.0)
    @patch('agent.get_gpu_usage', return_value=5.0)
    def test_log_file_path_generation_in_main(self, mock_time_sleep, mock_send_data,
                                             mock_get_active_window, mock_get_disk,
                                             mock_get_ip, mock_get_netbios,
                                             mock_log_data_to_file, mock_datetime,
                                             mock_load_app_config, mock_get_gpu, mock_get_cpu):
        mock_load_app_config.return_value = {
            'log_folder': '/custom/logs', 'server_address': 'testserver.com',
            'cpu_alert_threshold': 90, 'gpu_alert_threshold': 90
        }
        fixed_datetime = datetime.datetime(2023, 10, 28, 14, 30, 0)
        mock_datetime.now.return_value = fixed_datetime
        try: agent_main()
        except LoopBreak: pass
        self.assertTrue(mock_log_data_to_file.called)
        actual_call_args = mock_log_data_to_file.call_args
        self.assertIsNotNone(actual_call_args)
        logged_file_path = actual_call_args[0][0]
        expected_log_filename = "231028Log_Usage_Windows.log"
        expected_full_path = os.path.join('/custom/logs', expected_log_filename)
        self.assertEqual(logged_file_path, expected_full_path)

    @main_loop_test_decorators
    @patch('agent.get_cpu_usage', return_value=75.5) # CPU above threshold
    @patch('agent.get_gpu_usage', return_value=None)  # GPU not relevant here or None
    def test_cpu_usage_above_threshold_in_payload(self, mock_time_sleep, mock_send_data,
                                             mock_get_active_window, mock_get_disk,
                                             mock_get_ip, mock_get_netbios,
                                             mock_log_data_to_file, mock_datetime,
                                             mock_load_app_config, mock_get_gpu, mock_get_cpu):
        mock_load_app_config.return_value = {
            'log_folder': '.', 'server_address': 'dummy',
            'cpu_alert_threshold': 50, 'gpu_alert_threshold': 90
        }
        mock_datetime.now.return_value = datetime.datetime(2023, 1, 1)
        try: agent_main()
        except LoopBreak: pass
        self.assertTrue(mock_log_data_to_file.called)
        json_payload_str = mock_log_data_to_file.call_args[0][1]
        payload = json.loads(json_payload_str)
        self.assertEqual(payload['cpu_usage_percent'], 75.5)

    @main_loop_test_decorators
    @patch('agent.get_cpu_usage', return_value=30.0) # CPU below threshold
    @patch('agent.get_gpu_usage', return_value=None)
    def test_cpu_usage_below_threshold_in_payload(self, mock_time_sleep, mock_send_data,
                                             mock_get_active_window, mock_get_disk,
                                             mock_get_ip, mock_get_netbios,
                                             mock_log_data_to_file, mock_datetime,
                                             mock_load_app_config, mock_get_gpu, mock_get_cpu):
        mock_load_app_config.return_value = {
            'log_folder': '.', 'server_address': 'dummy',
            'cpu_alert_threshold': 50, 'gpu_alert_threshold': 90
        }
        mock_datetime.now.return_value = datetime.datetime(2023, 1, 1)
        try: agent_main()
        except LoopBreak: pass
        self.assertTrue(mock_log_data_to_file.called)
        json_payload_str = mock_log_data_to_file.call_args[0][1]
        payload = json.loads(json_payload_str)
        self.assertIsNone(payload['cpu_usage_percent'])

    @main_loop_test_decorators
    @patch('agent.get_cpu_usage', return_value=None) # CPU not relevant
    @patch('agent.get_gpu_usage', return_value=95.2)  # GPU above threshold
    def test_gpu_usage_above_threshold_in_payload(self, mock_time_sleep, mock_send_data,
                                             mock_get_active_window, mock_get_disk,
                                             mock_get_ip, mock_get_netbios,
                                             mock_log_data_to_file, mock_datetime,
                                             mock_load_app_config, mock_get_gpu, mock_get_cpu):
        mock_load_app_config.return_value = {
            'log_folder': '.', 'server_address': 'dummy',
            'cpu_alert_threshold': 90, 'gpu_alert_threshold': 70
        }
        mock_datetime.now.return_value = datetime.datetime(2023, 1, 1)
        try: agent_main()
        except LoopBreak: pass
        self.assertTrue(mock_log_data_to_file.called)
        json_payload_str = mock_log_data_to_file.call_args[0][1]
        payload = json.loads(json_payload_str)
        self.assertEqual(payload['gpu_usage_percent'], 95.2)

    @main_loop_test_decorators
    @patch('agent.get_cpu_usage', return_value=None)
    @patch('agent.get_gpu_usage', return_value=60.0)  # GPU below threshold
    def test_gpu_usage_below_threshold_in_payload(self, mock_time_sleep, mock_send_data,
                                             mock_get_active_window, mock_get_disk,
                                             mock_get_ip, mock_get_netbios,
                                             mock_log_data_to_file, mock_datetime,
                                             mock_load_app_config, mock_get_gpu, mock_get_cpu):
        mock_load_app_config.return_value = {
            'log_folder': '.', 'server_address': 'dummy',
            'cpu_alert_threshold': 90, 'gpu_alert_threshold': 70
        }
        mock_datetime.now.return_value = datetime.datetime(2023, 1, 1)
        try: agent_main()
        except LoopBreak: pass
        self.assertTrue(mock_log_data_to_file.called)
        json_payload_str = mock_log_data_to_file.call_args[0][1]
        payload = json.loads(json_payload_str)
        self.assertIsNone(payload['gpu_usage_percent'])

if __name__ == '__main__':
    unittest.main()
