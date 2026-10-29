"""Provider setup through their official installers and browser authentication."""
from __future__ import annotations
import os
import queue
import re
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
import certifi
from PyQt6 import QtCore
from .planners import find_cli
from .process import external_env, spawn

INSTALLERS = {
    'claude': ('https://claude.ai/install.sh', 'https://claude.ai/install.ps1'),
    'codex': ('https://chatgpt.com/codex/install.sh', 'https://chatgpt.com/codex/install.ps1'),
}
AUTH_HOSTS = {'claude.ai', 'console.anthropic.com', 'platform.claude.com', 'auth.openai.com', 'chatgpt.com', 'auth0.openai.com'}


def auth_url(text):
    for url in re.findall(r'https://[^\s\x1b<>"\']+', text):
        if urlparse(url).hostname in AUTH_HOSTS:
            return url
    return None


class Connector(QtCore.QThread):
    progress = QtCore.pyqtSignal(str)
    browser = QtCore.pyqtSignal(str)
    connected = QtCore.pyqtSignal()
    failed = QtCore.pyqtSignal(str)

    def __init__(self, provider):
        super().__init__()
        self.provider = provider
        self.cancelled = threading.Event()

    def cancel(self):
        self.cancelled.set()

    def command(self, command, timeout=600, login=False):
        if self.cancelled.is_set():
            raise RuntimeError('Setup cancelled. You can try again whenever you are ready.')
        with spawn(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                              env=external_env()) as proc:
            lines = queue.Queue()
            def read():
                for line in proc.stdout:
                    lines.put(line)
            reader = threading.Thread(target=read, daemon=True)
            reader.start()
            deadline = time.monotonic() + timeout
            output = ''
            opened = False
            try:
                while proc.poll() is None or not lines.empty() or reader.is_alive():
                    if self.cancelled.is_set() or time.monotonic() > deadline:
                        raise RuntimeError('Setup was cancelled or took too long. Check your connection and try again.')
                    try:
                        line = lines.get(timeout=.1)
                    except queue.Empty:
                        continue
                    output = (output + line)[-32000:]
                    if login and not opened:
                        url = auth_url(line)
                        if url:
                            self.browser.emit(url)
                            opened = True
                return proc.wait(), output
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()

    def run(self):
        try:
            binary = find_cli(self.provider)
            if not binary:
                self.progress.emit('Downloading the official installer… This may take a few minutes.')
                windows = sys.platform == 'win32'
                url = INSTALLERS[self.provider][int(windows)]
                with tempfile.TemporaryDirectory(prefix='alfred-connect-') as directory:
                    script = Path(directory) / ('install.ps1' if windows else 'install.sh')
                    context = ssl.create_default_context(cafile=certifi.where())
                    with urllib.request.urlopen(url, timeout=30, context=context) as response:
                        data = response.read(2_000_001)
                    if len(data) > 2_000_000 or not data:
                        raise RuntimeError('The provider installer could not be downloaded. Please try again.')
                    script.write_bytes(data)
                    self.progress.emit('Installing your AI connection… Please keep Alfred open.')
                    command = (['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(script)]
                               if windows else ['bash' if self.provider == 'claude' else 'sh', str(script)])
                    code, _ = self.command(command)
                    binary = find_cli(self.provider)
                    if code or not binary:
                        raise RuntimeError('The provider could not be installed. Check your internet connection, then retry. See Help for system requirements.')
            self.progress.emit('Checking your account…')
            status = [binary, 'auth', 'status'] if self.provider == 'claude' else [binary, 'login', 'status']
            code, output = self.command(status, timeout=30)
            if code:
                self.progress.emit('Finish signing in in your browser, then return here. Alfred will detect when you are connected.')
                login = [binary, 'auth', 'login'] if self.provider == 'claude' else [binary, 'login']
                code, _ = self.command(login, login=True)
                if code:
                    raise RuntimeError('Sign-in was not completed. Click Connect to try again.')
                code, _ = self.command(status, timeout=30)
                if code:
                    raise RuntimeError('We could not confirm your sign-in. Please try connecting again.')
            if not self.cancelled.is_set():
                self.connected.emit()
        except Exception as exc:
            self.failed.emit(str(exc) if isinstance(exc, RuntimeError) else 'Could not connect. Check your internet connection and try again, or open Help.')
