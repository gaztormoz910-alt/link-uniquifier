; Inno Setup — установщик Facet. Без абсолютных путей: собирается и локально, и в CI.
; Локальная сборка передаёт версию/пути через ISCC /D..., CI — то же самое; иначе
; берём значения по умолчанию (версия — из файла VERSION).

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
; AppId менять НЕЛЬЗЯ: по нему находится предыдущая установка при обновлении.
AppId={{2DCEA151-DD2B-4C19-9D67-F28197B8E6ED}
AppName=Facet
AppVersion={#AppVersion}
; Издатель/копирайт/URL намеренно НЕ заданы: это метаданные (свойства setup.exe и
; строка «Издатель» в списке программ), их в проекте не держим.
; В профиль пользователя, а не в Program Files: приложение сохраняет файлы туда,
; куда укажет пользователь, и не требует прав администратора (без UAC).
DefaultDirName={localappdata}\Programs\Facet
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\Facet.exe
UninstallDisplayName=Facet
OutputDir={#OutDir}
; Имя файла БЕЗ версии — иначе постоянная ссылка releases/latest/download сломается.
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
