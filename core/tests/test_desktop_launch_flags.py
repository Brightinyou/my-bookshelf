"""데스크톱 런처가 Streamlit에 넘기는 플래그.

업로드 상한(maxUploadSize)은 두 번 조용히 200MB로 되돌아갔다 — 2026-08-11에는
설치본에 config.toml이 빠져서, 2026-09-21에는 cwd가 runtime 폴더로 옮겨져
Streamlit이 config.toml을 못 찾아서. 설정 파일 위치와 무관하게 플래그로
넘어가는지, 그리고 그 값이 config.toml과 어긋나지 않는지 붙들어 둔다.
"""
from pathlib import Path
from unittest.mock import patch
import re
import unittest

import desktop


def _launch_cmd():
    with patch.object(desktop, "_port_in_use", return_value=False), \
         patch.object(desktop.subprocess, "Popen") as popen:
        desktop._start_streamlit(8501)
    args, kwargs = popen.call_args
    return list(args[0]), kwargs


def _flag(cmd, name):
    return cmd[cmd.index(name) + 1]


class DesktopLaunchFlagsTest(unittest.TestCase):
    def test_upload_limit_is_passed_as_flag(self):
        cmd, _ = _launch_cmd()
        self.assertEqual(_flag(cmd, "--server.maxUploadSize"), str(desktop.MAX_UPLOAD_MB))
        self.assertGreater(desktop.MAX_UPLOAD_MB, 200, "Streamlit 기본값(200MB)보다 커야 한다")

    def test_file_watcher_is_off_by_flag(self):
        cmd, _ = _launch_cmd()
        self.assertEqual(_flag(cmd, "--server.fileWatcherType"), "none")

    def test_flag_matches_config_toml(self):
        toml = (Path(desktop.HERE) / ".streamlit" / "config.toml").read_text(encoding="utf-8")
        m = re.search(r"^maxUploadSize\s*=\s*(\d+)", toml, re.M)
        self.assertIsNotNone(m, "config.toml 에 maxUploadSize 가 없다")
        self.assertEqual(int(m.group(1)), desktop.MAX_UPLOAD_MB)

    def test_cwd_is_outside_app_bundle(self):
        # 업데이트로 교체되는 번들 밖에서 도는 것은 의도된 동작(2026-09-08) — 그래서
        # config.toml 대신 플래그가 필요하다.
        _, kwargs = _launch_cmd()
        self.assertFalse(Path(kwargs["cwd"]).is_relative_to(desktop.APP_ROOT))


if __name__ == "__main__":
    unittest.main()
