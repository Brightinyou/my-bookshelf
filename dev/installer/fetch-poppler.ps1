# fetch-poppler.ps1 — 인스톨러 번들용 poppler(pdftotext) 준비
# vendor\poppler에 pdftotext.exe + DLL + CJK 데이터(share/poppler)만 트리밍해 넣는다.
# CI나 새 클론에서 vendor\poppler가 없을 때 실행. (poppler-windows 릴리스 사용)
param(
    [string]$Version = "25.07.0-0",
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..")
)
$ErrorActionPreference = "Stop"
$dest = Join-Path $RepoRoot "vendor\poppler"
if (Test-Path (Join-Path $dest "Library\bin\pdftotext.exe")) {
    Write-Host "vendor\poppler 이미 준비됨 — 건너뜀"
    exit 0
}
$url = "https://github.com/oschwartz10612/poppler-windows/releases/download/v$Version/Release-$Version.zip"
$tmp = Join-Path $env:TEMP "poppler-fetch"
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $tmp | Out-Null
$zip = Join-Path $tmp "poppler.zip"
Write-Host "다운로드: $url"
Invoke-WebRequest $url -OutFile $zip
Expand-Archive $zip -DestinationPath $tmp
$src = Get-ChildItem $tmp -Directory | Where-Object { Test-Path (Join-Path $_.FullName "Library\bin\pdftotext.exe") } | Select-Object -First 1
if (-not $src) { throw "압축 해제 결과에서 pdftotext.exe를 찾지 못함" }
New-Item -ItemType Directory -Force (Join-Path $dest "Library\bin") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $dest "share") | Out-Null
Copy-Item (Join-Path $src.FullName "Library\bin\pdftotext.exe") (Join-Path $dest "Library\bin")
Copy-Item (Join-Path $src.FullName "Library\bin\*.dll") (Join-Path $dest "Library\bin")
Copy-Item (Join-Path $src.FullName "share\poppler") (Join-Path $dest "share") -Recurse
Remove-Item $tmp -Recurse -Force
Write-Host "완료: $dest"
& (Join-Path $dest "Library\bin\pdftotext.exe") -v
