"""WebView2 가 없는 윈도우에서 앱 창이 빈 창이 되던 것 (2026-09-30 Windows Sandbox 실측).

GitHub 윈도우 러너에는 WebView2 가 이미 있어 부재 상황은 재현되지 않는다. 판정은
레지스트리를 흉내 내어 묶고, 실제 부재는 Sandbox 실측으로 확인한다.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
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
    def _needs(self, platform="win32", renderer=None, version=""):
        with mock.patch.object(desktop.sys, "platform", platform), \
             mock.patch.object(desktop, "_pywebview_renderer", return_value=renderer), \
             mock.patch.object(desktop, "webview2_version", return_value=version):
            return desktop._needs_browser_fallback()

    def test_follows_pywebview_renderer_first(self):
        """판정이 어긋나 WebView2 로 잘 그려질 PC 가 브라우저로 떨어지면 안 된다."""
        self.assertTrue(self._needs(renderer="mshtml", version="140.0"))
        self.assertFalse(self._needs(renderer="edgechromium", version=""))   # 예: Beta 채널만

    def test_registry_only_when_pywebview_cannot_tell(self):
        self.assertTrue(self._needs(renderer=None, version=""))
        self.assertFalse(self._needs(renderer=None, version="140.0"))

    def test_never_outside_windows(self):
        self.assertFalse(self._needs(platform="darwin", renderer="mshtml", version=""))

    @unittest.skipUnless(desktop.sys.platform == "win32" and desktop.webview2_version(),
                         "WebView2 가 있는 Windows 에서만")
    def test_real_pc_with_webview2_is_not_sent_to_browser(self):
        self.assertEqual(desktop._pywebview_renderer(), "edgechromium")
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

    def test_notice_gives_the_address_in_both_languages(self):
        """브라우저가 없는 PC 에서도 직접 열 수 있게 주소를 적는다(오프라인 Sandbox 실측)."""
        url = "http://127.0.0.1:8502/"
        for lang, phrase in (("ko", "브라우저 주소창에 다음 주소를 입력하세요"),
                             ("en", "type this address in your browser's address bar")):
            with mock.patch("services.i18n.get_lang", return_value=lang):
                msg = desktop._no_webview2_message(url)
            self.assertIn(phrase, msg)
            self.assertIn(url, msg)
            self.assertIn(desktop.WEBVIEW2_DOWNLOAD, msg)

    def test_notice_uses_the_real_server_address(self):
        with mock.patch.object(desktop, "_open_in_browser", return_value=True), \
             mock.patch.object(desktop, "_write_launch_log"), \
             mock.patch.object(desktop, "_stop_server"), \
             mock.patch("ctypes.windll", create=True) as windll:
            desktop._run_in_browser("http://127.0.0.1:8503/", mock.Mock())
        self.assertIn("http://127.0.0.1:8503/", windll.user32.MessageBoxW.call_args.args[1])

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

    def test_progress_bar_moves_while_bootstrapper_runs(self):
        """40초 남짓 멈춘 막대는 설치가 멈춘 것처럼 보인다(연구자 지적)."""
        code = self.iss[self.iss.index("procedure EnsureWebView2"):]
        code = code[:code.index("\nend;")]
        self.assertLess(code.index("npbstMarquee"), code.index("Exec("))
        self.assertIn("WizardForm.ProgressGauge.Style := npbstNormal", code[code.index("finally"):])
        self.assertIn("CustomMessage('InstallingWebView2')", code)
        self.assertIn("korean.InstallingWebView2=", self.iss)
        self.assertIn("english.InstallingWebView2=", self.iss)

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
