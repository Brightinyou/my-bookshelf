#define MyAppName           "My Bookshelf"
#define MyAppVersion        "1.3.6"

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
; 2026-09-21 세 번째: v1.3.0부터 cwd가 %LOCALAPPDATA%\MyBookshelf\runtime이라 여기 둔 파일도
; 안 읽힌다. 상한·파일감시는 desktop.py가 플래그로 넘긴다(정본). 이 파일은 참고용으로 둔다.
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
; GPL 준수: 번들한 poppler 바이너리 «옆에» 3년 서면 제안이 있어야 한다(GPLv2 3(b)).
; 저장소에만 두면 설치본을 받은 사람에게 닿지 않으므로 패키지에 함께 넣는다.
; v2에는 v3 6(d) 같은 «네트워크 서버 제공» 선택지가 없어 링크만으로는 요건이 안 찬다.
Source: "..\..\THIRD-PARTY-LICENSES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE";                 DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\vendor\poppler\*";        DestDir: "{app}\poppler"; Flags: ignoreversion recursesubdirs createallsubdirs
; ★동봉 파이썬 런타임(2026-09-29) — dev\installer\fetch-runtime.ps1 이 빌드 때 만든다.
;   패키지까지 미리 깔린 채로 들어가므로 받는 PC는 python.org·pip·인터넷이 필요 없다.
;   setup.bat 이 이것을 base 로 .venv 를 몇 초 만에 잇는다(오프라인).
Source: "..\..\vendor\runtime\*";       DestDir: "{app}\runtime"; Flags: ignoreversion recursesubdirs createallsubdirs

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
    StatusMsg: "Preparing the application runtime."; \
    Flags: waituntilterminated runhidden

; venv 가 만들어진 **뒤에** 실행 파일 복사본을 마련한다. 위 바로가기들이 이 파일을
; 가리키므로 첫 실행 전에 있어야 한다. 앱도 없으면 스스로 만들지만, 그러면 첫
; 실행만 pythonw 로 떠서 작업표시줄이 잠깐 «Python» 으로 보인다.
Filename: "{app}\.venv\Scripts\pythonw.exe"; \
    Parameters: "-c ""import sys; sys.path.insert(0, r'{app}\core'); import desktop; desktop.prepare_own_exe()"""; \
    WorkingDir: "{app}"; \
    StatusMsg: "Preparing the application shortcut."; \
    Flags: waituntilterminated runhidden

; AI(Claude·Codex) 설정은 설치에서 뺐다 — 앱이 AI 없이 처음 뜨면 «AI 연결» 안내를
; 보이고, 구독을 고른 사람에게만 windows_setup_extras.ps1 창을 연다 (2026-09-30).
; ★wscript + start-app.vbs 로 열면 안 된다 (2026-09-30 Windows Sandbox 실측).
;   VBScript 는 Windows 에서 없앨 수 있는 선택 기능이라, 없는 PC 에서는
;   «".vbs"에 해당하는 스크립트 엔진이 없습니다» 창만 뜨고 앱이 안 열렸다.
;   바로가기와 똑같이 venv 의 MyBookshelf.exe 를 곧장 연다.
Filename: "{app}\.venv\Scripts\MyBookshelf.exe"; \
    Parameters: """{app}\core\desktop.py"""; \
    WorkingDir: "{app}"; \
    Flags: nowait postinstall skipifsilent; \
    Description: "Start My Bookshelf"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\runtime"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\install.log"
Type: dirifempty; Name: "{app}"

[UninstallRun]
Filename: "cmd.exe"; \
    Parameters: "/c taskkill /f /im pythonw.exe >nul 2>nul & taskkill /f /im python.exe >nul 2>nul"; \
    Flags: runhidden; RunOnceId: "KillPython"

[Code]
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

  Exec(
    ExpandConstant('{cmd}'),
    '/c powershell -NoProfile -Command "Get-CimInstance Win32_Process | ' +
    'Where-Object { $_.Name -in @(''python.exe'',''pythonw.exe'',''MyBookshelf.exe'') -and ' +
    '($_.CommandLine -like ''*pipeline_app.py*'' -or $_.CommandLine -like ''*desktop.py*'') } | ' +
    'ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode
  );
  { ★MyBookshelf.exe 도 끈다(2026-09-29). 앱은 .venv\Scripts\MyBookshelf.exe 로 도는데
    setup.bat 이 동봉 런타임에 .venv 를 다시 이을 때(--clear) 그 파일이 잠겨 있으면 실패한다. }
  { 포트와 파일 잠금이 풀릴 틈을 준다 }
  Sleep(1500);
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
