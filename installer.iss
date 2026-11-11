#define MyAppName "Market Insight"
#define MyAppVersion "V1.12"
#define MyAppPublisher "Adrian Vale"
#define MyAppExeName "Market Insight.exe"

[Setup]
AppId={{A4B2C890-3D65-4D51-9B10-21C5D6A7E821}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Market Insight
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer-output
OutputBaseFilename=Market_Insight_Setup_{#MyAppVersion}
SetupIconFile=market_insight.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "dist\Market Insight\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Start_Market_Insight.vbs"; DestDir: "{app}"; Flags: ignoreversion
Source: "Create_Desktop_Shortcut.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Uninstall Market Insight"; Filename: "{uninstallexe}"; WorkingDir: "{app}"
Name: "{autoprograms}\Market Insight"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\market_insight.ico"; IconIndex: 0; AppUserModelID: "AdrianVale.MarketInsight"; WorkingDir: "{app}"
Name: "{autodesktop}\Market Insight"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\market_insight.ico"; IconIndex: 0; AppUserModelID: "AdrianVale.MarketInsight"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Market Insight"; Flags: postinstall nowait skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := IsWin64;
  if not Result then
    MsgBox('Market Insight requires 64-bit Windows 10 or Windows 11.', mbError, MB_OK);
end;
