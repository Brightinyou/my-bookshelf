# -*- coding: utf-8 -*-
"""앱 내 업데이트 (반자동, Windows·macOS). GitHub Releases 기반, 별도 서버 불필요.

흐름(가드레일 포함):
  1) 감지: 플랫폼별 레포의 releases/latest tag_name을 APP_VERSION과 비교
  2) 다운로드: 설치 자산을 임시폴더에 받고 크기·헤더 검증
       · Windows → Setup.exe (PE 헤더 'MZ')
       · macOS   → MyBookshelf-*-mac.zip (zip 헤더 'PK')
  3) 설치: 분리형 헬퍼가 앱 종료를 기다린 뒤(백업으로 강제종료)
       · Windows → PowerShell 헬퍼가 Setup.exe /SILENT 실행 → 앱 재실행
       · macOS   → bash 헬퍼가 zip을 풀어 .app 번들을 교체(ditto) → open 재실행
  4) 어느 단계든 실패하면 호출부가 '릴리스 페이지 열기'(안내형 A)로 폴백

두 플랫폼 모두 브라우저가 아니라 urllib로 직접 내려받으므로, 받은 파일에
격리 속성(Windows MOTW / macOS com.apple.quarantine)이 붙지 않는다 →
SmartScreen·Gatekeeper 재경고 없이 곧바로 실행된다.
"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import webbrowser
from pathlib import Path

import config as cfg
from services.common import append_log

try:
    from version import APP_VERSION
except Exception:
    APP_VERSION = "v0.0.0"

REPO_WIN = "Brightinyou/my-bookshelf-for-pc"
REPO_MAC = "Brightinyou/my-bookshelf-for-mac"


def _repo() -> str:
    return REPO_MAC if sys.platform == "darwin" else REPO_WIN


def _api_latest() -> str:
    return f"https://api.github.com/repos/{_repo()}/releases/latest"


# 이전 이름 호환(외부에서 참조할 수 있어 유지)
REPO = REPO_WIN
API_LATEST = f"https://api.github.com/repos/{REPO_WIN}/releases/latest"


def _mac_app_bundle() -> Path | None:
    """macOS에서 현재 코드가 담긴 .app 번들 경로. 번들 밖(개발 실행)이면 None."""
    for parent in Path(cfg.__file__).resolve().parents:
        if parent.suffix == ".app":
            return parent
    return None


def _parse_ver(s: str) -> tuple:
    s = (s or "").strip().lstrip("vV")
    parts = []
    for chunk in s.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def _app_root() -> Path:
    """설치 루트(=코드가 있는 곳). 설치본은 {localappdata}\\My Bookshelf."""
    return Path(cfg.__file__).resolve().parent.parent


def _pick_asset_url(assets: list) -> str:
    """플랫폼별 설치 자산의 download URL. 없으면 빈 문자열."""
    if sys.platform == "darwin":
        # 자동 업데이트는 zip을 쓴다(dmg 마운트 없이 ditto로 바로 풀 수 있음).
        # 'mac'이 이름에 든 zip을 우선, 없으면 아무 .zip.
        cand = ""
        for a in assets:
            name = (a.get("name", "") or "").lower()
            if name.endswith(".zip"):
                url = a.get("browser_download_url", "")
                if "mac" in name:
                    return url
                cand = cand or url
        return cand
    for a in assets:
        if (a.get("name", "") or "").lower() == "setup.exe":
            return a.get("browser_download_url", "")
    return ""


def check_for_update(timeout: int = 4) -> dict | None:
    """새 버전이 있으면 정보 dict, 없거나(=최신) 오류면 None. 네트워크 실패는 조용히 무시."""
    if sys.platform not in ("win32", "darwin"):
        return None
    # macOS는 설치된 .app 번들에서 실행 중일 때만 자동 교체가 가능하다(개발 실행 제외).
    if sys.platform == "darwin" and _mac_app_bundle() is None:
        return None
    try:
        req = urllib.request.Request(
            _api_latest(),
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "MyBookshelf-Updater"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
    except Exception as e:
        append_log(f"업데이트 확인 실패(무시): {type(e).__name__} {str(e)[:80]}")
        return None
    tag = data.get("tag_name", "")
    if _parse_ver(tag) <= _parse_ver(APP_VERSION):
        return None
    asset_url = _pick_asset_url(data.get("assets", []))
    return {
        "available": True,
        "current": APP_VERSION,
        "latest": tag,
        "notes": (data.get("body") or "").strip(),
        "page_url": data.get("html_url", ""),
        "asset_url": asset_url,
    }


def download_installer(asset_url: str, progress_cb=None) -> tuple[Path | None, str]:
    """설치 자산을 임시폴더에 받고 검증. 반환: (경로 또는 None, 오류문구).
    Windows=Setup.exe(MZ), macOS=업데이트 zip(PK)."""
    if not asset_url:
        return None, "설치 파일 주소를 찾을 수 없습니다."
    if sys.platform == "darwin":
        dest = Path(tempfile.gettempdir()) / "MyBookshelf-update.zip"
        magic, min_size, bad_msg = b"PK", 100_000, "받은 파일이 올바른 업데이트 파일(zip)이 아닙니다."
    else:
        dest = Path(tempfile.gettempdir()) / "MyBookshelf-Setup-update.exe"
        magic, min_size, bad_msg = b"MZ", 200_000, "받은 파일이 올바른 설치 파일이 아닙니다."
    try:
        req = urllib.request.Request(asset_url, headers={"User-Agent": "MyBookshelf-Updater"})
        with urllib.request.urlopen(req, timeout=30) as r:
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    if progress_cb and total:
                        progress_cb(min(1.0, got / total))
    except Exception as e:
        return None, f"다운로드 실패: {type(e).__name__} {str(e)[:80]}"
    # 무결성 검증: 크기 + 매직 헤더(Win=MZ / mac=PK). 브라우저 경유가 아니라
    # 격리 속성이 없어 SmartScreen·Gatekeeper 위험도 낮음.
    try:
        if dest.stat().st_size < min_size:
            return None, "다운로드가 불완전합니다(파일 크기 이상)."
        with open(dest, "rb") as f:
            if f.read(2) != magic:
                return None, bad_msg
    except Exception as e:
        return None, f"검증 실패: {str(e)[:80]}"
    return dest, ""


_HELPER_PS1 = r"""
param([string]$Root, [string]$Setup, [string]$Relaunch)
$ErrorActionPreference = 'SilentlyContinue'
$Log = Join-Path $env:TEMP 'mybookshelf_update.log'
function Log($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $m" | Out-File -FilePath $Log -Append -Encoding utf8 }
Log "helper start (Root=$Root)"
function AppProcs {
  Get-CimInstance Win32_Process | Where-Object {
    $_.ExecutablePath -and $_.ExecutablePath.ToLower().StartsWith($Root.ToLower()) -and $_.Name -match 'python'
  }
}
# 1) 앱(설치 폴더의 python) 종료 대기 — 파일 잠금 해제 목적 (짧게)
$deadline = (Get-Date).AddSeconds(10)
while ((Get-Date) -lt $deadline -and (AppProcs)) { Start-Sleep -Milliseconds 300 }
# 2) 백업: 남아 있으면 강제 종료
foreach ($p in AppProcs) { try { Log "force-kill $($p.ProcessId)"; Stop-Process -Id $p.ProcessId -Force } catch {} }
Start-Sleep -Seconds 2
# 3) 설치 (per-user, UAC 없음; /SILENT = 진행바 표시, 클릭 불필요)
Log "install start: $Setup"
try {
  $pr = Start-Process -FilePath $Setup -ArgumentList '/SILENT','/NORESTART' -PassThru -Wait
  Log "install exit code: $($pr.ExitCode)"
} catch { Log "install error: $_" }
Log "install done"
# 4) MyBookshelf.iss의 [Run]에 이미 postinstall 항목(start-app.vbs)이 있고,
#    이건 skipifsilent가 붙어 있어도 우리가 쓰는 /SILENT(=/VERYSILENT 아님)
#    에서는 실제로 실행된다는 걸 로그로 확인했다(Setup.exe /LOG=... 로 뜬
#    두 번째 "-- Run entry --"가 wscript.exe start-app.vbs). 즉 보통은
#    Setup.exe 자신이 이미 앱을 띄운다 — 예전처럼 이 헬퍼가 항상 추가로
#    MyBookshelf.exe를 또 실행하면 두 인스턴스가 동시에 부트스트랩하며
#    충돌해 "Failed to load Python DLL" 오류 창이 두 개씩 뜨는 문제가 있었다.
#    다만 중첩된 프로세스 체인(hidden PowerShell → Setup.exe → wscript.exe)
#    안에서는 그 자동 실행이 창 세션 접근 등의 이유로 가끔 늦거나 아예 안
#    뜨는 것도 확인됨 — 그래서 넉넉히 기다려 보고, 정말 안 떴을 때만
#    보조로 딱 한 번 수동 실행한다 (2026-07-25).
$deadline2 = (Get-Date).AddSeconds(20)
$cameUp = $false
while ((Get-Date) -lt $deadline2) {
  if (AppProcs) { $cameUp = $true; break }
  Start-Sleep -Milliseconds 500
}
if ($cameUp) {
  Log "app came up on its own (via Setup.exe's own postinstall launch)"
} else {
  Log "app did not come up on its own within 20s - launching it as a fallback"
  if (Test-Path $Relaunch) {
    Start-Process -FilePath $Relaunch -WorkingDirectory $Root
    Log "fallback relaunch: $Relaunch"
  } else {
    Log "fallback relaunch target missing: $Relaunch"
  }
}
Log "helper done"
"""


def _write_helper() -> Path:
    helper = Path(tempfile.gettempdir()) / "mybookshelf_update_helper.ps1"
    helper.write_text(_HELPER_PS1, encoding="utf-8")
    return helper


# ── macOS 설치 헬퍼 ────────────────────────────────────────
# 앱(streamlit + pywebview 창)이 종료되길 기다린 뒤, 내려받은 zip을 풀어
# .app 번들을 통째로 교체(ditto)하고 open으로 재실행한다. 실패하면 백업(.old)을
# 되돌려 최소한 이전 버전이라도 다시 뜨게 한다.
_MAC_HELPER_SH = r"""#!/bin/bash
APP_PATH="$1"     # 교체 대상 .app 번들
ZIP_PATH="$2"     # 내려받은 업데이트 zip
SUPPORT="$HOME/Library/Application Support/MyBookshelf"
LOG="$SUPPORT/update.log"
mkdir -p "$SUPPORT" 2>/dev/null
log(){ echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" >> "$LOG" 2>/dev/null; }
log "helper start APP=$APP_PATH ZIP=$ZIP_PATH"

# 1) 앱 프로세스(streamlit pipeline_app.py + 창 desktop.py) 종료 대기(최대 ~10초)
for i in $(seq 1 33); do
  pgrep -f "pipeline_app.py" >/dev/null 2>&1 || break
  sleep 0.3
done
# 2) 남아 있으면 강제 종료(파일 잠금 해제)
pkill -f "streamlit run.*pipeline_app.py" 2>/dev/null
pkill -f "MyBookshelf.app/Contents/Resources/desktop.py" 2>/dev/null
sleep 1

# 3) zip 해제
TMPD="$(mktemp -d)"
if ! /usr/bin/ditto -x -k "$ZIP_PATH" "$TMPD" >>"$LOG" 2>&1; then
  log "extract failed"; /usr/bin/open "$APP_PATH" 2>/dev/null; exit 1
fi
NEWAPP="$TMPD/MyBookshelf.app"
if [ ! -d "$NEWAPP" ]; then
  NEWAPP="$(/usr/bin/find "$TMPD" -maxdepth 3 -name 'MyBookshelf.app' -type d 2>/dev/null | head -1)"
fi
if [ ! -d "$NEWAPP" ]; then
  log "new .app not found in zip"; /usr/bin/open "$APP_PATH" 2>/dev/null; exit 1
fi

# 4) 번들 교체(백업 후 ditto). 실패하면 백업 복원.
rm -rf "$APP_PATH.old" 2>/dev/null
if [ -d "$APP_PATH" ]; then mv "$APP_PATH" "$APP_PATH.old" 2>>"$LOG"; fi
if /usr/bin/ditto "$NEWAPP" "$APP_PATH" >>"$LOG" 2>&1; then
  rm -rf "$APP_PATH.old" 2>/dev/null
  log "swap ok -> $APP_PATH"
else
  log "swap failed - restoring backup"
  rm -rf "$APP_PATH" 2>/dev/null
  [ -d "$APP_PATH.old" ] && mv "$APP_PATH.old" "$APP_PATH"
fi

# 5) 격리 속성 제거(방어) + 재실행
/usr/bin/xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null
rm -rf "$TMPD" 2>/dev/null
sleep 1
/usr/bin/open "$APP_PATH" 2>>"$LOG"
log "relaunched; helper done"
"""


def _mac_launch_helper_and_exit(zip_path: Path) -> bool:
    bundle = _mac_app_bundle()
    if not bundle:
        append_log("업데이트 헬퍼 실행 실패(mac): .app 번들을 찾지 못함")
        return False
    try:
        helper = Path(tempfile.gettempdir()) / "mybookshelf_update_helper.sh"
        helper.write_text(_MAC_HELPER_SH, encoding="utf-8")
        helper.chmod(0o755)
        # start_new_session=True → setsid(2) 로 세션 분리. 부모(streamlit)가
        # 종료돼도 헬퍼는 계속 살아 번들을 교체한다.
        subprocess.Popen(
            ["/bin/bash", str(helper), str(bundle), str(zip_path)],
            start_new_session=True, close_fds=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        append_log(f"업데이트 헬퍼 실행(mac): {zip_path.name} → {bundle.name}")
    except Exception as e:
        append_log(f"업데이트 헬퍼 실행 실패(mac): {type(e).__name__} {str(e)[:80]}")
        return False

    _terminate_parent_tree()
    import threading
    threading.Timer(0.8, lambda: os._exit(0)).start()
    return True


def launch_helper_and_exit(installer_path: Path) -> bool:
    """대기/설치/재실행 헬퍼를 백그라운드로 실행하고 앱을 종료한다.
    성공 시 곧 프로세스가 종료된다. 실행 자체가 실패하면 False(→ 호출부는 A로 폴백)."""
    if sys.platform == "darwin":
        return _mac_launch_helper_and_exit(installer_path)
    root = _app_root()
    relaunch = root / "MyBookshelf.exe"
    if not relaunch.exists():
        relaunch = root / "start-app.vbs"
    try:
        helper = _write_helper()
        # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP.
        # ⚠ DETACHED_PROCESS(0x08)는 pythonw(무콘솔)에서 프로세스 생성을 막으므로 쓰지 않는다.
        # 부모가 죽어도 자식은 Windows 기본상 살아남는다.
        flags = 0x08000000 | 0x00000200
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden",
             "-ExecutionPolicy", "Bypass", "-File", str(helper),
             "-Root", str(root), "-Setup", str(installer_path), "-Relaunch", str(relaunch)],
            creationflags=flags, close_fds=True,
        )
        append_log(f"업데이트 헬퍼 실행: {installer_path.name}")
    except Exception as e:
        append_log(f"업데이트 헬퍼 실행 실패: {type(e).__name__} {str(e)[:80]}")
        return False

    # 앱(창=desktop.py 및 자신=streamlit)을 정리하고 종료 → 헬퍼가 즉시 설치 진행
    _terminate_parent_tree()
    import threading
    threading.Timer(0.8, lambda: os._exit(0)).start()
    return True


def _terminate_parent_tree() -> None:
    """창 런처(desktop.py의 pythonw 등) 부모 python 프로세스를 정리한다(헬퍼 대기 단축)."""
    try:
        import psutil
        me = psutil.Process()
        for p in me.parents():
            try:
                if "python" in p.name().lower():
                    p.terminate()
            except Exception:
                pass
    except Exception:
        pass


def open_release_page(url: str) -> None:
    """안내형(A) 폴백 — 릴리스 페이지를 기본 브라우저로 연다."""
    try:
        webbrowser.open(url or f"https://github.com/{_repo()}/releases/latest")
    except Exception:
        pass
