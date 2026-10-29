"""Alfred's interchangeable brains.

Every backend does the same job: look at the current screenshot and return the
single next action as JSON. Alfred's loop executes it, screenshots again, and
asks for the next one. Backends:

  • ClaudeCliPlanner — shells out to the user's logged-in `claude` (Claude Code),
    reading the screenshot via its Read tool. No API key.
  • CodexCliPlanner  — shells out to the user's logged-in `codex exec -i`. No API key.
  • ClaudeApiPlanner — talks to the Anthropic API with a key the user pasted.

They all return an `Action`, so the loop in agent.py never cares which brain is
driving.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .screen import Shot

STEP_TIMEOUT = 180  # seconds a single planning call may take

# A double-clicked GUI app (macOS .app especially) inherits a bare PATH, so the
# CLIs a user installed in their shell often aren't found. Search the usual spots.
_EXTRA_BINS = [
    Path.home() / ".local" / "bin",
    Path.home() / ".npm-global" / "bin",
    Path.home() / ".codex" / "bin",
    Path.home() / ".claude" / "local",
    Path("/opt/homebrew/bin"),
    Path("/usr/local/bin"),
    Path("/usr/bin"),
    Path(os.environ.get("APPDATA", "")) / "npm",  # Windows npm global
]


def find_cli(name: str) -> str | None:
    """Locate a CLI by PATH first, then the common install dirs above."""
    hit = shutil.which(name)
    if hit:
        return hit
    for d in _EXTRA_BINS:
        for ext in ("", ".cmd", ".exe"):
            p = d / (name + ext)
            if p.exists():
                return str(p)
    return None

SYSTEM = (
    "You are Alfred, carefully operating the user's REAL computer. This is not a "
    "sandbox. Before any irreversible or high-stakes step — buying, paying, sending "
    "a message/email, posting publicly, deleting data, or submitting personal "
    'details — do NOT do it; return the "ask" action describing what you are about '
    "to do so the user can confirm. Never type passwords or card numbers yourself; "
    'use "ask" instead.'
)

SCHEMA = """Respond with ONLY one JSON object (no prose, no code fences, no extra text):
{"action":"click","x":<int>,"y":<int>}              left click at a point
{"action":"double_click","x":<int>,"y":<int>}
{"action":"right_click","x":<int>,"y":<int>}
{"action":"move","x":<int>,"y":<int>}
{"action":"drag","x":<int>,"y":<int>,"x2":<int>,"y2":<int>}
{"action":"type","text":"..."}                       type text at the current focus
{"action":"key","text":"ctrl+s"}                     press a key or combo (e.g. Return, ctrl+a)
{"action":"scroll","direction":"up|down|left|right","amount":<int>,"x":<int>,"y":<int>}
{"action":"wait","amount":<seconds>}
{"action":"ask","message":"..."}                     STOP and ask the user (blocked, unsure, or anything irreversible)
{"action":"done","message":"..."}                    the task is complete
Rules: pick exactly ONE action. Look carefully before you click. Prefer keyboard
shortcuts when they're reliable. Coordinates must lie inside the screenshot."""


@dataclass
class Action:
    action: str
    x: int | None = None
    y: int | None = None
    x2: int | None = None
    y2: int | None = None
    text: str = ""
    direction: str = "down"
    amount: int = 3
    message: str = ""


class PlannerError(RuntimeError):
    """A backend couldn't produce an action (CLI missing, timeout, bad output)."""


def build_prompt(goal: str, shot: Shot, history: list[str]) -> str:
    done = "\n".join(f"- {h}" for h in history[-12:]) or "- (nothing yet)"
    return (
        f"{SYSTEM}\n\n"
        f"You choose ONE action at a time to accomplish a goal on the screen.\n"
        f"The attached screenshot is the current screen, {shot.width}x{shot.height} "
        f"pixels; all coordinates must be within it.\n\n"
        f"GOAL: {goal}\n\n"
        f"Actions so far:\n{done}\n\n"
        f"{SCHEMA}"
    )


def parse_action(raw: str) -> Action:
    obj = _extract_json(raw)
    if not isinstance(obj, dict) or "action" not in obj:
        raise PlannerError(f"backend did not return a JSON action; got: {raw[:200]!r}")
    def i(k):
        v = obj.get(k)
        return int(v) if isinstance(v, (int, float)) else None
    return Action(
        action=str(obj["action"]).strip().lower(),
        x=i("x"), y=i("y"), x2=i("x2"), y2=i("y2"),
        text=str(obj.get("text", "")),
        direction=str(obj.get("direction", "down")),
        amount=i("amount") or 3,
        message=str(obj.get("message", "")),
    )


def _extract_json(text: str) -> dict | None:
    """Find the last balanced {...} in the text that parses as an object."""
    starts = [i for i, c in enumerate(text) if c == "{"]
    for start in reversed(starts):
        depth = 0
        for end in range(start, len(text)):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:end + 1])
                    except ValueError:
                        break
    return None


