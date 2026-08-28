<#
.SYNOPSIS
  My Bookshelf 무인 설치 — 파이썬부터 AI CLI·기본 설정까지 한 번에.

.DESCRIPTION
  사용자가 손으로 하던 과정을 그대로 옮긴 것:
    1) 파이썬 3.14 (없을 때만)      4) AI CLI (codex 또는 claude)
    2) Setup.exe 내려받기            5) 옵시디언 (선택)
    3) 무음 설치 + 첫 실행 준비      6) 기본 설정 미리 넣기

  ★ 파이썬을 먼저 까는 이유: Setup.exe 의 파이썬 자동 설치는 마법사 버튼
    (NextButtonClick)에 걸려 있어 /VERYSILENT 로는 실행되지 않는다.
    무음 설치 전에 파이썬이 없으면 setup.bat 이 그대로 실패한다.

  자동화되지 않는 것은 둘뿐 — 구독 CLI 브라우저 로그인, API 키 입력.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\install-mybookshelf.ps1
  powershell -ExecutionPolicy Bypass -File .\install-mybookshelf.ps1 -AI claude -Obsidian -Launch
#>
[CmdletBinding()]
param(
    [ValidateSet('codex','claude','none')] [string] $AI = 'codex',
    [switch] $Obsidian,
    [ValidateSet('ko','en')] [string] $Lang = 'ko',
    [string] $TargetLang = 'ko',
    [int]    $WikiLengthPct = 30,
    [switch] $NoPrefs,
    [switch] $Launch
)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo      = 'Brightinyou/my-bookshelf'
$AppDir    = Join-Path $env:LOCALAPPDATA 'My Bookshelf'
$ConfigDir = Join-Path $HOME '.config\mybookshelf'
$WorkDir   = Join-Path $env:TEMP 'mybookshelf-bootstrap'
$LogFile   = Join-Path $WorkDir 'bootstrap.log'
$PyUrl     = 'https://www.python.org/ftp/python/3.14.6/python-3.14.6-amd64.exe'
$PySha     = '14b3e9a710a3fcf0bd9b55ab6b60412bd91227563f813fc49040cabc0209e0bd'

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
$script:Manual = @()

function Say  ($m) { Write-Host "  $m" }
function Step ($n, $m) { Write-Host ''; Write-Host "[$n/7] $m" -ForegroundColor Cyan }
function Warn ($m) { Write-Host "  ! $m" -ForegroundColor Yellow }
function Log  ($m) { "$(Get-Date -Format 'HH:mm:ss')  $m" | Add-Content -Path $LogFile -Encoding UTF8 }

function Refresh-Path {
    # 방금 깐 프로그램을 같은 세션에서 바로 부르려면 PATH 를 다시 읽어야 한다.
    $m = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $u = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = (@($m, $u) | Where-Object { $_ }) -join ';'
}

