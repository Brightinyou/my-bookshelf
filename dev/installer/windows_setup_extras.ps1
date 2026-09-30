[CmdletBinding()]
param(
    # 앱이 자기 언어를 넘긴다(ai_setup.launch_setup_window). 없으면 Windows 표시 언어.
    [ValidateSet('', 'ko', 'en')] [string] $Lang = ''
)

# ★이 파일은 UTF-8 **BOM** 으로 저장한다. Windows PowerShell 5.1 은 BOM 없는
#   .ps1 을 ANSI 로 읽어 한국어 문구가 깨진다.
$ErrorActionPreference = 'Stop'
# PS 5.1 의 진행 막대는 Invoke-WebRequest 를 수십 배 느리게 만든다(Node.js zip 30MB).
$ProgressPreference = 'SilentlyContinue'
if (-not $Lang) { $Lang = if ((Get-UICulture).Name -like 'ko*') { 'ko' } else { 'en' } }
$Ko = $Lang -eq 'ko'
function L([string] $KoText, [string] $EnText) { if ($Ko) { $KoText } else { $EnText } }

$Host.UI.RawUI.WindowTitle = (L 'My Bookshelf - AI 연결 설정' 'My Bookshelf - Additional setup')

$AppDir = $PSScriptRoot
$ConfigDir = Join-Path $HOME '.config\mybookshelf'
$LogFile = Join-Path $AppDir 'setup-extras.log'
# 앱 폴더에 못 쓰면 TEMP 에 남긴다 (2026-09-30 Sandbox 실측 — 읽기 전용 폴더에서
# 로그 한 줄을 못 써서 Node.js 설치가 «실패»로 끝나고 스크립트가 멈췄다).
try { [IO.File]::AppendAllText($LogFile, '') }
catch { $LogFile = Join-Path $env:TEMP 'mybookshelf-setup-extras.log' }

function Say([string] $Message) { Write-Host "  $Message" }
function Warn([string] $Message) { Write-Host "  ! $Message" -ForegroundColor Yellow }
function Heading([string] $Message) {
    Write-Host ''
    Write-Host "== $Message ==" -ForegroundColor Cyan
}
function Log([string] $Message) {
    # 기록은 거들 뿐 — 실패해도 설치를 멈추지 않는다.
    try {
        "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $Message" |
            Add-Content -LiteralPath $LogFile -Encoding UTF8 -ErrorAction Stop
    } catch { }
}

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = (@($machine, $user) | Where-Object { $_ }) -join ';'
}

function Add-UserPath([string] $Directory) {
    if (-not (Test-Path -LiteralPath $Directory)) { return }

    $current = [Environment]::GetEnvironmentVariable('Path', 'User')
    $parts = @($current -split ';' | Where-Object { $_ })
    if ($parts -notcontains $Directory) {
        [Environment]::SetEnvironmentVariable(
            'Path',
            (($parts + $Directory) -join ';'),
            'User'
        )
        Log "PATH registered: $Directory"
    }
    Refresh-Path
}

