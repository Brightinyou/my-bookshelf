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


class AnthologyGuardTest(unittest.TestCase):
    """소논문 모음에서는 「들어가는 말」·「나가는 말」에서 가르지 않는다 (2026-09-21).

    『기술윤리』(HTSN 논문집) 실측: 논문마다 있는 절 제목이 낱말별로 한 번씩 장이
    되어 「I. 들어가는 말」·「V. 나가는 말」·「I. 들어가며」·「III. 맺는말」·「VII. 나가며」
    가 장으로 잡히고, 그 앞 논문 제목 장은 97자짜리 껍데기가 됐다. 한 권짜리 책(서론
    하나·결론 하나)은 예전처럼 가른다 — 연구자: "이것은 소논문이 묶인 경우만 해당".
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="antho_"))
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

    def test_논문마다_여는_말이_다른_꼴로_있으면_손대지_않는다(self):
        self._write("01_첫 논문.txt", "I. 들어가는 말", "본문. " * 20, "V. 나가는 말", "정리. " * 20)
        self._write("02_둘째 논문.txt", "I. 들어가며", "본문. " * 20, "IV. 맺으며", "정리. " * 20)
        self.assertEqual(cmap.auto_split_known_headings(WS, BOOK), [])
        self.assertEqual(self._titles(), ["첫 논문", "둘째 논문"])

    def test_같은_절_제목이_세_번이면_모음집이다(self):
        for k in (1, 2, 3):
            self._write(f"0{k}_논문 {k}.txt", "본문. " * 20, "결론", "정리. " * 20)
        self.assertEqual(cmap.auto_split_known_headings(WS, BOOK), [])

    def test_한_권짜리_책은_예전처럼_가른다(self):
        self._write("01_본문.txt", "본문. " * 20, "결론", "정리. " * 20)
        self.assertEqual(cmap.auto_split_known_headings(WS, BOOK), ["결론"])

    def test_두_번_나온_같은_낱말은_목차_잔재로_보고_한_번_가른다(self):
        """『서양철학사』「머 리 말」×2 — 모음집이 아니라 장 안에 남은 목차다."""
        self._write("01_A.txt", "본문. " * 20, "결론", "정리. " * 20, "결론", "또 정리. " * 20)
        self.assertEqual(cmap.auto_split_known_headings(WS, BOOK), ["결론"])

    def test_이미_절_제목으로_갈라진_장을_찾아낸다(self):
        self._write("01_첫 논문.txt", "제목뿐인 장")
        self._write("02_I. 들어가는 말.txt", "본문. " * 20)
        self._write("03_V. 나가는 말.txt", "정리. " * 20)
        self._write("04_둘째 논문.txt", "본문. " * 20)
        self._write("05_I. 들어가며.txt", "본문. " * 20)
        self.assertEqual(cmap.section_title_chapters(WS, BOOK), [1, 2, 4])
        found = " ".join(cmap.review_findings(WS, BOOK))
        self.assertIn("절 제목이 장으로", found)
        self.assertIn("본문이 거의 없는 장", found)

    def test_한_권짜리_책의_서론_장은_절_제목이_아니다(self):
        self._write("01_서론.txt", "본문. " * 20)
        self._write("02_본론.txt", "본문. " * 20)
        self._write("03_결론.txt", "정리. " * 20)
        self.assertEqual(cmap.section_title_chapters(WS, BOOK), [])

    def test_새_낱말도_알아본다(self):
        self.assertEqual(cmap.boundary_word("IV. 맺으며"), "맺으며")
        self.assertEqual(cmap.boundary_word("IX. 나오는 말"), "나오는말")


class PageMapTest(unittest.TestCase):
    """챕터 파일의 자리를 원본 쪽 번호로 옮긴다 — chapter_map.PageMap (2026-09-21)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pagemap_"))
        self._prev = (cfg.CHAPTERS_DIR, cfg.TXT_DIR, cfg.TXT_ARCHIVE_DIR)
        cfg.CHAPTERS_DIR = self.tmp / "ch"
        cfg.TXT_DIR = self.tmp / "txt"
        cfg.TXT_ARCHIVE_DIR = self.tmp / "txt" / "done"
        self.d = cfg.CHAPTERS_DIR / BOOK
        self.d.mkdir(parents=True)
        cfg.TXT_ARCHIVE_DIR.mkdir(parents=True)
        # 원본: 4쪽. 챕터는 공백만 다르게 이어 붙인 것.
        pages = ["첫 장 첫 쪽입니다.", "첫 장 둘째 쪽입니다.", "둘째 장 시작\n본문입니다.", "둘째 장 끝 쪽."]
        (cfg.TXT_ARCHIVE_DIR / f"{BOOK}.txt").write_text("\f".join(pages), encoding="utf-8")
        (self.d / "01_첫 장.txt").write_text("첫 장 첫 쪽입니다.\n\n첫 장 둘째 쪽입니다.\n", encoding="utf-8")
        (self.d / "02_둘째 장.txt").write_text("둘째 장 시작\n\n본문입니다. 둘째 장 끝 쪽.\n", encoding="utf-8")

    def tearDown(self):
        cfg.CHAPTERS_DIR, cfg.TXT_DIR, cfg.TXT_ARCHIVE_DIR = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_장마다_쪽_범위를_센다(self):
        pm = cmap.PageMap(WS, BOOK)
        self.assertTrue(pm.ok)
        self.assertEqual(pm.chapter_range(0), (1, 2))
        self.assertEqual(pm.chapter_range(1), (3, 4))

    def test_장_안의_자리도_쪽으로_옮긴다(self):
        pm = cmap.PageMap(WS, BOOK)
        self.assertEqual(pm.page_at(1, "둘째 장 시작\n\n본문입니다. "), 4)
        self.assertEqual(pm.page_at(0, ""), 1)

    def test_글자_수가_어긋나면_모른다고_한다(self):
        (self.d / "02_둘째 장.txt").write_text("손으로 고쳐서 원본과 다릅니다.\n", encoding="utf-8")
        pm = cmap.PageMap(WS, BOOK)
        self.assertFalse(pm.ok)
        self.assertIsNone(pm.chapter_range(0))

    def test_원본이_없으면_모른다고_한다(self):
        (cfg.TXT_ARCHIVE_DIR / f"{BOOK}.txt").unlink()
        self.assertFalse(cmap.PageMap(WS, BOOK).ok)


