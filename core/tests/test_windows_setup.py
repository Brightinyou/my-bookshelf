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

    def test_installer_launches_interactive_cli_setup(self):
        installer = (ROOT / "dev" / "installer" / "MyBookshelf.iss").read_text(
            encoding="utf-8-sig"
        )
        script = (
            ROOT / "dev" / "installer" / "windows_setup_extras.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn('Source: "windows_setup_extras.ps1"', installer)
        self.assertIn('Flags: waituntilterminated postinstall skipifsilent', installer)
        self.assertIn("& claude auth login", script)
        self.assertIn("& codex login --device-auth", script)
        self.assertIn("'pref_use_claude_cli'", script)
        self.assertIn("'pref_use_codex_cli'", script)
        self.assertIn("'pref_use_obsidian'", script)
        self.assertIn("Obsidian.Obsidian", script)

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
