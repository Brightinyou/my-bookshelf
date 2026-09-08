from html.parser import HTMLParser
from unittest.mock import patch
import unittest
from services.ui_layout import navigation_html, status_chip, window_geometry, font_scale, COMPACT_CSS
from desktop import _remember_window_size


class Tags(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class CompactLayoutTest(unittest.TestCase):
    def test_navigation_has_accessible_names_and_one_current_label(self):
        items = [(k, k + ' "<label>"') for k in ("menu", "1_txt", "2_split", "3_translate", "4_summary", "5_wiki", "settings")]
        html = navigation_html(items, "3_translate", False, "Workflow")
        links = [attrs for tag, attrs in Tags(html).tags if tag == "a"]
        self.assertEqual(len(links), 7)
        self.assertTrue(all(a.get("aria-label") and a.get("title") for a in links))
        self.assertEqual(sum(a.get("aria-current") == "page" for a in links), 1)
        self.assertEqual(html.count('class="nav-current-label"'), 1)
        self.assertNotIn("<label>", html)

    def test_locked_navigation_cannot_navigate(self):
        html = navigation_html([("settings", "Settings")], "settings", True, "Workflow")
        self.assertNotIn("href=", html)
        self.assertIn('aria-disabled="true"', html)

    def test_chip_escapes_model_text_and_has_accessible_details(self):
        html = status_chip('<model>', 'details "quoted"')
        self.assertNotIn('<model>', html)
        self.assertEqual(Tags(html).tags[0][1]["aria-label"], 'details "quoted"')

    def test_geometry_defaults_restores_and_clamps(self):
        self.assertEqual(window_geometry(1920, 1080), (1100, 820, 380, 600))
        self.assertEqual(window_geometry(1920, 1080, {"width": 810, "height": 640})[:2], (810, 640))
        self.assertEqual(window_geometry(1366, 768, {"width": 4000, "height": 3000}), (1297, 691, 380, 600))
        self.assertEqual(window_geometry(1920, 1080, {"width": 10, "height": 20})[:2], (380, 600))
        self.assertEqual(window_geometry(1920, 1080, {"width": 380, "height": 640})[:2], (380, 640))
        self.assertLess(window_geometry(640, 480)[0], 640)
        self.assertEqual(window_geometry(1920, 1080, {"width": "broken"})[:2], (1100, 820))

    def test_window_size_saved_and_bad_resize_ignored(self):
        with patch("llm_providers.set_pref") as save:
            _remember_window_size(810, 640)
            save.assert_called_once_with("window_size", {"width": 810, "height": 640})
            _remember_window_size(0, 0)
            self.assertEqual(save.call_count, 1)

    def test_font_scale_clamped(self):
        self.assertEqual(font_scale("bad"), 1)
        self.assertEqual(font_scale(7), 1.35)
        self.assertEqual(font_scale(0), .85)

    def test_narrow_navigation_keeps_all_seven_svg_icons(self):
        items = [(k, k) for k in ("menu", "1_txt", "2_split", "3_translate", "4_summary", "5_wiki", "settings")]
        html = navigation_html(items, "settings", False, "Workflow")
        self.assertEqual(sum(tag == "svg" for tag, _ in Tags(html).tags), 7)
        self.assertNotIn("<details", html)
        self.assertIn("grid-template-columns:repeat(7,minmax(0,1fr))", COMPACT_CSS)
        self.assertNotIn(".stage-nav { display:none", COMPACT_CSS)

    def test_compact_css_is_scoped_and_does_not_hide_failures(self):
        self.assertIn("@media (max-width:560px)", COMPACT_CSS)
        self.assertIn("13px * var(--mb-font-scale)", COMPACT_CSS)
        self.assertIn("min-height:40px", COMPACT_CSS)
        self.assertIn("st-key-document_row_", COMPACT_CSS)
        # Streamlit 1.62 inserts stLayoutWrapper between a container and its row.
        self.assertNotIn('st-key-document_row_\"] > [data-testid="stHorizontalBlock"]', COMPACT_CSS)
        self.assertNotIn("stAlert", COMPACT_CSS)

    def test_screenshot_adjustments_preserve_fixed_row_alignment(self):
        fixed = COMPACT_CSS.split("@media")[0]
        self.assertIn("grid-template-columns:minmax(0,1fr) 40px", fixed)
        self.assertIn("justify-self:start; width:40px", fixed)
        self.assertIn("st-key-stage_folders_", fixed)
        self.assertIn("20px * var(--mb-font-scale)", COMPACT_CSS)
        self.assertIn("10.5px * var(--mb-font-scale)", COMPACT_CSS)
        self.assertIn("13.5px * var(--mb-font-scale)", COMPACT_CSS)

    def test_chapters_are_indented_and_selection_buttons_are_separated(self):
        self.assertIn("st-key-chapter_children_", COMPACT_CSS)
        self.assertIn("padding-left:20px", COMPACT_CSS)
        self.assertIn("column-gap:14px !important", COMPACT_CSS)


if __name__ == "__main__":
    unittest.main()
