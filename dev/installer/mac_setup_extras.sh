#!/bin/bash
# mac_setup_extras.sh — 설치 직후 터미널에서 묻는 추가 설정 (2026-08-29)
#
# .pkg 는 파이썬·venv 까지만 갖춘다. 그 뒤의 «AI 연결»과 «옵시디언»은 고를
# 일이라 물어야 하는데, macOS 설치 관리자에는 순차 질문이라는 것이 없다
# (사용자화 창의 체크박스뿐이고, 그 창은 대부분 열지 않는다).
#
# 그래서 postinstall 이 이 스크립트를 «open -a Terminal» 로 띄운다. 확인한 것:
#   - 로그인 사용자 권한으로 돈다(root 아님)  - 진짜 TTY 가 붙어 read 가 된다
#   - pkg 로 깔린 파일은 격리 속성이 없어 경고가 뜨지 않는다
#   - osascript 대화상자와 달리 TCC 권한을 묻지 않는다
#
# postinstall 안에서 직접 묻지 않는 이유: 설치 관리자 스크립트에서 GUI 를
# 띄우면 창이 안 뜬 채 멎을 수 있다 — 이 앱의 런처가 실제로 그렇게 멎었다.

set -uo pipefail

CONFIG_DIR="$HOME/.config/mybookshelf"
SUPPORT="$HOME/Library/Application Support/MyBookshelf"
VENV="$SUPPORT/.venv"
LOG="$SUPPORT/install.log"

# 실측치(2026-08-29, Apple Silicon). 고를 때 알아야 할 정보라 함께 보여 준다.
SZ_CLAUDE="약 293 MB"
SZ_CODEX="약 363 MB (Node.js 79 MB 포함)"
SZ_BOTH="약 656 MB"
SZ_OBSIDIAN="약 515 MB"

# 지원 폴더가 없으면 로그 기록이 통째로 실패한다(zip 설치 등 pkg 를 거치지
# 않은 경로). 먼저 만들어 둔다.
mkdir -p "$SUPPORT" 2>/dev/null

C_B=$'\033[1m'; C_C=$'\033[36m'; C_Y=$'\033[33m'; C_D=$'\033[2m'; C_0=$'\033[0m'
say()  { echo "  $*"; }
head_() { echo; echo "${C_C}${C_B}$*${C_0}"; }
warn() { echo "${C_Y}  ! $*${C_0}"; }
log()  { echo "$(date '+%H:%M:%S')  extras: $*" >> "$LOG" 2>/dev/null; }
have() { command -v "$1" >/dev/null 2>&1; }

# 설치 직후에는 postinstall이 로그 소유권을 맞춘다. 그래도 과거 판에서 root
# 소유 로그가 남아 있으면 설치 명령 자체가 `>> install.log` 때문에 멈추지 않게
# /dev/null로만 기록하고, 화면에 이유를 알린다.
mkdir -p "$SUPPORT" 2>/dev/null || true
if ! { : >> "$LOG"; } 2>/dev/null; then
    warn "설치 기록에 쓸 수 없습니다. 설치는 계속하고 기록만 남기지 않습니다."
    LOG="/dev/null"
fi

register_cli_path() {
    # Finder로 연 앱은 자체 PATH를 쓰지만, 사용자가 어느 새 Terminal을 열어도
    # claude/codex를 바로 쓸 수 있게 zsh의 로그인·일반 셸에 한 번만 등록한다.
    # 사용자 전용 Node를 쓴 경우에는 Codex의 `env node` 셔뱅에도 이 경로가 필요하다.
    local profile marker line
    marker="# My Bookshelf CLI PATH"
    line='export PATH="$HOME/.local/bin:$HOME/Library/Application Support/MyBookshelf/node/bin:$PATH"'
    export PATH="$HOME/.local/bin:$SUPPORT/node/bin:$PATH"
    for profile in "$HOME/.zprofile" "$HOME/.zshrc"; do
        if [ -e "$profile" ] && grep -Fqx "$marker" "$profile" 2>/dev/null; then
            continue
        fi
        if {
            printf '\n%s\n%s\n' "$marker" "$line"
        } >> "$profile" 2>/dev/null; then
            log "PATH 등록: $profile"
        else
            warn "터미널 PATH를 $profile 에 기록하지 못했습니다."
        fi
    done
}

