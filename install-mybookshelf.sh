#!/bin/bash
# install-mybookshelf.sh — My Bookshelf 무인 설치 (macOS)
#
# install-mybookshelf.ps1 의 맥판. 사용자가 손으로 하던 과정을 그대로 옮겼다:
#   1) 파이썬 3.14 (없을 때만)      4) AI CLI (codex 또는 claude)
#   2) MyBookshelf.pkg 내려받기      5) 옵시디언 (선택)
#   3) 무음 설치 + 환경 준비          6) 기본 설정 미리 넣기
#
#   ★ 맥에서는 파이썬을 미리 깔 필요가 없다. pkg 의 postinstall 이 없으면
#     스스로 받아 설치한다. 그래도 먼저 확인하는 이유는 Homebrew 가 있는
#     기기에서 arm64 네이티브 판을 쓰는 편이 낫기 때문이다.
#   ★ installer(1) 로 깔면 «확인되지 않은 개발자» 경고를 아예 만나지 않는다.
#     Gatekeeper 는 Finder 로 열 때 걸린다.
#
#   자동화되지 않는 것은 둘뿐 — 구독 CLI 브라우저 로그인, API 키 입력.
#
# 쓰기:
#   bash install-mybookshelf.sh
#   bash install-mybookshelf.sh --ai claude --obsidian --launch

set -uo pipefail

REPO="Brightinyou/my-bookshelf"
CONFIG_DIR="$HOME/.config/mybookshelf"
SUPPORT="$HOME/Library/Application Support/MyBookshelf"
WORK="$(mktemp -d -t mybookshelf-bootstrap)"
LOG="$WORK/bootstrap.log"
PY_VERSION="3.14.6"
PY_URL="https://www.python.org/ftp/python/${PY_VERSION}/python-${PY_VERSION}-macos11.pkg"
PY_SHA="d3c9fff52214847e4fab03e9eaf53dd2a8e51e3534aa0b61f201b749f86bef28"

AI="codex"; OBSIDIAN=0; LANG_UI="ko"; TARGET_LANG="ko"
WIKI_PCT=30; NO_PREFS=0; LAUNCH=0
MANUAL=()

while [ $# -gt 0 ]; do
    case "$1" in
        --ai)          AI="${2:-codex}"; shift 2 ;;
        --obsidian)    OBSIDIAN=1; shift ;;
        --lang)        LANG_UI="${2:-ko}"; shift 2 ;;
        --target-lang) TARGET_LANG="${2:-ko}"; shift 2 ;;
        --wiki-pct)    WIKI_PCT="${2:-30}"; shift 2 ;;
        --no-prefs)    NO_PREFS=1; shift ;;
        --launch)      LAUNCH=1; shift ;;
        -h|--help)     sed -n '2,22p' "$0"; exit 0 ;;
        *) echo "모르는 옵션: $1"; exit 2 ;;
    esac
done
case "$AI" in codex|claude|none) ;; *) echo "--ai 는 codex·claude·none 중 하나"; exit 2 ;; esac

