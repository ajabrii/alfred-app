"""Create a package users open with their Ubuntu/Debian software installer."""
from pathlib import Path
import os
import shutil
import subprocess
from alfred import __version__
root = Path('build/deb')
(root/'DEBIAN').mkdir(parents=True, exist_ok=True)
(root/'opt/alfred').mkdir(parents=True, exist_ok=True)
(root/'usr/share/applications').mkdir(parents=True, exist_ok=True)
shutil.copy2('dist/Alfred', root/'opt/alfred/Alfred')
os.chmod(root/'opt/alfred/Alfred', 0o755)
(root/'DEBIAN/control').write_text(f'''Package: alfred-assistant
Version: {__version__}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Alfred <noreply@github.com>
Depends: libegl1, libgl1, libxkbcommon0, libxcb-cursor0, libxcb-xinerama0, libxcb-icccm4, libxcb-keysyms1, libxcb-shape0, libxcb-xkb1, libxkbcommon-x11-0, libxcb-render-util0, xdg-utils, curl, ca-certificates
Description: Alfred desktop assistant
 Guided setup for Claude or Codex. Requires an X11 desktop session.
''')
(root/'usr/share/applications/alfred.desktop').write_text('''[Desktop Entry]
Type=Application
Name=Alfred
Comment=Your desktop assistant
Exec=/opt/alfred/Alfred
Icon=utilities-terminal
Terminal=false
Categories=Utility;
StartupNotify=true
''')
Path('release').mkdir(exist_ok=True)
subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(root), 'release/Alfred-ubuntu-debian-amd64.deb'], check=True)