start_cli_login() {
    local cli="$1"
    case "$cli" in
        claude)
            head_ "4. Claude 로그인"
            say "브라우저 로그인 창을 엽니다. Claude 계정으로 로그인한 뒤 이 창으로 돌아오세요."
            log "Claude 로그인 시작"
            claude auth login
            ;;
        codex)
            head_ "4. Codex 로그인"
            say "브라우저 로그인 창을 엽니다. ChatGPT 계정으로 로그인한 뒤 이 창으로 돌아오세요."
            log "Codex 로그인 시작"
            codex login --device-auth
            ;;
    esac
}

install_node_local() {
    # Homebrew가 없는 깨끗한 Mac도 Codex를 고를 수 있어야 한다. nodejs.org의
    # 최신 LTS 아카이브를 검증해 앱 지원 폴더에 푼다(관리자 암호 불필요).
    local arch node_arch tmp index version archive expected got
    arch="$(uname -m)"
    case "$arch" in
        arm64)  node_arch="arm64" ;;
        x86_64) node_arch="x64" ;;
        *) return 1 ;;
    esac
    tmp="$(mktemp -d -t mybookshelf-node)" || return 1
    index="$tmp/index.json"
    if ! curl -fsSL https://nodejs.org/dist/index.json -o "$index"; then
        rm -rf "$tmp"; return 1
    fi
    version="$($PY - "$index" "$node_arch" <<'PYEOF'
import json, sys
rows = json.load(open(sys.argv[1], encoding="utf-8"))
kind = f"osx-{sys.argv[2]}-tar"
print(next((r["version"] for r in rows if r.get("lts") and kind in r.get("files", [])), ""))
PYEOF
)"
    [ -n "$version" ] || { rm -rf "$tmp"; return 1; }
    archive="node-${version}-darwin-${node_arch}.tar.xz"
    curl -fsSL "https://nodejs.org/dist/${version}/${archive}" -o "$tmp/$archive" \
        && curl -fsSL "https://nodejs.org/dist/${version}/SHASUMS256.txt" -o "$tmp/SHASUMS256.txt" \
        || { rm -rf "$tmp"; return 1; }
    expected="$(awk -v f="$archive" '$2 == f {print $1; exit}' "$tmp/SHASUMS256.txt")"
    got="$(shasum -a 256 "$tmp/$archive" | awk '{print $1}')"
    [ -n "$expected" ] && [ "$got" = "$expected" ] \
        || { warn "Node.js 체크섬이 맞지 않아 설치하지 않습니다."; rm -rf "$tmp"; return 1; }
    rm -rf "$SUPPORT/node"
    mkdir -p "$SUPPORT/node"
    tar -xJf "$tmp/$archive" -C "$SUPPORT/node" --strip-components 1 \
        || { rm -rf "$tmp"; return 1; }
    rm -rf "$tmp"
    export PATH="$SUPPORT/node/bin:$HOME/.local/bin:$PATH"
    have node
}

