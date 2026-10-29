"""First-run setup for double-clicked native apps; no terminal required."""
from dataclasses import replace
from PyQt6 import QtWidgets
from . import config
from .planners import available_backends


class SetupDialog(QtWidgets.QDialog):
    def __init__(self, cfg: config.Config):
        super().__init__()
        self.cfg = replace(cfg)
        self.available = available_backends()
        self.setWindowTitle('Welcome to Alfred')
        self.setMinimumWidth(460)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        intro = QtWidgets.QLabel('Choose the AI Alfred will use to help on your computer.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.backend = QtWidgets.QComboBox()
        for key, title in config.BACKENDS.items():
            self.backend.addItem(title, key)
        label = QtWidgets.QLabel('&AI provider')
        label.setBuddy(self.backend)
        layout.addWidget(label)
        layout.addWidget(self.backend)
        self.hint = QtWidgets.QLabel()
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.key = QtWidgets.QLineEdit(cfg.api_key)
        self.key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.key_label = QtWidgets.QLabel('Anthropic API &key')
        self.key_label.setBuddy(self.key)
        layout.addWidget(self.key_label)
        layout.addWidget(self.key)
        self.error = QtWidgets.QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel |
            QtWidgets.QDialogButtonBox.StandardButton.Save)
        self.save_button = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Save)
        self.save_button.setText('Start Alfred')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.backend.currentIndexChanged.connect(self.update_fields)
        self.key.textChanged.connect(self.validate)
        preferred = cfg.backend or next((k for k, v in self.available.items() if v), 'claude-api')
        self.backend.setCurrentIndex(max(0, self.backend.findData(preferred)))
        self.update_fields()

    def update_fields(self):
        backend = self.backend.currentData()
        api = backend == 'claude-api'
        self.key.setVisible(api)
        self.key_label.setVisible(api)
        if api:
            self.hint.setText('Use your own Anthropic API key. API usage is billed by Anthropic.')
        elif self.available.get(backend):
            self.hint.setText('CLI found. Make sure you have signed in to it before starting a task.')
        else:
            self.hint.setText('CLI not found. Install and sign in to this CLI, then reopen Alfred, or choose another provider.')
        self.validate()

    def validate(self):
        backend = self.backend.currentData()
        valid = bool(self.key.text().strip()) if backend == 'claude-api' else self.available.get(backend, False)
        self.save_button.setEnabled(valid)
        self.error.setText('Enter an API key to continue.' if backend == 'claude-api' and not valid else '')

    def accept(self):
        self.validate()
        if not self.save_button.isEnabled():
            return
        self.cfg.backend = self.backend.currentData()
        self.cfg.api_key = self.key.text().strip() if self.cfg.backend == 'claude-api' else ''
        try:
            config.save(self.cfg)
        except OSError:
            self.error.setText('Could not save settings. Check that your configuration folder is writable.')
            return
        super().accept()
