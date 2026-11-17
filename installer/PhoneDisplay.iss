; Inno Setup script for Phone Display
; Build: ISCC.exe /DAppVersion=1.0.0 installer\PhoneDisplay.iss
; Expects PyInstaller output in dist\PhoneDisplay\ and icon in build\icon.ico

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Phone Display"
#define AppExe "PhoneDisplay.exe"
#define AppUrl "https://github.com/ShakalIST/Phone-Dispaly"

[Setup]
AppId={{7C3E2B1A-5D4F-4E8B-9A61-2F0C8D7E4B13}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=ShakalIST
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
DefaultDirName={autopf}\PhoneDisplay
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=Output
OutputBaseFilename=PhoneDisplay-Setup-{#AppVersion}
SetupIconFile=..\build\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
LicenseFile=..\LICENSE

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
ru.TaskVdd=Установить виртуальный экран (отдельный рабочий стол на телефоне, а не копия экрана)
en.TaskVdd=Install a virtual display (the phone gets its own desktop instead of a mirror)
ru.TaskAutostart=Запускать вместе с Windows
en.TaskAutostart=Start with Windows
ru.StatusVdd=Устанавливаю виртуальный экран (может занять минуту)...
en.StatusVdd=Installing the virtual display (may take a minute)...
ru.RunApp=Запустить Phone Display
en.RunApp=Launch Phone Display
ru.PhoneHint=На телефоне включите «Отладку по USB» (Настройки → Для разработчиков) и подключите его кабелем.
en.PhoneHint=On the phone enable "USB debugging" (Settings → Developer options) and connect it with a cable.

[Tasks]
Name: "vdd"; Description: "{cm:TaskVdd}"
Name: "autostart"; Description: "{cm:TaskAutostart}"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\PhoneDisplay\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "install_vdd.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "PhoneDisplay"; ValueData: """{app}\{#AppExe}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\install_vdd.ps1"""; StatusMsg: "{cm:StatusVdd}"; Flags: runhidden waituntilterminated; Tasks: vdd
Filename: "{app}\{#AppExe}"; Description: "{cm:RunApp}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "taskkill.exe"; Parameters: "/F /IM {#AppExe}"; Flags: runhidden; RunOnceId: "KillApp"

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\PhoneDisplay"

[Code]
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then
    WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + #13#10#13#10 + CustomMessage('PhoneHint');
end;
