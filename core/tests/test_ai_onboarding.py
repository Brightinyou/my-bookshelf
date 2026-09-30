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


class CliInstallStepsTest(unittest.TestCase):
    """붙여 넣는 명령이 설치 스크립트가 실제로 쓰는 것과 어긋나지 않게 한다."""

    SCRIPTS = {"win32": ROOT / "dev" / "installer" / "windows_setup_extras.ps1",
               "darwin": ROOT / "dev" / "installer" / "mac_setup_extras.sh"}

    def test_commands_match_setup_scripts(self):
        for plat, path in self.SCRIPTS.items():
            script = path.read_text(encoding="utf-8")
            joined = " ".join(c for cli in ("claude", "codex")
                              for _, c in ai_setup.cli_install_steps(cli, plat) if c)
            for needle in ("https://claude.ai/install." + ("ps1" if plat == "win32" else "sh"),
                           "@openai/codex", "claude auth login", "codex login --device-auth"):
                self.assertIn(needle, joined, (plat, needle))
                self.assertIn(needle.split(" ")[0] if needle.startswith("http") else needle, script, (plat, needle))

    def test_mac_codex_installs_to_user_folder_like_the_script(self):
        steps = dict(ai_setup.cli_install_steps("codex", "darwin"))
        self.assertIn('--prefix "$HOME/.local"', steps["설치"])
        self.assertIn('--prefix "$HOME/.local"', self.SCRIPTS["darwin"].read_text(encoding="utf-8"))

    def test_every_step_label_is_translated(self):
        from services import i18n
        for plat in self.SCRIPTS:
            for cli in ("claude", "codex"):
                for label, _ in ai_setup.cli_install_steps(cli, plat):
                    self.assertIn(label, i18n._EN, label)


if __name__ == "__main__":
    unittest.main()
