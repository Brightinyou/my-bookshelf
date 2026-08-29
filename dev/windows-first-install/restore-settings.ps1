param(
    [string] $BackupRoot = (Join-Path $HOME 'MyBookshelf-FirstInstall-Backup')
)

$ErrorActionPreference = 'Stop'
$latestFile = Join-Path $BackupRoot 'latest.txt'
if (-not (Test-Path -LiteralPath $latestFile)) { throw 'No first-install backup was found.' }
$backup = (Get-Content -LiteralPath $latestFile -Raw -Encoding UTF8).Trim()
$postTest = Join-Path $backup ('post-test-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force -Path $postTest | Out-Null

function Restore-Item([string] $StoredName, [string] $Destination) {
    $source = Join-Path $backup $StoredName
    if (-not (Test-Path -LiteralPath $source)) { return }
    if (Test-Path -LiteralPath $Destination) {
        Move-Item -LiteralPath $Destination -Destination (Join-Path $postTest $StoredName) -Force
    }
    $parent = Split-Path -Parent $Destination
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    Move-Item -LiteralPath $source -Destination $Destination -Force
    Write-Host "Restored $Destination"
}

Get-Process -Name MyBookshelf,Obsidian,node,codex,codex-code-mode-host -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name claude -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        if ($_.Path -like "$HOME\.local\bin\claude.exe") { Stop-Process -Id $_.Id -Force }
    } catch {}
}

Restore-Item 'mybookshelf-config' (Join-Path $HOME '.config\mybookshelf')
Restore-Item 'claude-config' (Join-Path $HOME '.claude')
Restore-Item 'claude.json' (Join-Path $HOME '.claude.json')
Restore-Item 'claude.json.backup' (Join-Path $HOME '.claude.json.backup')
Restore-Item 'codex-config' (Join-Path $HOME '.codex')
Restore-Item 'local-cli-files' (Join-Path $HOME '.local')
Restore-Item 'npm-global-files' (Join-Path $env:APPDATA 'npm')
Restore-Item 'obsidian-config' (Join-Path $env:APPDATA 'obsidian')

$environmentFile = Join-Path $backup 'environment.json'
if (Test-Path -LiteralPath $environmentFile) {
    $environment = Get-Content -LiteralPath $environmentFile -Raw -Encoding UTF8 | ConvertFrom-Json
    [Environment]::SetEnvironmentVariable('Path', $environment.UserPath, 'User')
    Write-Host 'Restored the original user PATH.'
}

Write-Host "Original settings restored. Fresh-test settings are in $postTest" -ForegroundColor Green
