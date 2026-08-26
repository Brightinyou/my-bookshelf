# -*- coding: utf-8 -*-
"""장 나누기 회귀 테스트 — services/chapter_map.

2026-08-26에 «말로 고치기» 채팅을 걷어내면서, 나누기가 **화면에서 고르는 유일한
경로**가 됐다(제목 바꾸기·앞 장에 합치기는 표에서 이미 되고, 채팅의 '다시 나누기'는
실행조차 하지 않았다). 채팅과 함께 그 테스트도 사라졌으므로 여기서 다시 못 박는다.

지키는 것:
  · 고른 자리에서 정확히 둘로 갈린다.
  · **본문 글자는 하나도 잃지 않는다** — 앞뒤를 도로 이으면 원문과 같다.
  · 후보 줄은 '제목처럼 생긴 줄'이고, 검색어로 좁힐 수 있다.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

import config as cfg
from services import chapter_map as cmap

WS = "default"
BOOK = "테스트책"

# ★괄호 안에서 문자열을 이어 붙인 뒤 곱하면 **묶음 전체가** 반복된다.
# 처음에 그렇게 썼다가 4줄을 만들려던 것이 91줄이 됐다.
_HEAD = "첫 장의 앞부분입니다. " * 30
_TAIL = "새 장이 여기서 시작합니다. " * 30
BODY = _HEAD + "\n여기까지가 앞 이야기입니다.\n정든 인공지능과\n" + _TAIL + "\n"


class ChapterSplitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="chsplit_"))
        self._prev = cfg.CHAPTERS_DIR
        cfg.CHAPTERS_DIR = self.tmp
        d = self.tmp / BOOK
        d.mkdir(parents=True)
        (d / "01_첫 장.txt").write_text(BODY, encoding="utf-8")

    def tearDown(self):
        cfg.CHAPTERS_DIR = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _at(self, needle):
        cands, _ = cmap.split_candidates(WS, BOOK, 0, query=needle)
        self.assertTrue(cands, "후보에 %r 가 없다" % needle)
        return cands[0][0]

    def test_검색어로_후보를_좁힌다(self):
        cands, total = cmap.split_candidates(WS, BOOK, 0, query="정든 인공지능과")
        self.assertEqual(len(cands), 1)
        self.assertIn("정든 인공지능과", cands[0][1])
        self.assertEqual(total, 1)

    def test_고른_자리에서_둘로_갈린다(self):
        self.assertTrue(cmap.split_chapter(WS, BOOK, 0, self._at("정든 인공지능과")))
        files = cmap.chapter_files(WS, BOOK)
        self.assertEqual(len(files), 2)
        self.assertIn("정든 인공지능과", files[1].read_text(encoding="utf-8"))

    def test_본문_글자를_잃지_않는다(self):
        """이게 이 파일의 존재 이유다 — 나누다 본문이 사라지면 안 된다."""
        before = "".join(BODY.split())
        cmap.split_chapter(WS, BOOK, 0, self._at("정든 인공지능과"))
        after = "".join("".join(f.read_text(encoding="utf-8").split())
                        for f in cmap.chapter_files(WS, BOOK))
        self.assertEqual(after, before)

    def test_제목을_비우면_그_줄이_제목이_된다(self):
        cmap.split_chapter(WS, BOOK, 0, self._at("정든 인공지능과"), "")
        self.assertIn("정든 인공지능과", cmap.chapter_title(cmap.chapter_files(WS, BOOK)[1]))

    def test_말도_안_되는_자리는_거절한다(self):
        self.assertFalse(cmap.split_chapter(WS, BOOK, 0, 0))
        self.assertFalse(cmap.split_chapter(WS, BOOK, 0, 10 ** 9))
        self.assertFalse(cmap.split_chapter(WS, BOOK, 99, 100))


if __name__ == "__main__":
    unittest.main()


class MissedHeadingsTest(unittest.TestCase):
    """장 목록이 놓친 절 제목 찾기 — services/chapter_map.missed_headings.

    2026-08-26에 실제로 났던 일: reflow가 `Conclusion`을 제 문단으로 남기게 고쳤는데,
    장 목록은 시각 판독이 만들고 그것이 그 제목을 놓쳐서 결론 장이 끝내 생기지 않았다.
    본문에 제 줄로 서 있는 제목을 **알려는 주어야** 한다.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="missed_"))
        self._prev = cfg.CHAPTERS_DIR
        cfg.CHAPTERS_DIR = self.tmp
        self.d = self.tmp / BOOK
        self.d.mkdir(parents=True)

    def tearDown(self):
        cfg.CHAPTERS_DIR = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name, *paras):
        (self.d / name).write_text("\n\n".join(paras) + "\n", encoding="utf-8")

    def test_홀로_선_영문_제목을_찾는다(self):
        self._write("00_제목·초록·서론.txt", "Abstract: something. " * 20)
        self._write("01_Some Chapter.txt", "Body text that runs on. " * 20,
                    "Conclusion", "Although AI does not. " * 20)
        self.assertEqual(cmap.missed_headings(WS, BOOK), [(1, "Conclusion")])

    def test_앞부분_덩어리는_보지_않는다(self):
        """00장은 판권지·초록·저자 자리라 제목처럼 보이는 줄이 널려 있다."""
        self._write("00_머리말.txt", "Body. " * 20, "Mark Coeckelbergh", "More body. " * 20)
        self._write("01_Some Chapter.txt", "Body. " * 20)
        self.assertEqual(cmap.missed_headings(WS, BOOK), [])

    def test_러닝헤더처럼_반복되는_줄은_뺀다(self):
        for n in ("01_A.txt", "02_B.txt"):
            self._write(n, "Body. " * 20, "Some Running Header", "More. " * 20)
        self.assertEqual(cmap.missed_headings(WS, BOOK), [])

    def test_숫자가_든_줄과_긴_문장_조각은_뺀다(self):
        self._write("01_A.txt", "Body. " * 20,
                    "AI and Ethics (2025) 5:5527",
                    "According to Kant, anyone who violates rights does not",
                    "More. " * 20)
        self.assertEqual(cmap.missed_headings(WS, BOOK), [])

    def test_한글_책에서는_보지_않는다(self):
        """한글 책의 한 줄짜리 라틴 문단은 제목이 아니라 미주의 인용 조각이다."""
        self._write("01_A.txt", "한국어 본문이 길게 이어집니다. " * 20,
                    "Publishing Company", "계속 이어집니다. " * 20)
        self.assertEqual(cmap.missed_headings(WS, BOOK), [])


