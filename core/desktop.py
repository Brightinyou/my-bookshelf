#!/usr/bin/env python3
"""My Bookshelf Windows desktop launcher."""
from __future__ import annotations

import os
import shutil
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


# 작업표시줄에서 «Python»으로 묶이던 것을 고친다 (2026-08-27 연구자 지적 — 재발).
# 창 아이콘(WM_SETICON)과 AppUserModelID를 붙여도 소용이 없었던 까닭은 프로세스
# 자체가 pythonw.exe 였기 때문이다. Windows는 작업표시줄 항목을 **실행 파일**로
# 묶으므로, 다른 파이썬 앱과 한 덩어리가 되고 아이콘도 파이썬 것을 따라간다.
# 그래서 venv 안의 pythonw.exe 를 «MyBookshelf.exe» 라는 이름으로 복사해 두고,
# 그 이름으로 자기 자신을 다시 띄운다. 복사본도 같은 폴더의 pyvenv.cfg 를 보므로
# 인터프리터 동작은 완전히 같다.
OWN_EXE_NAME = "MyBookshelf.exe"


def _relaunch_under_own_name() -> bool:
    """pythonw.exe로 떠 있으면 MyBookshelf.exe라는 이름으로 자신을 다시 띄운다.

    Returns: 다시 띄웠으면 True (그러면 이 프로세스는 조용히 끝나야 한다).
    """
    if sys.platform != "win32":
        return False
    if os.environ.get("MYBOOKSHELF_NO_RELAUNCH"):
        return False                            # 콘솔에서 오류를 보며 고칠 때
    exe = Path(sys.executable)
    if exe.name.lower() == OWN_EXE_NAME.lower():
        return False                            # 이미 우리 이름으로 돌고 있다
    if exe.stem.lower() not in ("python", "pythonw"):
        return False                            # 얼린 실행 파일 등 — 건드리지 않는다
    # ★venv의 pythonw.exe 를 복사하면 안 된다 (2026-08-27 실측). 그것은 **중계
    #   stub**(251KB)이라 기본 인터프리터(C:\PythonXX\pythonw.exe, 105KB)를 자식
    #   프로세스로 다시 띄운다. 그래서 stub 이름만 바꿔 봐야 정작 창을 든
    #   프로세스는 여전히 pythonw.exe 였고 작업표시줄은 그대로 «Python» 이었다.
    #   **기본 인터프리터**를 Scripts\ 안에 복사해야 한다. 그 자리에 두면 한 단계
    #   위의 pyvenv.cfg 를 읽어 venv 가 그대로 살아난다(venv 의 원래 구조다).
    _base = Path(getattr(sys, "_base_executable", None) or sys.executable)
    _want = _base.with_name(exe.name)           # python ↔ pythonw 짝을 맞춘다
    if _want.exists():
        _base = _want
    if not _base.exists() or _base.samefile(exe):
        return False                            # 기본 인터프리터를 못 찾았다
    target = exe.with_name(OWN_EXE_NAME)
    try:
        # 파이썬을 판올림하면 인터프리터도 바뀌므로 다르면 다시 복사한다.
        # 크기까지 견주는 까닭은 예전 판이 stub 을 복사해 둔 적이 있기 때문이다.
        if (not target.exists()
                or target.stat().st_size != _base.stat().st_size
                or target.stat().st_mtime < _base.stat().st_mtime):
            shutil.copy2(_base, target)
    except OSError:
        return False                            # 못 만들면 그냥 예전처럼 뜬다
    try:
        # ★os.execv 를 쓰면 안 된다 (2026-08-27 실측). Windows의 execv 는 argv 를
        #   그대로 이어 붙여 명령줄을 만들 뿐 인용을 하지 않아서, 설치 경로
        #   «...\My Bookshelf\...» 의 공백에서 잘렸다. 실제 오류:
        #     can't open file '...\My Bookshelf\Bookshelf\.venv\...'
        #   Popen 은 목록을 받아 인용까지 해 주므로 공백이 있어도 안전하다.
        subprocess.Popen([str(target), str(Path(__file__).resolve()), *sys.argv[1:]],
                         cwd=str(APP_ROOT))
    except OSError:
        return False                            # 못 띄우면 하던 대로 계속한다
    return True


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
                 # ★Name 조건이 반드시 있어야 한다 (2026-08-27 실측). 이 필터를
                 #   실행하는 powershell 자신의 **명령줄에 그 패턴이 그대로 들어
                 #   있어서**, 진짜 서버를 죽이기 전에 자기를 먼저 죽이고 끝났다.
                 #   그래서 «옛 서버를 정리한다»는 말과 달리 서버가 쌓여 갔다.
                 "Get-CimInstance Win32_Process | Where-Object { "
                 "$_.Name -in @('python.exe','pythonw.exe','MyBookshelf.exe') -and "
                 "$_.CommandLine -like '*streamlit*pipeline_app.py*' } | "
                 "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                capture_output=True,
                creationflags=0x08000000,
            )
        else:
            subprocess.run(["pkill", "-f", "streamlit run.*pipeline_app.py"],
                           capture_output=True)
    except Exception:
        pass