C_CYAN=$'\033[36m'; C_YELLOW=$'\033[33m'; C_OFF=$'\033[0m'
say()  { echo "  $*"; }
step() { echo; echo "${C_CYAN}[$1/7] $2${C_OFF}"; }
warn() { echo "${C_YELLOW}  ! $*${C_OFF}"; }
log()  { echo "$(date '+%H:%M:%S')  $*" >> "$LOG"; }
die()  { echo "${C_YELLOW}중단: $*${C_OFF}"; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

find_python() {
    # postinstall·런처와 같은 판정 — 호스트와 아키텍처가 같은 3.10 이상.
    local hostarch cand info fallback=""
    hostarch="$(uname -m)"
    for cand in /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3.13 \
                /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3 \
                /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
                /usr/local/bin/python3 /usr/bin/python3; do
        [ -x "$cand" ] || continue
        info="$("$cand" -c 'import sys,platform;print(sys.version_info[0],sys.version_info[1],platform.machine())' 2>/dev/null)" || continue
        set -- $info
        if [ "${1:-0}" = "3" ] && [ "${2:-0}" -ge 10 ]; then
            if [ "${3:-}" = "$hostarch" ]; then echo "$cand"; return 0; fi
            [ -z "$fallback" ] && fallback="$cand"
        fi
    done
    [ -n "$fallback" ] && { echo "$fallback"; return 0; }
    return 1
}

echo "My Bookshelf 무인 설치 (macOS) — 기록: $LOG"
say "설치와 파이썬 설치에 관리자 암호가 한 번 필요합니다."
sudo -v || die "관리자 권한을 얻지 못했습니다."
# 긴 설치 동안 sudo 시간이 끊기지 않게 유지한다.
( while kill -0 "$$" 2>/dev/null; do sudo -n true 2>/dev/null; sleep 50; done ) &
SUDO_KEEPALIVE=$!
trap 'kill "$SUDO_KEEPALIVE" 2>/dev/null; [ -z "${UNATTENDED_MARK:-}" ] || rm -f "$UNATTENDED_MARK"; rm -rf "$WORK"' EXIT

# ── 1. 파이썬 ────────────────────────────────────────────────
step 1 "파이썬 확인"
PY="$(find_python || true)"
if [ -n "$PY" ]; then
    say "이미 쓸 수 있는 파이썬이 있습니다 — 건너뜁니다. ($PY)"
else
    say "파이썬 ${PY_VERSION} 을 설치합니다 (몇 분)."
    if have brew; then
        say "Homebrew 로 설치합니다 (아키텍처 네이티브)."
        brew install python@3.14 >>"$LOG" 2>&1 || warn "brew 설치 실패 — python.org 로 넘어갑니다."
        PY="$(find_python || true)"
    fi
    if [ -z "$PY" ]; then
        say "python.org 에서 직접 내려받습니다."
        if curl -fsSL -o "$WORK/python.pkg" "$PY_URL"; then
            GOT="$(shasum -a 256 "$WORK/python.pkg" | awk '{print $1}')"
            [ "$GOT" = "$PY_SHA" ] || die "파이썬 설치 파일이 손상됐습니다 (SHA256 $GOT)"
            sudo installer -pkg "$WORK/python.pkg" -target / >>"$LOG" 2>&1
            PY="$(find_python || true)"
        else
            die "파이썬을 내려받지 못했습니다."
        fi
    fi
    [ -n "$PY" ] || die "파이썬 설치를 확인하지 못했습니다. python.org 에서 직접 설치한 뒤 다시 실행하세요."
    say "파이썬 준비 완료. ($PY)"
fi

# ── 2. pkg 내려받기 ──────────────────────────────────────────
step 2 "최신 릴리스 내려받기"
REL_JSON="$WORK/release.json"
curl -fsSL -H "User-Agent: mybookshelf-bootstrap" \
     "https://api.github.com/repos/$REPO/releases/latest" -o "$REL_JSON" \
     || die "릴리스 정보를 받지 못했습니다."
read -r TAG URL SIZE <<EOF
$("$PY" - "$REL_JSON" <<'PYEOF'
import json, sys
rel = json.load(open(sys.argv[1]))
a = next((x for x in rel["assets"] if x["name"] == "MyBookshelf.pkg"), None)
if not a:
    print("", "", "0"); raise SystemExit(0)
print(rel["tag_name"], a["browser_download_url"], a["size"])
PYEOF
)
EOF
[ -n "${URL:-}" ] || die "릴리스 ${TAG:-?} 에 MyBookshelf.pkg 가 없습니다."
say "$TAG — MyBookshelf.pkg ($(( SIZE / 1024 )) KB)"
curl -fsSL -o "$WORK/MyBookshelf.pkg" "$URL" || die "pkg 를 내려받지 못했습니다."
log "downloaded $TAG"

# ── 3. 무음 설치 (+ 환경 준비) ───────────────────────────────
step 3 "설치 — 파이썬 패키지를 받는 동안 몇 분 걸립니다. 그대로 두세요."
T0=$(date +%s)
# 이 스크립트가 4~6단계를 스스로 하므로, pkg 의 추가 설정 창은 뜨지 않게 한다.
mkdir -p "$SUPPORT"
UNATTENDED_MARK="$SUPPORT/.unattended-install"
: > "$UNATTENDED_MARK"
sudo installer -pkg "$WORK/MyBookshelf.pkg" -target / >>"$LOG" 2>&1 \
    || { rm -f "$UNATTENDED_MARK"; die "설치에 실패했습니다. $LOG 를 확인하세요."; }
rm -f "$UNATTENDED_MARK"
VENV="$SUPPORT/.venv"
if [ ! -x "$VENV/bin/python" ] || ! "$VENV/bin/python" -c "import streamlit, webview" >/dev/null 2>&1; then
    [ -f "$SUPPORT/install.log" ] && tail -15 "$SUPPORT/install.log" | sed 's/^/  /'
    warn "환경 준비가 끝나지 않았습니다 — 앱 첫 실행이 이어서 처리합니다."
    MANUAL+=("앱을 한 번 실행해 환경 준비를 마치기 (몇 분)")
else
    say "완료 ($(( ($(date +%s) - T0) / 60 ))분). 설치 위치: /Applications/MyBookshelf.app"
fi

# ── 4. Node.js + AI CLI ──────────────────────────────────────
step 4 "AI 연결 준비"
if [ "$AI" = "none" ]; then
    say "CLI 설치를 건너뜁니다 — 앱 설정 탭에서 API 키를 넣으세요."
    MANUAL+=("앱 ⚙️ 설정 탭에 AI API 키 입력 (Gemini/OpenAI/Anthropic 중 하나)")
else
    if have node; then
        say "Node.js 이미 있음 ($(node --version))"
    elif have brew; then
        say "Node.js 를 설치합니다."
        brew install node >>"$LOG" 2>&1
    fi
    if ! have node && [ "$AI" != "claude" ]; then
        warn "Node.js 를 설치하지 못했습니다 — https://nodejs.org 에서 LTS 를 직접 설치하세요."
        MANUAL+=("Node.js LTS 설치 후 이 스크립트를 다시 실행")
    else
        if [ "$AI" = "claude" ]; then
            # 공식 설치본이 ~/.local/bin 에 네이티브로 깐다. npm 전역 설치는 알맹이
            # 없는 껍데기가 남는 사고가 있어 앱도 이쪽을 먼저 본다.
            say "Claude Code CLI 설치 중..."
            curl -fsSL https://claude.ai/install.sh 2>>"$LOG" | bash >>"$LOG" 2>&1 \
                || { warn "공식 설치 실패 — npm 으로 시도합니다."
                     have npm && npm install -g @anthropic-ai/claude-code >>"$LOG" 2>&1; }
            CLI="claude"
        else
            say "Codex CLI 설치 중..."
            npm install -g @openai/codex >>"$LOG" 2>&1
            CLI="codex"
        fi
        export PATH="$HOME/.local/bin:$PATH"
        if have "$CLI"; then say "$CLI 준비 완료 — 로그인만 남았습니다."
        else warn "$CLI 를 찾지 못했습니다. 새 터미널 창에서 확인하세요."; fi
        MANUAL+=("터미널에서 '$CLI' 를 한 번 실행해 브라우저로 로그인 (구독 계정)")
    fi
fi

# ── 5. 옵시디언 (선택) ───────────────────────────────────────
step 5 "옵시디언"
if [ "$OBSIDIAN" != "1" ]; then
    say "건너뜁니다 (--obsidian 을 주면 설치합니다)."
elif [ -d "/Applications/Obsidian.app" ]; then
    say "이미 설치돼 있습니다."
elif have brew; then
    brew install --cask obsidian >>"$LOG" 2>&1 \
        && say "설치 완료 — 앱 설정 탭에서 보관함(Vault) 폴더를 지정하세요." \
        || warn "설치 실패 — https://obsidian.md/download"
else
    warn "Homebrew 가 없어 자동 설치를 못 했습니다 — https://obsidian.md/download"
fi

# ── 6. 기본 설정 미리 넣기 ───────────────────────────────────
step 6 "기본 설정"
if [ "$NO_PREFS" = "1" ]; then
    say "건너뜁니다 — 앱 설정 탭에서 직접 고르세요."
else
    mkdir -p "$CONFIG_DIR"
    "$PY" - "$CONFIG_DIR" "$TARGET_LANG" "$WIKI_PCT" "$OBSIDIAN" "$AI" "$LANG_UI" <<'PYEOF'
import json, os, sys
cfg_dir, target_lang, pct, obsidian, ai, ui_lang = sys.argv[1:7]
obsidian = obsidian == "1"
keys_file = os.path.join(cfg_dir, "keys.json")
# 기존 파일이 있으면 병합한다 — 이미 들어 있는 API 키를 지우면 안 된다.
keys = {}
if os.path.exists(keys_file):
    try:
        keys = json.load(open(keys_file, encoding="utf-8"))
    except ValueError:
        keys = {}
keys.update({
    "pref_target_lang": target_lang,
    "pref_do_translate": True,
    "pref_translate_want_plain": True,
    "pref_translate_want_bilingual": False,
    "pref_wiki_length_pct": int(pct),
    "pref_skip_processed": True,
    "pref_use_epub": True,
    "pref_use_obsidian": obsidian,
    "pref_use_docx": not obsidian,      # 옵시디언을 안 쓰면 Word 로 받는다
    "pref_use_hwpx": False,
    "pref_use_claude_cli": ai == "claude",
    "pref_use_codex_cli": ai == "codex",
})
if ai != "none":
    prov = "claude_cli" if ai == "claude" else "codex_cli"
    keys["wiki_provider"] = prov
    keys["wiki_model"] = "default"
    keys["pref_translate_engine"] = f"{prov}:default"
with open(keys_file, "w", encoding="utf-8") as f:
    json.dump(keys, f, ensure_ascii=False, indent=2)
os.chmod(keys_file, 0o600)

cfg_file = os.path.join(cfg_dir, "config.json")
if not os.path.exists(cfg_file):
    # 경로(binaries/dirs)는 일부러 비워 둔다 — 기기마다 다르고, 앱이 스스로 찾는다.
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump({"lang": ui_lang, "folder_lang": ui_lang}, f, ensure_ascii=False)
PYEOF
    OUTPUTS="EPUB+Word"; [ "$OBSIDIAN" = "1" ] && OUTPUTS="EPUB+옵시디언"
    say "도착언어 $TARGET_LANG · 요약 ${WIKI_PCT}% · 출력 $OUTPUTS 로 맞췄습니다."
fi

# ── 7. 마무리 ────────────────────────────────────────────────
step 7 "끝"
say "실행: Launchpad 의 «My Bookshelf» (또는 open -a MyBookshelf)"
say "기록: $LOG · $SUPPORT/install.log"
if [ "${#MANUAL[@]}" -gt 0 ]; then
    echo
    echo "${C_YELLOW}손으로 하실 일 (자동화 불가):${C_OFF}"
    i=1; for m in "${MANUAL[@]}"; do echo "  $i) $m"; i=$((i+1)); done
    echo "  → 로그인 뒤 앱을 껐다 켜면 설정 탭 토글이 이미 켜져 있습니다."
fi
[ "$LAUNCH" = "1" ] && open /Applications/MyBookshelf.app
exit 0
