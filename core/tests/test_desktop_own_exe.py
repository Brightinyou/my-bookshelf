"""venv 안의 MyBookshelf.exe 복사본이 번들 runtime 의 DLL 을 쓰는지.

2026-09-30 실측: 복사본 옆에 python314.dll 이 없어서 PATH 의
C:\\Python314\\python314.dll 을 잡았고, base_prefix 가 번들 runtime 이 아닌
C:\\Python314 가 되어 «No module named 'webview'» 로 창이 안 떴다.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
from pathlib import Path
from unittest.mock import patch
import os
import sys
import tempfile
import unittest

import desktop


@unittest.skipUnless(sys.platform == "win32", "Windows 전용")
class PrepareOwnExeTest(unittest.TestCase):
    def test_interpreter_dlls_are_copied_next_to_own_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "runtime"
            scripts = Path(tmp) / ".venv" / "Scripts"
            runtime.mkdir()
            scripts.mkdir(parents=True)
            (runtime / "pythonw.exe").write_bytes(b"MZ interpreter")
            (runtime / "python314.dll").write_bytes(b"dll314")
            (runtime / "python3.dll").write_bytes(b"dll3")
            venv_exe = scripts / "pythonw.exe"
            venv_exe.write_bytes(b"MZ stub")

            with patch.object(sys, "_base_executable", str(runtime / "pythonw.exe"), create=True), \
                 patch.object(desktop, "_stamp_icon", return_value=True):
                target = desktop.prepare_own_exe(venv_exe)

            self.assertEqual(target, scripts / desktop.OWN_EXE_NAME)
            self.assertEqual((scripts / "python314.dll").read_bytes(), b"dll314")
            self.assertEqual((scripts / "python3.dll").read_bytes(), b"dll3")

    def test_changed_dll_is_recopied_even_if_exe_stamp_matches(self):
        """표식(.exe.src)이 그대로여도 원본 DLL 이 바뀌면 다시 옮긴다."""
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "runtime"
            scripts = Path(tmp) / ".venv" / "Scripts"
            runtime.mkdir()
            scripts.mkdir(parents=True)
            (runtime / "pythonw.exe").write_bytes(b"MZ interpreter")
            dll = runtime / "python314.dll"
            dll.write_bytes(b"old")
            venv_exe = scripts / "pythonw.exe"
            venv_exe.write_bytes(b"MZ stub")

            with patch.object(sys, "_base_executable", str(runtime / "pythonw.exe"), create=True), \
                 patch.object(desktop, "_stamp_icon", return_value=True):
                desktop.prepare_own_exe(venv_exe)
                stamp = (scripts / desktop.OWN_EXE_NAME).with_suffix(".exe.src").read_text(encoding="utf-8")
                dll.write_bytes(b"new")           # 같은 크기, 다른 내용·시각
                os.utime(dll, (dll.stat().st_atime, dll.stat().st_mtime + 10))
                desktop.prepare_own_exe(venv_exe)

            self.assertEqual((scripts / desktop.OWN_EXE_NAME).with_suffix(".exe.src")
                             .read_text(encoding="utf-8"), stamp)
            self.assertEqual((scripts / "python314.dll").read_bytes(), b"new")


if __name__ == "__main__":
    unittest.main()
