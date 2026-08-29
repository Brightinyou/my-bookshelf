from pathlib import Path
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
