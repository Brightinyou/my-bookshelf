"""WMI(Get-CimInstance)가 막힌 PC 에서도 앱을 끄고 정리한다 (2026-09-30).

Windows Sandbox 에서 Get-CimInstance Win32_Process 가 «액세스가 거부되었습니다»였다.
그러면 옛 서버·창 정리, «Stop My Bookshelf», 설치·업데이트 전 앱 끄기가 모두 조용히
실패했다. 명령줄은 WMI 로만 읽히지만 실행 파일 경로는 권한 없이 읽힌다.
"""
from pathlib import Path
from unittest import mock
import os
import sys
import unittest

import desktop

ROOT = Path(__file__).resolve().parents[2]
APP = Path(r"C:\Users\u\AppData\Local\My Bookshelf")
DIRS = [APP / ".venv" / "Scripts", APP / "runtime"]


class AppExeTest(unittest.TestCase):
    def test_picks_only_our_interpreters(self):
        self.assertTrue(desktop._is_app_exe(str(APP / ".venv" / "Scripts" / "MyBookshelf.exe"), DIRS))
        self.assertTrue(desktop._is_app_exe(str(APP / ".venv" / "Scripts" / "pythonw.exe"), DIRS))
        self.assertTrue(desktop._is_app_exe(str(APP / "runtime" / "python.exe"), DIRS))
        self.assertFalse(desktop._is_app_exe(r"C:\Python314\python.exe", DIRS))
        self.assertFalse(desktop._is_app_exe(str(APP / "runtime" / "Scripts" / "pip.exe"), DIRS))
        self.assertFalse(desktop._is_app_exe(str(APP / "poppler" / "pdftotext.exe"), DIRS))

    def test_case_insensitive_on_windows(self):
        if sys.platform != "win32":
            self.skipTest("Windows 경로 대소문자")
        self.assertTrue(desktop._is_app_exe(str(APP / ".VENV" / "scripts" / "MYBOOKSHELF.EXE"), DIRS))


class PathFallbackTest(unittest.TestCase):
    def test_kills_ours_except_self_and_parent(self):
        procs = {
            10: str(APP / ".venv" / "Scripts" / "MyBookshelf.exe"),   # 옛 창
            11: str(APP / "runtime" / "python.exe"),                   # 옛 서버(껍데기 밑)
            12: r"C:\Python314\python.exe",                           # 남의 파이썬
            20: str(APP / ".venv" / "Scripts" / "MyBookshelf.exe"),   # 나
            21: str(APP / ".venv" / "Scripts" / "pythonw.exe"),       # 내 부모(껍데기)
        }
        with mock.patch.object(desktop, "_process_image_paths", return_value=procs), \
             mock.patch.object(desktop.os, "kill") as kill:
            killed = desktop._kill_app_processes_by_path({20, 21}, DIRS)
        self.assertEqual(sorted(killed), [10, 11])
        self.assertEqual(sorted(c.args[0] for c in kill.call_args_list), [10, 11])

    def test_cleanup_falls_back_only_when_wmi_is_blocked(self):
        with mock.patch.object(desktop.sys, "platform", "win32"), \
             mock.patch.object(desktop, "_kill_app_processes_by_path") as by_path:
            with mock.patch.object(desktop, "_run_cim_kill", return_value=True):
                desktop._kill_all_streamlit_procs()
                desktop._kill_stale_windows()
            by_path.assert_not_called()
            with mock.patch.object(desktop, "_run_cim_kill", return_value=False):
                desktop._kill_all_streamlit_procs()
                desktop._kill_stale_windows()
            self.assertEqual(by_path.call_count, 2)
            for call in by_path.call_args_list:
                self.assertIn(os.getpid(), call.args[0])

    def test_blocked_wmi_is_reported_by_exit_code(self):
        with mock.patch.object(desktop.subprocess, "run",
                               return_value=mock.Mock(returncode=desktop._CIM_BLOCKED)) as run:
            self.assertFalse(desktop._run_cim_kill("$true"))
        cmd = run.call_args.args[0][-1]
        self.assertIn("-ErrorAction Stop", cmd)
        self.assertIn(f"exit {desktop._CIM_BLOCKED}", cmd)
        with mock.patch.object(desktop.subprocess, "run", return_value=mock.Mock(returncode=0)):
            self.assertTrue(desktop._run_cim_kill("$true"))

    @unittest.skipUnless(sys.platform == "win32", "Windows 전용")
    def test_real_process_paths_include_this_process(self):
        paths = desktop._process_image_paths()
        self.assertIn(os.getpid(), paths)
        self.assertTrue(paths[os.getpid()].lower().endswith(".exe"))


class ScriptsWithoutWmiTest(unittest.TestCase):
    def test_stop_app_uses_process_path_and_catches_own_exe(self):
        bat = (ROOT / "stop-app.bat").read_text(encoding="utf-8")
        cmd = next(l for l in bat.splitlines() if l.startswith("powershell"))
        self.assertNotIn("Get-CimInstance", cmd)
        self.assertIn("Get-Process", cmd)
        self.assertIn("MyBookshelf", cmd)
        self.assertIn(".venv\\Scripts", cmd)

    def test_installer_prepare_and_uninstall_use_process_path(self):
        iss = (ROOT / "dev" / "installer" / "MyBookshelf.iss").read_text(encoding="utf-8-sig")
        prepare = iss[iss.index("function PrepareToInstall"):]
        prepare = prepare[:prepare.index("\nend;")]
        self.assertNotIn("Get-CimInstance Win32_Process |", prepare)
        self.assertIn("Get-Process", prepare)
        uninstall = iss[iss.index("[UninstallRun]"):iss.index("[Code]")]
        uninstall = "\n".join(l for l in uninstall.splitlines() if not l.lstrip().startswith(";"))
        self.assertNotIn("taskkill", uninstall)
        self.assertIn("Get-Process", uninstall)
        self.assertIn("MyBookshelf", uninstall)

    def test_update_helper_does_not_need_wmi(self):
        from services import updater
        code = "\n".join(l for l in updater._HELPER_PS1.splitlines() if not l.lstrip().startswith("#"))
        self.assertNotIn("Get-CimInstance", code)
        self.assertIn("Get-Process", code)


if __name__ == "__main__":
    unittest.main()
