"""Real Streamlit render/rerun checks; use a disposable MYBOOKSHELF_CONFIG_DIR."""
from pathlib import Path
import os
import threading
import re
import unittest
from unittest.mock import patch

import config as cfg
import llm_providers as llm
from services import translate as tr
from services import i18n


@unittest.skipUnless(os.environ.get("MYBOOKSHELF_CONFIG_DIR"), "requires isolated test config")
class UIImprovementsTest(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest
        self.app = AppTest.from_file(str(Path(__file__).parents[1] / "pipeline_app.py"), default_timeout=15)
        self.app.session_state["_update_info"] = {}
        self.app.session_state["_update_result"] = {}
        for p in (patch.object(llm, "has_key", return_value=True),
                  patch.object(llm, "default_provider_model", return_value=("codex_cli", "default"))):
            p.start()
            self.addCleanup(p.stop)

    def test_settings_and_each_stage_render_without_exceptions(self):
        for view in ("settings", "1_txt", "2_split", "3_translate", "4_summary", "5_wiki"):
            self.app.session_state["active_view"] = view
            self.app.run()
            self.assertFalse(self.app.exception, (view, [x.message for x in self.app.exception]))

    def test_eight_views_in_both_languages_and_compact_navigation(self):
        from streamlit.testing.v1 import AppTest
        for lang in ("ko", "en"):
            for view in (None, "all_run", "settings", "1_txt", "2_split", "3_translate", "4_summary", "5_wiki"):
                app = AppTest.from_file(str(Path(__file__).parents[1] / "pipeline_app.py"), default_timeout=15)
                app.session_state["_update_info"] = {}
                app.session_state["_update_result"] = {}
                app.session_state["active_view"] = view
                with patch.object(i18n, "_lang_cache", lang):
                    app.run()
                self.assertFalse(app.exception, (lang, view, [x.message for x in app.exception]))
                self.assertFalse(any(b.key in ("font_size_minus", "font_size_plus") for b in app.button))
                if view and view != "all_run":
                    nav = next(x.value for x in app.markdown if '<nav class="stage-nav"' in x.value)
                    self.assertEqual(nav.count('aria-label='), 8)
                if view != "settings":
                    self.assertFalse(any(str(b.key).startswith("open_loc_") for b in app.button))
                if lang == "en":
                    leaks = []
                    for kind in ("caption", "info", "warning", "error", "subheader", "markdown"):
                        for element in app.get(kind):
                            text = re.sub(r"<style>.*?</style>", "", element.value, flags=re.S)
                            text = re.sub(r"<[^>]+>", "", text)
                            if re.search(r"[가-힣]", text):
                                leaks.append(text[:160])
                    self.assertFalse(leaks, (view, leaks))

    def test_font_scale_setting_persists(self):
        self.app.session_state["active_view"] = "settings"
        with patch.object(llm, "set_pref") as save:
            self.app.run()
            self.app.slider(key="settings_font_percent").set_value(120).run()
            self.assertIn(unittest.mock.call("ui_font_scale", 1.2), save.call_args_list)
            self.assertEqual(self.app.session_state["ui_font_scale"], 1.2)

    def test_failed_items_remain_visible_with_retry(self):
        self.app.session_state["active_view"] = "3_translate"
        self.app.session_state["tr3_failed_items"] = ["missing-chapter.txt"]
        self.app.run()
        self.assertTrue(self.app.error)
        self.assertTrue(self.app.button(key="tr3_retry_recent"))

    def test_populated_list_icon_buttons_keep_accessible_labels(self):
        path = cfg.UPLOAD_TMP / "UI_layout_long_document_title_for_readability.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("A document for the layout test.", encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)
        self.app.session_state["active_view"] = "1_txt"
        self.app.run()
        self.assertFalse(self.app.exception)
        buttons = [b for b in self.app.button if str(b.key).startswith("ocr1_view_")]
        self.assertTrue(buttons)
        self.assertTrue(all(b.label and b.proto.help for b in buttons))
        self.assertTrue(all(b.proto.icon == ":material/description:" for b in buttons))

    def test_output_folders_have_names_and_keep_their_targets(self):
        self.app.session_state["active_view"] = "5_wiki"
        self.app.run()
        self.assertFalse(self.app.exception)
        for key, label in (("epub5_open_dir", "EPUB 전자책 생성 폴더 열기"),
                           ("wiki5_docx_open", "DOCX 폴더 열기"),
                           ("wiki5_hwpx_open", "HWPX 폴더 열기"),
                           ("wiki5_obsidian_open", "Obsidian 폴더 열기")):
            button = self.app.button(key=key)
            self.assertEqual(button.label, label)
            self.assertEqual(button.proto.icon, ":material/folder_open:")
            target = Path(button.proto.help)
            with patch("services.common.open_path") as opened:
                button.click().run()
                opened.assert_called_once_with(target)
            self.assertFalse(self.app.exception)

    def test_completed_wiki_folder_has_visible_text(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / "test.md").write_text("# Test", encoding="utf-8")
            self.app.session_state["wiki5_active_dir"] = str(target)
            self.app.session_state["active_view"] = "5_wiki"
            self.app.run()
            self.assertFalse(self.app.exception)
            self.assertEqual(self.app.button(key="w5_folder").label, "Wiki 저장 폴더 열기")
            # Not wrapped in icon_*: the descriptive text must remain visible.
            source = (Path(__file__).parents[1] / "pipeline_app.py").read_text()
            self.assertIn('_wv_col2.button(t("Wiki 저장 폴더 열기")', source)

    def test_model_dropdown_saves_selection_without_text_input(self):
        self.app.session_state["active_view"] = "settings"
        with patch.object(llm, "set_wiki_model") as save, \
             patch.object(llm, "codex_model_catalog", return_value={"account-model": "Account Model"}):
            self.app.run()
            self.assertFalse(any(x.label == "모델 ID" for x in self.app.text_input))
            self.assertNotIn("모델 ID 직접 입력", self.app.selectbox(key="ai_default_codex_cli_choice").options)
            self.app.selectbox(key="ai_default_codex_cli_choice").select("account-model").run()
            self.app.button(key="ai_default_save").click().run()
            save.assert_called_once_with("codex_cli", "account-model")
            self.assertFalse(self.app.exception)

    def test_rerun_reuses_active_job_and_stop_waits_for_current_item(self):
        path = cfg.CHAPTERS_DIR / "ui-test" / "01_Test.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Test paragraph.", encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)
        release = threading.Event()
        self.addCleanup(release.set)
        entered = threading.Event()
        def translate(*args, **kwargs):
            entered.set()
            release.wait(10)
            return False, "test stopped"
        s = self.app.session_state
        s["active_view"] = "3_translate"
        s["tr3_running"] = True
        s["tr3_queue"] = [str(path.relative_to(cfg.BASE_DIR))] * 2
        s["tr3_total"] = 2
        s["_run_lock"] = "tr3"
        with patch.object(tr, "translate_one_chapter", side_effect=translate) as call:
            self.app.run()
            self.assertFalse(self.app.exception)
            self.assertTrue(entered.wait(2))
            job = s["tr3_job"]
            self.app.run()
            self.assertIs(s["tr3_job"], job)
            self.app.button(key="tr3_stopbtn").click().run()
            self.assertTrue(job.stop_after)
            release.set()
            self.assertTrue(job.done.wait(3))
            self.app.run()
            self.assertFalse(self.app.exception)
            self.assertFalse(s["tr3_running"])
            self.assertEqual(len(s["tr3_queue"]), 1)
            self.assertEqual(call.call_count, 1)


if __name__ == "__main__":
    unittest.main()
