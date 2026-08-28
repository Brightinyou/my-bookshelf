#!/bin/bash
# mac_postinstall.sh — .pkg 설치 직후 파이썬 환경을 준비한다 (2026-08-29).
#
# Windows 의 [Run] «setup.bat --installer» 와 같은 자리다. 설치가 끝나면
# 바로 실행되도록 만드는 것이 목적 — 첫 실행 때 5~20분 기다리지 않는다.
#
# 실패해도 exit 0 한다. 앱 런처에 첫 실행 준비 경로가 그대로 남아 있어서,
# 여기서 못 끝내도 앱은 열린다. 설치 자체를 실패로 만들 이유가 없다.
#
# 인자(macOS Installer 규약): $1 패키지 경로, $2 설치 위치, $3 대상 볼륨

set -u

PY_VERSION="3.14.6"
PY_PKG_URL="https://www.python.org/ftp/python/${PY_VERSION}/python-${PY_VERSION}-macos11.pkg"
PY_PKG_SHA="d3c9fff52214847e4fab03e9eaf53dd2a8e51e3534aa0b61f201b749f86bef28"

APP="${2:-/Applications}/MyBookshelf.app"
RESOURCES="$APP/Contents/Resources"

# ── 실제 사용자를 찾는다. 이 스크립트는 root 로 돈다 ──
USER_NAME="$(/usr/bin/stat -f '%Su' /dev/console 2>/dev/null)"
if [ -z "$USER_NAME" ] || [ "$USER_NAME" = "root" ]; then
    USER_NAME="${USER:-}"
fi
if [ -z "$USER_NAME" ] || [ "$USER_NAME" = "root" ]; then
    exit 0        # 로그인 사용자를 못 찾으면 손대지 않는다
fi
USER_HOME="$(/usr/bin/dscl . -read "/Users/$USER_NAME" NFSHomeDirectory 2>/dev/null | awk '{print $2}')"
[ -z "$USER_HOME" ] && USER_HOME="/Users/$USER_NAME"

SUPPORT="$USER_HOME/Library/Application Support/MyBookshelf"
VENV="$SUPPORT/.venv"
LOG="$SUPPORT/install.log"

/usr/bin/install -d -o "$USER_NAME" -m 755 "$SUPPORT" 2>/dev/null

log() { echo "[$(date '+%m-%d %H:%M:%S')] $*" >> "$LOG"; }
# -H 로 HOME 을 그 사용자 것으로 맞춘다. 없으면 pip 이 root 의 캐시 경로를
# 보다가 권한이 없어 캐시를 통째로 포기한다.
asuser() { /usr/bin/sudo -H -u "$USER_NAME" "$@"; }

log "── postinstall 시작 (사용자 $USER_NAME) ──"

if [ ! -f "$RESOURCES/requirements.txt" ]; then
    log "requirements.txt 없음 ($RESOURCES) — 건너뜀"
    exit 0
fi

# ── 이미 준비돼 있으면 끝 ──
if [ -x "$VENV/bin/python" ] \
   && asuser "$VENV/bin/python" -c "import streamlit, webview" >/dev/null 2>&1; then
    log "이미 준비된 환경이 있다 — 패키지만 최신으로 맞춘다"
    asuser "$VENV/bin/python" -m pip install -r "$RESOURCES/requirements.txt" -q >>"$LOG" 2>&1
    log "완료"
    exit 0
fi

# ── 쓸 만한 파이썬 찾기 ──
# 호스트와 아키텍처가 같은 것을 고른다. universal2 를 x86_64 로 띄우면
# 창이 «Intel 기반 앱» 으로 뜬다.
HOSTARCH="$(uname -m)"
PY=""
PY_FALLBACK=""
for cand in /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3.13 \
            /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3 \
            /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
            /usr/local/bin/python3.14 /usr/local/bin/python3 /usr/bin/python3; do
    [ -x "$cand" ] || continue
    info="$("$cand" -c 'import sys,platform;print(sys.version_info[0],sys.version_info[1],platform.machine())' 2>/dev/null)" || continue
    set -- $info
    if [ "${1:-0}" = "3" ] && [ "${2:-0}" -ge 10 ]; then
        if [ "${3:-}" = "$HOSTARCH" ]; then PY="$cand"; break; fi
        [ -z "$PY_FALLBACK" ] && PY_FALLBACK="$cand"
    fi
done
[ -z "$PY" ] && PY="$PY_FALLBACK"

# ── 없으면 python.org 판을 받아 설치한다 ──
if [ -z "$PY" ]; then
    log "파이썬 3.10+ 이 없다 — python.org ${PY_VERSION} 을 받는다"
    TMP="$(mktemp -d)"
    if /usr/bin/curl -fsSL -o "$TMP/python.pkg" "$PY_PKG_URL"; then
        GOT="$(/usr/bin/shasum -a 256 "$TMP/python.pkg" | awk '{print $1}')"
        if [ "$GOT" = "$PY_PKG_SHA" ]; then
            /usr/sbin/installer -pkg "$TMP/python.pkg" -target / >>"$LOG" 2>&1 \
                && PY="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
            log "파이썬 설치 결과: ${PY:-실패}"
        else
            log "체크섬 불일치 — 설치하지 않는다 (기대 $PY_PKG_SHA / 실제 $GOT)"
        fi
    else
        log "내려받기 실패 — 첫 실행 때 다시 안내한다"
    fi
    rm -rf "$TMP"
fi

if [ -z "$PY" ] || [ ! -x "$PY" ]; then
    log "쓸 파이썬을 못 구했다 — 앱 첫 실행이 이어서 처리한다"
    exit 0
fi
log "파이썬: $PY"

# ── venv 만들고 패키지 설치 (사용자 권한으로) ──
rm -rf "$VENV"
if [ "$HOSTARCH" = "arm64" ] || [ "$HOSTARCH" = "x86_64" ]; then
    asuser /usr/bin/arch -"$HOSTARCH" "$PY" -m venv "$VENV" >>"$LOG" 2>&1
else
    asuser "$PY" -m venv "$VENV" >>"$LOG" 2>&1
fi
if [ ! -x "$VENV/bin/python" ]; then
    log "venv 생성 실패"
    exit 0
fi

asuser "$VENV/bin/python" -m pip install --upgrade pip -q >>"$LOG" 2>&1
asuser "$VENV/bin/python" -m pip install -r "$RESOURCES/requirements.txt" -q >>"$LOG" 2>&1

# Streamlit 첫 실행 영문 환영문 건너뛰기 — 런처가 하던 일을 여기서 미리 한다
asuser /bin/mkdir -p "$USER_HOME/.streamlit"
[ -f "$USER_HOME/.streamlit/credentials.toml" ] || \
    asuser /usr/bin/tee "$USER_HOME/.streamlit/credentials.toml" >/dev/null <<'TOML'
[general]
email = ""
TOML

if asuser "$VENV/bin/python" -c "import streamlit, webview" >/dev/null 2>&1; then
    log "준비 완료 — 첫 실행부터 바로 열린다"
    asuser /usr/bin/osascript -e 'display notification "설치가 끝났습니다. 바로 실행할 수 있습니다." with title "My Bookshelf"' >/dev/null 2>&1
else
    log "패키지 확인 실패 — 앱 첫 실행이 이어서 처리한다"
fi
exit 0
