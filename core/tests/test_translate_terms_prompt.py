# -*- coding: utf-8 -*-
"""번역 지시문의 용어 규칙 — services/translate.build_translate_system.

2026-10-04 연구자 보고: 번역본 본문에 agent·accountability·ethics 같은 낱말이
영어로 남았다(『AI and Ethics When Human Beings Collaborate With AI Agents』 109단락 중
42단락). 지시문의 «Preserve technical terms … as-is» 를 모델이 «학술 용어는 영어로
둔다»로 읽었기 때문이다. 연구자가 정한 규칙은 «고유명사·보통명사 다 번역하고
(원어)를 넣는다»이다.

실제 엔진(codex_cli:default)으로 같은 세 단락을 비교한 결과, 본문에 남은 영어 낱말이
45개 → 2개(둘 다 원문이 낱말 자체를 다루는 responsabilidad·“responsibility”)였다.
여기서는 그 규칙이 지시문에서 다시 빠지지 않게 못 박는다.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import translate as tr


class TranslateTermsPromptTest(unittest.TestCase):
    def test_학술_용어를_원어로_두라는_지시가_없다(self):
        prompt = tr.build_translate_system("en", "ko")
        self.assertNotIn("Preserve technical terms", prompt)

    def test_모든_낱말을_번역하고_첫_등장에_원어를_붙인다(self):
        prompt = tr.build_translate_system("en", "ko")
        self.assertIn("Translate EVERY word into Korean, including technical terms", prompt)
        self.assertIn("original in parentheses", prompt)
        self.assertIn("책무성(accountability)", prompt)

    def test_제목도_번역_대상이다(self):
        self.assertIn("titles of works", tr.build_translate_system("en", "ko").split("Keep as-is only")[0])

    def test_한국어_예시는_한국어_도착일_때만(self):
        prompt = tr.build_translate_system("en", "de")
        self.assertIn("Translate EVERY word into German", prompt)
        self.assertNotIn("책무성", prompt)


OLD_STYLE = ("AI 시스템의 행위는 윤리적 기준을 따른다. 그러나 patient-oriented ethics에서는 "
             "accountability, responsibility, liability를 구분한다.")
NEW_STYLE = "AI 시스템의 행위는 윤리적 기준을 따른다. 그러나 피행위자 중심 윤리(patient-oriented ethics)에서는 책무성을 구분한다."


class TermsRedoTest(unittest.TestCase):
    def test_괄호_속_원어는_세지_않는다(self):
        self.assertEqual(tr.leftover_source_words(NEW_STYLE), 0)
        self.assertGreaterEqual(tr.leftover_source_words(OLD_STYLE), 5)

    def test_예전_규칙_단락만_다시_번역_대상(self):
        self.assertTrue(tr.needs_terms_redo({"tgt": OLD_STYLE}, "ko"))
        self.assertFalse(tr.needs_terms_redo({"tgt": NEW_STYLE}, "ko"))
        # 새 규칙으로 번역한 단락은 원어가 남아도 되풀이하지 않는다(낱말 자체를 다루는 대목 등).
        self.assertFalse(tr.needs_terms_redo({"tgt": OLD_STYLE, "terms": tr.TERMS_RULE}, "ko"))
        # 라틴 문자권 도착언어는 셀 수 없으므로 건드리지 않는다.
        self.assertFalse(tr.needs_terms_redo({"tgt": OLD_STYLE}, "de"))


class TermsRedoChapterTest(unittest.TestCase):
    """이미 번역된 장을 다시 돌리면 원어가 남은 단락만 AI 에 다시 묻는다."""

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

    def test_원어가_남은_단락만_다시_번역한다(self):
        with patch.object(tr, "_translate_paragraph", side_effect=["첫 번째 완성된 문장이다.", OLD_STYLE]):
            ok, msg = tr.translate_one_chapter(self.path, "codex_cli:default")
        self.assertTrue(ok, msg)
        # 예전 규칙으로 만든 캐시를 흉내 낸다 — «terms» 표시를 지운다.
        cache_path = self.path.with_name("01_Test_ko.cache.json")
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        for row in cache["entries"].values():
            row.pop("terms", None)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

        with patch.object(tr, "_translate_paragraph", return_value=NEW_STYLE) as translate:
            ok, msg = tr.translate_one_chapter(self.path, "codex_cli:default")
        self.assertTrue(ok, msg)
        self.assertEqual(translate.call_count, 1)
        self.assertIn("Second", translate.call_args.args[0])
        out = tr.find_translation(self.path).read_text(encoding="utf-8")
        self.assertIn("첫 번째", out)
        self.assertIn("책무성", out)

        # 새 규칙 단락은 표시가 붙어 세 번째에는 아무것도 다시 묻지 않는다.
        with patch.object(tr, "_translate_paragraph") as translate:
            ok, _ = tr.translate_one_chapter(self.path, "codex_cli:default")
        self.assertTrue(ok)
        self.assertEqual(translate.call_count, 0)


if __name__ == "__main__":
    unittest.main()
