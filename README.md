# Alfred

A desktop assistant with a guided installer and setup wizard.

**[Download Alfred](https://alfred-chi-five.vercel.app/setup.html)** · **[Help & docs](https://alfred-chi-five.vercel.app/docs.html)**

1. Download the installer for your computer and open it.
2. Open Alfred. Choose Claude or ChatGPT / Codex and click **Install & connect**.
3. Approve the provider's browser sign-in, check permissions, and click **Start Alfred**.

Alfred installs the official provider connection when missing. No terminal,
Python, or Node installation is needed by the user. An eligible AI account is
required; provider usage limits and billing apply. Existing connections are reused.
An Anthropic API key is an advanced alternative. Antigravity is not implemented.

## Installers

- Windows 10/11, Intel/AMD 64-bit: `.exe` installer, Start menu shortcut, uninstaller.
- macOS 15+, Apple Silicon or Intel: `.pkg` installer into Applications.
- Ubuntu 24.04+ / Debian 13+, Intel/AMD 64-bit: `.deb` package, app-menu entry.
  Requires an X11 session and a graphical package installer. Other distributions,
  ARM Linux and Wayland are not supported by this installer.

These preview packages are unsigned. See the docs for first-open instructions.
CI validates the setup wizard and builds on each native platform; full real-device
end-to-end onboarding is not verified on all systems.

## Using Alfred

Type a small task such as “Open my browser.” Ctrl+Space summons Alfred.
Use Stop in the bar to stop before the next action once an in-flight AI response
returns. Use the tray menu to reopen setup or quit.

Supervise the app. Its AI is instructed to ask before sensitive actions, but that
is not an enforced security boundary. Screenshots go to your selected AI provider
during tasks. A directly entered API key is saved in a local settings file.

## Development

Use Python 3.12. Install `requirements.txt`, then run `python -m alfred`.
Run setup tests with `QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v`.
Build with `pyinstaller --noconfirm packaging/alfred.spec`.
The release workflow builds the native installers when a version tag is pushed.

The `site/` folder contains the landing page, download guide and docs. Deploy only
that folder to Vercel. Provider installer URLs and sign-in flows are based on:
- https://learn.chatgpt.com/docs/cli
- https://learn.chatgpt.com/docs/auth
- https://code.claude.com/docs/en/setup
