# -*- coding: utf-8 -*-
"""장 제목 → 파일 이름 회귀 테스트 — services/chapter_map._safe.

이 장치의 존재 이유(연구자 지적, 2026-08-25): 장 제목을 고쳤는데 넣은 낱말이
사라졌다. 원인은 둘이었다.

  ① 쓸 수 없는 글자(`:`)를 **공백**으로 바꿔 `과제와 전망: 인간과`가
     `과제와 전망  인간과`가 됐다 — 부제가 붙은 자리인지 알 수 없고 공백만 뭉친다.
  ② **50자에서 잘라 냈다** — 한글 52자(130바이트) 제목이 잘려 `가치로서 ‘`로 끝났다.
     파일 이름 한도는 255바이트라 한참 여유가 있었다.

★그리고 **원래 제목에 있던 하이픈은 건드리지 않아야** 한다(`co-evolution`).
"""
import unittest

from services.chapter_map import MAX_TITLE_BYTES, _safe


class SafeTitleTest(unittest.TestCase):
    def test_콜론은_대시로_바뀐다(self):
        got = _safe("첨단기술 시대, 신학의 과제와 전망: 인간과 기술의 공진화")
        self.assertIn("전망 - 인간과", got)
        self.assertNotIn(":", got)

    def test_원래_있던_하이픈은_그대로_둔다(self):
        """★`co-evolution`을 `co - evolution`으로 벌리면 안 된다."""
        got = _safe("공진화(co-evolution)에 대한 신학적 성찰")
        self.assertIn("co-evolution", got)

    def test_긴_제목이_잘리지_않는다(self):
        t = "정든 인공지능과 정 많은 인공지능: 인간과의 공생을 위한 인공지능 개발과 지역 가치로서 ‘정’"
        got = _safe(t)
        self.assertTrue(got.endswith("‘정’"), got)

    def test_다른_금지_글자도_대시로(self):
        got = _safe('제목/부제*별표?물음표"따옴표<꺾쇠>파이프|끝')
        for ch in '/\\:*?"<>|':
            self.assertNotIn(ch, got)
        self.assertIn(" - ", got)

    def test_공백이_뭉치지_않는다(self):
        self.assertNotIn("  ", _safe("앞:  뒤"))

    def test_아주_긴_제목은_바이트로_자른다(self):
        got = _safe("가나다라마바사아자차" * 30)
        self.assertLessEqual(len(got.encode("utf-8")), MAX_TITLE_BYTES)

    def test_자를_때_낱말_한복판을_피한다(self):
        t = "아주긴제목 " + "낱말 " * 60 + "마지막낱말"
        got = _safe(t)
        self.assertFalse(got.endswith("낱"), got)

    def test_빈_제목은_기본값(self):
        self.assertEqual(_safe("   "), "제목없음")
        self.assertEqual(_safe(":::"), "제목없음")


if __name__ == "__main__":
    unittest.main()
