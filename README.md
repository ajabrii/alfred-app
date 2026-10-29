# Alfred

A desktop agent that actually clicks for you. Tell Alfred what you want —
"book my swim," "clean up my downloads folder," "reply to the last email" — and
it looks at your screen and does it, on macOS, Windows, or Linux.

Alfred runs on the AI **you already have**. Pick your brain in setup:

| Backend | What it uses | Need a key? |
|---------|--------------|-------------|
| **Claude Code CLI** | your logged-in `claude` | No |
| **Codex CLI** | your logged-in `codex` | No |
| **Claude API key** | the Anthropic API directly | Yes (you paste one) |

If you already use the `claude` or `codex` command, Alfred just borrows it — no
API keys, nothing extra to pay for beyond the subscription you already have.

---

## Install

Download the file for your computer from the
[latest release](../../releases/latest):

| OS | File |
|----|------|
| macOS (Apple Silicon) | `Alfred-macos-arm64.dmg` |
| macOS (Intel) | `Alfred-macos-x86_64.dmg` |
| Windows | `Alfred-windows-x86_64.exe` |
| Linux | `Alfred-linux-x86_64` |

### First launch — getting past the "unidentified developer" warning

These early builds aren't code-signed yet, so your OS will warn you the first time.
This is expected; here's how to open Alfred anyway:

- **macOS:** open the `.dmg`, drag Alfred to Applications, then **right-click
  Alfred → Open → Open**. (A plain double-click is blocked the first time.)
- **Windows:** on the blue "Windows protected your PC" screen, click
  **More info → Run anyway**.
- **Linux:** `chmod +x Alfred-linux-x86_64 && ./Alfred-linux-x86_64`

On macOS, Alfred also needs **Accessibility** and **Screen Recording** permission
to see and control the screen — macOS will prompt you; grant both in
*System Settings → Privacy & Security*, then relaunch.

---

## Using Alfred

1. On first launch, Alfred asks **which AI to use** — Claude CLI, Codex CLI, or an
   Anthropic API key. It auto-detects which CLIs you already have. Your choice
   (and a key, only if you picked that option) is saved locally.
2. Alfred lives in your menu bar / system tray. Press **Ctrl+Space** (the default
   hotkey) to summon the bar, type what you want, and hit Enter.
3. Watch it work. Press **Esc** or **stop** to halt it at any time.

**Safety:** Alfred pauses and asks before anything irreversible — buying, sending,
posting, deleting, or submitting personal details — and never types passwords or
card numbers itself.

---

## Run from source / develop

```bash
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m alfred setup            # choose your AI backend (Claude CLI / Codex CLI / API key)
python -m alfred                  # launch the assistant
python -m alfred run "open my calendar"   # one task, headless
```

## Build a native app yourself

```bash
pip install pyinstaller
pyinstaller --noconfirm packaging/alfred.spec
# -> dist/Alfred (Linux), dist/Alfred.exe (Windows), dist/Alfred.app (macOS)
```

CI (`.github/workflows/build.yml`) builds all four targets on real runners when you
push a tag like `v0.1.0`, and publishes them to a GitHub Release.

---

Not affiliated with Apple, Microsoft, or Anthropic. Alfred is a client for the
Anthropic API that you bring your own key to.
