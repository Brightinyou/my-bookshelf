[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'My Bookshelf - Additional setup'

$AppDir = $PSScriptRoot
$ConfigDir = Join-Path $HOME '.config\mybookshelf'
$LogFile = Join-Path $AppDir 'setup-extras.log'

function Say([string] $Message) { Write-Host "  $Message" }
function Warn([string] $Message) { Write-Host "  ! $Message" -ForegroundColor Yellow }
function Heading([string] $Message) {
    Write-Host ''
    Write-Host "== $Message ==" -ForegroundColor Cyan
}
function Log([string] $Message) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $Message" |
        Add-Content -LiteralPath $LogFile -Encoding UTF8
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

function Ensure-Node {
    if ((Have-Command 'node') -and (Have-Command 'npm.cmd')) { return $true }
    if (-not (Have-Command 'winget')) {
        Warn 'winget was not found, so Node.js cannot be installed automatically.'
        return $false
    }

    Say 'Installing Node.js LTS for Codex.'
    & winget install -e --id OpenJS.NodeJS.LTS --silent `
        --accept-source-agreements --accept-package-agreements
    Refresh-Path
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
    Say 'Installing Claude Code CLI.'
    try {
        Invoke-RestMethod 'https://claude.ai/install.ps1' | Invoke-Expression
    } catch {
        Warn 'The official installer failed; retrying with npm.'
        [void](Install-NpmPackage '@anthropic-ai/claude-code')
    }
    Add-UserPath (Join-Path $HOME '.local\bin')
    Refresh-Path
    return Have-Command 'claude'
}

function Install-Codex {
    if (Have-Command 'codex') { return $true }
    Say 'Installing Codex CLI.'
    if (-not (Install-NpmPackage '@openai/codex')) { return $false }
    return Have-Command 'codex'
}

function Install-Obsidian {
    $obsidian = Join-Path $env:LOCALAPPDATA 'Programs\Obsidian\Obsidian.exe'
    if (Test-Path -LiteralPath $obsidian) { return $true }
    if (-not (Have-Command 'winget')) {
        Warn 'winget was not found, so Obsidian cannot be installed automatically.'
        return $false
    }

    Say 'Installing Obsidian.'
    & winget install -e --id Obsidian.Obsidian --silent `
        --accept-source-agreements --accept-package-agreements
    return Test-Path -LiteralPath $obsidian
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
            Warn 'Existing AI settings could not be read. CLI preferences were not saved.'
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
    Heading "$Cli sign-in"
    Say 'Opening browser sign-in. Return to this window when it finishes.'
    Log "$Cli login started"
    try {
        if ($Cli -eq 'claude') {
            & claude auth login
        } else {
            & codex login --device-auth
        }
    } catch {
        Warn "$Cli sign-in could not start. You can retry from the app settings."
        Log "${Cli} login failed: $($_.Exception.Message)"
    }
}

Clear-Host
Heading 'Choose an AI CLI'
Say '1) Claude Code CLI   - Claude Pro/Max subscription'
Say '2) Codex CLI         - ChatGPT Plus/Pro subscription'
Say '3) Both              - Codex is the default AI'
Say '4) Later             - connect from app settings'
Write-Host ''

$choice = Read-Host 'Enter a number (default 4)'
if ([string]::IsNullOrWhiteSpace($choice)) { $choice = '4' }
while ($choice -notin @('1', '2', '3', '4')) {
    $choice = Read-Host 'Enter 1, 2, 3, or 4'
}

$claudeReady = $false
$codexReady = $false
if ($choice -in @('1', '3')) {
    try { $claudeReady = Install-Claude }
    catch { Warn 'Claude installation failed.'; Log $_ }
}
if ($choice -in @('2', '3')) {
    try { $codexReady = Install-Codex }
    catch { Warn 'Codex installation failed.'; Log $_ }
}

Write-Host ''
$obsidianPath = Join-Path $env:LOCALAPPDATA 'Programs\Obsidian\Obsidian.exe'
$obsidianReady = Test-Path -LiteralPath $obsidianPath
if ($obsidianReady) {
    Say 'Obsidian is already installed.'
} else {
    $obsidianChoice = Read-Host 'Install Obsidian too? (y/N)'
    if ($obsidianChoice -match '^(y|yes)$') {
        try { $obsidianReady = Install-Obsidian }
        catch { Warn 'Obsidian installation failed.'; Log $_ }
    }
}

Save-Preferences $claudeReady $codexReady $obsidianReady
if ($claudeReady) { Start-Login 'claude' }
if ($codexReady) { Start-Login 'codex' }

Heading 'Finished'
if ($choice -eq '4') {
    Say 'Connect a CLI or API key from the app Settings tab.'
} else {
    Say 'The selected CLI has been enabled in the app settings.'
}
if ($obsidianReady) { Say 'Obsidian has been enabled in the app settings.' }
[void](Read-Host 'Press Enter to close this window')