function Have-Command([string] $Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Install-NodeZip {
    # winget 이 없는 Windows(Windows Sandbox, LTSC, 스토어를 뺀 PC)에서는
    # nodejs.org 의 LTS zip 을 사용자 폴더에 풀고 사용자 PATH 에 올린다.
    # 관리자 권한이 필요 없다 (2026-09-30 Sandbox 실측 — winget 없음).
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { 'x64' }
    $index = Invoke-RestMethod 'https://nodejs.org/dist/index.json'
    $release = $index | Where-Object { $_.lts -and ($_.files -contains "win-$arch-zip") } |
        Select-Object -First 1
    if (-not $release) { throw "No Node.js LTS zip for win-$arch" }
    $name = "node-$($release.version)-win-$arch"
    $zip = Join-Path $env:TEMP "$name.zip"
    Say (L "Node.js $($release.version) 내려받는 중..." "Downloading Node.js $($release.version)...")
    Invoke-WebRequest "https://nodejs.org/dist/$($release.version)/$name.zip" `
        -OutFile $zip -UseBasicParsing
    $root = Join-Path $env:LOCALAPPDATA 'Programs'
    New-Item -ItemType Directory -Force -Path $root | Out-Null
    Expand-Archive -LiteralPath $zip -DestinationPath $root -Force
    Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
    $nodeDir = Join-Path $root 'nodejs'
    if (Test-Path -LiteralPath $nodeDir) { Remove-Item -LiteralPath $nodeDir -Recurse -Force }
    Rename-Item -LiteralPath (Join-Path $root $name) -NewName 'nodejs'
    Add-UserPath $nodeDir
    # npm -g 는 %APPDATA%\npm 에 깐다 — codex.cmd 가 거기 생기므로 PATH 에 올린다.
    $npmGlobal = Join-Path $env:APPDATA 'npm'
    New-Item -ItemType Directory -Force -Path $npmGlobal | Out-Null
    & (Join-Path $nodeDir 'npm.cmd') config set prefix $npmGlobal --global | Out-Null
    Add-UserPath $npmGlobal
    Log "Node.js zip installed: $($release.version) -> $nodeDir"
}

function Ensure-Node {
    if ((Have-Command 'node') -and (Have-Command 'npm.cmd')) { return $true }

    Say (L 'Codex 에 필요한 Node.js 를 설치합니다.' 'Installing Node.js LTS for Codex.')
    if (Have-Command 'winget') {
        & winget install -e --id OpenJS.NodeJS.LTS --silent `
            --accept-source-agreements --accept-package-agreements
        Refresh-Path
    }
    if (-not ((Have-Command 'node') -and (Have-Command 'npm.cmd'))) {
        try { Install-NodeZip }
        catch {
            Warn (L 'Node.js 를 자동으로 설치하지 못했습니다. https://nodejs.org 에서 LTS 를 설치한 뒤 다시 실행하세요.' `
                    'Node.js could not be installed automatically. Install the LTS from https://nodejs.org and run this again.')
            Warn $_.Exception.Message
            Log "Node.js install failed: $($_.Exception.Message)"
        }
    }
    return (Have-Command 'node') -and (Have-Command 'npm.cmd')
}

function Install-NpmPackage([string] $Package) {
    if (-not (Ensure-Node)) { return $false }
    & npm.cmd install -g $Package
    Refresh-Path
    return $LASTEXITCODE -eq 0
}

function Install-Claude {
    if (Have-Command 'claude') { return $true }
    Say (L 'Claude Code CLI 를 설치합니다.' 'Installing Claude Code CLI.')
    # ★irm | iex 로 돌리면 안 된다. 공식 스크립트는 실패하면 `exit 1` 하고
    #   Set-StrictMode Latest 를 켠다 — 같은 범위에서 돌면 이 창이 통째로 끝나고
    #   엄격 모드가 뒤따르는 코드에 남는다. 따로 된 PowerShell 프로세스로 돌린다.
    try {
        $installer = Join-Path $env:TEMP 'claude-install.ps1'
        Invoke-WebRequest 'https://claude.ai/install.ps1' -OutFile $installer -UseBasicParsing
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer
        $code = $LASTEXITCODE
        Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
        if ($code -ne 0) { throw "claude install.ps1 exit code $code" }
    } catch {
        Log "Claude official installer failed: $($_.Exception.Message)"
        Warn (L '공식 설치 프로그램이 실패해 npm 으로 다시 시도합니다.' 'The official installer failed; retrying with npm.')
        [void](Install-NpmPackage '@anthropic-ai/claude-code')
    }
    Add-UserPath (Join-Path $HOME '.local\bin')
    Refresh-Path
    return Have-Command 'claude'
}

function Install-Codex {
    if (Have-Command 'codex') { return $true }
    Say (L 'Codex CLI 를 설치합니다.' 'Installing Codex CLI.')
    if (-not (Install-NpmPackage '@openai/codex')) { return $false }
    return Have-Command 'codex'
}

function Install-ObsidianDirect([string] $Target) {
    # winget 이 없으면 공식 GitHub 릴리스의 설치 파일을 조용히(/S) 실행한다.
    # 사용자 폴더에 깔리므로 관리자 권한이 필요 없다.
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    # «latest» 만 보면 안 된다 — 모바일 전용 릴리스(apk 만 있음)가 latest 일 때가
    # 있다(2026-09-30 실측 v1.13.8). 최근 릴리스 중 Windows 설치 파일이 있는 첫 것.
    $rels = Invoke-RestMethod 'https://api.github.com/repos/obsidianmd/obsidian-releases/releases?per_page=15' `
        -Headers @{ 'User-Agent' = 'MyBookshelf-setup' }
    $rel = $null; $asset = $null
    foreach ($r in $rels) {
        if ($r.prerelease -or $r.draft) { continue }
        $asset = $r.assets | Where-Object { $_.name -match '^Obsidian-[\d.]+\.exe$' } | Select-Object -First 1
        if ($asset) { $rel = $r; break }
    }
    if (-not $asset) { throw 'Obsidian installer asset not found' }
    $exe = Join-Path $env:TEMP $asset.name
    Say (L "옵시디언 $($rel.tag_name) 내려받는 중..." "Downloading Obsidian $($rel.tag_name)...")
    Invoke-WebRequest $asset.browser_download_url -OutFile $exe -UseBasicParsing
    Start-Process -FilePath $exe -ArgumentList '/S' -Wait
    Remove-Item -LiteralPath $exe -Force -ErrorAction SilentlyContinue
    Log "Obsidian installed from GitHub release $($rel.tag_name)"
    return Test-Path -LiteralPath $Target
}

function Install-Obsidian {
    $obsidian = Join-Path $env:LOCALAPPDATA 'Programs\Obsidian\Obsidian.exe'
    if (Test-Path -LiteralPath $obsidian) { return $true }

    Say (L '옵시디언을 설치합니다.' 'Installing Obsidian.')
    if (Have-Command 'winget') {
        & winget install -e --id Obsidian.Obsidian --silent `
            --accept-source-agreements --accept-package-agreements
        if (Test-Path -LiteralPath $obsidian) { return $true }
    }
    try { return Install-ObsidianDirect $obsidian }
    catch {
        Warn (L '옵시디언을 자동으로 설치하지 못했습니다. https://obsidian.md 에서 받아 설치할 수 있습니다.' `
                'Obsidian could not be installed automatically. You can get it from https://obsidian.md')
        Log "Obsidian install failed: $($_.Exception.Message)"
        return $false
    }
}

function Save-Preferences(
    [bool] $ClaudeReady,
    [bool] $CodexReady,
    [bool] $ObsidianReady
) {
    New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
    $keysFile = Join-Path $ConfigDir 'keys.json'
    $keys = @{}
    if (Test-Path -LiteralPath $keysFile) {
        try {
            (Get-Content $keysFile -Raw -Encoding UTF8 | ConvertFrom-Json).PSObject.Properties |
                ForEach-Object { $keys[$_.Name] = $_.Value }
        } catch {
            Warn (L '기존 AI 설정을 읽지 못해 CLI 설정을 저장하지 않았습니다.' `
                    'Existing AI settings could not be read. CLI preferences were not saved.')
            return
        }
    }

    $keys['pref_use_claude_cli'] = $ClaudeReady
    $keys['pref_use_codex_cli'] = $CodexReady
    $keys['pref_use_obsidian'] = $ObsidianReady
    if (-not $ObsidianReady -and -not $keys.ContainsKey('pref_use_docx')) {
        $keys['pref_use_docx'] = $true
    }
    if ($ClaudeReady -or $CodexReady) {
        $provider = if ($CodexReady) { 'codex_cli' } else { 'claude_cli' }
        $keys['wiki_provider'] = $provider
        $keys['wiki_model'] = 'default'
        $keys['pref_translate_engine'] = "${provider}:default"
    }
    [IO.File]::WriteAllText(
        $keysFile,
        ($keys | ConvertTo-Json -Depth 5),
        [Text.UTF8Encoding]::new($false)
    )
}

function Start-Login([string] $Cli) {
    Heading (L "$Cli 로그인" "$Cli sign-in")
    Say (L '브라우저에서 로그인 창이 열립니다. 로그인을 마치면 이 창으로 돌아오세요.' `
           'Opening browser sign-in. Return to this window when it finishes.')
    # 로그인은 잘못된 코드를 넣어도 끝나지 않고 되묻는다 (2026-09-30 Sandbox 실측).
    Say (L '로그인을 끝낼 수 없으면 이 창을 닫아도 됩니다. 설정은 이미 저장됐습니다.' `
           'If sign-in cannot finish, you can close this window. Settings are already saved.')
    Log "$Cli login started"
    try {
        if ($Cli -eq 'claude') {
            & claude auth login
        } else {
            & codex login --device-auth
        }
    } catch {
        Warn (L "$Cli 로그인을 시작하지 못했습니다. 앱 설정에서 다시 시도할 수 있습니다." `
                "$Cli sign-in could not start. You can retry from the app settings.")
        Log "${Cli} login failed: $($_.Exception.Message)"
    }
}

Clear-Host
Heading (L 'AI CLI 선택' 'Choose an AI CLI')
Say (L '1) Claude Code CLI   - Claude Pro/Max 구독' '1) Claude Code CLI   - Claude Pro/Max subscription')
Say (L '2) Codex CLI         - ChatGPT Plus/Pro 구독' '2) Codex CLI         - ChatGPT Plus/Pro subscription')
Say (L '3) 둘 다             - 기본 AI 는 Codex' '3) Both              - Codex is the default AI')
Say (L '4) 나중에            - 앱 설정에서 연결' '4) Later             - connect from app settings')
Write-Host ''

$choice = Read-Host (L '번호를 입력하세요 (기본 4)' 'Enter a number (default 4)')
if ([string]::IsNullOrWhiteSpace($choice)) { $choice = '4' }
while ($choice -notin @('1', '2', '3', '4')) {
    $choice = Read-Host (L '1, 2, 3, 4 중에서 입력하세요' 'Enter 1, 2, 3, or 4')
}

$claudeReady = $false
$codexReady = $false
if ($choice -in @('1', '3')) {
    try { $claudeReady = Install-Claude }
    catch { Warn (L 'Claude 설치에 실패했습니다.' 'Claude installation failed.'); Warn $_.Exception.Message; Log $_ }
}
if ($choice -in @('2', '3')) {
    try { $codexReady = Install-Codex }
    catch { Warn (L 'Codex 설치에 실패했습니다.' 'Codex installation failed.'); Warn $_.Exception.Message; Log $_ }
}

Write-Host ''
$obsidianPath = Join-Path $env:LOCALAPPDATA 'Programs\Obsidian\Obsidian.exe'
$obsidianReady = Test-Path -LiteralPath $obsidianPath
if ($obsidianReady) {
    Say (L '옵시디언이 이미 설치되어 있습니다.' 'Obsidian is already installed.')
} else {
    # 대부분은 옵시디언을 모른다 — 무엇이고 없으면 어떻게 되는지 먼저 알려 준다 (2026-09-30).
    Heading (L '옵시디언(Obsidian)' 'Obsidian')
    Say (L '옵시디언은 무료 메모 앱입니다. My Bookshelf 가 만든 책 요약·위키 노트를' `
           'Obsidian is a free note-taking app. It shows the book summaries and wiki notes')
    Say (L '서로 링크로 이어서 보여 주고, 노트 사이를 오가며 읽을 수 있게 해 줍니다.' `
           'My Bookshelf creates as linked pages you can browse between.')
    Say (L '없어도 앱은 그대로 쓸 수 있고, 결과는 Word(DOCX) 문서로 저장됩니다.' `
           'Without it the app still works and saves results as Word (DOCX) files.')
    Say (L '나중에 앱 설정에서 언제든 켤 수 있습니다.' 'You can turn it on later in the app settings.')
    Write-Host ''
    $obsidianChoice = Read-Host (L '옵시디언도 설치할까요? (y/N)' 'Install Obsidian too? (y/N)')
    if ($obsidianChoice -match '^(y|yes|ㅛ)$') {
        try { $obsidianReady = Install-Obsidian }
        catch { Warn (L '옵시디언 설치에 실패했습니다.' 'Obsidian installation failed.'); Warn $_.Exception.Message; Log $_ }
        # 성공·실패를 꼭 알린다 — 조용히 넘어가면 됐는지 알 수 없다 (2026-09-30).
        if ($obsidianReady) { Say (L '옵시디언을 설치했습니다.' 'Obsidian has been installed.') }
        else { Warn ((L '옵시디언이 설치되지 않았습니다. 로그 파일: ' 'Obsidian was not installed. Log: ') + $LogFile) }
    }
}

Save-Preferences $claudeReady $codexReady $obsidianReady
if ($claudeReady) { Start-Login 'claude' }
if ($codexReady) { Start-Login 'codex' }

Heading (L '완료' 'Finished')
if ($choice -eq '4') {
    Say (L '앱 설정에서 CLI 나 API 키를 연결하세요.' 'Connect a CLI or API key from the app Settings tab.')
} else {
    if ($claudeReady -or $codexReady) {
        Say (L '고른 CLI 를 앱 설정에서 켰습니다. 앱에서 [다시 확인]을 누르세요.' `
               'The selected CLI has been enabled in the app settings. Press [Check again] in the app.')
    }
    if (($choice -in @('1', '3')) -and -not $claudeReady) {
        Warn ((L 'Claude CLI 를 설치하지 못했습니다. 로그 파일: ' 'Claude CLI was not installed. Log: ') + $LogFile)
    }
    if (($choice -in @('2', '3')) -and -not $codexReady) {
        Warn ((L 'Codex CLI 를 설치하지 못했습니다. 로그 파일: ' 'Codex CLI was not installed. Log: ') + $LogFile)
    }
}
if ($obsidianReady) { Say (L '옵시디언을 앱 설정에서 켰습니다.' 'Obsidian has been enabled in the app settings.') }
[void](Read-Host (L 'Enter 를 누르면 창이 닫힙니다' 'Press Enter to close this window'))