class LeadTitleForTest(unittest.TestCase):
    def test_초록이_있으면_논문으로_본다(self):
        self.assertEqual(cmap.lead_title_for("Title\n\nAbstract: Modern developments"),
                         cmap.LEAD_TITLE_PAPER)

    def test_초록이_없으면_머리말(self):
        self.assertEqual(cmap.lead_title_for("어떤 책의 앞머리 글"), cmap.LEAD_TITLE)


class AutoBoundarySplitTest(unittest.TestCase):
    """'결론'·'서론'에서는 묻지 않고 나눈다 — chapter_map.auto_split_known_headings.

    알려만 주고 사람이 «장 나누기»에서 누르게 했더니 "너무 번거롭다"는 지적을 받았다
    (2026-08-26 연구자). 다만 아무 제목에나 하지는 않는다 — 절 제목까지 장으로 삼으면
    책이 잘게 부서진다. 자동으로 나누는 낱말은 _BOUNDARY_WORDS 로 못 박혀 있다.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="autosp_"))
        self._prev = cfg.CHAPTERS_DIR
        cfg.CHAPTERS_DIR = self.tmp
        self.d = self.tmp / BOOK
        self.d.mkdir(parents=True)

    def tearDown(self):
        cfg.CHAPTERS_DIR = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name, *paras):
        (self.d / name).write_text("\n\n".join(paras) + "\n", encoding="utf-8")

    def _titles(self):
        return [cmap.chapter_title(f) for f in cmap.chapter_files(WS, BOOK)]

    def test_영문_결론에서_나눈다(self):
        self._write("01_Body.txt", "Body text. " * 20, "Conclusion", "Although AI. " * 20)
        self.assertEqual(cmap.auto_split_known_headings(WS, BOOK), ["Conclusion"])
        self.assertIn("Conclusion", self._titles())

    def test_한글_결론에서도_나눈다(self):
        self._write("01_본문.txt", "본문이 이어집니다. " * 20, "결론", "정리하면 이렇습니다. " * 20)
        self.assertEqual(cmap.auto_split_known_headings(WS, BOOK), ["결론"])

    def test_번호가_붙어도_알아본다(self):
        self._write("01_본문.txt", "본문. " * 20, "IV. 결론", "정리하면. " * 20)
        self.assertEqual(cmap.auto_split_known_headings(WS, BOOK), ["IV. 결론"])

    def test_같은_낱말로는_한_번만_나눈다(self):
        """장 안에 남은 목차나 러닝헤더가 다시 걸리는 것을 막는다."""
        self._write("01_A.txt", "본문. " * 20, "결론", "정리. " * 20, "결론", "또 정리. " * 20)
        self.assertEqual(cmap.auto_split_known_headings(WS, BOOK), ["결론"])

    def test_경계_낱말이_아니면_두지_않는다(self):
        self._write("01_A.txt", "Body. " * 20, "Privacy, Security, and Safety", "More. " * 20)
        self.assertEqual(cmap.auto_split_known_headings(WS, BOOK), [])

    def test_문단_한가운데_낱말은_건드리지_않는다(self):
        """홀로 선 문단이라야 제목이다 — 본문 속 '결론'은 그냥 낱말이다."""
        self._write("01_A.txt", "이 결론은 본문 한가운데 있는 낱말입니다. " * 20)
        self.assertEqual(cmap.auto_split_known_headings(WS, BOOK), [])

    def test_장의_맨_앞이면_이미_경계다(self):
        self._write("01_A.txt", "Conclusion", "Although AI. " * 20)
        self.assertEqual(cmap.auto_split_known_headings(WS, BOOK), [])

    def test_boundary_word_는_핵심_낱말을_돌려준다(self):
        self.assertEqual(cmap.boundary_word("1. Introduction"), "introduction")
        self.assertEqual(cmap.boundary_word("INTRODUCTION"), "introduction")
        self.assertEqual(cmap.boundary_word("들어가는 말"), "들어가는말")
        self.assertEqual(cmap.boundary_word("본문입니다"), "")