# --------------------------------------------------------------------------
class ClaudeCliPlanner:
    """Uses the user's logged-in Claude Code CLI as the vision planner."""

    name = "Claude CLI"

    def __init__(self, cfg: Config) -> None:
        self.model = cfg.model if cfg.model and cfg.model != "claude-sonnet-5-5" else ""
        self.bin = find_cli("claude")
        if not self.bin:
            raise PlannerError("The `claude` CLI isn't installed or on PATH. "
                               "Install Claude Code, run `claude` once to log in, then retry.")

    def plan(self, goal, shot, history):
        with tempfile.TemporaryDirectory(prefix="alfred-") as d:
            img = Path(d) / "screen.png"
            img.write_bytes(shot.png)
            prompt = (build_prompt(goal, shot, history)
                      + f"\n\nThe screenshot is the image file at: {img}\n"
                        "Use the Read tool to view it, then output only the JSON action.")
            cmd = [self.bin, "-p", prompt, "--output-format", "json",
                   "--allowedTools", "Read", "--add-dir", d]
            if self.model:
                cmd += ["--model", self.model]
            out = _run(cmd, cwd=d)
        try:  # claude --output-format json wraps the reply in an envelope
            env = json.loads(out)
            result = env.get("result", out) if isinstance(env, dict) else out
        except ValueError:
            result = out
        return parse_action(result if isinstance(result, str) else json.dumps(result))


class CodexCliPlanner:
    """Uses the user's logged-in Codex CLI (`codex exec -i`) as the vision planner."""

    name = "Codex CLI"

    def __init__(self, cfg: Config) -> None:
        self.model = cfg.model if cfg.model and not cfg.model.startswith("claude") else ""
        self.bin = find_cli("codex")
        if not self.bin:
            raise PlannerError("The `codex` CLI isn't installed or on PATH. "
                               "Install Codex, run `codex login` once, then retry.")

    def plan(self, goal, shot, history):
        with tempfile.TemporaryDirectory(prefix="alfred-") as d:
            img = Path(d) / "screen.png"
            img.write_bytes(shot.png)
            last = Path(d) / "reply.txt"
            prompt = (build_prompt(goal, shot, history)
                      + "\n\nLook only at the attached image. Do not run commands or "
                        "use tools. Output only the JSON action.")
            # read-only sandbox so Codex can't touch the machine; -o gives us just
            # the final assistant message, no log scraping.
            cmd = [self.bin, "exec", "--skip-git-repo-check", "-s", "read-only",
                   "--color", "never", "-i", str(img), "-o", str(last)]
            if self.model:
                cmd += ["-m", self.model]
            cmd.append(prompt)
            out = _run(cmd, cwd=d)
            reply = last.read_text("utf-8") if last.exists() else out
        return parse_action(reply)


class ClaudeApiPlanner:
    """Talks to the Anthropic API with the user's key (vision -> one JSON action)."""

    name = "Claude API"

    def __init__(self, cfg: Config) -> None:
        import anthropic
        if not cfg.api_key:
            raise PlannerError("No Anthropic API key set. Run `alfred setup`.")
        self.client = anthropic.Anthropic(api_key=cfg.api_key)
        self.model = cfg.model

    def plan(self, goal, shot, history):
        import anthropic
        img = {"type": "image", "source": {"type": "base64", "media_type": "image/png",
               "data": base64.standard_b64encode(shot.png).decode()}}
        try:
            resp = self.client.messages.create(
                model=self.model, max_tokens=1024,
                messages=[{"role": "user", "content": [
                    img, {"type": "text", "text": build_prompt(goal, shot, history)}]}],
            )
        except anthropic.AuthenticationError as e:
            raise PlannerError("Anthropic rejected the API key. Re-run setup.") from e
        except anthropic.APIError as e:
            raise PlannerError(f"Anthropic API error: {e}") from e
        text = "".join(b.text for b in resp.content if b.type == "text")
        return parse_action(text)


PLANNERS = {"claude-cli": ClaudeCliPlanner, "codex-cli": CodexCliPlanner,
            "claude-api": ClaudeApiPlanner}


def get_planner(cfg: Config):
    cls = PLANNERS.get(cfg.backend)
    if cls is None:
        raise PlannerError(f"Unknown backend {cfg.backend!r}. Run `alfred setup`.")
    return cls(cfg)


def available_backends() -> dict[str, bool]:
    """Which backends can run right now (CLI found; API always offerable)."""
    return {"claude-cli": bool(find_cli("claude")),
            "codex-cli": bool(find_cli("codex")),
            "claude-api": True}


def _run(cmd: list[str], cwd: str) -> str:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=STEP_TIMEOUT)
    except FileNotFoundError as e:
        raise PlannerError(f"{cmd[0]} not found: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise PlannerError(f"{cmd[0]} took too long to respond.") from e
    if p.returncode != 0:
        raise PlannerError(f"{cmd[0]} failed: {(p.stderr or p.stdout)[:300].strip()}")
    return p.stdout or ""
