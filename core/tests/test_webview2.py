"""WebView2 가 없는 윈도우에서 앱 창이 빈 창이 되던 것 (2026-09-30 Windows Sandbox 실측).

GitHub 윈도우 러너에는 WebView2 가 이미 있어 부재 상황은 재현되지 않는다. 판정은
레지스트리를 흉내 내어 묶고, 실제 부재는 Sandbox 실측으로 확인한다.
"""
from pathlib import Path
from unittest import mock
import unittest

import desktop

ROOT = Path(__file__).resolve().parents[2]
GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


def _reader(values):
    """values: {(hive, path_suffix): pv}. 경로 끝이 맞는 첫 값을 돌려준다."""
    def read(hive, path):
        for (h, suffix), pv in values.items():
            if h == hive and path.endswith(suffix):
                return pv
        return ""
    return read


class WebView2VersionTest(unittest.TestCase):
    def test_missing_everywhere(self):
        self.assertEqual(desktop.webview2_version(_reader({})), "")

    def test_zero_version_counts_as_missing(self):
        read = _reader({("HKLM", rf"WOW6432Node\Microsoft\EdgeUpdate\Clients\{GUID}"): "0.0.0.0"})
        self.assertEqual(desktop.webview2_version(read), "")

    def test_machine_install_wow6432node(self):
        read = _reader({("HKLM", rf"WOW6432Node\Microsoft\EdgeUpdate\Clients\{GUID}"): "140.0.1"})
        self.assertEqual(desktop.webview2_version(read), "140.0.1")

    def test_per_user_install(self):
        """설치 프로그램이 관리자 권한 없이 돌면 부트스트래퍼가 HKCU 에 깐다."""
        read = _reader({("HKCU", rf"Microsoft\EdgeUpdate\Clients\{GUID}"): "140.0.2"})
        self.assertEqual(desktop.webview2_version(read), "140.0.2")

    def test_reader_errors_are_missing_not_crash(self):
        def boom(hive, path):
            raise OSError("denied")
        self.assertEqual(desktop.webview2_version(boom), "")


class BrowserFallbackTest(unittest.TestCase):
    def test_only_windows_without_webview2(self):
        with mock.patch.object(desktop.sys, "platform", "win32"), \
             mock.patch.object(desktop, "webview2_version", return_value=""):
            self.assertTrue(desktop._needs_browser_fallback())
        with mock.patch.object(desktop.sys, "platform", "win32"), \
             mock.patch.object(desktop, "webview2_version", return_value="140.0"):
            self.assertFalse(desktop._needs_browser_fallback())
        with mock.patch.object(desktop.sys, "platform", "darwin"), \
             mock.patch.object(desktop, "webview2_version", return_value=""):
            self.assertFalse(desktop._needs_browser_fallback())

    def test_opens_browser_and_stops_server_after_notice(self):
        proc = mock.Mock()
        with mock.patch.object(desktop, "_open_in_browser", return_value=True) as open_, \
             mock.patch.object(desktop, "_write_launch_log"), \
             mock.patch.object(desktop, "_stop_server") as stop, \
             mock.patch("ctypes.windll", create=True) as windll:
            rc = desktop._run_in_browser("http://127.0.0.1:8501/", proc)
        self.assertEqual(rc, 0)
        open_.assert_called_once_with("http://127.0.0.1:8501/")
        windll.user32.MessageBoxW.assert_called_once()
        stop.assert_called_once_with(proc)

    def test_popup_goes_to_browser_too(self):
        with mock.patch.object(desktop, "_needs_browser_fallback", return_value=True), \
             mock.patch.object(desktop, "_open_in_browser", return_value=True) as open_:
            self.assertEqual(desktop.run_popup("http://127.0.0.1:8501/?view=x", "t"), 0)
        open_.assert_called_once()

    def test_main_checks_before_creating_the_window(self):
        src = (ROOT / "core" / "desktop.py").read_text(encoding="utf-8")
        main = src[src.index("def main() -> int:"):]
        self.assertLess(main.index("_needs_browser_fallback()"), main.index("webview.create_window("))


class InstallerWebView2Test(unittest.TestCase):
    def setUp(self):
        self.iss = (ROOT / "dev" / "installer" / "MyBookshelf.iss").read_text(encoding="utf-8-sig")

    def test_bootstrapper_is_bundled_but_not_copied(self):
        self.assertIn('Source: "..\\..\\vendor\\webview2\\MicrosoftEdgeWebview2Setup.exe"; Flags: dontcopy',
                      self.iss)

    def test_runs_silently_only_when_missing(self):
        code = self.iss[self.iss.index("procedure EnsureWebView2"):]
        self.assertIn("if WebView2Installed() then", code)
        self.assertIn("'/silent /install'", code)
        self.assertIn("webview2-install.log", code)
        self.assertIn("EnsureWebView2();", self.iss[self.iss.index("procedure CurStepChanged"):])

    def test_checks_machine_and_user_keys(self):
        self.assertIn(GUID, self.iss)
        for root in ("HKLM32", "HKLM64", "HKCU"):
            self.assertIn(f"WebView2PvOk({root})", self.iss)

    def test_ci_fetches_and_verifies_signature(self):
        wf = (ROOT / ".github" / "workflows" / "build-windows.yml").read_text(encoding="utf-8")
        self.assertLess(wf.index("fetch-webview2.ps1"), wf.index('iscc "dev\\installer\\MyBookshelf.iss"'))
        fetch = (ROOT / "dev" / "installer" / "fetch-webview2.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("Get-AuthenticodeSignature", fetch)
        self.assertIn("O=Microsoft Corporation", fetch)


if __name__ == "__main__":
    unittest.main()
