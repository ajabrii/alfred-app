"""A guided first launch, with provider installation and browser sign-in."""
from dataclasses import replace
import ctypes
import os
import sys
from PyQt6 import QtCore, QtGui, QtWidgets
from . import config
from .connect import Connector
from .planners import available_backends

HELP_URL = 'https://alfred-chi-five.vercel.app/docs.html'


class SetupDialog(QtWidgets.QDialog):
    def __init__(self, cfg: config.Config):
        super().__init__()
        self.cfg = replace(cfg)
        self.available = available_backends()
        self.connected_backends = set()
        self.worker = None
        self.closing = False
        self.screen_ready = False
        self.stage = 0
        self.setWindowTitle('Set up Alfred')
        self.setMinimumWidth(520)
        self.setStyleSheet('''QDialog { background:#f7f1e4; color:#231d14; }
            QLabel { color:#231d14; font-size:14px; }
            QLineEdit, QComboBox { padding:10px; background:#fffdf6; color:#231d14; border:1px solid #8a7f6c; border-radius:6px; }
            QPushButton { padding:10px 18px; min-height:24px; }
            QPushButton:focus { border:2px solid #8b5a08; }
            QLabel#title { font-size:27px; font-weight:600; }
        ''')
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)
        outer.setSpacing(18)
        self.step_label = QtWidgets.QLabel()
        outer.addWidget(self.step_label)
        title = QtWidgets.QLabel('A little setup. Then, at your service.')
        title.setObjectName('title')
        title.setWordWrap(True)
        outer.addWidget(title)
        self.pages = QtWidgets.QStackedWidget()
        outer.addWidget(self.pages)
        first = QtWidgets.QWidget()
        form = QtWidgets.QVBoxLayout(first)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(12)
        intro = QtWidgets.QLabel('Choose your AI account. Alfred can install its connection for you. You will sign in on the provider’s own website.')
        intro.setWordWrap(True)
        form.addWidget(intro)
        self.backend = QtWidgets.QComboBox()
        for key, title in [('claude-cli', 'Claude'), ('codex-cli', 'ChatGPT / Codex'), ('claude-api', 'Advanced: Anthropic API key')]:
            self.backend.addItem(title, key)
        label = QtWidgets.QLabel('&Use an account from')
        label.setBuddy(self.backend)
        form.addWidget(label)
        form.addWidget(self.backend)
        self.hint = QtWidgets.QLabel()
        self.hint.setWordWrap(True)
        form.addWidget(self.hint)
        self.connect_button = QtWidgets.QPushButton('Install & connect')
        self.connect_button.clicked.connect(self.connect_provider)
        form.addWidget(self.connect_button)
        self.browser_button = QtWidgets.QPushButton('Open sign-in page again')
        self.browser_button.hide()
        self.browser_button.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(self.login_url)))
        form.addWidget(self.browser_button)
        self.key = QtWidgets.QLineEdit(cfg.api_key)
        self.key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.key_label = QtWidgets.QLabel('Anthropic API &key')
        self.key_label.setBuddy(self.key)
        form.addWidget(self.key_label)
        form.addWidget(self.key)
        self.progress = QtWidgets.QLabel()
        self.progress.setWordWrap(True)
        form.addWidget(self.progress)
        form.addStretch()
        self.pages.addWidget(first)

        permissions = QtWidgets.QWidget()
        perm = QtWidgets.QVBoxLayout(permissions)
        perm.setContentsMargins(0, 0, 0, 0)
        text = ('Alfred needs Screen Recording to see the screen and Accessibility to use your mouse and keyboard. Enable Alfred in both settings, then check access.' if sys.platform == 'darwin'
                else 'Alfred needs to see your screen and use the mouse and keyboard. Click Check access to test screen capture. No image is saved or sent during this check.')
        if sys.platform.startswith('linux'):
            text += '\n\nUse an X11 desktop session. Wayland is not supported in this preview.'
        info = QtWidgets.QLabel(text)
        info.setWordWrap(True)
        perm.addWidget(info)
        if sys.platform == 'darwin':
            for label, anchor in [('Open Screen Recording settings', 'Privacy_ScreenCapture'), ('Open Accessibility settings', 'Privacy_Accessibility')]:
                button = QtWidgets.QPushButton(label)
                button.clicked.connect(lambda checked=False, target=anchor: QtGui.QDesktopServices.openUrl(QtCore.QUrl('x-apple.systempreferences:com.apple.preference.security?' + target)))
                perm.addWidget(button)
        check = QtWidgets.QPushButton('Check access')
        check.clicked.connect(self.check_access)
        perm.addWidget(check)
        self.permission_status = QtWidgets.QLabel()
        self.permission_status.setWordWrap(True)
        perm.addWidget(self.permission_status)
        perm.addStretch()
        self.pages.addWidget(permissions)

        ready = QtWidgets.QWidget()
        ready_layout = QtWidgets.QVBoxLayout(ready)
        ready_layout.setContentsMargins(0, 0, 0, 0)
        ready_text = QtWidgets.QLabel('You’re ready.\n\nTry: “Open my browser.”\n\nPress Ctrl + Space to bring Alfred back. Use Stop in Alfred’s bar to stop a task.\n\nStay nearby while Alfred works. Your chosen AI receives screenshots during tasks. Provider usage limits and billing still apply.')
        ready_text.setWordWrap(True)
        ready_layout.addWidget(ready_text)
        ready_layout.addStretch()
        self.pages.addWidget(ready)
        self.error = QtWidgets.QLabel()
        self.error.setWordWrap(True)
        outer.addWidget(self.error)
        row = QtWidgets.QHBoxLayout()
        help_button = QtWidgets.QPushButton('Help')
        help_button.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(HELP_URL)))
        row.addWidget(help_button)
        row.addStretch()
        self.back = QtWidgets.QPushButton('Back')
        self.back.clicked.connect(self.go_back)
        row.addWidget(self.back)
        self.cancel_button = QtWidgets.QPushButton('Cancel')
        self.cancel_button.clicked.connect(self.reject)
        row.addWidget(self.cancel_button)
        self.save_button = QtWidgets.QPushButton('Continue')
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self.accept)
        row.addWidget(self.save_button)
        outer.addLayout(row)
        self.backend.currentIndexChanged.connect(self.update_fields)
        self.key.textChanged.connect(self.validate)
        preferred = cfg.backend or next((k for k, v in self.available.items() if v and k != 'claude-api'), 'claude-cli')
        self.backend.setCurrentIndex(max(0, self.backend.findData(preferred)))
        self.update_fields()
        self.render_stage()

    def update_fields(self):
        backend = self.backend.currentData()
        api = backend == 'claude-api'
        self.key.setVisible(api)
        self.key_label.setVisible(api)
        self.connect_button.setVisible(not api)
        self.browser_button.hide()
        self.progress.clear()
        self.error.clear()
        self.hint.setText('Advanced option: API usage is billed separately by Anthropic. Your key is saved in your local Alfred settings.' if api else 'An eligible provider account is required. Alfred installs the official provider software only when you click below.')
        self.connect_button.setText('Check connection' if self.available.get(backend) else 'Install & connect')
        self.validate()

    def connect_provider(self):
        if self.worker and self.worker.isRunning():
            return
        backend = self.backend.currentData()
        self.backend.setEnabled(False)
        self.connect_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.error.clear()
        self.worker = Connector('claude' if backend == 'claude-cli' else 'codex')
        self.worker.progress.connect(self.progress.setText)
        self.worker.browser.connect(self.open_login)
        self.worker.connected.connect(lambda: self.connection_ok(backend))
        self.worker.failed.connect(self.error.setText)
        self.worker.finished.connect(self.connection_finished)
        self.worker.start()

    def open_login(self, url):
        self.login_url = url
        self.browser_button.show()
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def connection_ok(self, backend):
        self.connected_backends.add(backend)
        self.progress.setText('Connected. You can continue.')
        self.browser_button.hide()

    def connection_finished(self):
        self.backend.setEnabled(True)
        self.connect_button.setEnabled(True)
        self.validate()
        if self.closing:
            super().reject()

    def check_access(self):
        try:
            if sys.platform.startswith('linux') and os.environ.get('XDG_SESSION_TYPE') == 'wayland':
                raise RuntimeError('Sign out, choose an X11 / Xorg session on your login screen, then open Alfred again.')
            if sys.platform == 'darwin':
                access = ctypes.CDLL('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
                access.AXIsProcessTrusted.restype = ctypes.c_bool
                if not access.AXIsProcessTrusted():
                    raise RuntimeError('Enable Alfred under Accessibility, then check again.')
                capture = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
                capture.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
                if not capture.CGPreflightScreenCaptureAccess():
                    capture.CGRequestScreenCaptureAccess()
                    raise RuntimeError('Enable Screen Recording for Alfred, then quit and reopen Alfred.')
            import mss
            with mss.mss() as screen:
                screen.grab(screen.monitors[1])
            self.screen_ready = True
            self.permission_status.setText('Screen access is ready.')
        except Exception as exc:
            self.screen_ready = False
            self.permission_status.setText(str(exc) if isinstance(exc, RuntimeError) else 'Screen access is not ready. Check your permissions and desktop session, then try again.')
        self.validate()

    def validate(self):
        if self.stage == 0:
            backend = self.backend.currentData()
            valid = bool(self.key.text().strip()) if backend == 'claude-api' else backend in self.connected_backends
        else:
            valid = self.screen_ready
        busy = self.worker and self.worker.isRunning()
        self.save_button.setEnabled(bool(valid and not busy))

    def render_stage(self):
        self.pages.setCurrentIndex(self.stage)
        self.step_label.setText(['1 of 3 · Connect your AI', '2 of 3 · Check permissions', '3 of 3 · Ready'][self.stage])
        self.back.setEnabled(self.stage > 0)
        self.save_button.setText('Start Alfred' if self.stage == 2 else 'Continue')
        self.validate()

    def go_back(self):
        self.stage = max(0, self.stage - 1)
        self.render_stage()

    def accept(self):
        self.validate()
        if not self.save_button.isEnabled():
            return
        if self.stage < 2:
            self.stage += 1
            self.render_stage()
            return
        self.cfg.backend = self.backend.currentData()
        self.cfg.api_key = self.key.text().strip() if self.cfg.backend == 'claude-api' else ''
        try:
            config.save(self.cfg)
        except OSError:
            self.error.setText('Could not save settings. Check that your configuration folder is writable.')
            return
        super().accept()

    def reject(self):
        if self.worker and self.worker.isRunning():
            self.closing = True
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self.progress.setText('Cancelling setup…')
            return
        super().reject()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.reject()
            event.ignore()
        else:
            event.accept()
