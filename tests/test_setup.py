import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from PyQt6 import QtWidgets
from alfred.config import Config
from alfred.setup_ui import SetupDialog

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

class SetupTests(unittest.TestCase):
    def test_cli_selection_saves_without_terminal(self):
        with tempfile.TemporaryDirectory() as folder, patch('alfred.config.config_path', return_value=Path(folder)/'config.json'), patch('alfred.setup_ui.available_backends', return_value={'claude-cli':False,'codex-cli':True,'claude-api':True}):
            d = SetupDialog(Config())
            self.assertEqual(d.backend.currentData(), 'codex-cli')
            d.accept()
            self.assertEqual(d.result(), QtWidgets.QDialog.DialogCode.Accepted)
            self.assertIn('codex-cli', (Path(folder)/'config.json').read_text())

    def test_missing_cli_and_empty_api_key_cannot_continue(self):
        with patch('alfred.setup_ui.available_backends', return_value={'claude-cli':False,'codex-cli':False,'claude-api':True}):
            d = SetupDialog(Config())
            self.assertFalse(d.save_button.isEnabled())
            d.key.setText('test-placeholder')
            self.assertTrue(d.save_button.isEnabled())
            d.backend.setCurrentIndex(0)
            self.assertFalse(d.save_button.isEnabled())
            d.reject()
            self.assertEqual(d.result(), QtWidgets.QDialog.DialogCode.Rejected)

if __name__ == '__main__':
    unittest.main()
