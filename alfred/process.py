"""Launch external provider tools without PyInstaller's private runtime paths."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys


def external_env():
    env = os.environ.copy()
    if getattr(sys, 'frozen', False):
        for name in ('LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH'):
            original = env.get(name + '_ORIG')
            if original is None:
                env.pop(name, None)
            else:
                env[name] = original
    env['CODEX_NON_INTERACTIVE'] = '1'
    env['PATH'] = os.pathsep.join([str(Path.home()/'.local/bin'), env.get('PATH', '')])
    return env


def spawn(command, **kwargs):
    kwargs.setdefault('env', external_env())
    if sys.platform == 'win32':
        kwargs.setdefault('creationflags', subprocess.CREATE_NO_WINDOW)
    frozen_windows = sys.platform == 'win32' and getattr(sys, 'frozen', False)
    if frozen_windows:
        ctypes.windll.kernel32.SetDllDirectoryW(None)
    try:
        return subprocess.Popen(command, **kwargs)
    finally:
        if frozen_windows:
            ctypes.windll.kernel32.SetDllDirectoryW(sys._MEIPASS)