class AuthorAnthologyTest(unittest.TestCase):
    """글마다 저자가 다르면 논문집이다 (2026-09-21 연구자) — chapter_map.note_authors."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="authors_"))
        self._prev = cfg.CHAPTERS_DIR
        cfg.CHAPTERS_DIR = self.tmp
        self.d = self.tmp / BOOK
        self.d.mkdir(parents=True)
        (self.d / "01_첫 논문.txt").write_text("본문. " * 20 + "\n\n결론\n\n" + "정리. " * 20 + "\n", encoding="utf-8")
        (self.d / "02_둘째 논문.txt").write_text("본문. " * 20 + "\n", encoding="utf-8")

    def tearDown(self):
        cfg.CHAPTERS_DIR = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_저자가_둘_이상이면_결론_하나여도_가르지_않는다(self):
        self.assertTrue(cmap.note_authors(WS, BOOK, {"첫 논문": "김철수", "둘째 논문": "이영희"}))
        self.assertIn("저자가 다릅니다", cmap.is_anthology(WS, BOOK))
        self.assertEqual(cmap.auto_split_known_headings(WS, BOOK), [])

    def test_저자가_한_사람이면_책이다(self):
        self.assertFalse(cmap.note_authors(WS, BOOK, {"첫 논문": "김철수", "둘째 논문": "김철수"}))
        self.assertEqual(cmap.auto_split_known_headings(WS, BOOK), ["결론"])

    def test_표시는_지도를_다시_써도_남는다(self):
        cmap.note_authors(WS, BOOK, {"첫 논문": "김철수", "둘째 논문": "이영희"})
        cmap.save_map(WS, BOOK, mode="visual", confirmed=False)
        m = cmap.load_map(WS, BOOK)
        self.assertTrue(m["anthology"])
        self.assertEqual(m["authors"]["둘째 논문"], "이영희")

    def test_저자_표시가_있으면_절_제목_장을_하나만_있어도_잡는다(self):
        cmap.note_authors(WS, BOOK, {"첫 논문": "김철수", "둘째 논문": "이영희"})
        (self.d / "03_결론.txt").write_text("정리. " * 20 + "\n", encoding="utf-8")
        self.assertEqual(cmap.section_title_chapters(WS, BOOK), [2])
