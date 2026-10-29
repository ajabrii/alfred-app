import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from PyQt6 import QtWidgets
from alfred.config import Config
from alfred.setup_ui import SetupDialog
from alfred.connect import auth_url, external_env

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

class SetupTests(unittest.TestCase):
    def test_connected_cli_and_permissions_required_before_save(self):
        with tempfile.TemporaryDirectory() as folder, patch('alfred.config.config_path', return_value=Path(folder)/'config.json'), patch('alfred.setup_ui.available_backends', return_value={'claude-cli':False,'codex-cli':True,'claude-api':True}):
            d = SetupDialog(Config())
            self.assertEqual(d.backend.currentData(), 'codex-cli')
            self.assertFalse(d.save_button.isEnabled())
            d.connection_ok('codex-cli');d.validate();d.accept()
            self.assertEqual(d.stage, 1)
            self.assertFalse(d.save_button.isEnabled())
            self.assertFalse((Path(folder)/'config.json').exists())
            d.screen_ready = True;d.accept()
            self.assertEqual(d.stage, 2)
            d.accept()
            self.assertEqual(d.result(), QtWidgets.QDialog.DialogCode.Accepted)
            self.assertIn('codex-cli', (Path(folder)/'config.json').read_text())

    def test_api_key_and_back_navigation(self):
        with patch('alfred.setup_ui.available_backends', return_value={}):
            d = SetupDialog(Config())
            d.backend.setCurrentIndex(2)
            self.assertFalse(d.save_button.isEnabled())
            d.key.setText('test-placeholder')
            self.assertTrue(d.save_button.isEnabled())
            d.accept();d.go_back()
            self.assertEqual(d.key.text(), 'test-placeholder')
            d.backend.setCurrentIndex(0)
            self.assertFalse(d.save_button.isEnabled())
            d.reject()
            self.assertEqual(d.result(), QtWidgets.QDialog.DialogCode.Rejected)

    def test_only_official_login_links_are_opened(self):
        self.assertEqual(auth_url('Open https://auth.openai.com/oauth/authorize?state=abc'), 'https://auth.openai.com/oauth/authorize?state=abc')
        self.assertIsNone(auth_url('https://auth.openai.com.attacker.example/login'))
        self.assertIsNone(auth_url('http://auth.openai.com/login'))

    def test_frozen_library_path_is_not_leaked_to_installer(self):
        with patch('sys.frozen', True, create=True), patch.dict(os.environ, {'LD_LIBRARY_PATH':'/tmp/bundle', 'LD_LIBRARY_PATH_ORIG':'/usr/lib'}):
            self.assertEqual(external_env()['LD_LIBRARY_PATH'], '/usr/lib')

if __name__ == '__main__':
    unittest.main()
