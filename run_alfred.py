"""Frozen-app entry point (what PyInstaller bundles)."""
from alfred.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
