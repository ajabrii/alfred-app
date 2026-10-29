"""Alfred's brain: hand Claude a goal and the screen, let it drive.

This is a Claude *computer-use* loop. Alfred doesn't guess pixels or script apps;
Claude looks at a screenshot and calls member tools (`left_click`, `type`, `key`,
`scroll`, `screenshot`, ...) which Alfred's `Screen` carries out on the real
desktop. The same loop runs on macOS, Windows, and Linux because `Screen` is the
only OS-specific part.

Uses the GA computer toolset (`computer_toolset_20260801`) — no beta header, the
action is the tool_use block's `name`, several calls can arrive per turn, and
every tool_result must echo `"toolset_name": "computer"`.
"""
from __future__ import annotations

import base64
from typing import Callable

import anthropic

from .config import Config
from .screen import Screen

Event = Callable[[str, str], None]  # (kind, text) -> None, for the UI/CLI to show

TOOLSET = "computer_toolset_20260801"
CLICKS = {"left_click": ("left", 1), "right_click": ("right", 1),
          "middle_click": ("middle", 1), "double_click": ("left", 2),
          "triple_click": ("left", 3)}

SYSTEM = """You are Alfred, a careful desktop assistant operating the user's REAL
computer through screenshots and mouse/keyboard actions. The screen may be macOS,
Windows, or Linux — look at the screenshot to tell which, and use that OS's
conventions (menus, shortcuts, window controls).

How to work:
- Take a screenshot whenever you're unsure what's on screen. Look before you click.
- Work in small, verifiable steps. After an action that changes the screen, take a
  screenshot to confirm it did what you expected before continuing.
- Prefer keyboard shortcuts and typing over hunting for tiny targets when it's reliable.
- If something is ambiguous or you're blocked, stop and say so in plain words rather
  than guessing.

SAFETY — this is the user's real machine, not a sandbox:
- Before any irreversible or high-stakes action — buying, paying, sending a message
  or email, posting publicly, deleting data, submitting a form with personal details,
  or confirming anything involving money — STOP. Do not perform it. Describe exactly
  what you are about to do and why, and end your turn so the user can confirm. Only
  proceed with such an action if the user's instruction already clearly authorized
  that specific step.
- Never enter passwords, card numbers, or other credentials yourself. If a step needs
  one, stop and ask the user to type it.

When the task is done, say briefly what you accomplished and stop."""


class Stopped(Exception):
    """The user asked Alfred to stop mid-task."""


class Agent:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.client = anthropic.Anthropic(api_key=cfg.api_key)
        self.screen = Screen()

    def run(self, goal: str, on_event: Event | None = None,
            should_stop: Callable[[], bool] | None = None, max_steps: int = 40) -> str:
        """Carry out `goal`, returning Alfred's final message. `on_event` receives
        ("thinking"|"action"|"say"|"error", text) as it works; `should_stop` is
        polled between steps so the UI can cancel."""
        say = on_event or (lambda *_: None)
        stop = should_stop or (lambda: False)

        tools = [{"type": TOOLSET, "configs": {"zoom": {"enabled": False}}}]
        shot = self.screen.grab()
        messages = [{"role": "user", "content": [
            {"type": "text", "text":
                f"Here is the current screen ({shot.width}x{shot.height}). "
                f"Please do this: {goal}"},
            _image(shot.png),
        ]}]

        final = ""
        for _ in range(max_steps):
            if stop():
                raise Stopped()
            resp = self.client.messages.create(
                model=self.cfg.model, max_tokens=8192, system=SYSTEM,
                tools=tools, messages=messages,
            )
            messages.append({"role": "assistant", "content": resp.content})

            calls = []
            for block in resp.content:
                if block.type == "text" and block.text.strip():
                    final = block.text.strip()
                    say("say", final)
                elif block.type == "tool_use":
                    calls.append(block)

            if not calls:  # end_turn — Alfred finished or is waiting on the user
                return final

            results, failed = [], False
            for block in calls:
                if failed:
                    results.append(_result(block.id, text="Not executed: an earlier "
                                           "action this turn failed.", error=True))
                    continue
                if stop():
                    raise Stopped()
                try:
                    kind, payload = self._do(block.name, block.input or {}, say)
                    if kind == "image":
                        results.append(_result(block.id, image=payload))
                    else:
                        results.append(_result(block.id, text=payload))
                except Exception as e:  # noqa: BLE001 — report the failure to Claude
                    say("error", f"{block.name}: {e}")
                    results.append(_result(block.id, text=f"Action failed: {e}", error=True))
                    failed = True
            messages.append({"role": "user", "content": results})

        say("say", "Reached the step limit for this task — stopping here.")
        return final or "Reached the step limit for this task."

    def _do(self, name: str, inp: dict, say: Event):
        """Execute one computer member tool; return ("image", png) or ("text", str)."""
        s = self.screen
        coord = inp.get("coordinate")
        mods = tuple(inp["text"].split("+")) if inp.get("text") and name in CLICKS else ()

        if name == "screenshot":
            return "image", s.grab().png
        if name in CLICKS:
            button, count = CLICKS[name]
            say("action", f"{name} at {coord}" if coord else name)
            s.click(coord, button=button, count=count, modifiers=mods)
        elif name == "mouse_move":
            s.move(coord)
        elif name == "left_mouse_down":
            s.mouse_down()
        elif name == "left_mouse_up":
            s.mouse_up()
        elif name == "left_click_drag":
            say("action", f"drag {inp.get('start_coordinate')} -> {coord}")
            s.drag(inp["start_coordinate"], coord)
        elif name == "cursor_position":
            return "text", f"cursor at {s.cursor()}"
        elif name == "scroll":
            s.scroll(inp.get("scroll_direction", "down"), inp.get("scroll_amount", 3), coord)
        elif name == "type":
            say("action", f'type "{_short(inp.get("text", ""))}"')
            s.type_text(inp.get("text", ""))
        elif name == "key":
            say("action", f'key {inp.get("text", "")}')
            s.key(inp.get("text", ""), int(inp.get("repeat", 1)))
        elif name == "hold_key":
            s.hold_key(inp.get("text", ""), inp.get("duration", 1))
        elif name == "wait":
            s.wait(inp.get("duration", 1))
        else:
            return "text", f"Unknown action '{name}' — skipped."
        return "text", "OK"


def _image(png: bytes) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                        "data": base64.standard_b64encode(png).decode()}}


def _result(tool_use_id: str, *, text: str | None = None,
            image: bytes | None = None, error: bool = False) -> dict:
    content = [_image(image)] if image is not None else [{"type": "text", "text": text}]
    r = {"type": "tool_result", "tool_use_id": tool_use_id,
         "toolset_name": "computer", "content": content}
    if error:
        r["is_error"] = True
    return r


def _short(text: str, n: int = 50) -> str:
    text = text.replace("\n", " ")
    return text if len(text) <= n else text[:n] + "…"