install_obsidian_local() {
    # 공식 릴리스의 최신 DMG를 사용자 Applications에 넣는다. Homebrew와 sudo가
    # 모두 없어도 되며, curl로 받은 파일이라 브라우저 격리 속성도 붙지 않는다.
    local tmp release url app copied
    tmp="$(mktemp -d -t mybookshelf-obsidian)" || return 1
    release="$tmp/release.json"
    if ! curl -fsSL -H "User-Agent: mybookshelf-installer" \
        "https://api.github.com/repos/obsidianmd/obsidian-releases/releases?per_page=30" -o "$release"; then
        rm -rf "$tmp"; return 1
    fi
    url="$($PY - "$release" <<'PYEOF'
import json, sys
releases = json.load(open(sys.argv[1], encoding="utf-8"))
releases = releases if isinstance(releases, list) else [releases]
pick = None
for release in releases:  # 모바일 최신판에는 DMG가 없으므로 첫 데스크톱 릴리스를 찾는다.
    dmgs = [a for a in release.get("assets", [])
            if a.get("name", "").lower().endswith(".dmg")]
    if dmgs:
        pick = next((a for a in dmgs if "universal" in a.get("name", "").lower()), dmgs[0])
        break
print(pick.get("browser_download_url", "") if pick else "")
PYEOF
)"
    [ -n "$url" ] && curl -fsSL "$url" -o "$tmp/Obsidian.dmg" \
        || { rm -rf "$tmp"; return 1; }
    mkdir -p "$tmp/mnt"
    hdiutil attach "$tmp/Obsidian.dmg" -nobrowse -readonly -mountpoint "$tmp/mnt" >>"$LOG" 2>&1 \
        || { rm -rf "$tmp"; return 1; }
    app="$(find "$tmp/mnt" -maxdepth 2 -name Obsidian.app -print -quit)"
    mkdir -p "$HOME/Applications"
    if [ -n "$app" ] && ditto "$app" "$HOME/Applications/Obsidian.app"; then
        copied=0
    else
        copied=1
    fi
    hdiutil detach "$tmp/mnt" -quiet >/dev/null 2>&1 || true
    rm -rf "$tmp"
    return "$copied"
}

PY="$VENV/bin/python"
[ -x "$PY" ] || PY="$(command -v python3 || true)"

clear 2>/dev/null
echo "${C_B}My Bookshelf — 추가 설정${C_0}"
echo "${C_D}앱과 파이썬 환경은 이미 설치됐습니다. 두 가지만 고르시면 됩니다.${C_0}"
echo "${C_D}번호를 입력한 뒤 Return(Enter)을 누르세요. 그냥 Enter면 나중에 설정합니다.${C_0}"

# ── 1. AI 연결 ───────────────────────────────────────────────
head_ "1. AI 연결"
CLAUDE_SIZE="$SZ_CLAUDE"; have claude && CLAUDE_SIZE="이미 설치됨 · 추가 0 MB"
CODEX_SIZE="$SZ_CODEX"; have codex && CODEX_SIZE="이미 설치됨 · 추가 0 MB"
BOTH_SIZE="$SZ_BOTH"
if have claude && have codex; then
    BOTH_SIZE="모두 설치됨 · 추가 0 MB"
elif have claude; then
    BOTH_SIZE="$SZ_CODEX 추가"
elif have codex; then
    BOTH_SIZE="$SZ_CLAUDE 추가"
fi
echo "  요약·번역에 쓸 AI 를 고릅니다. 구독이 있으면 추가 요금 없이 씁니다."
echo
echo "    ${C_B}1${C_0}) Claude Code CLI   ${C_D}${CLAUDE_SIZE}${C_0}   Claude Pro/Max 구독"
echo "    ${C_B}2${C_0}) Codex CLI         ${C_D}${CODEX_SIZE}${C_0}   ChatGPT Plus/Pro 구독"
echo "    ${C_B}3${C_0}) 둘 다 설치        ${C_D}${BOTH_SIZE}${C_0}   기본 작업 AI는 Codex"
echo "    ${C_B}4${C_0}) 나중에            ${C_D}0 MB${C_0}            앱에서 API 키를 직접 넣습니다"
echo
while true; do
    read -r -p "  선택 [1-4, 기본 4] (번호 후 Enter): " pick
    case "${pick:-4}" in
        1) AI="claude"; break ;;
        2) AI="codex"; break ;;
        3) AI="both"; break ;;
        4) AI="none"; break ;;
        *) warn "1, 2, 3, 4 중 하나를 입력한 뒤 Enter를 누르세요." ;;
    esac
done

if { [ "$AI" = "claude" ] || [ "$AI" = "both" ]; } && ! have claude; then
    say "Claude Code CLI 를 설치합니다…"
    curl -fsSL https://claude.ai/install.sh 2>>"$LOG" | bash >>"$LOG" 2>&1 \
        || { warn "공식 설치 실패 — npm 으로 시도합니다."
             have npm && npm install -g @anthropic-ai/claude-code --prefix "$HOME/.local" >>"$LOG" 2>&1; }
    export PATH="$HOME/.local/bin:$PATH"
