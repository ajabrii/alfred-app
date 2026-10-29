(() => {
  'use strict';
  const base = 'https://github.com/ajabrii/alfred-app/releases/download/v0.2.0/';
  const targets = {
    windows: {file:'Alfred-Setup-windows-x86_64.exe', name:'Windows', requirements:'Windows 10 / 11 · 64-bit Intel or AMD. Windows ARM is not supported by this installer.', instructions:'Open the installer in Downloads. Click Install, then leave “Open Alfred” selected and click Finish.'},
    arm64: {file:'Alfred-Setup-macos-arm64.pkg', name:'Mac (Apple Silicon)', requirements:'macOS 15 or later · Apple Silicon.', instructions:'Open the package in Downloads. Follow Continue → Install, then open Alfred from Applications.'},
    x86_64: {file:'Alfred-Setup-macos-x86_64.pkg', name:'Mac (Intel)', requirements:'macOS 15 or later · Intel processor.', instructions:'Open the package in Downloads. Follow Continue → Install, then open Alfred from Applications.'},
    linux: {file:'Alfred-ubuntu-debian-amd64.deb', name:'Ubuntu / Debian', requirements:'Ubuntu 24.04+ or Debian 13+ · Intel / AMD 64-bit · X11 session. Use your system’s graphical package installer.', instructions:'Open the package with your software installer and click Install. Open Alfred from your applications menu. Use an X11 / Xorg desktop session.'}
  };
  const ua = navigator.userAgent || '';
  const mobile = /Android|iPhone|iPad|iPod/i.test(ua) || (/Mac/.test(navigator.platform || '') && navigator.maxTouchPoints > 1);
  const detected = mobile ? '' : /Windows/i.test(ua) ? 'windows' : /Mac/i.test(ua) ? 'mac' : /Linux/i.test(ua) ? 'linux' : '';
  const hero = document.getElementById('hero-download');
  if (hero && detected) {
    hero.textContent = 'download for ' + (detected === 'mac' ? 'mac' : detected === 'linux' ? 'linux' : 'windows');
    hero.href = detected === 'windows' ? base + targets.windows.file : '/setup.html?os=' + detected;
  }
  const select = document.getElementById('platform');
  if (!select) return;
  const query = new URLSearchParams(location.search).get('os');
  if (['windows','mac','linux'].includes(query || detected)) select.value = query || detected;
  const chip = document.getElementById('chip');
  const download = document.getElementById('download');
  const status = document.getElementById('download-status');
  function render() {
    const mac = select.value === 'mac';
    document.getElementById('mac-choice').hidden = !mac;
    const target = targets[mac ? chip.value : select.value];
    status.hidden = true;
    download.hidden = !target;
    if (!target) {
      document.getElementById('requirements').textContent = 'Choose your Mac’s chip above to get the correct installer.';
      document.getElementById('filename').textContent = '';
      document.getElementById('install-instructions').textContent = 'Open the package in Downloads. Follow Continue → Install, then open Alfred from Applications.';
      return;
    }
    download.href = base + target.file;
    download.textContent = 'Download for ' + target.name;
    document.getElementById('requirements').textContent = target.requirements;
    document.getElementById('filename').textContent = 'Installer · v0.2.0 · ' + target.file.split('.').pop().toUpperCase();
    document.getElementById('install-instructions').textContent = target.instructions;
    if (mobile) {
      status.hidden = false;
      status.textContent = 'You appear to be on a phone or tablet. Open this page on your computer to install Alfred.';
    }
  }
  select.addEventListener('change', render);
  chip.addEventListener('change', render);
  download.addEventListener('click', () => {
    status.hidden = false;
    status.textContent = 'Your browser will request the installer. Look in Downloads, then open it to continue. If nothing appears, try again.';
  });
  render();
})();