def _kill_stale_windows() -> None:
    """이전 실행에서 남은 **앱 창**(desktop.py)을 닫는다. 자기 자신은 뺀다.

    ★2026-08-27. 서버만 죽이고 창을 남겨 둔 것이 «화면이 깜빡이고 체크박스가
    안 보인다»의 원인이었다. 흐름은 이랬다.

      1. 앱이 이미 떠 있다(창 A + 서버 A).
      2. 앱을 다시 연다 → _kill_stale_servers()가 **서버 A를 죽인다**.
      3. **창 A는 그대로 남는다.** 붙어 있던 웹소켓이 끊겼으니 Streamlit 화면이
         끝없이 재접속을 시도하며 다시 그린다 → 깜빡임. 그 사이 위젯은 세션이
         없어 안 그려지고, 목록도 비어 보인다.
      4. 새 서버 B가 같은 포트를 잡으면 창 A가 거기 붙는데, 세션이 달라
         체크 상태가 사라지고 다시 그려진다.

    실측(2026-08-27): 창 6개 · 서버 2개가 동시에 떠 있었다. 창을 함께 정리하지
    않으면 앱을 열 때마다 창이 하나씩 쌓인다.
    """
    # ★자기 자신뿐 아니라 **부모까지** 빼야 한다 (2026-08-27 실측).
    #   venv의 python.exe/pythonw.exe 는 껍데기(stub) 프로세스가 먼저 뜨고 그 밑에
    #   **명령줄이 완전히 같은** 실제 인터프리터가 자식으로 붙는다. 그래서 자기
    #   PID만 빼면 껍데기 부모가 목록에 남고, 그것을 죽이는 순간 자식인 나까지
    #   함께 죽었다. 증상은 «앱이 아무 소리 없이 안 뜬다»였고 오류 기록도 없었다.
    _skip = {os.getpid()}
    try:
        _skip.add(os.getppid())
    except (OSError, AttributeError):
        pass
    _self_list = ",".join(str(_p) for _p in sorted(_skip))
    try:
        if sys.platform == "win32":
            # 이 앱 venv 폴더에서 뜬 desktop.py만 고른다 — 이름만 같은 남의
            # 스크립트를 죽이지 않도록. 실행 파일 이름이 아니라 **폴더**로 맞추는
            # 까닭은 pythonw.exe로 뜬 옛 창과 MyBookshelf.exe로 뜬 새 창을 함께
            # 잡아야 하기 때문이다 (2026-08-27).
            _exe = str(Path(sys.executable).parent).replace("'", "''")
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process | Where-Object { "
                 "$_.Name -in @('python.exe','pythonw.exe','MyBookshelf.exe') -and "
                 f"$_.CommandLine -like '*desktop.py*' -and $_.CommandLine -like '*{_exe}*' "
                 f"-and $_.ProcessId -notin @({_self_list}) "
                 "} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                capture_output=True,
                creationflags=0x08000000,
            )
        else:
            _out = subprocess.run(["ps", "-eo", "pid=,command="],
                                  capture_output=True, text=True).stdout
            for _line in _out.splitlines():
                _line = _line.strip()
                if not _line:
                    continue
                _pid, _, _cmd = _line.partition(" ")
                if "desktop.py" not in _cmd or str(Path(sys.executable).parent) not in _cmd:
                    continue
                try:
                    if int(_pid) not in _skip:
                        os.kill(int(_pid), 9)
                except (ValueError, ProcessLookupError, PermissionError):
                    pass
    except Exception:
        pass


