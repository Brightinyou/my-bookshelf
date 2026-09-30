"""AI 연결을 설치에서 떼어 앱 첫 화면으로 옮긴다 (2026-09-30).

설치 마지막에 «Claude·Codex 설정» 창을 띄우던 것을 없앴다 — 비개발자에게는 설치 도중
구독 로그인이 가장 큰 관문이었다. 대신 앱이 AI 없이 처음 뜨면 «AI 연결» 안내를 보이고,
구독(CLI)을 고른 사람에게만 그 설정 창을 연다. 설정 창 자체는 설치 때 쓰던 스크립트를
그대로 쓴다(설치·로그인·설정 저장이 이미 검증돼 있다).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# core/services/ai_setup.py 기준:
#   Windows 설치본  {app}\core\services → {app}\windows_setup_extras.ps1
#   맥 번들         Resources/services   → Resources/setup-extras.command
#   저장소(개발)    core/services        → dev/installer/…
_HERE = Path(__file__).resolve().parent.parent

# 발급 주소 — 링크 대신 글자로도 보이게 한다(웹뷰에서 링크가 안 열릴 수 있다).
API_KEY_PAGES = {
    "gemini": "https://aistudio.google.com/apikey",
    "openai": "https://platform.openai.com/api-keys",
    "anthropic": "https://console.anthropic.com/settings/keys",
}


# 직접 붙여 넣는 설치 명령 (2026-09-30 연구자 제안) — «설정 창 열기»가 실패할 때의
# 대비책. 설치 스크립트(windows_setup_extras.ps1·mac_setup_extras.sh)가 실제로 쓰는
# 명령과 같게 둔다. 맥은 npm 전역 설치가 /usr/local 권한에 막히므로 스크립트처럼
# ~/.local 로 넣고, 그 폴더가 PATH 에 없을 수 있어 로그인도 전체 경로로 부른다.
# 각 단계: (설명, 명령 또는 None)
def cli_install_steps(cli: str, platform: str | None = None) -> list[tuple[str, str | None]]:
    win = (platform or sys.platform) == "win32"
    if cli == "claude":
        if win:
            return [("설치", "irm https://claude.ai/install.ps1 | iex"),
                    # 공식 설치는 claude.exe 를 ~\.local\bin 에 두지만 PATH 에 넣지 않는다
                    # (2026-09-30 Sandbox 실측 — 새 창에서도 «'claude' is not recognized»).
                    # 맥처럼 전체 경로로 부른다.
                    ("로그인", '& "$env:USERPROFILE\\.local\\bin\\claude.exe" auth login')]
        return [("설치", "curl -fsSL https://claude.ai/install.sh | bash"),
                ("로그인", "~/.local/bin/claude auth login")]
    if cli == "codex":
        if win:
            return [("Node.js 설치 (이미 있으면 건너뛰기)",
                     "winget install -e --id OpenJS.NodeJS.LTS"),
                    ("winget 명령이 없다고 나오면 — 아래 주소에서 LTS 설치 파일(.msi)을 받아 실행",
                     "https://nodejs.org/"),
                    ("PowerShell 창을 닫고 새로 연 뒤 설치", "npm install -g @openai/codex"),
                    ("로그인", "codex login --device-auth")]
        return [("Node.js 설치 (이미 있으면 건너뛰기) — 아래 주소에서 LTS 설치 파일(.pkg)을 받아 실행",
                 "https://nodejs.org/"),
                ("설치", 'npm install -g @openai/codex --prefix "$HOME/.local"'),
                ("로그인", "~/.local/bin/codex login --device-auth")]
    return []


def setup_script() -> Path | None:
    if sys.platform == "win32":
        cands = [_HERE.parent / "windows_setup_extras.ps1",
                 _HERE.parent / "dev" / "installer" / "windows_setup_extras.ps1"]
    elif sys.platform == "darwin":
        cands = [_HERE / "setup-extras.command",
                 _HERE.parent / "dev" / "installer" / "mac_setup_extras.sh"]
    else:
        return None
    return next((p for p in cands if p.is_file()), None)


def launch_setup_window() -> tuple[bool, str]:
    """구독(CLI) 설정 창을 새 창으로 연다. (성공 여부, 실패 이유)."""
    script = setup_script()
    if script is None:
        return False, "설정 스크립트를 찾지 못했습니다."
    try:
        if sys.platform == "win32":
            # 앱에서 고른 언어로 설정 창을 띄운다 (2026-09-30 — 한국어 앱에 영어 메뉴가 떴다).
            from services.i18n import get_lang
            subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(script), "-Lang", get_lang()],
                cwd=str(script.parent),
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
        else:
            subprocess.Popen(["/usr/bin/open", "-a", "Terminal", str(script)])
    except OSError as e:
        return False, str(e)
    return True, ""
