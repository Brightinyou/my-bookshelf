# stop-app.ps1 — My Bookshelf 의 창·서버를 모두 끈다 (2026-09-30).
# stop-app.bat(«Stop My Bookshelf»), 설치 프로그램의 PrepareToInstall(설치·업데이트 전),
# 제거 프로그램([UninstallRun])이 모두 이 스크립트 하나를 쓴다.
#
# ★두 가지 방법의 **합집합**으로 찾는다.
#   1) 실행 파일 경로(Get-Process Path) — WMI 없이 읽힌다. {Root}\.venv\Scripts 와
#      {Root}\runtime 에서 뜬 python·pythonw·MyBookshelf.exe. WMI(Get-CimInstance)가
#      «액세스가 거부되었습니다»로 막힌 PC(Windows Sandbox 실측)에서도 된다.
#   2) 명령줄(Get-CimInstance) — pipeline_app.py·desktop.py. 옛 설치본(v1.3.6 까지,
#      python.org 파이썬 기반 .venv)은 venv 의 python·pythonw 가 중계 stub 이라 실제
#      프로세스가 C:\Python314\python.exe 처럼 **앱 폴더 밖**에서 돈다. 경로로는 못
#      잡으므로 WMI 가 되는 PC 에서는 명령줄로도 잡는다(맥 세션 검토). WMI 가 막히면
#      이쪽은 아무것도 못 찾을 뿐이다.
param([Parameter(Mandatory = $true)][string]$Root)

$ErrorActionPreference = 'SilentlyContinue'
$Root = [IO.Path]::GetFullPath($Root).TrimEnd('\')
$dirs = @((Join-Path $Root '.venv\Scripts'), (Join-Path $Root 'runtime')) | ForEach-Object { $_.ToLower() }
$ids = New-Object 'System.Collections.Generic.HashSet[int]'

# 1) 경로
Get-Process | Where-Object {
    $_.Path -and $_.ProcessName -match '^(python|pythonw|MyBookshelf)$' -and
    ($dirs -contains (Split-Path $_.Path -Parent).ToLower())
} | ForEach-Object { [void]$ids.Add([int]$_.Id) }
$byPath = $ids.Count

# 2) 명령줄 — 이름 조건이 있어야 이 스크립트를 돌리는 powershell 자신을 잡지 않는다.
#    ★명령줄에 **이 설치 폴더**가 들어 있어야 한다. 이름만 보면 다른 설치본이나 남의
#    desktop.py 까지 끈다. stub 밑의 실제 인터프리터(C:\Python314\pythonw.exe)도
#    명령줄은 stub 의 것("…\My Bookshelf\.venv\Scripts\pythonw.exe" core\desktop.py)을
#    그대로 물려받아 폴더가 들어 있다(2026-09-30 실측).
$rootLower = $Root.ToLower()
try {
    Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
        $_.Name -in @('python.exe', 'pythonw.exe', 'MyBookshelf.exe') -and $_.CommandLine -and
        $_.CommandLine.ToLower().Contains($rootLower) -and
        ($_.CommandLine -like '*pipeline_app.py*' -or $_.CommandLine -like '*desktop.py*')
    } | ForEach-Object { [void]$ids.Add([int]$_.ProcessId) }
    $wmi = 'ok'
} catch { $wmi = 'blocked' }

[void]$ids.Remove($PID)
foreach ($id in $ids) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
Write-Output ("stopped {0} process(es) (path {1}, wmi {2})" -f $ids.Count, $byPath, $wmi)
