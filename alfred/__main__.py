"""`alfred` — launch the assistant, or run a one-off task from the terminal.

    alfred            launch the floating assistant (system tray + hotkey)
    alfred setup      enter / change your Anthropic API key
    alfred run "..."  do one task headlessly and print what happens
    alfred --version
"""
from __future__ import annotations

import getpass
import sys

from . import __version__, config


def _setup() -> config.Config:
    cfg = config.load()
    print("Alfred needs your own Anthropic API key (you pay Anthropic directly for\n"
          "what Alfred does). Get one at https://console.anthropic.com/settings/keys\n")
    if cfg.api_key:
        print("A key is already saved. Press Enter to keep it, or paste a new one.")
    try:
        key = getpass.getpass("Anthropic API key (hidden): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        sys.exit(1)
    if key:
        cfg.api_key = key
    if not cfg.api_key:
        print("No key given — setup not complete.")
        sys.exit(1)
    config.save(cfg)
    print(f"Saved to {config.config_path()}. You're set — run `alfred` to start.")
    return cfg


def _run_headless(goal: str) -> int:
    from .agent import Agent, Stopped
    cfg = config.load()
    if not cfg.ready:
        print("No API key yet. Run `alfred setup` first.")
        return 1
    agent = Agent(cfg)
    print(f"Alfred: {goal}\n")
    try:
        result = agent.run(goal, on_event=lambda kind, text: print(f"  {text}"))
    except Stopped:
        print("\nStopped.")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"\nFailed: {e}")
        return 1
    print(f"\n{result}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] in ("--version", "-V"):
        print(f"alfred {__version__}")
        return 0
    if args and args[0] == "setup":
        _setup()
        return 0
    if args and args[0] == "run":
        goal = " ".join(args[1:]).strip()
        if not goal:
            print('Usage: alfred run "what you want done"')
            return 1
        return _run_headless(goal)

    cfg = config.load()
    if not cfg.ready:
        print("Welcome to Alfred. Let's set up your API key.\n")
        cfg = _setup()
    from .ui import run_app
    return run_app(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
