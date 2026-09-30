from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


class WindowsSetupTest(unittest.TestCase):
    def test_setup_verifies_imports_after_pip_install(self):
        script = (ROOT / "setup.bat").read_text(encoding="utf-8")

        self.assertIn('-c "import streamlit, webview"', script)
        self.assertIn("--force-reinstall", script)
        self.assertIn('"pywebview>=5.0" "pythonnet>=3.0"', script)

    def test_installer_packages_setup_and_glossary_entrypoint(self):
        installer = (ROOT / "dev" / "installer" / "MyBookshelf.iss").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn('Source: "..\\..\\setup.bat"', installer)
        self.assertIn('Source: "..\\..\\glossary.bat"', installer)

    def test_installer_leaves_cli_setup_to_the_app(self):
        installer = (ROOT / "dev" / "installer" / "MyBookshelf.iss").read_text(
            encoding="utf-8-sig"
        )
        script = (
            ROOT / "dev" / "installer" / "windows_setup_extras.ps1"
        ).read_text(encoding="utf-8")

        # 스크립트는 계속 설치하되(앱의 «AI 연결» 안내가 연다) 설치 마지막에 띄우지 않는다.
        self.assertIn('Source: "windows_setup_extras.ps1"', installer)
        self.assertNotIn('Set up Claude or Codex', installer)
        self.assertNotIn('File ""{app}\\windows_setup_extras.ps1', installer)
        self.assertIn("& claude auth login", script)
        self.assertIn("& codex login --device-auth", script)
        self.assertIn("'pref_use_claude_cli'", script)
        self.assertIn("'pref_use_codex_cli'", script)
        self.assertIn("'pref_use_obsidian'", script)
        self.assertIn("Obsidian.Obsidian", script)

    def test_app_launch_does_not_depend_on_vbscript(self):
        """VBScript 를 없앤 PC(Windows Sandbox 실측)에서도 설치 뒤 앱이 열려야 한다."""
        installer = (ROOT / "dev" / "installer" / "MyBookshelf.iss").read_text(
            encoding="utf-8-sig"
        )
        run = installer.split("[Run]", 1)[1].split("[UninstallDelete]", 1)[0]
        self.assertNotIn("wscript.exe", run)
        self.assertIn('Filename: "{app}\\.venv\\Scripts\\MyBookshelf.exe"', run)

        start = (ROOT / "start.bat").read_text(encoding="utf-8")
        self.assertLess(start.index(".venv\\Scripts\\MyBookshelf.exe"),
                        start.index("wscript.exe"))

    def test_unattended_installer_supports_both_clis_and_login(self):
        script = (ROOT / "install-mybookshelf.ps1").read_text(encoding="utf-8-sig")

        self.assertIn("'codex','claude','both','none'", script)
        self.assertIn("[switch] $NoLogin", script)
        self.assertIn("& claude auth login", script)
        self.assertIn("& codex login --device-auth", script)

    def test_host_first_install_reset_is_reversible_and_removes_python(self):
        script = (
            ROOT / "dev" / "windows-first-install" / "reset-host.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("Python.Python.3.14", script)
        self.assertIn("Python.Python.3.13", script)
        self.assertIn("Python.Launcher", script)
        self.assertIn("Move-ToBackup", script)
        self.assertNotIn("Remove-Item", script)
        self.assertIn("Documents and vaults were not changed", script)

    def test_source_and_installer_versions_match(self):
        source = (ROOT / "core" / "version.py").read_text(encoding="utf-8")
        installer = (ROOT / "dev" / "installer" / "MyBookshelf.iss").read_text(
            encoding="utf-8-sig"
        )

        source_version = re.search(r'APP_VERSION\s*=\s*"v([^"]+)"', source).group(1)
        installer_version = re.search(
            r'#define MyAppVersion\s+"([^"]+)"', installer
        ).group(1)
        self.assertEqual(source_version, installer_version)

    def test_workflow_publishes_unattended_installer(self):
        workflow = (
            ROOT / ".github" / "workflows" / "build-windows.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("- '*.ps1'", workflow)
        self.assertGreaterEqual(workflow.count("install-mybookshelf.ps1"), 2)
