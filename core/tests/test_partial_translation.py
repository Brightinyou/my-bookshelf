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

    def test_stop_request_halts_before_the_next_paragraph(self):
        # «현재 항목 후 중단»이 문서 경계에서만 들어 수백 단락을
        # 끝내 번역하고서야 멈추던 것 (2026-09-09).
        with patch.object(tr.jobs, "stop_requested", side_effect=[False, True]),                 patch.object(tr, "_translate_paragraph", return_value="첫 번째 완성된 문장입니다.") as translate:
            ok, msg = tr.translate_one_chapter(self.path, "codex_cli:default")
        self.assertFalse(ok)
        self.assertIn("중단됨", msg)
        self.assertEqual(translate.call_count, 1)
        status = tr.translation_status(self.path)
        self.assertTrue(status["stopped"])
        self.assertEqual(status["pending"], 1)
        self.assertIsNone(tr.find_translation(self.path))
        # 멈춘 자리부터 이어한다 — 이미 된 단락은 다시 물지 않는다.
        with patch.object(tr, "_translate_paragraph", return_value="두 번째 완성된 문장입니다.") as translate:
            ok, msg = tr.translate_one_chapter(self.path, "codex_cli:default")
        self.assertTrue(ok, msg)
        self.assertEqual(translate.call_count, 1)
        self.assertEqual(tr.translation_status(self.path)["state"], "complete")

    def test_repeated_failure_gives_up_on_the_document(self):
        # 사용량 한도처럼 다음 단락이라고 나아질 이유가 없는 고장을
        # 끝까지 물고 다니며 시간을 버리지 않는다 (2026-09-09).
        path = Path(self.tmp.name) / "02_Test.txt"
        path.write_text("\n\n".join(f"This is a complete sentence about topic {n}."
                                    for n in range(tr.FAIL_STREAK_LIMIT * 3)), encoding="utf-8")
        with patch.object(tr, "_translate_paragraph", return_value=None) as translate:
            ok, msg = tr.translate_one_chapter(path, "codex_cli:default")
        self.assertFalse(ok)
        self.assertEqual(translate.call_count, tr.FAIL_STREAK_LIMIT)
        self.assertTrue(tr.translation_status(path)["blocked"])

    def test_usage_limit_is_fatal_not_one_more_paragraph(self):
        hit = RuntimeError("codex CLI exit 1: ERROR: You've hit your usage limit. Upgrade to Pro")
        self.assertTrue(llm.usage_limit_error(hit))
        self.assertFalse(llm.usage_limit_error(RuntimeError("connection reset")))
        with patch.object(tr.llm, "complete", side_effect=hit):
            with self.assertRaises(llm.ModelConfigurationError):
                tr.translate("Some source text.", "codex_cli:default")

    def test_failed_retranslation_preserves_previous_output(self):
        old = self.path.with_name("01_Test_ko.txt")
        old.write_text("이전 결과", encoding="utf-8")
        with patch.object(tr, "_translate_paragraph", return_value=None):
            tr.translate_one_chapter(self.path, "codex_cli:default")
        self.assertEqual(old.read_text(encoding="utf-8"), "이전 결과")
        self.assertIsNone(tr.find_translation(self.path))

    def test_usage_limit_stops_real_paragraph_retry_and_preserves_resume(self):
        hit = RuntimeError("codex CLI exit 1: " + "source " * 100
                           + "ERROR: You've hit your usage limit.")
        with patch.object(tr.llm, "complete", side_effect=["첫 번째 완성된 문장입니다.", hit]) as complete:
            ok, _ = tr.translate_one_chapter(self.path, "codex_cli:default")
        self.assertFalse(ok)
        self.assertEqual(complete.call_count, 2)
        status = tr.translation_status(self.path)
        self.assertTrue(status["blocked"])
        self.assertEqual(status["translated"], 1)
        self.assertIn("usage limit", status["error"])
        self.assertTrue(any("usage limit" in str(call) for call in tr.append_log.call_args_list))
        with patch.object(tr.llm, "complete", return_value="두 번째 완성된 문장입니다.") as complete:
            ok, msg = tr.translate_one_chapter(self.path, "codex_cli:default")
        self.assertTrue(ok, msg)
        self.assertEqual(complete.call_count, 1)

    def test_title_usage_limit_blocks_following_chapters(self):
        with patch.object(tr, "_translate_paragraph", return_value="완성된 번역 문장입니다."), \
                patch.object(tr, "translate_title", side_effect=llm.ModelConfigurationError("usage limit")):
            ok, _ = tr.translate_one_chapter(self.path, "codex_cli:default")
        self.assertFalse(ok)
        self.assertTrue(tr.translation_status(self.path)["blocked"])
        self.assertIsNone(tr.find_translation(self.path))


if __name__ == "__main__":
    unittest.main()
