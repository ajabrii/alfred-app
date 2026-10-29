#define AppVersion GetEnv('ALFRED_VERSION')
[Setup]
AppId={{271B7255-30C4-4114-8208-749521138CA6}
AppName=Alfred
AppVersion={#AppVersion}
AppPublisher=Alfred
DefaultDirName={localappdata}\Programs\Alfred
DefaultGroupName=Alfred
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=Alfred-Setup-windows-x86_64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\Alfred.exe
CloseApplications=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
[Files]
Source: "..\dist\Alfred.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{autoprograms}\Alfred"; Filename: "{app}\Alfred.exe"
Name: "{autodesktop}\Alfred"; Filename: "{app}\Alfred.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\Alfred.exe"; Description: "Open Alfred and finish setup"; Flags: nowait postinstall skipifsilent
