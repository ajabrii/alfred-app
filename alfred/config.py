"""Alfred's local settings — the friend's own Anthropic API key and preferences,
stored in a per-user config file (never bundled into the app, never sent anywhere
but Anthropic). Cross-platform: respects %APPDATA% on Windows, ~/Library on macOS,
~/.config on Linux.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

APP = "Alfred"

# Alfred's "brain" can be one of several backends. The CLI backends use a coding
# CLI the friend already has logged in (no API key needed); the API backend talks
# to Anthropic directly with a key the friend pastes in.
BACKENDS = {
    "claude-cli": "Claude Code CLI  (uses your logged-in `claude`)",
    "codex-cli":  "Codex CLI        (uses your logged-in `codex`)",
    "claude-api": "Claude API key   (paste an Anthropic key)",
}
CLI_BACKENDS = {"claude-cli", "codex-cli"}
API_BACKENDS = {"claude-api"}

# Model used only by the API backend. Claude Sonnet 5.5 — Anthropic's strongest,
# cheapest tier for this kind of work. CLI backends use whatever model that CLI is
# configured with. Override via the config file or the ALFRED_MODEL env var.
DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_HOTKEY = "<ctrl>+<space>"


def config_dir() -> Path:
    """Where Alfred keeps its settings on this OS."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return Path(base) / APP
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / "alfred"


def config_path() -> Path:
    return config_dir() / "config.json"


@dataclass
class Config:
    backend: str = ""           # one of BACKENDS
    api_key: str = ""           # only for API backends
    model: str = DEFAULT_MODEL
    hotkey: str = DEFAULT_HOTKEY
    # Alfred pauses and asks before anything destructive (buying, sending,
    # deleting, posting). Leave this on unless you really know what you're doing.
    confirm_risky_actions: bool = True

    @property
    def ready(self) -> bool:
        """Has the user finished setup — picked a backend (and a key if it needs one)?"""
        if self.backend not in BACKENDS:
            return False
        if self.backend in API_BACKENDS:
            return bool(self.api_key.strip())
        return True  # CLI backends: the CLI's presence is checked when Alfred runs


def load() -> Config:
    """Read the saved config, or return defaults (plus any ANTHROPIC_API_KEY env)."""
    cfg = Config()
    path = config_path()
    if path.exists():
        try:
            data = json.loads(path.read_text("utf-8"))
            if isinstance(data, dict):
                for field in ("backend", "api_key", "model", "hotkey"):
                    if isinstance(data.get(field), str) and data[field]:
                        setattr(cfg, field, data[field])
                if isinstance(data.get("confirm_risky_actions"), bool):
                    cfg.confirm_risky_actions = data["confirm_risky_actions"]
        except (ValueError, OSError):
            pass  # corrupt or unreadable — fall back to defaults, don't crash
    if not cfg.api_key:
        cfg.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    cfg.model = os.environ.get("ALFRED_MODEL", cfg.model)
    return cfg


def save(cfg: Config) -> None:
    """Persist the config with user-only permissions (it holds an API key)."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), indent=2), "utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # best effort (Windows ACLs differ); the file is still per-user
