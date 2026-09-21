import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from services import updater


class UpdateSafetyTest(unittest.TestCase):
    def test_network_failure_is_not_reported_as_latest(self):
        with patch.object(updater.sys, "platform", "darwin"), \
             patch.object(updater, "_mac_app_bundle", return_value=Path("/Applications/MyBookshelf.app")), \
             patch.object(updater.urllib.request, "urlopen", side_effect=OSError("offline")), \
             patch.object(updater, "append_log"):
            result = updater.check_for_update()
        self.assertFalse(result["available"])
        self.assertIn("offline", result["error"])

    def test_permission_failure_never_starts_helper_or_exits(self):
        with patch.object(updater.sys, "platform", "darwin"), \
             patch.object(updater, "_mac_app_bundle", return_value=Path("/Applications/MyBookshelf.app")), \
             patch.object(updater.os, "access", return_value=False), \
             patch.object(updater, "append_log"), \
             patch.object(updater.subprocess, "Popen") as spawn, \
             patch.object(updater, "_terminate_parent_tree") as terminate:
            self.assertFalse(updater.launch_helper_and_exit(Path("/tmp/update.zip")))
            spawn.assert_not_called()
            terminate.assert_not_called()


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(sys.platform == "win32", "PowerShell 헬퍼는 Windows 전용")
class HelperRelaunchQuotingTest(unittest.TestCase):
    """헬퍼의 보조 재실행이 공백 있는 설치 경로에서도 산다 (2026-09-21).

    v1.3.4 업데이트 뒤 앱이 다시 뜨지 않았다. Setup.exe 는 끝났는데 헬퍼의 보조
    재실행이 «…\Local\My Bookshelf\core\desktop.py» 를 따옴표 없이 넘겨
    "can't open file '…\Local\My'" 로 곧장 죽은 것. 실제 헬퍼 스크립트에서 그
    재실행 줄을 그대로 떼어 python.exe 로 돌려 본다."""

    def test_relaunch_args_with_space_survive(self):
        import re
        import subprocess
        import tempfile
        from services import updater
        m = re.search(r"if \(\$RelaunchArgs\) \{\n(.*?)\n\s*\} else", updater._HELPER_PS1, re.S)
        self.assertIsNotNone(m, "헬퍼에서 재실행 줄을 못 찾았다")
        launch_line = m.group(1).strip()
        with tempfile.TemporaryDirectory(prefix="mb space ") as tmp:
            root = Path(tmp)
            script = root / "core" / "desktop.py"
            script.parent.mkdir()
            marker = root / "ran.txt"
            script.write_text(f"open(r'{marker}', 'w').write('ok')\n", encoding="utf-8")
            ps = "\n".join([
                f"$Root = '{root}'", f"$Relaunch = '{sys.executable}'", f"$RelaunchArgs = '{script}'",
                launch_line.replace("Start-Process ", "Start-Process -Wait "),
            ])
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                           capture_output=True, timeout=60)
            self.assertTrue(marker.exists(), f"재실행이 스크립트를 열지 못했다: {launch_line}")
