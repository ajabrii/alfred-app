"""Alfred's face: a small bar you summon with a hotkey, tell what to do, and
watch work. Frameless, always-on-top, lives in the system tray. The agent runs
on a worker thread so the bar stays responsive, and Esc stops a running task.
"""
from __future__ import annotations

import sys

from PyQt6 import QtCore, QtGui, QtWidgets

from .config import Config

PAPER, INK, GOLD, MUTED = "#f7f1e4", "#231d14", "#d79a2b", "#8a7f6d"


class Worker(QtCore.QThread):
    event = QtCore.pyqtSignal(str, str)
    done = QtCore.pyqtSignal(str)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, cfg: Config, goal: str) -> None:
        super().__init__()
        self.cfg, self.goal, self._stop = cfg, goal, False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        from .agent import Agent, Stopped
        try:
            agent = Agent(self.cfg)
            result = agent.run(self.goal, on_event=self.event.emit,
                               should_stop=lambda: self._stop)
            self.done.emit(result)
        except Stopped:
            self.done.emit("Stopped.")
        except Exception as e:  # noqa: BLE001 — surface any failure in the bar
            self.failed.emit(str(e))


class Bar(QtWidgets.QWidget):
    summon_requested = QtCore.pyqtSignal()

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self.worker: Worker | None = None
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build()
        self.summon_requested.connect(self.summon)

    def _build(self) -> None:
        self.card = QtWidgets.QFrame(self)
        self.card.setObjectName("card")
        self.input = QtWidgets.QLineEdit()
        self.input.setPlaceholderText("tell alfred what to do…  (e.g. open my email)")
        self.input.returnPressed.connect(self._submit)
        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        self.status.hide()
        self.stop_btn = QtWidgets.QPushButton("stop")
        self.stop_btn.setObjectName("stop")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.hide()

        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.input)
        row.addWidget(self.stop_btn)
        lay = QtWidgets.QVBoxLayout(self.card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)
        lay.addLayout(row)
        lay.addWidget(self.status)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.card)

        self.setStyleSheet(f"""
            #card {{ background:{PAPER}; border:1.5px solid {INK};
                     border-radius:16px; }}
            QLineEdit {{ background:transparent; border:none; color:{INK};
                         font-size:17px; padding:6px 2px; }}
            #status {{ color:{MUTED}; font-size:13px; }}
            #stop {{ background:{INK}; color:{PAPER}; border:none;
                     border-radius:9px; padding:6px 14px; font-size:13px; }}
            QPushButton#stop:hover {{ background:{GOLD}; color:{INK}; }}
        """)
        self.resize(560, 70)

    # ---- show / hide ------------------------------------------------------
    def summon(self) -> None:
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        self.move(screen.center().x() - self.width() // 2, screen.top() + 120)
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def keyPressEvent(self, e: QtGui.QKeyEvent) -> None:
        if e.key() == QtCore.Qt.Key.Key_Escape:
            if self.worker and self.worker.isRunning():
                self._stop()
            else:
                self.hide()
        else:
            super().keyPressEvent(e)

    # ---- run --------------------------------------------------------------
    def _submit(self) -> None:
        goal = self.input.text().strip()
        if not goal or (self.worker and self.worker.isRunning()):
            return
        self.input.setEnabled(False)
        self.status.setText("on it…")
        self.status.show()
        self.stop_btn.show()
        self.adjustSize()
        self.worker = Worker(self.cfg, goal)
        self.worker.event.connect(self._on_event)
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_event(self, kind: str, text: str) -> None:
        prefix = {"action": "▸ ", "say": "", "error": "⚠ ", "thinking": "… "}.get(kind, "")
        self.status.setText(prefix + text)
        self.adjustSize()

    def _on_done(self, text: str) -> None:
        self.status.setText(text or "done.")
        self._reset_input()

    def _on_failed(self, text: str) -> None:
        hint = text
        if "authentication" in text.lower() or "api_key" in text.lower():
            hint = "That API key didn't work. Re-run setup to fix it."
        self.status.setText("⚠ " + hint)
        self._reset_input()

    def _stop(self) -> None:
        if self.worker:
            self.worker.stop()
        self.status.setText("stopping…")

    def _reset_input(self) -> None:
        self.input.setEnabled(True)
        self.input.clear()
        self.input.setFocus()
        self.stop_btn.hide()
        self.adjustSize()


def _hotkey_listener(bar: Bar, combo: str):
    """Global hotkey via pynput; emits into the GUI thread. Returns the listener
    (or None if hotkeys aren't permitted — common on macOS before accessibility
    is granted; the tray menu still works)."""
    try:
        from pynput import keyboard
    except Exception:  # noqa: BLE001
        return None
    try:
        hk = keyboard.GlobalHotKeys({combo: bar.summon_requested.emit})
        hk.daemon = True
        hk.start()
        return hk
    except Exception:  # noqa: BLE001
        return None


def _tray(app: QtWidgets.QApplication, bar: Bar) -> QtWidgets.QSystemTrayIcon:
    pix = QtGui.QPixmap(64, 64)
    pix.fill(QtGui.QColor(INK))
    p = QtGui.QPainter(pix)
    p.setPen(QtGui.QColor(GOLD))
    f = QtGui.QFont()
    f.setPointSize(34)
    f.setBold(True)
    p.setFont(f)
    p.drawText(pix.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "a")
    p.end()
    tray = QtWidgets.QSystemTrayIcon(QtGui.QIcon(pix), app)
    menu = QtWidgets.QMenu()
    menu.addAction("Summon Alfred", bar.summon)
    menu.addSeparator()
    menu.addAction("Quit", app.quit)
    tray.setContextMenu(menu)
    tray.setToolTip("Alfred — press the hotkey to summon")
    tray.show()
    return tray


def run_app(cfg: Config) -> int:
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # live in the tray, not tied to the bar
    if not cfg.ready:
        from .setup_ui import SetupDialog
        dialog = SetupDialog(cfg)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return 0
        cfg = dialog.cfg
    bar = Bar(cfg)
    bar._hotkey = _hotkey_listener(bar, cfg.hotkey)   # keep a ref alive
    bar._tray = _tray(app, bar)
    bar.summon()
    return app.exec()
