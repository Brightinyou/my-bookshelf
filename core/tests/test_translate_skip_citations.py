"""서지 조각 보존·참고문헌 장 건너뛰기 (2026-09-30 연구자 PC 실측).

Butlin 외 2026 «07_References» 번역에서 «실패 4단락»이 났다. 모두 PDF 줄바꿈에 잘린
서지 조각(«0020174X.2024.2434860»·«arXiv.2411.00986»·«pp. 327–336, Blackwell»·
«Neurosci. Conscious. 2024, niae013»)이라 AI 가 그대로 돌려주면 실패로 세고 두세 번씩
다시 물었다.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
from pathlib import Path  # noqa: E402
from unittest import mock  # noqa: E402
import json  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402

from services import translate as tr  # noqa: E402

FRAGMENTS = ["Neurosci. Conscious. 2024, niae013", "0020174X.2024.2434860", "arXiv.2411.00986",
             "pp. 327–336, Blackwell", "arXiv:2308.08708v3",
             "Braidotti, Rosi. 2019. Posthuman Knowledge. Cambridge: Polity Press."]
PROSE = ["Dr. Smith argued this in 2020.", "The theory of mind.",
         "In 2024, researchers proposed new indicators.", "Section 2.3.1", "Global workspace theory",
         "St. Augustine wrote Confessions.", "See Fig. 3 and Tab. 2 for details.",
         "Consciousness in Artificial Intelligence: Insights from the Science of Consciousness"]


class CitationFragmentTest(unittest.TestCase):
    def test_short_bibliographic_fragments_are_preserved(self):
        for s in FRAGMENTS:
            self.assertIsNotNone(tr.skip_reason(s), s)

    def test_short_prose_is_still_translated(self):
        for s in PROSE:
            self.assertIsNone(tr.skip_reason(s), s)


class ReferenceChapterTest(unittest.TestCase):
    def test_titles(self):
        for n in ("07_References.txt", "12_Bibliography.txt", "09_참고문헌.txt", "10_참고 문헌.txt",
                  "05_Works Cited.txt", "11_Literaturverzeichnis.txt"):
            self.assertTrue(tr.is_reference_chapter(Path(n)), n)
        for n in ("03_Notes.txt", "09_부록.txt", "02_References to God in Scripture.txt",
                  "01_Introduction.txt"):
            self.assertFalse(tr.is_reference_chapter(Path(n)), n)

    def _run(self, skip_on: bool):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ch = Path(tmp.name) / "Some Paper" / "07_References.txt"
        ch.parent.mkdir()
        ch.write_text("Butlin, P. and Long, R. (2025) Identifying indicators of consciousness in AI "
                      "systems. Trends Cogn. Sci. 29, 1-3.\n\nSome other entry in the reference list "
                      "that reads like a sentence and is quite long indeed.", encoding="utf-8")
        with mock.patch.object(tr.llm, "get_pref",
                               side_effect=lambda k, d=None: skip_on if k == "skip_reference_chapters" else d), \
             mock.patch.object(tr.llm, "complete", return_value="한국어로 번역된 참고문헌 문장이다.") as call, \
             mock.patch.object(tr, "target_language", return_value="ko"), \
             mock.patch.object(tr, "translate_title", return_value="참고문헌"), \
             mock.patch.object(tr.jobs, "stop_requested", return_value=False):
            ok, msg = tr.translate_one_chapter(ch, "codex_cli:gpt-x")
        return ch, ok, msg, call

    def test_reference_chapter_is_kept_in_original_without_ai(self):
        ch, ok, msg, call = self._run(skip_on=True)
        self.assertTrue(ok, msg)
        self.assertIn("참고문헌", msg)
        call.assert_not_called()
        ko = ch.with_name("07_References_ko.txt")
        self.assertEqual(ko.read_text(encoding="utf-8"), ch.read_text(encoding="utf-8"))
        status = json.loads(ch.with_name("07_References_ko.status.json").read_text(encoding="utf-8"))
        self.assertEqual(status.get("skipped"), "references")

    def test_switch_off_translates_it(self):
        _ch, _ok, _msg, call = self._run(skip_on=False)
        self.assertTrue(call.called)


if __name__ == "__main__":
    unittest.main()
