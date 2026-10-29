"""Alfred's loop: screenshot → ask the chosen brain for one action → do it → repeat.

The brain is a `planners.Planner` (Claude CLI, Codex CLI, or the Anthropic API) —
whichever the user picked in setup. The loop, the safety stops, and the actual
mouse/keyboard work are the same no matter which brain is driving.
"""
from __future__ import annotations

from typing import Callable

from .config import Config
from .planners import Action, PlannerError, get_planner
from .screen import Screen

Event = Callable[[str, str], None]  # (kind, text); kind in {action, say, error, thinking}


class Stopped(Exception):
    """The user asked Alfred to stop mid-task."""


class Agent:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.planner = get_planner(cfg)      # raises PlannerError if the backend isn't usable
        self.screen = Screen()

    def run(self, goal: str, on_event: Event | None = None,
            should_stop: Callable[[], bool] | None = None, max_steps: int = 40) -> str:
        say = on_event or (lambda *_: None)
        stop = should_stop or (lambda: False)
        history: list[str] = []

        for _ in range(max_steps):
            if stop():
                raise Stopped()
            shot = self.screen.grab()
            say("thinking", "looking at the screen…")
            try:
                act = self.planner.plan(goal, shot, history)
            except PlannerError as e:
                say("error", str(e))
                raise
            if stop():
                raise Stopped()

            if act.action == "done":
                msg = act.message or "Done."
                say("say", msg)
                return msg
            if act.action == "ask":
                msg = act.message or "I need you to take it from here."
                say("say", msg)
                return msg

            say("action", _describe(act))
            try:
                self._apply(act)
                history.append(_describe(act))
            except Exception as e:  # noqa: BLE001 — tell the brain the step failed, keep going
                say("error", f"{act.action}: {e}")
                history.append(f"(tried {act.action} but it failed: {e})")

        say("say", "Reached the step limit for this task — stopping here.")
        return "Reached the step limit for this task."

    def _apply(self, a: Action) -> None:
        s = self.screen
        xy = (a.x, a.y) if a.x is not None and a.y is not None else None
        if a.action == "click":
            s.click(xy)
        elif a.action == "double_click":
            s.click(xy, count=2)
        elif a.action == "right_click":
            s.click(xy, button="right")
        elif a.action == "move":
            s.move(xy)
        elif a.action == "drag" and xy and a.x2 is not None and a.y2 is not None:
            s.drag(xy, (a.x2, a.y2))
        elif a.action == "type":
            s.type_text(a.text)
        elif a.action == "key":
            s.key(a.text)
        elif a.action == "scroll":
            s.scroll(a.direction, a.amount, xy)
        elif a.action == "wait":
            s.wait(a.amount)
        else:
            raise ValueError(f"don't know how to do '{a.action}'")


def _describe(a: Action) -> str:
    if a.action in ("click", "double_click", "right_click", "move"):
        return f"{a.action.replace('_', ' ')} ({a.x}, {a.y})"
    if a.action == "drag":
        return f"drag ({a.x},{a.y}) → ({a.x2},{a.y2})"
    if a.action == "type":
        return f'type "{_short(a.text)}"'
    if a.action == "key":
        return f"press {a.text}"
    if a.action == "scroll":
        return f"scroll {a.direction} {a.amount}"
    if a.action == "wait":
        return f"wait {a.amount}s"
    return a.action


def _short(text: str, n: int = 50) -> str:
    text = text.replace("\n", " ")
    return text if len(text) <= n else text[:n] + "…"
