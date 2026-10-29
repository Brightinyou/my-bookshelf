import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
import io
import json
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import config as cfg
from services import bugreport, updater

CORE = Path(__file__).resolve().parents[1]


def _fake_response(payload):
    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    return _Resp(json.dumps(payload).encode("utf-8"))


def _rel(tag, draft=False, pre=False, asset=True):
    assets = [{"name": "Setup.exe", "browser_download_url": f"https://x/{tag}/Setup.exe"},
              {"name": f"MyBookshelf-{tag}-mac.zip", "browser_download_url": f"https://x/{tag}/mac.zip"}]
    return {"tag_name": tag, "draft": draft, "prerelease": pre, "body": f"notes {tag}",
            "html_url": f"https://x/{tag}", "published_at": "2026-10-01T00:00:00Z",
            "assets": assets if asset else []}


class RollbackListTest(unittest.TestCase):
    """이전 버전으로 되돌리기 (2026-10-30 연구자 요청)."""

    def _list(self, payload):
        with patch.object(updater.sys, "platform", "win32"), \
             patch.object(updater.urllib.request, "urlopen", return_value=_fake_response(payload)), \
             patch.object(updater, "append_log"):
            return updater.list_releases()

    def test_초안과_시험판은_빼고_새_버전부터(self):
        rels, err = self._list([_rel("v1.4.9"), _rel("v1.5.10"), _rel("v1.6.0", pre=True),
                                _rel("v1.7.0", draft=True), _rel("v1.5.2")])
        self.assertEqual(err, "")
        self.assertEqual([r["tag"] for r in rels], ["v1.5.10", "v1.5.2", "v1.4.9"])
        self.assertTrue(rels[0]["asset_url"].endswith("Setup.exe"))

    def test_되돌릴_후보는_지금보다_낮고_설치파일이_있는_것만(self):
        rels, _ = self._list([_rel("v1.5.4"), _rel("v1.5.3"), _rel("v1.5.2", asset=False),
                              _rel("v1.6.0")])
        with patch.object(updater, "APP_VERSION", "v1.5.4"):
            cands = updater.rollback_candidates(rels)
        self.assertEqual([r["tag"] for r in cands], ["v1.5.3"])

    def test_설치_대상은_업데이트와_같은_모양(self):
        target = updater.install_target({"tag": "v1.5.3", "asset_url": "https://x/a", "notes": "n",
                                         "page_url": "https://x/p"})
        self.assertTrue(target["available"])
        self.assertEqual(target["latest"], "v1.5.3")
        self.assertEqual(target["asset_url"], "https://x/a")

    def test_네트워크_실패는_오류문구로(self):
        with patch.object(updater.sys, "platform", "win32"), \
             patch.object(updater.urllib.request, "urlopen", side_effect=OSError("offline")), \
             patch.object(updater, "append_log"):
            rels, err = updater.list_releases()
        self.assertEqual(rels, [])
        self.assertIn("offline", err)


class NoUpdatePopupTest(unittest.TestCase):
    """업데이트는 팝업이 아니라 설정 화면 안내로만 알린다 (2026-10-30 연구자 요청)."""

    def test_업데이트_팝업이_없다(self):
        src = (CORE / "pipeline_app.py").read_text(encoding="utf-8")
        self.assertNotIn('st.dialog(t("업데이트 사용 가능"))', src)
        self.assertIn("_render_settings_update_notice()", src)
        self.assertIn("_render_rollback_panel()", src)
        self.assertIn("_render_bug_report_panel()", src)


class BugReportTest(unittest.TestCase):
    def setUp(self):
        Path(cfg.LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
        home = str(Path.home())
        Path(cfg.LOG_FILE).write_text(
            "[2026-10-30 09:00:00] 정상 처리\n"
            "[2026-10-30 09:01:00] 업데이트 확인 실패(무시): URLError\n"
            f"[2026-10-30 09:02:00] ERROR: 연속 3단락 번역 실패 — {home}\\Documents\\책.txt\n"
            "[2026-10-30 09:03:00] 보낸 사람 someone@example.com\n",
            encoding="utf-8")

    def test_최근_오류는_무시_표시를_빼고_경로를_가린다(self):
        errs = bugreport.recent_errors()
        self.assertEqual(len(errs), 1)
        self.assertIn("ERROR", errs[0])
        self.assertNotIn(str(Path.home()), errs[0])
        self.assertEqual(bugreport.last_error_stamp(), "2026-10-30 09:02:00")

    def test_로그_묶음은_가린_로그와_환경을_담는다(self):
        bundle = bugreport.build_bundle("버튼을 눌렀더니 멈췄어요")
        self.assertTrue(bundle.is_file())
        self.assertTrue(str(bundle).startswith(str(Path(cfg.LOG_DIR))))
        with zipfile.ZipFile(bundle) as z:
            names = z.namelist()
            self.assertIn("README.txt", names)
            self.assertIn("upload.log", names)
            log = z.read("upload.log").decode("utf-8")
            readme = z.read("README.txt").decode("utf-8")
        self.assertNotIn(str(Path.home()), log)
        self.assertNotIn("someone@example.com", log)
        self.assertIn("[email]", log)
        self.assertIn("버튼을 눌렀더니 멈췄어요", readme)

    def test_메일_링크는_개발자_주소와_묶음_이름을_담는다(self):
        url = bugreport.mail_url("설명", Path("mybookshelf_error_report_x.zip"))
        self.assertTrue(url.startswith("mailto:" + bugreport.helper.FEEDBACK_EMAIL))
        self.assertIn("mybookshelf_error_report_x.zip", __import__("urllib.parse").parse.unquote(url))


if __name__ == "__main__":
    unittest.main()
