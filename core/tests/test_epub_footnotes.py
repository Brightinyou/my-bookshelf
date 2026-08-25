# -*- coding: utf-8 -*-
"""EPUB 각주 회귀 테스트 — services/epub_export._with_footnotes.

이 장치의 존재 이유(연구자 요청, 2026-08-25): Markdown 쪽에서는 각주를 `[^n]`으로
살려 내고 있었는데 EPUB은 **본문 아래 맨숫자 덩어리**로 흘려보냈다. EPUB3의
`epub:type="noteref"`/`"footnote"`를 쓰면 읽는 이가 번호를 눌러 **그 자리에서**
각주를 펴 볼 수 있다. 학위논문 자료에서 각주는 본문만큼 중요하다.

★각주를 **찾는** 규칙은 services/footnotes.convert가 이미 갖고 있다. 여기서는
표시만 바꾼다 — 규칙을 두 벌로 만들면 한쪽만 고치게 된다.
"""
import re
import unittest

from services.epub_export import _with_footnotes

TEXT = ("이것이 본문이다.11 그리고 이어진다.12 끝.\f\n"
        "11 이기상, \"현대 기술의 본질,\" 『강연과 논문』, 454.\n"
        "12 박찬국, \"니힐리즘의 극복,\" 『강연과 논문』, 406.")


class WithFootnotesTest(unittest.TestCase):
    def setUp(self):
        self.body, self.notes = _with_footnotes(TEXT)

    def test_본문_번호가_링크가_된다(self):
        self.assertIn('epub:type="noteref"', self.body)
        self.assertIn('href="#fn-11"', self.body)
        self.assertIn("<sup>11</sup>", self.body)

    def test_각주가_aside로_나온다(self):
        self.assertIn('epub:type="footnote"', self.notes)
        self.assertIn('id="fn-11"', self.notes)
        self.assertIn("이기상", self.notes)

    def test_되돌아가는_링크가_있다(self):
        self.assertIn('href="#ref-11"', self.notes)

    def test_짝이_맞는다(self):
        refs = set(re.findall(r'href="#fn-([^"]+)"', self.body))
        defs = set(re.findall(r'id="fn-([^"]+)"', self.notes))
        self.assertEqual(refs, defs)

    def test_HTML을_이스케이프한다(self):
        body, notes = _with_footnotes('꺾쇠 <b>와 & 앰퍼샌드.1\f\n1 인용 "따옴표" 있음.')
        self.assertNotIn("<b>", body)
        self.assertIn("&lt;b&gt;", body)
        self.assertIn("&quot;", notes)

    def test_각주가_없으면_아무것도_안_붙인다(self):
        body, notes = _with_footnotes("각주 없는 평범한 본문이다.")
        self.assertEqual(notes, "")
        self.assertIn("<p>각주 없는 평범한 본문이다.</p>", body)

    def test_짝을_못_찾은_표시는_그대로_둔다(self):
        """정의가 없는 `[^k]`를 링크로 만들면 깨진 링크가 된다."""
        body, _ = _with_footnotes("본문에 [^99] 표시만 있다.")
        self.assertIn("[^99]", body)

    def test_문단_안_줄바꿈은_br로(self):
        body, _ = _with_footnotes("첫 줄\n둘째 줄\n\n다음 문단")
        self.assertIn("<br/>", body)


if __name__ == "__main__":
    unittest.main()