function Have-Command ($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function Have-Winget { Have-Command 'winget' }

function Have-Python {
    # .iss 의 HasSupportedPython 과 같은 판정 — 3.10 이상이면 된다.
    $probe = 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)'
    foreach ($c in @(@('py', '-3.14'), @('py', '-3'), @('python'))) {
        if (-not (Have-Command $c[0])) { continue }
        $pyArgs = @()
        if ($c.Count -gt 1) { $pyArgs += $c[1] }
        $pyArgs += @('-c', $probe)
        & $c[0] @pyArgs 2>$null
        if ($LASTEXITCODE -eq 0) { return $true }
    }
    return (Test-Path (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'))
}

# ── 1. 파이썬 ────────────────────────────────────────────────
Step 1 '파이썬 확인'
if (Have-Python) {
    Say '이미 쓸 수 있는 파이썬(3.10 이상)이 있습니다 — 건너뜁니다.'
} else {
    Say '파이썬 3.14.6 을 설치합니다 (몇 분).'
    $ok = $false
    if (Have-Winget) {
        winget install -e --id Python.Python.3.14 --scope user --silent --accept-source-agreements --accept-package-agreements | Out-Null
        Refresh-Path
        $ok = Have-Python
    }
    if (-not $ok) {
        $exe = Join-Path $WorkDir 'python-3.14.6-amd64.exe'
        Say 'python.org 에서 직접 내려받습니다.'
        Invoke-WebRequest -Uri $PyUrl -OutFile $exe -UseBasicParsing
        $sha = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLower()
        if ($sha -ne $PySha) { throw "파이썬 설치 파일이 손상됐습니다 (SHA256 $sha)" }
        # 인스톨러가 쓰는 것과 같은 인자 — 사용자 계정 설치 + PATH 등록 + pip 포함
        Start-Process -Wait -FilePath $exe -ArgumentList @(
            '/quiet', 'InstallAllUsers=0', 'Include_launcher=1', 'InstallLauncherAllUsers=0',
            'Include_pip=1', 'PrependPath=1', 'Include_test=0', 'AssociateFiles=0', 'Shortcuts=0')
        Refresh-Path
        $ok = Have-Python
    }
    if (-not $ok) { throw '파이썬 설치를 확인하지 못했습니다. python.org 에서 직접 설치한 뒤 다시 실행하세요.' }
    Say '파이썬 준비 완료.'
}

# ── 2. Setup.exe 내려받기 ────────────────────────────────────
Step 2 '최신 릴리스 내려받기'
$rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers @{ 'User-Agent' = 'mybookshelf-bootstrap' } -UseBasicParsing
$asset = $rel.assets | Where-Object { $_.name -eq 'Setup.exe' } | Select-Object -First 1
if (-not $asset) { throw "릴리스 $($rel.tag_name) 에 Setup.exe 가 없습니다." }
$setup = Join-Path $WorkDir 'Setup.exe'
Say "$($rel.tag_name) — Setup.exe ($([math]::Round($asset.size / 1MB, 1)) MB)"
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $setup -UseBasicParsing
# PowerShell 로 받은 파일에는 MOTW 가 붙지 않아 SmartScreen 파란 창이 뜨지 않는다.
Unblock-File $setup -ErrorAction SilentlyContinue
Log "downloaded $($rel.tag_name)"

# ── 3. 무음 설치 (+ 첫 실행 준비 5~20분) ─────────────────────
Step 3 '설치 — 패키지 준비까지 5~20분 걸립니다. 그대로 두세요.'
$isLang = if ($Lang -eq 'en') { 'english' } else { 'korean' }
$t0 = Get-Date
Start-Process -Wait -FilePath $setup -ArgumentList @(
    '/VERYSILENT', '/SP-', '/NORESTART', '/SUPPRESSMSGBOXES',
    "/LANG=$isLang", '/TASKS=desktopicon',
    "/LOG=$(Join-Path $WorkDir 'inno.log')")
$launcher = Join-Path $AppDir '.venv\Scripts\MyBookshelf.exe'
if (-not (Test-Path $launcher)) {
    $tail = Get-Content (Join-Path $AppDir 'install.log') -Tail 15 -ErrorAction SilentlyContinue
    if ($tail) { Warn ($tail -join "`n  ") }
    throw "설치가 끝나지 않았습니다. $AppDir\install.log 를 확인하세요."
}
Say "완료 ($([int]((Get-Date) - $t0).TotalMinutes)분). 설치 위치: $AppDir"

# ── 4. Node.js + AI CLI ──────────────────────────────────────
Step 4 'AI 연결 준비'
if ($AI -eq 'none') {
    Say 'CLI 설치를 건너뜁니다 — 앱 설정 탭에서 API 키를 넣으세요.'
    $script:Manual += '앱 ⚙️ 설정 탭에 AI API 키 입력 (Gemini/OpenAI/Anthropic 중 하나)'
} else {
    if (Have-Command 'node') {
        Say "Node.js 이미 있음 ($(node --version))"
    } elseif (Have-Winget) {
        Say 'Node.js LTS 를 설치합니다 (관리자 확인 창이 한 번 뜰 수 있습니다).'
        winget install -e --id OpenJS.NodeJS.LTS --silent --accept-source-agreements --accept-package-agreements | Out-Null
        Refresh-Path
    }
    if (-not (Have-Command 'node')) {
        Warn 'Node.js 를 설치하지 못했습니다 — https://nodejs.org 에서 LTS 를 직접 설치하세요.'
        $script:Manual += 'Node.js LTS 설치 후 이 스크립트를 다시 실행'
    } else {
        if ($AI -eq 'claude') {
            # 공식 설치 관리자가 ~/.local/bin 에 네이티브로 깐다. npm 전역 설치는
            # 알맹이 없는 껍데기가 남는 사고가 있어 앱도 이쪽을 먼저 본다.
            Say 'Claude Code CLI 설치 중...'
            try { Invoke-RestMethod 'https://claude.ai/install.ps1' | Invoke-Expression }
            catch {
                Warn '공식 설치 실패 — npm 으로 시도합니다.'
                npm install -g '@anthropic-ai/claude-code' | Out-Null
            }
        } else {
            Say 'Codex CLI 설치 중...'
            npm install -g '@openai/codex' | Out-Null
        }
        Refresh-Path
        $cli = if ($AI -eq 'claude') { 'claude' } else { 'codex' }
        if (Have-Command $cli) { Say "$cli 준비 완료 — 로그인만 남았습니다." }
        else { Warn "$cli 를 찾지 못했습니다. 새 PowerShell 창을 열고 확인하세요." }
        $script:Manual += "PowerShell 에서 '$cli' 를 한 번 실행해 브라우저로 로그인 (구독 계정)"
    }
}

# ── 5. 옵시디언 (선택) ───────────────────────────────────────
Step 5 '옵시디언'
if (-not $Obsidian) {
    Say '건너뜁니다 (-Obsidian 을 주면 설치합니다).'
} elseif (Test-Path (Join-Path $env:LOCALAPPDATA 'Programs\Obsidian\Obsidian.exe')) {
    Say '이미 설치돼 있습니다.'
} elseif (Have-Winget) {
    winget install -e --id Obsidian.Obsidian --silent --accept-source-agreements --accept-package-agreements | Out-Null
    Say '설치 완료 — 앱 설정 탭에서 보관함(Vault) 폴더를 지정하세요.'
} else {
    Warn 'winget 이 없어 자동 설치를 못 했습니다 — https://obsidian.md/download'
}

# ── 6. 기본 설정 미리 넣기 ───────────────────────────────────
Step 6 '기본 설정'
if ($NoPrefs) {
    Say '건너뜁니다 — 앱 설정 탭에서 직접 고르세요.'
} else {
    New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
    $keysFile = Join-Path $ConfigDir 'keys.json'
    # 기존 파일이 있으면 병합한다 — 그 PC에 이미 들어 있는 API 키를 지우면 안 된다.
    $keys = @{}
    if (Test-Path $keysFile) {
        (Get-Content $keysFile -Raw -Encoding UTF8 | ConvertFrom-Json).PSObject.Properties |
            ForEach-Object { $keys[$_.Name] = $_.Value }
    }
    $prefs = @{
        'pref_target_lang'              = $TargetLang
        'pref_do_translate'             = $true
        'pref_translate_want_plain'     = $true
        'pref_translate_want_bilingual' = $false
        'pref_wiki_length_pct'          = $WikiLengthPct
        'pref_skip_processed'           = $true
        'pref_use_epub'                 = $true
        'pref_use_obsidian'             = [bool]$Obsidian
        'pref_use_docx'                 = (-not [bool]$Obsidian)   # 옵시디언을 안 쓰면 Word 로 받는다
        'pref_use_hwpx'                 = $false
        'pref_use_claude_cli'           = ($AI -eq 'claude')
        'pref_use_codex_cli'            = ($AI -eq 'codex')
    }
    if ($AI -ne 'none') {
        $prov = if ($AI -eq 'claude') { 'claude_cli' } else { 'codex_cli' }
        $prefs['wiki_provider'] = $prov
        $prefs['wiki_model'] = 'default'
        $prefs['pref_translate_engine'] = "${prov}:default"
    }
    foreach ($k in $prefs.Keys) { $keys[$k] = $prefs[$k] }
    [IO.File]::WriteAllText($keysFile, ($keys | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding $false))

    $cfgFile = Join-Path $ConfigDir 'config.json'
    if (-not (Test-Path $cfgFile)) {
        # 경로(binaries/dirs)는 일부러 비워 둔다 — PC마다 다르고, 앱이 스스로 찾는다.
        $cfg = @{ lang = $Lang; folder_lang = $Lang }
        [IO.File]::WriteAllText($cfgFile, ($cfg | ConvertTo-Json), (New-Object Text.UTF8Encoding $false))
    }
    $outputs = if ($Obsidian) { 'EPUB+옵시디언' } else { 'EPUB+Word' }
    Say "도착언어 $TargetLang · 요약 $WikiLengthPct% · 출력 $outputs 로 맞췄습니다."
}

# ── 7. 마무리 ────────────────────────────────────────────────
Step 7 '끝'
Say '실행: 바탕화면의 «My Bookshelf» 아이콘'
Say "기록: $LogFile · $AppDir\install.log"
if ($script:Manual.Count) {
    Write-Host ''
    Write-Host '손으로 하실 일 (자동화 불가):' -ForegroundColor Yellow
    $i = 1
    foreach ($m in $script:Manual) { Write-Host "  $i) $m"; $i++ }
    Write-Host '  → 로그인 뒤 앱을 껐다 켜면 설정 탭 토글이 이미 켜져 있습니다.'
}
if ($Launch) {
    Start-Process -FilePath $launcher -ArgumentList "`"$AppDir\core\desktop.py`"" -WorkingDirectory $AppDir
}
