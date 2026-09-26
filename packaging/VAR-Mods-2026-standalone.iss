; VAR-Mods-2026 v1.0.0 standalone installer

#define AppName "VAR-Mods-2026"
#define AppVersion "1.0.0"

[Setup]
AppId={{F3B4E32B-7E2A-4C0B-9DB1-3CE9F08B8B6A}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=miladeazkat-maker
DefaultDirName={localappdata}\Programs\VAR-Mods-2026
DefaultGroupName={#AppName}
OutputDir=..\dist
OutputBaseFilename=VAR-Mods-2026-v1.0.0-Setup
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\MyMods.exe
VersionInfoVersion=1.0.0.0
VersionInfoDescription=VAR-Mods-2026 standalone installation package
VersionInfoProductName=VAR-Mods-2026

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut for MyMods"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\release-stage\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\VAR-Mods-2026\MyMods"; Filename: "{app}\MyMods.exe"
Name: "{autoprograms}\VAR-Mods-2026\ModBridge"; Filename: "{app}\ModBridge.exe"
Name: "{autoprograms}\VAR-Mods-2026\Asset Downloader"; Filename: "{app}\Asset Downloader.exe"
Name: "{autodesktop}\VAR-Mods-2026"; Filename: "{app}\MyMods.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MyMods.exe"; Description: "Launch VAR-Mods-2026"; Flags: nowait postinstall skipifsilent
