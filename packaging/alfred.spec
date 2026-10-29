# -*- mode: python ; coding: utf-8 -*-
"""One PyInstaller spec, built on each OS by CI to make a native Alfred:
  • Linux   → a single executable `Alfred`
  • Windows → `Alfred.exe` (windowed, no console)
  • macOS   → `Alfred.app` bundle
Run from the repo root:  pyinstaller packaging/alfred.spec
"""
import os
import sys
from PyInstaller.utils.hooks import collect_all

# SPECPATH is the spec's own directory (packaging/); the app lives one level up.
ROOT = os.path.dirname(SPECPATH)

datas, binaries, hiddenimports = [], [], []
for pkg in ("pyautogui", "pynput", "mss", "anthropic", "PyQt6"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [os.path.join(ROOT, "run_alfred.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Alfred",
    debug=False,
    strip=False,
    upx=False,
    console=False,            # GUI/tray app — no terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Alfred.app",
        icon=None,
        bundle_identifier="com.alfred.agent",
        info_plist={
            "NSHighResolutionCapable": True,
            "LSUIElement": True,  # menu-bar/tray app, no dock icon
            # macOS shows these when Alfred first asks for control of the screen:
            "NSAppleEventsUsageDescription":
                "Alfred controls apps on your behalf to do what you ask.",
        },
    )
