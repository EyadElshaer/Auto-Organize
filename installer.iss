; Auto Organizer Installer Script
; Created with Inno Setup

; Simplified version file reading
#define MyAppName "Auto Organizer"
#define MyAppVersion "v1.0.2"
#define MyAppPublisher "Eyad Elshaer"
#define MyAppExeName "Auto Organizer.exe"

[Setup]
AppId={{F7A76D84-5448-4E79-8F1B-EC8768B9610D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=.
OutputBaseFilename=AutoOrganizerSetup
SetupIconFile=icons\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline dialog
AppVerName={#MyAppName} {#MyAppVersion}
AppSupportURL=https://github.com/EyadElshaer/Auto-Organize
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
AppMutex=AutoOrganizerAppMutex_{#MyAppVersion}

; Add minimum Windows version requirement
MinVersion=10.0.17763

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "defenderexclusion"; Description: "Add Windows Defender exclusion (recommended for proper functionality)"; GroupDescription: "Security Settings"; Flags: checkedonce

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "icons\*"; DestDir: "{app}\icons"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "add_defender_exclusion.ps1"; DestDir: "{app}"; Flags: ignoreversion deleteafterinstall

; Visual C++ Redistributable requirement check
Source: "vcredist\VC_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\{#MyAppName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"
Root: HKCU; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"

[CustomMessages]
UpdateDetected=An existing installation of %1 (version %2) was found. Would you like to update to version %3?
DowngradeWarning=Warning: You are attempting to install version %1 which is older than the currently installed version %2. Are you sure you want to downgrade?
UpdateButton=Update
InstallButton=Install

[Run]
; Install Visual C++ Redistributable if needed
Filename: "{tmp}\VC_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing Visual C++ Redistributable..."; Check: VCRedistNeedsInstall; Flags: waituntilterminated

; Add Windows Defender exclusion with proper elevation and feedback
Filename: "powershell.exe"; \
    Parameters: "-ExecutionPolicy Bypass -NoProfile -WindowStyle Normal -Command ""Start-Process powershell.exe -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \""{app}\add_defender_exclusion.ps1\"" \""{app}\{#MyAppExeName}\"" ' -Verb RunAs -Wait"""; \
    StatusMsg: "Adding Windows Defender exclusion..."; \
    Tasks: defenderexclusion; \
    Flags: runascurrentuser shellexec waituntilterminated

; Launch application after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent runascurrentuser

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -Command ""& {{try {{ Remove-MpPreference -ExclusionPath '{app}\{#MyAppExeName}' -ErrorAction SilentlyContinue }} catch {{}}}}"""; Flags: runhidden; RunOnceId: "RemoveDefenderExclusion"

[Code]
// Function to check if Visual C++ Redistributable needs to be installed
function VCRedistNeedsInstall: Boolean;
var
  Version: String;
  Install: Boolean;
begin
  if RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Version', Version) then
  begin
    // Check if the installed version is older than the required version
    Install := (CompareStr(Version, '14.34.31938') < 0);
  end
  else
  begin
    // Visual C++ Redistributable is not installed
    Install := True;
  end;
  Result := Install;
end;

var
  WarningText: TNewStaticText;

procedure UpdateWarningVisibility(Checked: Boolean);
begin
  if WarningText <> nil then
  begin
    WarningText.Visible := not Checked;
  end;
end;

procedure TasksListClickCheck(Sender: TObject);
begin
  if WizardForm.CurPageID = wpSelectTasks then
  begin
    UpdateWarningVisibility(WizardIsTaskSelected('defenderexclusion'));
  end;
end;

procedure InitializeWizard;
begin
  // Create warning label
  WarningText := TNewStaticText.Create(WizardForm);
  with WarningText do
  begin
    Parent := WizardForm.SelectTasksPage;
    Left := WizardForm.TasksList.Left;
    Top := WizardForm.TasksList.Top + WizardForm.TasksList.Height + 8;
    Width := WizardForm.TasksList.Width;
    Height := ScaleY(40);
    Caption := '⚠️ Warning: Without Windows Defender exclusion, the application might be detected as a threat and could be blocked during installation or execution.';
    Font.Color := clRed;
    Font.Style := [fsBold];
    WordWrap := True;
    Visible := True;
  end;

  // Connect the click event to the TasksList
  WizardForm.TasksList.OnClickCheck := @TasksListClickCheck;
  
  // Set initial visibility
  UpdateWarningVisibility(WizardIsTaskSelected('defenderexclusion'));
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpSelectTasks then
  begin
    // Check initial state of the checkbox
    UpdateWarningVisibility(WizardIsTaskSelected('defenderexclusion'));
  end else begin
    // Hide warning on other pages
    if WarningText <> nil then
      WarningText.Visible := False;
  end;
end;

function CompareVersions(Version1, Version2: string): Integer;
var
  V1, V2: string;
  Num1, Num2: Integer;
  Pos1, Pos2: Integer;
begin
  // Remove 'v' prefix if present
  if Copy(Version1, 1, 1) = 'v' then
    V1 := Copy(Version1, 2, Length(Version1))
  else
    V1 := Version1;
    
  if Copy(Version2, 1, 1) = 'v' then
    V2 := Copy(Version2, 2, Length(Version2))
  else
    V2 := Version2;

  while (Length(V1) > 0) or (Length(V2) > 0) do
  begin
    Pos1 := Pos('.', V1);
    if Pos1 = 0 then 
      Pos1 := Length(V1) + 1;
    Pos2 := Pos('.', V2);
    if Pos2 = 0 then 
      Pos2 := Length(V2) + 1;
    
    if Length(V1) = 0 then
      Num1 := 0
    else
      Num1 := StrToIntDef(Copy(V1, 1, Pos1 - 1), 0);
      
    if Length(V2) = 0 then
      Num2 := 0
    else
      Num2 := StrToIntDef(Copy(V2, 1, Pos2 - 1), 0);
    
    if Num1 > Num2 then
    begin
      Result := 1;
      Exit;
    end
    else if Num1 < Num2 then
    begin
      Result := -1;
      Exit;
    end;
      
    if Length(V1) > 0 then
    begin
      Delete(V1, 1, Pos1);
      if Length(V1) > 0 then
        if V1[1] = '.' then 
          Delete(V1, 1, 1);
    end;
    
    if Length(V2) > 0 then
    begin
      Delete(V2, 1, Pos2);
      if Length(V2) > 0 then
        if V2[1] = '.' then 
          Delete(V2, 1, 1);
    end;
  end;
  
  Result := 0;
end;

function ExpandMessage(Message: String; AppName, OldVersion, NewVersion: String): String;
begin
  StringChangeEx(Message, '%1', AppName, True);
  StringChangeEx(Message, '%2', OldVersion, True);
  StringChangeEx(Message, '%3', NewVersion, True);
  Result := Message;
end;

function InitializeSetup(): Boolean;
var
  PrevPath, InstalledVersion, Msg: String;
  VersionCompare: Integer;
  UpdateMode: Boolean;
begin
  Result := True;
  UpdateMode := False;
  
  if RegQueryStringValue(HKEY_CURRENT_USER, 'Software\{#MyAppName}', 'InstallPath', PrevPath) and
     RegQueryStringValue(HKEY_CURRENT_USER, 'Software\{#MyAppName}', 'Version', InstalledVersion) then
  begin
    VersionCompare := CompareVersions('{#MyAppVersion}', InstalledVersion);
    
    if VersionCompare > 0 then
    begin
      // New version is newer - offer update
      Msg := 'An existing installation of ' + ExpandConstant('{#MyAppName}') + 
             ' (version ' + InstalledVersion + ') was found.' + #13#10 + 
             'Would you like to update to version ' + ExpandConstant('{#MyAppVersion}') + '?';
      
      if MsgBox(Msg, mbConfirmation, MB_YESNO) = IDNO then
      begin
        Result := False;
        Exit;
      end;
      WizardForm.NextButton.Caption := 'Update';
      UpdateMode := True;
    end
    else if VersionCompare < 0 then
    begin
      // New version is older - warn about downgrade
      Msg := 'Warning: You are attempting to install version ' + ExpandConstant('{#MyAppVersion}') + 
             ' which is older than the currently installed version ' + InstalledVersion + '.' + #13#10 + 
             'Are you sure you want to downgrade?';
      
      if MsgBox(Msg, mbError, MB_YESNO) = IDNO then
      begin
        Result := False;
        Exit;
      end;
    end
    else
    begin
      // Same version
      Msg := 'The same version is already installed. Do you want to reinstall?';
      
      if MsgBox(Msg, mbConfirmation, MB_YESNO) = IDNO then
      begin
        Result := False;
        Exit;
      end;
    end;
  end;
end;

function TerminateApp(const Filename: String): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec(ExpandConstant('{sys}\taskkill.exe'), 
                '/F /IM "' + Filename + '"', 
                '', 
                SW_HIDE, 
                ewWaitUntilTerminated, 
                ResultCode);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    TerminateApp('{#MyAppExeName}');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    TerminateApp('{#MyAppExeName}');
  end;
end;