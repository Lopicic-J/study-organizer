; ============================================================
;  Semetra — Inno Setup Installer Script
;  Voraussetzung: Inno Setup 6+ von https://jrsoftware.org
;  Ausführen:    Rechtsklick auf installer.iss → Compile
;  Ergebnis:     installer-output\Semetra-Setup.exe
; ============================================================

#define AppName      "Semetra"
#define AppVersion   "2.0.0"
#define AppPublisher "Lopicic Technologies"
#define AppURL       "https://www.semetra.ch"
#define AppExeName   "Semetra.exe"
#define BuildDir     "dist\Semetra"

[Setup]
AppId={{8F3A2B1C-4D5E-6F7A-8B9C-0D1E2F3A4B5C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Installer-EXE Ausgabe
OutputDir=installer-output
OutputBaseFilename=Semetra-Setup
; Kompression
Compression=lzma2/ultra64
SolidCompression=yes
; Kein Konsolenfenster
WindowVisible=yes
; Modernes UI
WizardStyle=modern
; Installer-Icon
SetupIconFile=icon.ico
; Benutzer braucht keine Admin-Rechte
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Mindest-Windows-Version: Windows 10
MinVersion=10.0
; Signatur-Hinweis für SmartScreen (hilft ohne Codesigning)
SignedUninstaller=no
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "german";     MessagesFile: "compiler:Languages\German.isl"
Name: "english";    MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Alle Dateien aus dem PyInstaller-Ausgabeordner
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"
Name: "{group}\{#AppName} deinstallieren"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";     Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
// Ladebalken-Animation während Installation
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then begin
    WizardForm.Caption := 'Semetra wird installiert...';
  end;
  if CurStep = ssPostInstall then begin
    WizardForm.Caption := 'Semetra – Installation abgeschlossen';
  end;
end;
