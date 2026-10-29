import sys
import unittest
from unittest.mock import patch, MagicMock
from alfred.connect import Connector

class ConnectorTests(unittest.TestCase):
    def test_existing_signed_in_provider_is_reused(self):
        worker = Connector('codex')
        connected = []
        worker.connected.connect(lambda: connected.append(True))
        with patch('alfred.connect.find_cli', return_value='/installed/codex'), patch.object(worker, 'command', return_value=(0, 'Logged in')) as command:
            worker.run()
            command.assert_called_once_with(['/installed/codex', 'login', 'status'], timeout=30)
        self.assertEqual(connected, [True])

    def test_browser_login_is_verified_before_success(self):
        worker = Connector('claude')
        connected = []
        worker.connected.connect(lambda: connected.append(True))
        with patch('alfred.connect.find_cli', return_value='/installed/claude'), patch.object(worker, 'command', side_effect=[(1,''),(0,''),(1,'')]) as command:
            worker.run()
        self.assertEqual(connected, [])
        self.assertEqual(command.call_count, 3)

    def test_missing_provider_uses_official_installer(self):
        worker = Connector('codex')
        connected = []
        worker.connected.connect(lambda: connected.append(True))
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'# official installer test fixture'
        with patch('alfred.connect.find_cli', side_effect=[None,'/installed/codex']), patch('alfred.connect.urllib.request.urlopen', return_value=response) as download, patch.object(worker, 'command', return_value=(0,'')) as command:
            worker.run()
        self.assertEqual(connected, [True])
        self.assertTrue(download.call_args.args[0].startswith('https://chatgpt.com/codex/install.'))
        self.assertEqual(command.call_count, 2)

    def test_process_timeout_and_cancel(self):
        worker=Connector('codex')
        with self.assertRaises(RuntimeError):
            worker.command([sys.executable,'-c','import time; time.sleep(10)'], timeout=.05)
        worker.cancel()
        with self.assertRaises(RuntimeError):
            worker.command([sys.executable,'-c','print(1)'])
