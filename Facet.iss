#ifndef AppVersion
  #define AppVersion Trim(FileRead(FileOpen("VERSION")))
#endif
#ifndef SrcDir
  #define SrcDir "dist\Facet"
#endif
#ifndef OutDir
  #define OutDir "installer"
#endif

[Setup]
AppId={{2DCEA151-DD2B-4C19-9D67-F28197B8E6ED}
AppName=Facet
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\Facet
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\Facet.exe
UninstallDisplayName=Facet
OutputDir={#OutDir}
OutputBaseFilename=Facet-setup
SetupIconFile=assets\Facet.ico
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
DisableDirPage=auto

[Files]
Source: "{#SrcDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Facet"; Filename: "{app}\Facet.exe"
Name: "{autodesktop}\Facet"; Filename: "{app}\Facet.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительно:"; Flags: unchecked

[Run]
Filename: "{app}\Facet.exe"; Description: "Запустить Facet"; Flags: nowait postinstall skipifsilent
