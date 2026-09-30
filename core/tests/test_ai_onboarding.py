"""AI 연결을 설치에서 앱 첫 화면으로 옮긴 것 (2026-09-30)."""
from pathlib import Path
import codecs
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
        self.assertTrue(args[args.index("-File") + 1].endswith("windows_setup_extras.ps1"))

    def test_windows_setup_window_follows_app_language(self):
        for lang in ("ko", "en"):
            with mock.patch.object(ai_setup.sys, "platform", "win32"),                  mock.patch("services.i18n.get_lang", return_value=lang),                  mock.patch.object(ai_setup.subprocess, "Popen") as popen:
                ai_setup.launch_setup_window()
            args = popen.call_args.args[0]
            self.assertEqual(args[args.index("-Lang") + 1], lang)

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


class WindowsSetupScriptTest(unittest.TestCase):
    """설치 뒤 AI 설정 창(windows_setup_extras.ps1) — 2026-09-30 Sandbox 실측."""
    SCRIPT = ROOT / "dev" / "installer" / "windows_setup_extras.ps1"

    def test_saved_with_bom_so_korean_survives_powershell_51(self):
        self.assertTrue(self.SCRIPT.read_bytes().startswith(codecs.BOM_UTF8))

    def test_menu_is_korean_when_lang_is_ko(self):
        s = self.SCRIPT.read_text(encoding="utf-8-sig")
        self.assertIn("[string] $Lang", s)
        self.assertIn("AI CLI 선택", s)
        self.assertIn("번호를 입력하세요", s)

    def test_node_installs_without_winget(self):
        s = self.SCRIPT.read_text(encoding="utf-8-sig")
        self.assertIn("function Install-NodeZip", s)
        self.assertIn("https://nodejs.org/dist/index.json", s)
        self.assertNotIn("winget was not found, so Node.js cannot be installed", s)

    def test_log_failure_never_stops_setup(self):
        """읽기 전용 폴더에서 로그 한 줄 못 써서 Node.js 설치가 «실패»로 끝났다."""
        s = self.SCRIPT.read_text(encoding="utf-8-sig")
        log_fn = s[s.index("function Log("):s.index("function Refresh-Path")]
        self.assertIn("catch { }", log_fn)
        self.assertIn("mybookshelf-setup-extras.log", s)

    def test_claude_installer_runs_in_its_own_process(self):
        """공식 스크립트의 `exit 1` 이 이 창까지 끝내면 안 된다."""
        s = self.SCRIPT.read_text(encoding="utf-8-sig")
        self.assertNotIn("| Invoke-Expression", s)
        self.assertIn("-File $installer", s)

    def test_obsidian_is_explained_before_asking(self):
        s = self.SCRIPT.read_text(encoding="utf-8-sig")
        self.assertLess(s.index("옵시디언은 무료 메모 앱입니다"), s.index("옵시디언도 설치할까요?"))
        self.assertIn("Word(DOCX)", s)


class OnboardingOrderTest(unittest.TestCase):
    def test_subscription_comes_first_and_api_label_is_plain(self):
        s = (ROOT / "core" / "pipeline_app.py").read_text(encoding="utf-8")
        self.assertIn('t("연결 방법"), ["cli", "api"]', s)
        self.assertNotIn("API 키 (권장)", s)


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
