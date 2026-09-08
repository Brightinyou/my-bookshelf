"""Exercise the actual checklist renderer with synthetic books, without I/O."""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from services import i18n


def app_source():
    source = (Path(__file__).parents[1] / "pipeline_app.py").read_text(encoding="utf-8")
    names = {"_responsive_columns", "_checklist_keys", "_checklist"}
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
st.session_state["selected"] = _checklist(items, "test")
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

    def test_closed_groups_keep_selection_and_global_buttons_apply_to_all(self):
        app = self.app()
        self.assertEqual(len(app.expander), 2)
        self.assertTrue(all(not x.proto.expanded for x in app.expander))
        self.assertEqual(len(app.expander[0].checkbox), 2)
        app.button(key="test_sa").click().run()
        self.assertEqual(app.session_state["selected"], ["a1", "b1", "a2"])
        app.run()
        self.assertEqual(app.session_state["selected"], ["a1", "b1", "a2"])
        app.button(key="test_da").click().run()
        self.assertEqual(app.session_state["selected"], [])
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
