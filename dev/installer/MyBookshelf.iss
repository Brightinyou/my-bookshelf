#define MyAppName           "My Bookshelf"
#define MyAppVersion        "1.2.67"
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
Source: "..\..\glossary.bat";            DestDir: "{app}"; Flags: ignoreversion
Source: "windows_setup_extras.ps1";       DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\vendor\poppler\*";        DestDir: "{app}\poppler"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; ★{app}\MyBookshelf.exe(PyInstaller 통짜 실행 파일)를 더 이상 거치지 않는다
;   (2026-08-27 연구자 보고 — "Failed to remove temporary directory" 창이 계속 뜸).
;   그것은 열 때마다 _MEI…\ 에 압축을 풀고 끝날 때 지우는데, 그 정리가 실패하면
;   경고 창이 뜬다. venv 안의 MyBookshelf.exe 를 곧장 가리키면 임시 폴더가 아예
;   생기지 않고, 프로세스도 한 겹 줄며, 작업표시줄 신원도 그 파일이 된다.
Name: "{userprograms}\{#MyAppName}"; Filename: "{app}\.venv\Scripts\MyBookshelf.exe"; Parameters: """{app}\core\desktop.py"""; IconFilename: "{app}\MyBookshelf.ico"; WorkingDir: "{app}"
Name: "{userprograms}\{#MyAppName} (Folder)\Start {#MyAppName}"; Filename: "{app}\.venv\Scripts\MyBookshelf.exe"; Parameters: """{app}\core\desktop.py"""; IconFilename: "{app}\MyBookshelf.ico"; WorkingDir: "{app}"
Name: "{userprograms}\{#MyAppName} (Folder)\Stop {#MyAppName}"; Filename: "{app}\stop-app.bat"; WorkingDir: "{app}"
Name: "{userprograms}\{#MyAppName} (Folder)\Glossary"; Filename: "{app}\glossary.bat"; WorkingDir: "{app}"
Name: "{userprograms}\{#MyAppName} (Folder)\Uninstall"; Filename: "{uninstallexe}"; IconFilename: "{app}\MyBookshelf.ico"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\.venv\Scripts\MyBookshelf.exe"; Parameters: """{app}\core\desktop.py"""; IconFilename: "{app}\MyBookshelf.ico"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userdesktop}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"; IconFilename: "{app}\MyBookshelf.ico"; Tasks: uninstallicon

[Run]
Filename: "cmd.exe"; \
    Parameters: "/c cd /d ""{app}"" && ""{app}\setup.bat"" --installer > ""{app}\install.log"" 2>&1"; \
    StatusMsg: "Preparing Python environment. This may take a few minutes."; \
    Flags: waituntilterminated runhidden

; venv 가 만들어진 **뒤에** 실행 파일 복사본을 마련한다. 위 바로가기들이 이 파일을
; 가리키므로 첫 실행 전에 있어야 한다. 앱도 없으면 스스로 만들지만, 그러면 첫
; 실행만 pythonw 로 떠서 작업표시줄이 잠깐 «Python» 으로 보인다.
Filename: "{app}\.venv\Scripts\pythonw.exe"; \
    Parameters: "-c ""import sys; sys.path.insert(0, r'{app}\core'); import desktop; desktop.prepare_own_exe()"""; \
    WorkingDir: "{app}"; \
    StatusMsg: "Preparing the application shortcut."; \
    Flags: waituntilterminated runhidden

Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
    Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\windows_setup_extras.ps1"""; \
    WorkingDir: "{app}"; \
    Flags: waituntilterminated postinstall skipifsilent; \
    Description: "Set up Claude or Codex"

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

{ 파이썬 설치 인자 — 마법사 경로와 무음 경로가 같은 값을 쓰도록 한 곳에 둔다. }
function PythonInstallArgs: String;
begin
  Result :=
    '/quiet InstallAllUsers=0 Include_launcher=1 InstallLauncherAllUsers=0 ' +
    'Include_pip=1 PrependPath=1 Include_test=0 AssociateFiles=0 Shortcuts=0';
end;

{ 내려받은 파이썬 설치 파일을 실행한다. 실패 사유는 여기서 한 번만 알린다
  (무음 설치에서는 SuppressibleMsgBox 가 창을 띄우지 않고 기본값으로 넘어간다). }
function RunPythonInstaller(const InstallerPath: String): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;

  if not Exec(
    InstallerPath,
    PythonInstallArgs,
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

  Result := True;
end;

function DownloadAndInstallPython: Boolean;
var
  Error: String;
begin
  Result := False;

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

  if not RunPythonInstaller(ExpandConstant('{tmp}\{#PythonInstallerName}')) then
    exit;

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

{ 무음 설치(/SILENT·/VERYSILENT)에서의 파이썬 확보.
  ★2026-08-29. 위의 DownloadAndInstallPython 은 NextButtonClick(마법사의 [다음])
  에서만 불리는데 **무음 설치에는 누를 버튼이 없어 한 번도 실행되지 않았다.**
  파이썬 없는 PC에 무음 설치를 걸면 그대로 진행되다가 setup.bat 이
  "Python 3.10 or newer is required" 로 실패한다 — 무인 배포(install-mybookshelf.ps1)가
  걸렸던 자리다. 여기서는 물어볼 사람이 없으니 곧장 받아 설치하고, 실패하면
  빈 문자열 대신 사유를 돌려줘 설치를 그 자리에서 멈춘다(반쪽 설치 방지). }
function EnsurePythonSilently: String;
begin
  Result := '';

  try
    DownloadTemporaryFile(
      '{#PythonInstallerUrl}',
      '{#PythonInstallerName}',
      '{#PythonInstallerSha}',
      nil
    );
  except
    Result :=
      'Python ' + '{#PythonVersion}' + ' could not be downloaded: ' + GetExceptionMessage;
    exit;
  end;

  if not RunPythonInstaller(ExpandConstant('{tmp}\{#PythonInstallerName}')) then begin
    Result :=
      'Python ' + '{#PythonVersion}' + ' could not be installed automatically.' + #13#10 +
      'Install Python from python.org, then run Setup.exe again.';
    exit;
  end;

  if not (HasSupportedPython or HasPython314InCommonPaths) then
    Result :=
      'Python ' + '{#PythonVersion}' + ' was installed but Setup could not verify it.' + #13#10 +
      'Run Setup.exe again once Python is visible on this PC.';
end;

{ 설치 전에 실행 중인 앱을 먼저 끈다.
  ★2026-08-27. 예전에는 taskkill이 [UninstallRun]에만 있어서, **설치 때는 앱이
  살아 있는 채로 core\*.py가 덮여 썼다.** 그러면 이미 불러온 옛 모듈과 새로
  불러오는 새 모듈이 한 프로세스에서 섞이고, 남은 창은 죽은 서버에 재접속을
  되풀이하며 깜빡인다. 실측(v1.2.59 설치 직후): 창 6개·서버 2개가 떠 있었다. }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';

  { 무음 설치에는 마법사 단계가 없어 NextButtonClick 이 안 불린다 — 여기서 확보한다. }
  if WizardSilent and not (HasSupportedPython or HasPython314InCommonPaths) then begin
    Result := EnsurePythonSilently;
    if Result <> '' then
      exit;
  end;

  Exec(
    ExpandConstant('{cmd}'),
    '/c powershell -NoProfile -Command "Get-CimInstance Win32_Process | ' +
    'Where-Object { $_.Name -in @(''python.exe'',''pythonw.exe'') -and ' +
    '($_.CommandLine -like ''*pipeline_app.py*'' -or $_.CommandLine -like ''*desktop.py*'') } | ' +
    'ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode
  );
  { 포트와 파일 잠금이 풀릴 틈을 준다 }
  Sleep(1500);
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
