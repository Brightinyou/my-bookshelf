"""Narrow editor interactions use disposable, in-memory chapter rows only."""
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from services import i18n


APP = '''
import streamlit as st
from services.ui_chapter_editor import chapter_editor
rows = [
    {"순번":"01", "부":"Part I", "제목":"First", "분량":"100", "시작 부분":"Opening", "앞 장에 합치기":False},
    {"순번":"02", "부":"", "제목":"Second", "분량":"200", "시작 부분":"Next", "앞 장에 합치기":False},
]
if st.session_state.get("source_changed"):
    rows[0]["제목"] = "Saved title"
st.session_state["result"] = chapter_editor(rows, "test", full=st.session_state.get("full", True)).to_dict("records")
'''


class ChapterEditorTest(unittest.TestCase):
    def app(self):
        return AppTest.from_string(APP, default_timeout=10).run()

    def test_single_editor_keeps_drafts_across_chapters_and_layouts(self):
        app = self.app()
        self.assertFalse(app.exception)
        self.assertTrue(app.checkbox[0].disabled)
        app.text_input[0].set_value("Renamed first").run()
        app.selectbox[1].set_value(1).run()
        app.text_input[0].set_value("Renamed second").run()
        app.checkbox[0].check().run()
        self.assertTrue(app.warning)
        app.selectbox[1].set_value(0).run()
        self.assertEqual(app.text_input[0].value, "Renamed first")
        self.assertEqual(app.session_state["result"][1]["제목"], "Renamed second")
        app.selectbox(key="test_mode").set_value("table").run()
        self.assertTrue(app.dataframe)
        app.selectbox(key="test_mode").set_value("single").run()
        self.assertEqual(app.text_input[0].value, "Renamed first")
        self.assertTrue(app.session_state["result"][1]["앞 장에 합치기"])
        self.assertFalse(app.exception)

    def test_table_edits_survive_reruns_and_switch_to_single(self):
        app = self.app()
        # AppTest cannot type into canvas cells. Simulate the widget's returned
        # dataframe, checking its input baseline stays immutable on reruns.
        def edit_table(frame, **kwargs):
            self.assertEqual(frame.iloc[1]["제목"], "Second")
            edited = frame.copy()
            edited.loc[1, "제목"] = "Table rename"
            return edited
        with patch("services.ui_chapter_editor.st.data_editor", side_effect=edit_table):
            app.selectbox(key="test_mode").set_value("table").run()
            self.assertEqual(app.session_state["result"][1]["제목"], "Table rename")
            app.run()
            self.assertEqual(app.session_state["result"][1]["제목"], "Table rename")
            app.selectbox(key="test_mode").set_value("single").run()
        app.selectbox[1].set_value(1).run()
        self.assertEqual(app.text_input[0].value, "Table rename")
        self.assertFalse(app.exception)

    def test_changed_source_drops_stale_draft(self):
        app = self.app()
        app.text_input[0].set_value("Unsaved").run()
        app.session_state["source_changed"] = True
        app.run()
        self.assertEqual(app.text_input[0].value, "Saved title")
        self.assertFalse(app.exception)

    def test_title_only_mode_does_not_offer_merge(self):
        app = self.app()
        app.session_state["full"] = False
        app.run()
        self.assertFalse(app.checkbox)
        self.assertFalse(app.exception)

    def test_english_labels_in_both_editors(self):
        with patch.object(i18n, "_lang_cache", "en"):
            app = self.app()
            self.assertEqual(app.selectbox[0].label, "Editor layout")
            self.assertEqual(app.selectbox[1].label, "Chapter to edit")
            self.assertEqual(app.caption[-1].value, "Opening text")
            self.assertEqual(app.text_input[0].label, "Chapter title")
            self.assertEqual(app.text_input[1].label, "Part")
            self.assertEqual(app.checkbox[0].label, "Merge into previous chapter")
            app.selectbox(key="test_mode").set_value("table").run()
            self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
