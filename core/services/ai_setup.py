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
            subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(script)],
                cwd=str(script.parent),
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
        else:
            subprocess.Popen(["/usr/bin/open", "-a", "Terminal", str(script)])
    except OSError as e:
        return False, str(e)
    return True, ""
