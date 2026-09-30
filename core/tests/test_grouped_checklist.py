"""Exercise the actual checklist renderer with synthetic books, without I/O."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from services import i18n


def app_source():
    source = (Path(__file__).parents[1] / "pipeline_app.py").read_text(encoding="utf-8")
    names = {"_responsive_columns", "_checklist_keys", "_checklist", "_delete_button"}
    definitions = "\n\n".join(ast.get_source_segment(source, node)
        for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name in names)
    return '''
import streamlit as st
from services.i18n import t, tf
''' + definitions + '''
items = st.session_state.get("items", [
    {"key":"a1", "label":"Chapter A1", "meta":"100", "obj":"a1", "group":"Book A"},
    {"key":"b1", "label":"Chapter B1", "meta":"100", "obj":"b1", "group":"Book B"},
    {"key":"a2", "label":"Chapter A2", "meta":"100", "obj":"a2", "group":"Book A"},
])
st.session_state["selected"] = _checklist(items, "test", preselect=st.session_state.get("pre", False))
st.session_state["deleted"] = st.session_state.get("deleted", 0) + _delete_button(st, "Delete", "test_del", len(st.session_state["selected"]))
'''


class GroupedChecklistTest(unittest.TestCase):
    def app(self):
        return AppTest.from_string(app_source(), default_timeout=10).run()

    def test_book_selects_only_its_chapters_and_individual_deselect_updates_book(self):
        app = self.app()
        book = next(x for x in app.checkbox if x.label == "Book A")
        book.check().run()
        self.assertEqual(app.session_state["selected"], ["a1", "a2"])
        self.assertFalse(app.checkbox(key="test_b1").value)
        app.checkbox(key="test_a1").uncheck().run()
        self.assertEqual(app.session_state["selected"], ["a2"])
        self.assertFalse(next(x for x in app.checkbox if x.label == "Book A").value)
        self.assertFalse(app.exception)

    def test_closed_groups_keep_selection_and_select_all_checkbox_applies_to_all(self):
        app = self.app()
        self.assertEqual(len(app.expander), 2)
        self.assertTrue(all(not x.proto.expanded for x in app.expander))
        self.assertEqual(len(app.expander[0].checkbox), 2)
        app.checkbox(key="test_all").check().run()
        self.assertEqual(app.session_state["selected"], ["a1", "b1", "a2"])
        app.run()
        self.assertEqual(app.session_state["selected"], ["a1", "b1", "a2"])
        self.assertTrue(app.checkbox(key="test_all").value)
        app.checkbox(key="test_all").uncheck().run()
        self.assertEqual(app.session_state["selected"], [])
        self.assertFalse(app.exception)

    def test_preselect_selects_new_items_but_keeps_user_deselection(self):
        app = AppTest.from_string(app_source(), default_timeout=10)
        app.session_state["pre"] = True
        app.run()
        self.assertEqual(app.session_state["selected"], ["a1", "b1", "a2"])
        self.assertTrue(app.checkbox(key="test_all").value)
        app.checkbox(key="test_b1").uncheck().run()
        app.run()
        self.assertEqual(app.session_state["selected"], ["a1", "a2"])
        self.assertFalse(app.checkbox(key="test_all").value)
        self.assertFalse(app.exception)

    def test_delete_needs_confirmation_and_cancel_disarms(self):
        app = AppTest.from_string(app_source(), default_timeout=10)
        app.session_state["pre"] = True
        app.run()
        app.button(key="test_del").click().run()
        self.assertEqual(app.session_state["deleted"], 0)
        app.button(key="test_del__cancel").click().run()
        self.assertEqual(app.session_state["deleted"], 0)
        app.button(key="test_del").click().run()
        app.button(key="test_del__ok").click().run()
        self.assertEqual(app.session_state["deleted"], 1)
        app.run()
        self.assertEqual(app.session_state["deleted"], 1)
        self.assertTrue(any(b.key == "test_del" for b in app.button))
        self.assertFalse(app.exception)

    def test_similar_book_names_do_not_share_checkbox_keys(self):
        app = self.app()
        app.session_state["items"] = [
            {"key":"one", "label":"One", "meta":"", "obj":1, "group":"A/B"},
            {"key":"two", "label":"Two", "meta":"", "obj":2, "group":"A?B"},
            {"key":"single", "label":"Single", "meta":"", "obj":3},
        ]
        app.run()
        next(x for x in app.checkbox if x.label == "A/B").check().run()
        self.assertEqual(app.session_state["selected"], [1])
        self.assertEqual(len(app.expander), 2)
        self.assertFalse(app.exception)

    def test_english_group_labels(self):
        with patch.object(i18n, "_lang_cache", "en"):
            app = self.app()
            self.assertEqual(app.expander[0].label, "2 chapters")
            self.assertTrue(any(x.value == "0 / 2 selected" for x in app.caption))
            self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
