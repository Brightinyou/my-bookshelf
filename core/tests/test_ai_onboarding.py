"""AI 연결을 설치에서 앱 첫 화면으로 옮긴 것 (2026-09-30)."""
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))

from services import ai_setup  # noqa: E402


class AiSetupScriptTest(unittest.TestCase):
    def test_finds_repo_script_on_each_platform(self):
        for plat, name in (("win32", "windows_setup_extras.ps1"), ("darwin", "mac_setup_extras.sh")):
            with mock.patch.object(ai_setup.sys, "platform", plat):
                self.assertEqual(ai_setup.setup_script().name, name)

    def test_windows_opens_new_console(self):
        with mock.patch.object(ai_setup.sys, "platform", "win32"), \
             mock.patch.object(ai_setup.subprocess, "Popen") as popen:
            ok, _ = ai_setup.launch_setup_window()
        self.assertTrue(ok)
        args = popen.call_args.args[0]
        self.assertEqual(args[0], "powershell.exe")
        self.assertTrue(args[-1].endswith("windows_setup_extras.ps1"))

    def test_mac_opens_terminal(self):
        with mock.patch.object(ai_setup.sys, "platform", "darwin"), \
             mock.patch.object(ai_setup.subprocess, "Popen") as popen:
            ok, _ = ai_setup.launch_setup_window()
        self.assertTrue(ok)
        self.assertEqual(popen.call_args.args[0][:3], ["/usr/bin/open", "-a", "Terminal"])

    def test_missing_script_is_reported_not_raised(self):
        with mock.patch.object(ai_setup.sys, "platform", "linux"):
            self.assertEqual(ai_setup.launch_setup_window()[0], False)

    def test_every_api_provider_has_a_key_page(self):
        import llm_providers as llm
        self.assertEqual(set(ai_setup.API_KEY_PAGES), set(llm.API_PROVIDERS))


class MacPostinstallTest(unittest.TestCase):
    def test_postinstall_opens_app_not_setup_window(self):
        script = (ROOT / "dev" / "installer" / "mac_postinstall.sh").read_text(encoding="utf-8")
        self.assertNotIn('open -a Terminal "$RESOURCES/setup-extras.command"', script)
        self.assertIn('asuser /usr/bin/open "$APP"', script)


if __name__ == "__main__":
    unittest.main()