def _kill_stale_servers() -> None:
    """이전 실행에서 남은 My Bookshelf 서버(streamlit pipeline_app.py)를 종료한다.

    앱을 강제 종료하거나 다시 열 때 옛 스트림릿이 포트를 잡은 채 붙어 있어
    창이 옛 서버에 연결되거나 좀비 프로세스가 쌓이던 문제를 근본 차단한다.
    실행 시 항상 이전 서버를 정리하고 최신 정본으로 새로 띄운다 (단일 실행, 2026-07-24).
    ★창도 함께 닫는다 — 서버만 죽이면 남은 창이 깜빡인다 (2026-08-27).
    """
    _kill_stale_windows()
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
        # ★127.0.0.1 로 묶는다 (2026-08-27). 기본값은 0.0.0.0 이라 서버가 랜 전체에
        #   열렸고, 그래서 «공용 및 프라이빗 네트워크에서 이 앱에 액세스하도록
        #   허용하시겠습니까?» 방화벽 창이 떴다. 창이 붙는 곳은 127.0.0.1 뿐이니
        #   밖으로 열 까닭이 없다 — 방화벽 창도 함께 사라지고 더 안전하다.
        "--server.address",
        "127.0.0.1",
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
    # ★맨 처음에 한다 — 창을 만든 뒤에 이름을 바꿔 봐야 작업표시줄은 이미
    #   pythonw.exe로 묶은 뒤다. 성공하면 이 프로세스는 여기서 끝난다.
    if _relaunch_under_own_name():
        return 0

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
    # ★작업표시줄에 파이썬 아이콘이 뜨던 것을 고친다 (2026-08-26 연구자 지적).
    # 창 아이콘(WM_SETICON)은 아래에서 제대로 붙이고 있어 **제목 표시줄**에는 올바른
    # 아이콘이 나왔다. 그런데 작업표시줄은 창이 아니라 **프로세스의 신원**
    # (AppUserModelID)으로 묶는데, 그 값이 없으면 호스트인 pythonw.exe 를 따라간다.
    # 그래서 작업표시줄에만 파이썬 아이콘이 떴다. 창을 만들기 **전에** 신원을 밝힌다.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Brightinyou.MyBookshelf")
        except Exception:
            pass                      # 못 해도 앱은 그대로 뜬다 — 아이콘만 아쉬울 뿐

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
            from ctypes import wintypes

            # ctypes의 기본 restype/argtypes는 c_int(32비트)라서 64비트 HWND/HICON
            # 포인터가 잘려 WM_SETICON에 쓰레기 값이 전달되던 문제 수정 (2026-07-23).
            user32 = ctypes.windll.user32
            user32.FindWindowW.restype = wintypes.HWND
            user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
            user32.LoadImageW.restype = wintypes.HICON
            user32.LoadImageW.argtypes = [
                wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                ctypes.c_int, ctypes.c_int, wintypes.UINT,
            ]
            user32.SendMessageW.restype = ctypes.c_void_p
            user32.SendMessageW.argtypes = [
                wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
            ]

            LR_LOADFROMFILE, LR_DEFAULTSIZE = 0x10, 0x40
            WM_SETICON = 0x0080
            ICON_SMALL, ICON_BIG = 0, 1

            hwnd = None
            for _ in range(20):  # pywebview가 창 제목을 늦게 붙이는 경우 대비 재시도
                hwnd = user32.FindWindowW(None, APP_TITLE)
                if hwnd:
                    break
                time.sleep(0.25)
            if not hwnd:
                return
            h_big = user32.LoadImageW(None, icon, 1, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
            h_small = user32.LoadImageW(None, icon, 1, 16, 16, LR_LOADFROMFILE)
            if h_big:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_big)
            if h_small:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_small)
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
