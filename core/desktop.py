#!/usr/bin/env python3
"""My Bookshelf Windows desktop launcher."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path

APP_TITLE = "My Bookshelf"
DEFAULT_PORT = 8501
HERE = Path(__file__).resolve().parent
APP_SCRIPT = HERE / "pipeline_app.py"
APP_ROOT = HERE.parent
LAUNCH_LOG = APP_ROOT / "launch-error.log"


def _find_app_icon() -> str:
    for base in (HERE, HERE.parent, HERE.parent / "platform" / "windows"):
        p = base / "MyBookshelf.ico"
        if p.exists():
            return str(p)
    return str(HERE.parent / "MyBookshelf.ico")


APP_ICON = _find_app_icon()


def _write_launch_log(message: str, details: str = "") -> None:
    try:
        body = message.strip()
        if details.strip():
            body = f"{body}\n\n{details.strip()}\n"
        LAUNCH_LOG.write_text(body + "\n", encoding="utf-8")
    except Exception:
        pass


def _show_error(message: str) -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, APP_TITLE, 0x10)
            return
        except Exception:
            pass
    sys.stderr.write(message + "\n")


def _fail(message: str, details: str = "") -> int:
    log_hint = f"\n\nCheck this file for details:\n{LAUNCH_LOG}"
    _write_launch_log(message, details)
    _show_error(message + log_hint)
    return 1


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _kill_all_streamlit_procs() -> None:
    """실행 중인 My Bookshelf 서버(streamlit pipeline_app.py)를 전부 종료한다.

    streamlit이 내부적으로 watcher 등 자식 프로세스를 추가로 띄우는 경우가 있어,
    Popen 핸들 하나만 terminate()해서는 프로세스가 완전히 안 죽고 포트에 남을 수 있다.
    커맨드라인 패턴으로 전부 찾아 강제 종료해야 확실하다.
    """
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process | "
                 "Where-Object { $_.CommandLine -like '*streamlit*pipeline_app.py*' } | "
                 "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                capture_output=True,
                creationflags=0x08000000,
            )
        else:
            subprocess.run(["pkill", "-f", "streamlit run.*pipeline_app.py"],
                           capture_output=True)
    except Exception:
        pass


def _kill_stale_servers() -> None:
    """이전 실행에서 남은 My Bookshelf 서버(streamlit pipeline_app.py)를 종료한다.

    앱을 강제 종료하거나 다시 열 때 옛 스트림릿이 포트를 잡은 채 붙어 있어
    창이 옛 서버에 연결되거나 좀비 프로세스가 쌓이던 문제를 근본 차단한다.
    실행 시 항상 이전 서버를 정리하고 최신 정본으로 새로 띄운다 (단일 실행, 2026-07-24).
    """
    _kill_all_streamlit_procs()
    # 포트(8501)가 풀릴 때까지 최대 ~6초 대기 — 새 서버가 같은 포트를 잡도록
    for _ in range(20):
        if not _port_in_use(DEFAULT_PORT):
            break
        time.sleep(0.3)


def _find_free_port(start: int = DEFAULT_PORT) -> int:
    for p in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise RuntimeError("No free local port available for My Bookshelf.")


def _server_ready(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


def _start_streamlit(port: int) -> subprocess.Popen | None:
    if _port_in_use(port) and _server_ready(port):
        return None
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(APP_SCRIPT),
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
        "--global.developmentMode",
        "false",
        # 개발자 툴바 숨김 → 'Clear caches' 등 개발 단축키·메뉴 제거 (2026-07-10)
        "--client.toolbarMode",
        "minimal",
        # 항상 라이트(흰 배경·검은 글씨) + 무채색(B&W) 강조색
        "--theme.base",
        "light",
        "--theme.primaryColor",
        "#111827",
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(HERE.parent),
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )


def main() -> int:
    try:
        if LAUNCH_LOG.exists():
            LAUNCH_LOG.unlink()
    except Exception:
        pass

    try:
        import webview
    except ImportError:
        return _fail(
            "pywebview is not installed.",
            "Run setup.bat again or reinstall My Bookshelf.",
        )

    # 이전 실행에서 남은 서버를 먼저 정리한다 (좀비 방지·항상 최신 로드, 2026-07-24)
    _kill_stale_servers()

    try:
        port = _find_free_port(DEFAULT_PORT)
    except RuntimeError as exc:
        return _fail(str(exc), "Close other running My Bookshelf windows and try again.")
    proc = _start_streamlit(port)

    url = f"http://127.0.0.1:{port}/"
    deadline = time.time() + 60
    while time.time() < deadline:
        if _server_ready(port):
            break
        time.sleep(0.4)
    else:
        if proc:
            proc.terminate()
        return _fail(
            "The app server did not start in time.",
            "Run setup.bat again or check whether security software blocked Python.",
        )

    # 창 크기를 화면 해상도에 맞춘다 — HD(1366×768)에서 세로 넘침 방지 (2026-07-09).
    # 화면의 ~92%를 넘지 않게, 기본 최대치(1280×1040)로 상한. 실패 시 HD 기준.
    try:
        _scr = webview.screens[0]
        _sw, _sh = int(_scr.width), int(_scr.height)
    except Exception:
        _sw, _sh = 1366, 768
    _win_w = max(900, min(1280, int(_sw * 0.92)))
    _win_h = max(640, min(1040, int(_sh * 0.92)))
    _min_w = min(900, _win_w)
    _min_h = min(720, _win_h)
    webview.create_window(
        APP_TITLE,
        url,
        width=_win_w,
        height=_win_h,
        min_size=(_min_w, _min_h),
        text_select=True,
    )
    icon = APP_ICON if os.path.exists(APP_ICON) else None

    def _apply_win32_icon() -> None:
        if sys.platform != "win32" or not icon:
            return
        try:
            import ctypes

            hwnd = ctypes.windll.user32.FindWindowW(None, APP_TITLE)
            if not hwnd:
                return
            hicon = ctypes.windll.user32.LoadImageW(None, icon, 1, 0, 0, 0x10 | 0x40)
            if hicon:
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon)
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon)
        except Exception:
            pass

    try:
        webview.start(icon=icon, func=_apply_win32_icon)
        return 0
    except Exception:
        return _fail(
            "The desktop window could not be created.",
            traceback.format_exc(),
        )
    finally:
        # 창 닫기(X) 시 서버를 확실히 종료한다. Popen 핸들 하나만 정리하면
        # streamlit이 띄운 자식 프로세스가 남을 수 있어, 커맨드라인 기준으로도
        # 한 번 더 정리한다 (기본 동작, 2026-07-25).
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        _kill_all_streamlit_procs()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(
            _fail("Unexpected startup error.", traceback.format_exc())
        )
