param(
    [string] $BackupRoot = (Join-Path $HOME 'MyBookshelf-FirstInstall-Backup')
)

$ErrorActionPreference = 'Stop'

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    $args = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'),
        '-BackupRoot', ('"' + $BackupRoot + '"')
    )
    Start-Process powershell.exe -Verb RunAs -ArgumentList $args -Wait
    exit
}

Write-Host 'This will remove Python, Node.js, Claude/Codex CLI, Obsidian, and My Bookshelf.' -ForegroundColor Yellow
Write-Host 'Documents, Obsidian vaults, the source repository, and Claude Desktop are preserved.'
if ((Read-Host 'Type RESET to continue') -cne 'RESET') { exit }

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $BackupRoot $stamp
New-Item -ItemType Directory -Force -Path $backup | Out-Null
Set-Content -LiteralPath (Join-Path $BackupRoot 'latest.txt') -Value $backup -Encoding UTF8
$log = Join-Path $backup 'reset.log'

function Log([string] $Message) {
    $line = "$(Get-Date -Format o)  $Message"
    Write-Host $line
    $line | Add-Content -LiteralPath $log -Encoding UTF8
}

function Move-ToBackup([string] $Source, [string] $Name) {
    if (-not (Test-Path -LiteralPath $Source)) { return }
    $destination = Join-Path $backup $Name
    Log "Backing up $Source -> $destination"
    Move-Item -LiteralPath $Source -Destination $destination -Force
}

function Get-UninstallEntries {
    $roots = @(
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    return Get-ItemProperty $roots -ErrorAction SilentlyContinue
}

function Invoke-UninstallString([string] $Name, [string] $CommandLine) {
    if ([string]::IsNullOrWhiteSpace($CommandLine)) { return }
    if ($CommandLine -match '^"([^"]+)"\s*(.*)$') {
        $exe = $Matches[1]
        $arguments = $Matches[2]
    } elseif ($CommandLine -match '^(\S+)\s*(.*)$') {
        $exe = $Matches[1]
        $arguments = $Matches[2]
    } else {
        throw "Cannot parse uninstall command for $Name"
    }
    Log "Uninstalling $Name"
    $process = Start-Process -FilePath $exe -ArgumentList $arguments -Wait -PassThru
    Log "$Name exit code: $($process.ExitCode)"
    if ($process.ExitCode -notin @(0, 1605, 1614, 3010)) {
        throw "$Name uninstall failed with exit code $($process.ExitCode)"
    }
}

function Invoke-WingetUninstall([string] $Name, [string] $Id) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        Log "winget is unavailable; skipping $Name package uninstall."
        return
    }
    Log "Uninstalling $Name with winget ($Id)"
    & winget.exe uninstall --exact --id $Id --silent --disable-interactivity
    Log "$Name winget exit code: $LASTEXITCODE"
}

$environment = [ordered]@{
    UserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    MachinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
}
$environment | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $backup 'environment.json') -Encoding UTF8
$entries = Get-UninstallEntries
$entries |
    Where-Object { $_.DisplayName -match '^(Python|Node\.js|Obsidian|My Bookshelf)' } |
    Select-Object DisplayName, DisplayVersion, InstallLocation, UninstallString |
    Format-List |
    Out-File -LiteralPath (Join-Path $backup 'installed-packages.txt') -Encoding UTF8

Log 'Stopping test-target applications and CLI processes.'
Get-Process -Name MyBookshelf,Obsidian,node,codex,codex-code-mode-host -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name claude -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        if ($_.Path -like "$HOME\.local\bin\claude.exe") {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    } catch {}
}
Start-Sleep -Seconds 2

Move-ToBackup (Join-Path $HOME '.config\mybookshelf') 'mybookshelf-config'
Move-ToBackup (Join-Path $HOME '.claude') 'claude-config'
Move-ToBackup (Join-Path $HOME '.claude.json') 'claude.json'
Move-ToBackup (Join-Path $HOME '.claude.json.backup') 'claude.json.backup'
Move-ToBackup (Join-Path $HOME '.codex') 'codex-config'
Move-ToBackup (Join-Path $HOME '.local') 'local-cli-files'
Move-ToBackup (Join-Path $env:APPDATA 'npm') 'npm-global-files'
Move-ToBackup (Join-Path $env:APPDATA 'obsidian') 'obsidian-config'

$myBookshelf = $entries | Where-Object { $_.DisplayName -like 'My Bookshelf*' } | Select-Object -First 1
if ($myBookshelf) {
    $command = if ($myBookshelf.QuietUninstallString) { $myBookshelf.QuietUninstallString } else { $myBookshelf.UninstallString + ' /VERYSILENT /SUPPRESSMSGBOXES /NORESTART' }
    Invoke-UninstallString $myBookshelf.DisplayName $command
}

$obsidian = $entries | Where-Object { $_.DisplayName -eq 'Obsidian' } | Select-Object -First 1
if ($obsidian) {
    $command = if ($obsidian.QuietUninstallString) { $obsidian.QuietUninstallString } else { $obsidian.UninstallString + ' /S' }
    Invoke-UninstallString $obsidian.DisplayName $command
}

Invoke-WingetUninstall 'Python 3.14' 'Python.Python.3.14'
Invoke-WingetUninstall 'Python 3.13' 'Python.Python.3.13'
Invoke-WingetUninstall 'Python Launcher' 'Python.Launcher'

$entries = Get-UninstallEntries
$node = $entries | Where-Object { $_.DisplayName -eq 'Node.js' } | Select-Object -First 1
if ($node -and $node.UninstallString -match '\{[0-9A-Fa-f-]+\}') {
    $productCode = $Matches[0]
    Invoke-UninstallString 'Node.js' "msiexec.exe /x $productCode /qn /norestart"
}

foreach ($item in @(
    @{ Path = (Join-Path $env:LOCALAPPDATA 'My Bookshelf'); Name = 'mybookshelf-app-residual' },
    @{ Path = (Join-Path $env:LOCALAPPDATA 'Programs\Obsidian'); Name = 'obsidian-app-residual' },
    @{ Path = 'C:\Python314'; Name = 'python314-residual' },
    @{ Path = (Join-Path $env:LOCALAPPDATA 'Programs\Python'); Name = 'python-user-residual' },
    @{ Path = 'C:\Program Files\nodejs'; Name = 'nodejs-residual' }
)) {
    Move-ToBackup $item.Path $item.Name
}

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$filtered = @($userPath -split ';' | Where-Object {
    $_ -and
    $_ -notmatch '\\.local\\bin' -and
    $_ -notmatch '\\AppData\\Roaming\\npm' -and
    $_ -notmatch '\\Python\d*' -and
    $_ -notmatch '\\nodejs'
})
[Environment]::SetEnvironmentVariable('Path', ($filtered -join ';'), 'User')

Log 'Final command check:'
foreach ($name in @('python', 'py', 'node', 'npm.cmd', 'claude', 'codex')) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    Log "${name}: $(if ($command) { $command.Source } else { 'missing' })"
}
Log 'Host reset completed. Documents and vaults were not changed.'

Write-Host ''
Write-Host "Backup: $backup" -ForegroundColor Green
Write-Host 'Opening the public v1.2.67 release page for the first-download test.' -ForegroundColor Green
Start-Process 'https://github.com/Brightinyou/my-bookshelf/releases/tag/v1.2.67'
Read-Host 'Press Enter to close this reset window'
