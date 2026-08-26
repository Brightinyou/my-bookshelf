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
