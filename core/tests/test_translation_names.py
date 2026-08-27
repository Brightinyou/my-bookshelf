# -*- coding: utf-8 -*-
"""번역본 파일 이름 규칙 — services/translate.

2026-08-26 이전에는 도착언어와 무관하게 늘 `_ko.txt`였다. 한국어→스페인어처럼
한국어가 도착언어가 아닐 때 이름이 사실과 어긋나서 바꿨다.

여기서 못 박는 것은 둘이다.
  · 새로 만드는 번역본은 도착언어를 따른다.
  · **이미 만들어 둔 `_ko.txt`는 계속 찾아진다** — 도착언어를 바꿔도 예전
    번역본이 사라지면 안 된다(실제로 47챕터가 그 이름으로 저장돼 있다).
"""
import tempfile
import unittest
from pathlib import Path

from services import translate as tr


class TranslationNameTest(unittest.TestCase):
    def setUp(self):
        self.prev = tr.target_language()
        self.tmp = Path(tempfile.mkdtemp(prefix="trname_"))
        self.ch = self.tmp / "01_Some Chapter.txt"
        self.ch.write_text("body", encoding="utf-8")

    def tearDown(self):
        tr.set_target_language(self.prev)

    def test_도착언어가_한국어면_예전과_같은_이름(self):
        tr.set_target_language("ko")
        self.assertEqual(tr.translated_path(self.ch).name, "01_Some Chapter_ko.txt")

    def test_도착언어를_바꾸면_이름도_바뀐다(self):
        tr.set_target_language("es")
        self.assertEqual(tr.translated_path(self.ch).name, "01_Some Chapter_es.txt")

    def test_예전_ko_번역본은_도착언어가_달라도_찾아진다(self):
        """이게 이 파일의 존재 이유다 — 기존 번역본이 미아가 되면 안 된다."""
        old = self.ch.with_name(self.ch.stem + "_ko.txt")
        old.write_text("옛 번역본", encoding="utf-8")
        tr.set_target_language("es")
        self.assertEqual(tr.find_translation(self.ch), old)
        self.assertTrue(tr.has_translation(self.ch))

    def test_현재_도착언어_번역본이_있으면_그것을_먼저(self):
        self.ch.with_name(self.ch.stem + "_ko.txt").write_text("ko", encoding="utf-8")
        es = self.ch.with_name(self.ch.stem + "_es.txt")
        es.write_text("es", encoding="utf-8")
        tr.set_target_language("es")
        self.assertEqual(tr.find_translation(self.ch), es)

    def test_번역본이_없으면_None(self):
        tr.set_target_language("ko")
        self.assertIsNone(tr.find_translation(self.ch))

    def test_파생물_판정은_모든_언어_접미사를_안다(self):
        for stem in ("01_x_ko", "01_x_es", "01_x_ja", "01_x_wiki",
                     "01_x_bilingual", "01_x_clean"):
            self.assertTrue(tr.is_derived(stem), stem)
        self.assertFalse(tr.is_derived("01_Some Chapter"))


class 쪽을걸친문장Test(unittest.TestCase):
    """쪽 경계에서 끊긴 문장을 하나로 이어 번역에 넘긴다 (2026-08-27 연구자 요청).

    연구자 말 — "페이지와 페이지를 넘어갈 때 문장이 끊겨서 번역이 되다보니 어색한
    곳이 곳곳에 보여. 다음페이지로 가기 전에 문장마침이 되지 않으면 다음 페이지의
    문장까지 보고 번역한다라는 원칙이 있으면 좋겠는데".

    _merge_dangling 은 예전부터 «종결부호 없이 끝나면 잇는다»를 했지만, 각주와
    쪽표식을 만나면 그 자리에서 내보내 버려 **이을 기회가 오지 않았다.** 실제 논문
    흐름이 «본문 … 각주 각주 각주 [[PAGEBREAK]] 다음쪽 본문» 이라 늘 막혔다.
    """

    def test_쪽표식을_건너뛰고_이어_붙인다(self):
        P = tr._PAGE_TOKEN
        out = tr._merge_dangling(["문장이 끊기고 우리의 기준이", P, "계속 이어진다."])
        self.assertEqual(out[0], "문장이 끊기고 우리의 기준이 계속 이어진다.")
        self.assertIn(P, out, "쪽표식은 남아야 한다 — 없으면 번역본에 \f 가 안 남는다")

    def test_각주가_사이에_끼어도_이어_붙인다(self):
        P = tr._PAGE_TOKEN
        out = tr._merge_dangling(
            ["왜냐하면 우리의 기준이",
             "34 For example, Saint Gregory of Nyssa.",
             "35 For a detailed argumentation.",
             P,
             "과연 지능이 무엇인지 묻게 된다."])
        self.assertEqual(out[0], "왜냐하면 우리의 기준이 과연 지능이 무엇인지 묻게 된다.")
        self.assertTrue(out[1].startswith("34 "), "각주는 홀로 서야 한다")
        self.assertTrue(out[2].startswith("35 "))
        self.assertIn(P, out)

    def test_문장이_끝났으면_잇지_않는다(self):
        P = tr._PAGE_TOKEN
        out = tr._merge_dangling(["문장이 끝난다.", P, "새 문장이다."])
        self.assertEqual(out, ["문장이 끝난다.", P, "새 문장이다."])

    def test_제목은_단독으로_남는다(self):
        P = tr._PAGE_TOKEN
        out = tr._merge_dangling(["# 제목", P, "본문이 시작된다."])
        self.assertEqual(out[0], "# 제목")


