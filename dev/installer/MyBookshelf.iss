#define MyAppName           "My Bookshelf"
#define MyAppVersion        "1.2.47"
#define PythonVersion       "3.14.6"
#define PythonInstallerName "python-3.14.6-amd64.exe"
#define PythonInstallerUrl  "https://www.python.org/ftp/python/3.14.6/python-3.14.6-amd64.exe"
#define PythonInstallerSha  "14b3e9a710a3fcf0bd9b55ab6b60412bd91227563f813fc49040cabc0209e0bd"

[Setup]
AppId={{3F8A9C12-B47D-4E21-A56F-82C310D4F1AB}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=My Bookshelf
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist\windows
OutputBaseFilename=Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern dynamic
MinVersion=10.0
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
SetupIconFile=..\..\MyBookshelf.ico

[Languages]
Name: "korean";  MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional options:"
Name: "uninstallicon"; Description: "Create an uninstall shortcut on the desktop"; GroupDescription: "Additional options:"

[Files]
; core/ 최상위 .py를 이름별로 나열하면 새 파일(source_metadata.py 등)이 추가돼도
; 여기 안 고치면 조용히 설치에서 빠진다 (2026-07-23 재발견 — Windows 설치본에
; source_metadata.py/note_retrofit.py/backfill_source_dates.py 누락으로 챕터분할
; 전체가 매번 즉시 실패했었음). 와일드카드로 통일해 재발 방지.
Source: "..\..\core\*.py";               DestDir: "{app}\core"; Flags: ignoreversion
Source: "..\..\core\services\*.py";      DestDir: "{app}\core\services"; Flags: ignoreversion
Source: "..\..\core\requirements.txt";   DestDir: "{app}\core"; Flags: ignoreversion
; 숨김 폴더라 목록에서 빠지기 쉬움 — 2026-08-11 재발견: maxUploadSize(1024MB) 설정이
; 설치본엔 한 번도 안 들어가서 업로드 상한이 Streamlit 기본값 200MB로 잡혀 있었음.
; 목적지가 core\.streamlit이 아니라 {app}\.streamlit인 이유: desktop.py가 streamlit을
; 띄울 때 cwd를 core/의 부모(앱 루트)로 잡아서, Streamlit이 설정을 앱 루트의
; .streamlit/에서 찾는다(core/.streamlit/에 두면 무시되고 기본 200MB로 조용히 되돌아감,
; 직접 재현·확인함).
Source: "..\..\core\.streamlit\config.toml"; DestDir: "{app}\.streamlit"; Flags: ignoreversion
Source: "..\..\MyBookshelf.exe";         DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\MyBookshelf.ico";         DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\MyBookshelf.iconset\*";   DestDir: "{app}\MyBookshelf.iconset"; Flags: ignoreversion recursesubdirs
Source: "..\..\start-app.vbs";           DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\start.bat";               DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\stop-app.bat";            DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\setup.bat";               DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\install-obsidian.bat";    DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\vendor\poppler\*";        DestDir: "{app}\poppler"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\{#MyAppName}"; Filename: "{app}\MyBookshelf.exe"; IconFilename: "{app}\MyBookshelf.ico"; WorkingDir: "{app}"
Name: "{userprograms}\{#MyAppName} (Folder)\Start {#MyAppName}"; Filename: "{app}\MyBookshelf.exe"; IconFilename: "{app}\MyBookshelf.ico"; WorkingDir: "{app}"
Name: "{userprograms}\{#MyAppName} (Folder)\Stop {#MyAppName}"; Filename: "{app}\stop-app.bat"; WorkingDir: "{app}"
Name: "{userprograms}\{#MyAppName} (Folder)\Uninstall"; Filename: "{uninstallexe}"; IconFilename: "{app}\MyBookshelf.ico"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\MyBookshelf.exe"; IconFilename: "{app}\MyBookshelf.ico"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userdesktop}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"; IconFilename: "{app}\MyBookshelf.ico"; Tasks: uninstallicon

[Run]
Filename: "cmd.exe"; \
    Parameters: "/c cd /d ""{app}"" && ""{app}\setup.bat"" --installer > ""{app}\install.log"" 2>&1"; \
    StatusMsg: "Preparing Python environment. This may take a few minutes."; \
    Flags: waituntilterminated runhidden

Filename: "{sys}\wscript.exe"; \
    Parameters: """{app}\start-app.vbs"""; \
    WorkingDir: "{app}"; \
    Flags: nowait postinstall skipifsilent; \
    Description: "Start My Bookshelf"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\install.log"
Type: dirifempty; Name: "{app}"

[UninstallRun]
Filename: "cmd.exe"; \
    Parameters: "/c taskkill /f /im pythonw.exe >nul 2>nul & taskkill /f /im python.exe >nul 2>nul"; \
    Flags: runhidden; RunOnceId: "KillPython"

[Code]
var
  PythonDownloadPage: TDownloadWizardPage;

function RunPythonCheck(const Command: String): Boolean;
var
  ResultCode: Integer;
begin
  Result :=
    Exec(
      ExpandConstant('{cmd}'),
      '/c ' + Command,
      '',
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    ) and (ResultCode = 0);
end;

function HasSupportedPython: Boolean;
begin
  Result :=
    RunPythonCheck('py -3.14 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"') or
    RunPythonCheck('py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"') or
    RunPythonCheck('python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"');
end;

function HasPython314InCommonPaths: Boolean;
begin
  Result :=
    FileExists(ExpandConstant('{localappdata}\Programs\Python\Python314\python.exe')) or
    FileExists(ExpandConstant('{localappdata}\Programs\Python\Python314-64\python.exe')) or
    FileExists(ExpandConstant('{autopf}\Python314\python.exe')) or
    FileExists('C:\Python314\python.exe');
end;

function DownloadAndInstallPython: Boolean;
var
  ResultCode: Integer;
  Error: String;
  PythonArgs: String;
begin
  Result := False;
  PythonArgs :=
    '/quiet InstallAllUsers=0 Include_launcher=1 InstallLauncherAllUsers=0 ' +
    'Include_pip=1 PrependPath=1 Include_test=0 AssociateFiles=0 Shortcuts=0';

  PythonDownloadPage.Clear;
  PythonDownloadPage.Add(
    '{#PythonInstallerUrl}',
    '{#PythonInstallerName}',
    '{#PythonInstallerSha}'
  );
  PythonDownloadPage.Show;
  try
    try
      PythonDownloadPage.Download;
    except
      if PythonDownloadPage.AbortedByUser then
        Log('Python download aborted by user.')
      else begin
        Error := Format('%s: %s', [PythonDownloadPage.LastBaseNameOrUrl, GetExceptionMessage]);
        SuppressibleMsgBox(AddPeriod(Error), mbCriticalError, MB_OK, IDOK);
      end;
      exit;
    end;
  finally
    PythonDownloadPage.Hide;
  end;

  if not Exec(
    ExpandConstant('{tmp}\{#PythonInstallerName}'),
    PythonArgs,
    '',
    SW_SHOWNORMAL,
    ewWaitUntilTerminated,
    ResultCode
  ) then begin
    SuppressibleMsgBox(
      'Could not start the Python installer.',
      mbCriticalError,
      MB_OK,
      IDOK
    );
    exit;
  end;

  if ResultCode <> 0 then begin
    SuppressibleMsgBox(
      'Python installer exited with code ' + IntToStr(ResultCode) + '.' + #13#10 +
      'Install Python manually from python.org and run Setup.exe again.',
      mbCriticalError,
      MB_OK,
      IDOK
    );
    exit;
  end;

  Result := HasSupportedPython or HasPython314InCommonPaths;
  if not Result then
    SuppressibleMsgBox(
      'Python 3.14.6 finished installing, but Setup could not verify it yet.' + #13#10 +
      'Setup will stop here. Run Setup.exe again once Python is visible on this PC.',
      mbCriticalError,
      MB_OK,
      IDOK
    );
end;

procedure InitializeWizard;
begin
  PythonDownloadPage :=
    CreateDownloadPage(
      SetupMessage(msgWizardPreparing),
      'Downloading Python ' + '{#PythonVersion}' + '...',
      nil
    );
  PythonDownloadPage.ShowBaseNameInsteadOfUrl := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID <> wpReady then
    exit;

  if HasSupportedPython or HasPython314InCommonPaths then
    exit;

  if SuppressibleMsgBox(
    'Python ' + '{#PythonVersion}' + ' is required for My Bookshelf.' + #13#10 + #13#10 +
    'Download and install it automatically now?',
    mbConfirmation,
    MB_YESNO,
    IDYES
  ) <> IDYES then begin
    Result := False;
    exit;
  end;

  Result := DownloadAndInstallPython;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Lang: String;
begin
  if CurStep = ssPostInstall then begin
    if ActiveLanguage = 'english' then
      Lang := 'en'
    else
      Lang := 'ko';
    SaveStringToFile(ExpandConstant('{app}\app_lang.txt'), Lang, False);
  end;
end;
