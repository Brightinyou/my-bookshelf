# fetch-poppler.ps1 — 인스톨러 번들용 poppler(pdftotext) 준비
# vendor\poppler에 pdftotext.exe + DLL + CJK 데이터(share/poppler)만 트리밍해 넣는다.
# vendor\poppler가 없거나 고정 버전과 다를 때 실행. (poppler-windows 릴리스 사용)
param(
    [string]$Version = "25.07.0-0",
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..")
)
$ErrorActionPreference = "Stop"
$dest = Join-Path $RepoRoot "vendor\poppler"

# GPL 전문이 조용히 빠지는 것을 막는다. 우리가 담는 GPLv2 전문은 우리가 관리하는
# 파일이 아니라 poppler-data가 share\poppler 안에 넣어 주는 것을 통째로 복사해
# 딸려 오는 것뿐이다. 상류가 구성을 바꾸면 전문 없는 패키지가 «성공적으로» 만들어진다.
# THIRD-PARTY-LICENSES.md가 GPLv2를 택하고 1조가 전문 동봉을 요구하므로 이건 준수 문제다.
# 있는지만이 아니라 크기와 첫머리까지 봐서 빈 파일·잘린 파일·엉뚱한 파일도 걸린다.
# 새로 받을 때든 이미 있어 건너뛸 때든 양쪽 다 검사한다 — 건너뛰는 쪽을 빼면
# 한번 망가진 vendor\poppler가 스탬프만 맞다는 이유로 그대로 배포된다.
function Assert-GplText {
    $gpl = Join-Path $dest "share\poppler\COPYING.gpl2"
    if (-not (Test-Path $gpl)) {
        throw "GPLv2 전문이 없다: $gpl — 상류 배포본 구성이 바뀌었는지 확인할 것"
    }
    $size = (Get-Item $gpl).Length
    if ($size -lt 15000) {
        throw "GPLv2 전문이 너무 작다 ($size bytes) — 잘렸을 수 있다: $gpl"
    }
    if (((Get-Content $gpl -TotalCount 3) -join " ") -notmatch "Version 2, June 1991") {
        throw "GPLv2 전문의 첫머리가 예상과 다르다 — 다른 라이선스이거나 손상됐다: $gpl"
    }
    Write-Host "GPLv2 전문 확인: $size bytes"
}

# 버전 스탬프로 건너뛴다. 예전에는 pdftotext.exe 존재만 보고 건너뛰었는데, 그
# 탓에 개발 PC는 한번 받아둔 판(26.02.0)에 묶이고 CI는 매번 고정값(25.07.0-0)을
# 받아, THIRD-PARTY-LICENSES.md가 선언한 버전과 실제 배포본이 갈라졌다.
# GPL 대응 소스는 «배포한 그 바이너리»의 것이어야 하므로 이 어긋남은 준수 문제다.
$stampFile = Join-Path $dest ".fetched-version"
$stamp = if (Test-Path $stampFile) { (Get-Content $stampFile -Raw).Trim() } else { "" }
if ((Test-Path (Join-Path $dest "Library\bin\pdftotext.exe")) -and $stamp -eq $Version) {
    Assert-GplText
    Write-Host "vendor\poppler 이미 $Version — 건너뜀"
    exit 0
}
if (Test-Path $dest) {
    Write-Host "vendor\poppler 버전 불일치 (있음: '$stamp', 필요: '$Version') — 다시 받는다"
    Remove-Item $dest -Recurse -Force
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
Assert-GplText
Set-Content -Path $stampFile -Value $Version -Encoding ascii
Write-Host "완료: $dest ($Version)"
& (Join-Path $dest "Library\bin\pdftotext.exe") -v