fi
if { [ "$AI" = "codex" ] || [ "$AI" = "both" ]; } && ! have codex; then
    if ! have node; then
        if have brew; then
            say "Codex 에 필요한 Node.js 를 설치합니다…"
            brew install node >>"$LOG" 2>&1 \
                || { warn "Homebrew 설치 실패 — 사용자 폴더에 다시 시도합니다."
                     install_node_local >>"$LOG" 2>&1; }
        else
            say "Codex 에 필요한 Node.js LTS 를 설치합니다…"
            install_node_local >>"$LOG" 2>&1 \
                || warn "Node.js 자동 설치에 실패했습니다 — https://nodejs.org 에서 LTS를 설치하세요."
        fi
    fi
    if have npm; then
        say "Codex CLI 를 설치합니다…"
        mkdir -p "$HOME/.local"
        npm install -g @openai/codex --prefix "$HOME/.local" >>"$LOG" 2>&1 \
            || warn "Codex CLI 설치에 실패했습니다. 설치 기록을 확인하세요: $LOG"
        export PATH="$HOME/.local/bin:$PATH"
    else
        warn "npm을 찾지 못해 Codex CLI를 설치하지 못했습니다."
    fi
fi

CLAUDE_OK=0; CODEX_OK=0
have claude && CLAUDE_OK=1
have codex && CODEX_OK=1
if [ "$AI" = "claude" ]; then
    [ "$CLAUDE_OK" = "1" ] && say "claude 준비 완료." || { warn "claude 를 찾지 못했습니다."; AI="none"; }
elif [ "$AI" = "codex" ]; then
    [ "$CODEX_OK" = "1" ] && say "codex 준비 완료." || { warn "codex 를 찾지 못했습니다."; AI="none"; }
elif [ "$AI" = "both" ]; then
    [ "$CLAUDE_OK" = "1" ] && say "claude 준비 완료." || warn "claude 를 찾지 못했습니다."
    [ "$CODEX_OK" = "1" ] && say "codex 준비 완료." || warn "codex 를 찾지 못했습니다."
    if [ "$CLAUDE_OK" = "0" ] && [ "$CODEX_OK" = "0" ]; then
        AI="none"
    elif [ "$CLAUDE_OK" = "0" ]; then
        AI="codex"
    elif [ "$CODEX_OK" = "0" ]; then
        AI="claude"
    fi
fi

if [ "$CLAUDE_OK" = "1" ] || [ "$CODEX_OK" = "1" ]; then
    register_cli_path
fi

# ── 2. 옵시디언 ──────────────────────────────────────────────
head_ "2. 옵시디언"
OBS=0
if [ -d "/Applications/Obsidian.app" ] || [ -d "$HOME/Applications/Obsidian.app" ]; then
    say "이미 설치돼 있습니다."; OBS=1
else
    echo "  요약 노트를 옵시디언 보관함에 위키로 쌓을 수 있습니다."
    echo "  ${C_D}설치하지 않으면 요약을 Word(.docx) 로 받습니다. 나중에 바꿀 수 있습니다.${C_0}"
    echo
    read -r -p "  옵시디언을 설치할까요? ${SZ_OBSIDIAN} [y/N]: " yn
    if [[ "${yn:-n}" =~ ^[Yy] ]]; then
        if have brew; then
            say "설치 중…"
            brew install --cask obsidian >>"$LOG" 2>&1 && OBS=1 \
                || { warn "Homebrew 설치 실패 — 공식 DMG로 다시 시도합니다."
                     if install_obsidian_local >>"$LOG" 2>&1; then OBS=1
                     else warn "설치 실패 — https://obsidian.md/download 에서 직접 받으세요."
                     fi; }
        else
            say "공식 최신 DMG를 받아 설치합니다…"
            install_obsidian_local >>"$LOG" 2>&1 && OBS=1 \
                || warn "설치 실패 — https://obsidian.md/download 에서 직접 받으세요."
        fi
    else
        say "건너뜁니다."
    fi
