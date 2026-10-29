"""Alfred's hands and eyes, the same on every OS.

Claude's computer-use works in the pixel space of the screenshots you send it,
and accuracy drops once an image gets much past ~1280px on the long edge. So
Alfred grabs the real screen with `mss`, downscales it to a target box for the
model, and scales the model's click coordinates *back* up to real pixels before
`pyautogui` acts. One class hides all of that; the agent just calls `grab()` and
the action methods, which take coordinates in the model's (downscaled) space.
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass

import mss
import pyautogui
from PIL import Image

pyautogui.FAILSAFE = False  # we have our own stop control; don't abort on corner-hit
pyautogui.PAUSE = 0.04

# Keep the model's view within this box. Accuracy/cost balance, not fidelity.
MAX_W, MAX_H = 1280, 800

# Claude returns xdotool-style key names; pyautogui wants its own. Translate the
# ones that actually differ (letters/digits/punctuation pass straight through).
_KEYMAP = {
    "return": "enter", "kp_enter": "enter", "escape": "esc", "prior": "pageup",
    "next": "pagedown", "page_up": "pageup", "page_down": "pagedown",
    "super": "win", "super_l": "win", "super_r": "win", "control": "ctrl",
    "control_l": "ctrl", "control_r": "ctrl", "alt_l": "alt", "alt_r": "alt",
    "shift_l": "shift", "shift_r": "shift", "meta": "win", "menu": "apps",
    "bprback": "backspace",
}
Coord = "list[int] | tuple[int, int] | None"


def _pg_key(name: str) -> str:
    return _KEYMAP.get(name.strip().lower(), name.strip().lower())


def _split(combo: str) -> list[str]:
    return [_pg_key(k) for k in combo.replace(" ", "").split("+") if k]


@dataclass
class Shot:
    png: bytes          # PNG bytes at the model's (downscaled) resolution
    width: int          # the width the model sees
    height: int         # the height the model sees


class Screen:
    """Grab the primary monitor and drive the mouse/keyboard, OS-agnostic."""

    def __init__(self) -> None:
        with mss.mss() as sct:
            mon = sct.monitors[1]  # [0] is the union of all monitors; [1] is primary
            self.left, self.top = mon["left"], mon["top"]
            self.real_w, self.real_h = mon["width"], mon["height"]
        scale = min(MAX_W / self.real_w, MAX_H / self.real_h, 1.0)
        self.view_w = max(1, round(self.real_w * scale))
        self.view_h = max(1, round(self.real_h * scale))

    # ---- eyes -------------------------------------------------------------
    def grab(self) -> Shot:
        with mss.mss() as sct:
            raw = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", (raw.width, raw.height), raw.rgb)
        if (img.width, img.height) != (self.view_w, self.view_h):
            img = img.resize((self.view_w, self.view_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Shot(buf.getvalue(), self.view_w, self.view_h)

    def _real(self, coord) -> tuple[int, int]:
        x, y = coord
        return (self.left + int(x * self.real_w / self.view_w),
                self.top + int(y * self.real_h / self.view_h))

    # ---- hands (coordinates are in the model's downscaled space) ----------
    def move(self, coord) -> None:
        pyautogui.moveTo(*self._real(coord))

    def click(self, coord=None, button="left", count=1, modifiers=()) -> None:
        if coord is not None:
            pyautogui.moveTo(*self._real(coord))
        keys = [_pg_key(m) for m in modifiers]
        for k in keys:
            pyautogui.keyDown(k)
        try:
            pyautogui.click(clicks=count, interval=0.08, button=button)
        finally:
            for k in reversed(keys):
                pyautogui.keyUp(k)

    def mouse_down(self, button="left") -> None:
        pyautogui.mouseDown(button=button)

    def mouse_up(self, button="left") -> None:
        pyautogui.mouseUp(button=button)

    def drag(self, start, end, button="left") -> None:
        pyautogui.moveTo(*self._real(start))
        pyautogui.dragTo(*self._real(end), duration=0.3, button=button)

    def scroll(self, direction, amount, coord=None) -> None:
        if coord is not None:
            pyautogui.moveTo(*self._real(coord))
        step = int(amount) * 100
        if direction in ("up", "down"):
            pyautogui.scroll(step if direction == "up" else -step)
        elif direction in ("left", "right") and hasattr(pyautogui, "hscroll"):
            pyautogui.hscroll(step if direction == "right" else -step)

    def type_text(self, text: str) -> None:
        pyautogui.write(text, interval=0.01)

    def key(self, combo: str, repeat: int = 1) -> None:
        keys = _split(combo)
        for _ in range(max(1, min(repeat, 100))):
            if len(keys) == 1:
                pyautogui.press(keys[0])
            elif keys:
                pyautogui.hotkey(*keys)

    def hold_key(self, combo: str, duration: float) -> None:
        keys = _split(combo)
        for k in keys:
            pyautogui.keyDown(k)
        time.sleep(min(float(duration), 10.0))
        for k in reversed(keys):
            pyautogui.keyUp(k)

    def cursor(self) -> tuple[int, int]:
        x, y = pyautogui.position()
        return (int((x - self.left) * self.view_w / self.real_w),
                int((y - self.top) * self.view_h / self.real_h))

    @staticmethod
    def wait(seconds: float = 0.5) -> None:
        time.sleep(min(float(seconds), 10.0))
