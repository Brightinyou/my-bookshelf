# fetch-runtime.ps1 — 인스톨러 번들용 파이썬 런타임 준비 (2026-09-29)
# vendor\runtime 에 독립형 파이썬(python-build-standalone)을 풀고 core\requirements.txt 를
# 그 안에 미리 설치한다. 설치하는 PC는 파이썬도, 인터넷도, pip 도 필요 없어진다.
#
# ★왜 이렇게 하나: 예전 Setup.exe 는 받는 PC에서 python.org 설치 파일을 돌리고
# venv 를 만들고 pip 로 17종을 받았다(5~20분, 무음). 초보자 PC에서 깨지는 곳이
# 거의 다 여기였다(winget 부재·네트워크 끊김·창을 닫아 버림). 조립을 빌드 쪽으로 옮긴다.
#
# 앱은 여전히 {app}\.venv 를 쓴다. setup.bat 이 이 런타임을 base 로 삼아
# --system-site-packages venv 를 몇 초 만에 만든다(오프라인). 그래서 바로가기·
# start-app.vbs·updater·prepare_own_exe 가 보던 .venv\Scripts\… 경로는 그대로다.
param(
    [string]$Release = "20260924",
    [string]$PyVersion = "3.14.7",
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..")
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$dest = Join-Path $RepoRoot "vendor\runtime"
$name = "cpython-$PyVersion+$Release-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
$base = "https://github.com/astral-sh/python-build-standalone/releases/download/$Release"

$tmp = Join-Path $env:TEMP "runtime-fetch"
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $tmp | Out-Null
$archive = Join-Path $tmp $name

Write-Host "다운로드: $base/$name"
Invoke-WebRequest "$base/$([uri]::EscapeDataString($name))" -OutFile $archive
Invoke-WebRequest "$base/SHA256SUMS" -OutFile (Join-Path $tmp "SHA256SUMS")
$line = Get-Content (Join-Path $tmp "SHA256SUMS") | Where-Object { $_ -match "\s$([regex]::Escape($name))$" } | Select-Object -First 1
if (-not $line) { throw "SHA256SUMS 에 $name 이 없다" }
$want = ($line -split "\s+")[0].ToLower()
$got = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLower()
if ($want -ne $got) { throw "SHA256 불일치: 기대 $want / 실제 $got" }
Write-Host "SHA256 확인: $got"

if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
tar -xzf $archive -C $tmp
if ($LASTEXITCODE -ne 0) { throw "압축 해제 실패" }
Move-Item (Join-Path $tmp "python") $dest

$py = Join-Path $dest "python.exe"
& $py -m pip install --disable-pip-version-check --no-cache-dir --no-warn-script-location `
    -r (Join-Path $RepoRoot "core\requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install 실패" }

# 받는 사람에게 필요 없는 것만 걷어낸다.
# ★tkinter·tcl 은 남긴다 — 설정의 «폴더 선택» 창(pipeline_app._pick_folder)이 쓴다.
#   맥 시험 빌드에서 지웠다가 그 창이 죽은 것을 뒤늦게 찾았다(2026-09-29).
$lib = Join-Path $dest "Lib"
foreach ($d in @("test", "idlelib", "turtledemo")) {
    Remove-Item (Join-Path $lib $d) -Recurse -Force -ErrorAction SilentlyContinue
}
Get-ChildItem (Join-Path $lib "site-packages") -Directory -Recurse -Filter tests -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $dest -Directory -Recurse -Filter __pycache__ -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

& $py -c "import streamlit, webview, pandas, pypdfium2, rhwp, hwpx, clr, tkinter; print('runtime imports OK')"
if ($LASTEXITCODE -ne 0) { throw "런타임 import 검증 실패" }

$mb = [math]::Round(((Get-ChildItem $dest -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
Set-Content (Join-Path $dest ".fetched-version") "$PyVersion+$Release"
Write-Host "vendor\runtime 준비 완료: $mb MB"
