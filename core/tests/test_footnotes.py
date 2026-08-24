# -*- coding: utf-8 -*-
"""각주 복원 회귀 테스트 — services/footnotes.

본문 숫자를 잘못 각주로 바꾸면 되돌릴 수 없다. 그래서 '안 바꾸는 것'을 지키는
시험이 '바꾸는 것'을 지키는 시험만큼 중요하다.
"""
import unittest

from services import footnotes


PAGE = """보게 된다.39 전통 신학에서는 오랫동안 물질성이나 신체성과 같은 개념이
낯설 수도 있다. 그러나 기술의 발생적 관점은 통찰을 통하여

39 벽돌이 만들어지는 기술 과정에서 우리는 흙이라는 물질을 생각할 수 있어야 한다."""


class FootnoteTest(unittest.TestCase):
    def test_각주를_찾아_연결한다(self):
        r = footnotes.convert(PAGE)
        self.assertEqual(len(r.notes), 1)
        self.assertEqual(r.notes[0].num, 39)
        self.assertEqual(r.linked, 1)
        self.assertIn("보게 된다.[^39]", r.markdown)
        self.assertIn("[^39]: 벽돌이", r.markdown)

    def test_각주블록은_본문에서_빠진다(self):
        r = footnotes.convert(PAGE)
        body = r.markdown.split("[^39]:")[0]
        self.assertNotIn("39 벽돌이", body)

    def test_쪽을_넘는_짝도_잇는다(self):
        two = "…라고 비판하였다.58 시몽동은\f58 시몽동, 『기술적 대상들의 존재양식』, 71-73."
        r = footnotes.convert(two)
        self.assertEqual(r.linked, 1)
        self.assertIn("비판하였다.[^58]", r.markdown)

    def test_각주가_없으면_손대지_않는다(self):
        plain = "제 3 장에서는 1 부의 논의를 이어받아 2026 년의 상황을 다룬다."
        r = footnotes.convert(plain)
        self.assertEqual(r.notes, [])
        self.assertNotIn("[^", r.markdown)

    def test_공백_뒤_숫자는_각주가_아니다(self):
        """`제 3 장`의 3을 각주로 바꾸면 안 된다 — 붙어 있는 숫자만 각주다."""
        page = "제 3 장을 보라.\n\n41 김은혜, 『기술신학』, 30."
        r = footnotes.convert(page)
        self.assertIn("제 3 장", r.markdown)

    def test_한줄짜리_짧은_숫자줄은_각주로_보지_않는다(self):
        page = "본문이다.\n\n12 짧음"
        self.assertEqual(footnotes.convert(page).notes, [])


if __name__ == "__main__":
    unittest.main()