fi

# ── 3. 고른 대로 설정에 기록 ─────────────────────────────────
head_ "3. 설정 기록"
if [ -x "$PY" ]; then
    mkdir -p "$CONFIG_DIR"
    "$PY" - "$CONFIG_DIR" "$AI" "$OBS" <<'PYEOF'
import json, os, sys
cfg_dir, ai, obs = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
keys_file = os.path.join(cfg_dir, "keys.json")
keys = {}
if os.path.exists(keys_file):
    try:
        keys = json.load(open(keys_file, encoding="utf-8"))
    except ValueError:
        keys = {}
# 고른 것만 건드린다 — 이미 맞춰 둔 다른 설정을 덮지 않는다.
keys["pref_use_claude_cli"] = ai in ("claude", "both")
keys["pref_use_codex_cli"] = ai in ("codex", "both")
if ai != "none":
    # 둘 다 고른 경우 무인 설치의 기본값과 같은 Codex를 기본 작업 AI로 둔다.
    prov = "claude_cli" if ai == "claude" else "codex_cli"
    keys["wiki_provider"] = prov
    keys["wiki_model"] = "default"
    keys["pref_translate_engine"] = f"{prov}:default"
keys["pref_use_obsidian"] = obs
keys.setdefault("pref_use_epub", True)
if not obs:
    keys.setdefault("pref_use_docx", True)     # 옵시디언을 안 쓰면 Word 로 받는다
with open(keys_file, "w", encoding="utf-8") as f:
    json.dump(keys, f, ensure_ascii=False, indent=2)
os.chmod(keys_file, 0o600)
PYEOF
    OUT="EPUB + Word"; [ "$OBS" = "1" ] && OUT="EPUB + 옵시디언 위키"
    AI_LABEL="$AI"; [ "$AI" = "both" ] && AI_LABEL="Claude + Codex"
    [ "$AI" = "none" ] && AI_LABEL="나중에 설정"
    say "AI: ${AI_LABEL} · 출력: ${OUT}"
else
    warn "설정을 기록하지 못했습니다 — 앱 ⚙️ 설정 탭에서 직접 골라 주세요."
fi

# ── 4. 마무리 ────────────────────────────────────────────────
# 선택한 CLI의 로그인 창을 설치 흐름 안에서 바로 연다. 각각 끝나거나 취소하면
# 다음 CLI가 이어서 열린다. 이미 로그인한 CLI는 자체적으로 상태만 알려 준다.
if [ "$AI" = "both" ]; then
    [ "$CLAUDE_OK" = "1" ] && start_cli_login claude
    [ "$CODEX_OK" = "1" ] && start_cli_login codex
elif [ "$AI" = "claude" ] && [ "$CLAUDE_OK" = "1" ]; then
    start_cli_login claude
elif [ "$AI" = "codex" ] && [ "$CODEX_OK" = "1" ]; then
    start_cli_login codex
fi

head_ "끝났습니다"
say "실행: Launchpad 의 «My Bookshelf»"
if [ "$AI" = "both" ]; then
    echo
    echo "${C_Y}  Claude와 Codex 로그인 창을 순서대로 열었습니다.${C_0}"
    echo "  ${C_D}앱을 켜면 두 CLI 토글이 모두 켜져 있고 기본 AI는 Codex입니다.${C_0}"
elif [ "$AI" = "claude" ] || [ "$AI" = "codex" ]; then
    CLI="$AI"
    echo
    echo "${C_Y}  ${CLI} 로그인 창을 열었습니다.${C_0}"
    echo "  ${C_D}앱을 켜면 설정 탭 토글이 이미 켜져 있습니다.${C_0}"
elif [ "$AI" = "none" ]; then
    echo
    echo "  앱 ${C_B}⚙️ 설정${C_0} 탭에서 AI API 키를 넣으시면 됩니다."
fi
log "완료 (ai=$AI obsidian=$OBS)"
echo
read -r -p "  Enter 를 누르면 설정을 끝냅니다. " _ || true
exit 0
