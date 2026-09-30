# fetch-webview2.ps1 — 인스톨러 번들용 WebView2 부트스트래퍼 준비 (2026-09-30)
# vendor\webview2\MicrosoftEdgeWebview2Setup.exe 를 받는다. 설치 프로그램은 받는 PC에
# WebView2 가 없을 때만 이것을 조용히 돌린다(MyBookshelf.iss [Code]).
#
# ★왜: WebView2 가 없으면 pywebview 가 옛 IE 엔진으로 떨어져 앱 창이 **빈 창**이 된다
# (Windows Sandbox 실측 — Edge·WebView2 없는 윈도우). 저장소에 exe 를 넣지 않고 빌드 때
# 받는다. 파일이 자주 바뀌어 해시를 고정할 수 없으니 Authenticode 서명으로 확인한다.
param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\.."),
    [string]$Url = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$dest = Join-Path $RepoRoot "vendor\webview2"
New-Item -ItemType Directory -Force $dest | Out-Null
$exe = Join-Path $dest "MicrosoftEdgeWebview2Setup.exe"

Write-Host "다운로드: $Url"
Invoke-WebRequest $Url -OutFile $exe -UseBasicParsing

$sig = Get-AuthenticodeSignature $exe
$subject = if ($sig.SignerCertificate) { $sig.SignerCertificate.Subject } else { "" }
if ($sig.Status -ne "Valid" -or $subject -notmatch "O=Microsoft Corporation") {
    Remove-Item $exe -Force -ErrorAction SilentlyContinue
    throw "WebView2 부트스트래퍼 서명 확인 실패: $($sig.Status) / $subject"
}
$kb = [math]::Round((Get-Item $exe).Length / 1KB)
Write-Host "서명 확인: $subject"
Write-Host "vendor\webview2 준비 완료: $kb KB"
