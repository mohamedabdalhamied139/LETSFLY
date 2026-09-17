[Setup]
AppId={{9F82A312-70B4-4061-91D7-70CE4D1EE3F8}
AppName=TableVerse
AppVersion=2.0.0
AppPublisher=LetsFly Team
DefaultDirName={autopf}\TableVerse
DefaultGroupName=TableVerse
AllowNoIcons=yes
OutputDir=C:\Users\midoa\Downloads\LetsFly_Setup
OutputBaseFilename=TableVerse_Setup_v2.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "C:\Users\midoa\Downloads\LetsFly_Release_Build\LetsFly\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\TableVerse"; Filename: "{app}\LetsFly.exe"
Name: "{group}\{cm:UninstallProgram,TableVerse}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\TableVerse"; Filename: "{app}\LetsFly.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LetsFly.exe"; Description: "{cm:LaunchProgram,TableVerse}"; Flags: nowait postinstall skipifsilent
