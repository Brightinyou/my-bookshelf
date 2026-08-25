import ctypes
import os
import subprocess
import sys
from pathlib import Path


APP_NAME = "My Bookshelf"


def _app_dir_from_exe() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _installed_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / APP_NAME


def _install_log(base: Path) -> Path:
    return base / "install.log"


def _candidate_dirs() -> list[Path]:
    here = _app_dir_from_exe()
    candidates = [here]
    installed = _installed_dir()
    if installed != here:
        candidates.append(installed)
    return candidates


def _find_app() -> tuple[Path, Path, Path] | None:
    for base in _candidate_dirs():
        pythonw = base / ".venv" / "Scripts" / "pythonw.exe"
        script = base / "core" / "desktop.py"
        if pythonw.exists() and script.exists():
            return base, pythonw, script
    return None


def _message(text: str) -> None:
    ctypes.windll.user32.MessageBoxW(0, text, APP_NAME, 0x10)


def main() -> int:
    found = _find_app()
    if not found:
        install_dir = _installed_dir()
        log_path = _install_log(install_dir)
        detail = ""
        if log_path.exists():
            detail = f"\n\nCheck this file for the exact error:\n{log_path}"
        _message(
            "My Bookshelf is not ready yet.\n\n"
            "Run setup.bat in the installed folder first."
            f"{detail}"
        )
        return 1

    app_dir, pythonw, script = found
    # PyInstaller onefile bootloader leaves _MEIPASS(2)/temp-extraction PATH
    # entries in this process's env; don't let the long-lived child (desktop.py)
    # inherit them, since it later spawns its own children (e.g. the update
    # helper) that can relaunch MyBookshelf.exe - inheriting a stale reference
    # makes that fresh instance try to reuse an already-deleted temp folder and
    # fail with "Failed to load Python DLL" (2026-07-25).
    env = dict(os.environ)
    env.pop("_MEIPASS2", None)
    env.pop("_MEIPASS", None)
    subprocess.Popen(
        [str(pythonw), str(script)],
        cwd=str(app_dir),
        creationflags=subprocess.CREATE_NO_WINDOW,
        env=env,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