if __name__ == "__main__":
    unittest.main()


class NeedsTranslationTargetTest(unittest.TestCase):
    """제목만 보고 하는 임시 판단도 **도착언어**를 따라야 한다 (2026-08-26).

    예전에는 '제목에 한글이 없으면 번역 필요'가 박혀 있어서, 도착언어를 스페인어로
    바꿔도 한국어 책은 번역 대상이 되지 않았다."""

    def setUp(self):
        self.prev = tr.target_language()

    def tearDown(self):
        tr.set_target_language(self.prev)

    def test_도착언어가_한국어면_예전_동작_그대로(self):
        tr.set_target_language("ko")
        self.assertTrue(tr._needs_translation("Robot Ethics"))
        self.assertFalse(tr._needs_translation("기술신학"))

    def test_도착언어가_스페인어면_한국어_책도_번역_대상(self):
        tr.set_target_language("es")
        self.assertTrue(tr._needs_translation("기술신학"))


class FootnoteBlockKeptTest(unittest.TestCase):
    """번역 입력에서 각주 문단이 살아남는가 — services/translate.

    2026-08-27. 변환 단계에서 각주를 제 문단으로 떼어 냈는데도 EPUB에서 여전히
    본문과 섞여 나왔다. 범인은 번역 전처리였다 — `_merge_short_blocks`가 50자 미만
    블록을 뒤에 붙이고(`3 Psalm 8:4.` 는 12자다), `_merge_dangling`이 종결부호 없는
    앞 문단에 또 붙였다. 실측: 원문 162문단/각주 15개 → 번역입력 45문단/각주 4개.
    각주는 어차피 번역하지 않으므로 홀로 두어야 한다.
    """

    # ★문단이 5개 미만이면 _split_paragraphs_robust 가 2차(줄 단위 청크)로 빠져
    # 구조를 통째로 버린다. 실제 챕터는 수십 문단이므로 표본도 그만큼 준다.
    BODY = ["본문이 길게 이어지는 %d번째 문단입니다. " % i * 4 for i in range(6)]

    def test_짧은_각주가_앞_문단에_먹히지_않는다(self):
        txt = "\n\n".join(self.BODY[:3] + ["3 Psalm 8:4.", "4 Genesis 1:26."] + self.BODY[3:])
        paras = tr._split_paragraphs_robust(txt)
        self.assertIn("3 Psalm 8:4.", paras)
        self.assertIn("4 Genesis 1:26.", paras)

    def test_각주_다음_문단도_각주에_붙지_않는다(self):
        note = "1 David Silver, “AlphaGo,” Nature, 2016."
        txt = "\n\n".join(self.BODY[:3] + [note] + self.BODY[3:])
        self.assertIn(note, tr._split_paragraphs_robust(txt))

    def test_각주가_아닌_짧은_블록은_예전대로_합친다(self):
        """짧다고 버리면 본문이 사라진다 — 그 동작은 지켜야 한다."""
        blocks = ["짧은 줄", "또 짧은 줄", "세 번째 짧은 줄"]
        self.assertLess(len(tr._merge_short_blocks(blocks, 50)), len(blocks))


class PageBreakSurvivesTest(unittest.TestCase):
    """쪽 구분자(\f)가 번역을 넘어 살아남는가 — services/translate.

    2026-08-27. EPUB 각주 변환기(services/footnotes)는 **쪽 단위**로 각주 묶음을
    찾는데, 번역본에 \f 가 하나도 없어 문서 전체를 한 쪽으로 보고 각주를 거의 못
    잡았다 — 1번 각주 뒤에 본문이 통째로 이어져 보였다. 챕터 원문에는 \f 가 있었다.
    """

    BODY = ["본문 문단이 충분히 깁니다. " * 5 for _ in range(5)]

    def test_표식이_제_문단으로_살아남는다(self):
        txt = ("\n\n".join(self.BODY[:2]) + "\n\n" + tr._PAGE_TOKEN + "\n\n"
               + "\n\n".join(self.BODY[2:]))
        self.assertIn(tr._PAGE_TOKEN, tr._split_paragraphs_robust(txt))

    def test_표식은_번역하지_않는다(self):
        self.assertTrue(tr.should_skip_translation(tr._PAGE_TOKEN))

    def test_긴_각주도_홀로_둔다(self):
        """연구자 지적: "각주에서 긴 문장이라 하더라도 마지막 마침표까지는 확인해야."
        500자 제한이던 시절, 544자짜리 서지 각주(책 네 권 나열)가 각주로 인정받지
        못하고 앞 본문 문단에 합쳐져 EPUB에서 통째로 사라졌다."""
        long_note = ("5 imago Dei 해석 검토로는 "
                     + "여러 책과 저자를 길게 나열한다. " * 120).strip()
        self.assertGreater(len(long_note), 2000)   # 길이 조건이 아예 없어야 통과한다
        self.assertTrue(tr._is_footnote_block(long_note))
        txt = "\n\n".join(self.BODY[:2] + [long_note] + self.BODY[2:])
        self.assertIn(long_note, tr._split_paragraphs_robust(txt))
