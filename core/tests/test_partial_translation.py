from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from services import translate as tr
import llm_providers as llm


class PartialTranslationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "01_Test.txt"
        self.path.write_text("First complete sentence.\n\nSecond complete sentence.", encoding="utf-8")
        for p in (patch.object(tr, "target_language", return_value="ko"),
                  patch.object(tr, "needs_translation", return_value=True),
                  patch.object(tr, "should_drop_paragraph", return_value=False),
                  patch.object(tr, "should_skip_translation", return_value=False),
                  patch.object(tr, "_split_paragraphs_robust", side_effect=lambda text: text.split("\n\n")),
                  patch.object(tr, "translate_title", return_value="시험"),
                  patch.object(tr, "append_log")):
            p.start()
            self.addCleanup(p.stop)

    def test_partial_keeps_cache_and_only_retries_failed_paragraph(self):
        with patch.object(tr, "_translate_paragraph", side_effect=["첫 번째 완성된 문장입니다.", None]):
            ok, msg = tr.translate_one_chapter(self.path, "codex_cli:default")
        self.assertFalse(ok)
        self.assertIn("부분완료", msg)
        self.assertEqual(tr.translation_status(self.path)["failed"], 1)
        self.assertIsNone(tr.find_translation(self.path))
        self.assertTrue(self.path.with_name("01_Test_ko.progress.json").exists())
        with patch.object(tr, "_translate_paragraph", return_value="두 번째 완성된 문장입니다.") as translate:
            ok, msg = tr.translate_one_chapter(self.path, "codex_cli:working")
        self.assertTrue(ok, msg)
        self.assertEqual(translate.call_count, 1)
        self.assertIn("Second", translate.call_args.args[0])
        self.assertEqual(tr.translation_status(self.path)["state"], "complete")
        self.assertIn("첫 번째", tr.find_translation(self.path).read_text(encoding="utf-8"))

    def test_model_error_stops_before_next_paragraph(self):
        with patch.object(tr, "_translate_paragraph", side_effect=llm.ModelConfigurationError("model 404")) as translate:
            ok, _ = tr.translate_one_chapter(self.path, "codex_cli:bad-model")
        self.assertFalse(ok)
        self.assertEqual(translate.call_count, 1)
        self.assertTrue(tr.translation_status(self.path)["blocked"])
        self.assertEqual(tr.translation_status(self.path)["pending"], 1)

    def test_failed_retranslation_preserves_previous_output(self):
        old = self.path.with_name("01_Test_ko.txt")
        old.write_text("이전 결과", encoding="utf-8")
        with patch.object(tr, "_translate_paragraph", return_value=None):
            tr.translate_one_chapter(self.path, "codex_cli:default")
        self.assertEqual(old.read_text(encoding="utf-8"), "이전 결과")
        self.assertIsNone(tr.find_translation(self.path))


if __name__ == "__main__":
    unittest.main()
