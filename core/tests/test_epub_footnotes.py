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

from services import epub_export
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


class 장을걸친각주Test(unittest.TestCase):
    """표시와 정의가 다른 장에 갈려도 이어 준다 (2026-08-27 연구자 보고).

    연구자 말 — "도로반투 각주는 다 되었는데, 이펍책의 23, 33, 34, 35, 36번이
    각주와 연결안되어 있어".

    논문 PDF는 쪽 아래 각주가 **다음 장 제목 뒤로 밀려** 나오는 일이 흔하다.
    실측(Dorobantu) — 34·35·36번 표시는 03장 끝에, 그 정의는 04장 첫머리에
    있었다. services/footnotes.convert 는 같은 글 안에 정의가 있는 번호만 표시로
    바꾸므로, 장별로 변환하면 서로 만나지 못한다.
    """

    def test_다음_장에_있는_정의를_찾아_잇는다(self):
        앞장 = "본문이 이어지다가 우리를 동물과 구별한다.34 그리고 계속된다."
        뒷장 = "다음 장이 시작된다.\n\n[^34]: For example, Saint Gregory of Nyssa."
        parts = [(앞장, {}), ("다음 장이 시작된다.", {"34": "For example, Saint Gregory of Nyssa."})]
        out = epub_export._book_chapter_bodies(parts)
        앞_본문, 앞_각주 = out[0]
        self.assertIn('href="#fn-34"', 앞_본문, "표시가 있는 장에 링크가 생겨야 한다")
        self.assertIn('id="fn-34"', 앞_각주, "각주도 표시가 있는 장으로 따라와야 한다")
        self.assertIn("backref", 앞_각주, "되돌아가기 화살표가 걸려야 한다")
        self.assertNotIn('id="fn-34"', out[1][1], "정의가 있던 장에는 남지 않는다")

    def test_번호_뒤에_한글이_붙어도_잡는다(self):
        """번역본은 「…강함이라.”36라고」처럼 번호 뒤에 곧바로 한글이 온다."""
        parts = [("내가 약한 그때에 강함이라.”36라고 말한다.", {}),
                 ("다음 장.", {"36": "2 Corinthians 12: 9-10."})]
        본문, 각주 = epub_export._book_chapter_bodies(parts)[0]
        self.assertIn('href="#fn-36"', 본문)
        self.assertIn('id="fn-36"', 각주)

    def test_표시를_끝내_못_찾으면_내용은_남긴다(self):
        """이을 자리가 없어도 각주 내용을 버리지 않는다 — 화살표만 뺀다."""
        parts = [("표시가 전혀 없는 본문이다.", {"9": "어딘가의 각주."})]
        본문, 각주 = epub_export._book_chapter_bodies(parts)[0]
        self.assertIn("어딘가의 각주.", 각주)
        self.assertNotIn("backref", 각주)

    def test_본문을_잃지_않는다(self):
        parts = [("첫 문장이다. 둘째 문장이다.34 셋째 문장이다.", {}),
                 ("뒷장 본문.", {"34": "각주 내용."})]
        out = epub_export._book_chapter_bodies(parts)
        for 조각 in ("첫 문장이다", "둘째 문장이다", "셋째 문장이다"):
            self.assertIn(조각, out[0][0])
        self.assertIn("뒷장 본문", out[1][0])


if __name__ == "__main__":
    unittest.main()


class 표지와서지Test(unittest.TestCase):
    """표지 면의 제목·저자와 서지정보 (2026-08-27 연구자 지적).

    연구자 말 — "이 책은 제목 아래 저자가 이름이 아니라 '기술'로 나와 있어.
    그리고 아쉬운 것은 서지정보를 메타정보로 넣으면 더 좋겠다는 거야".

    실측(『기술과 덕』) — 표제지 첫 줄이 저자였다. 첫 줄=제목, 마지막 줄=저자로
    못박아 두어서 **제목과 저자가 통째로 뒤바뀌고**, 표제지에서 흘러나온 조각
    "기술"이 저자로 찍혔다.
    """

    LINES = ["섀넌 밸러(Shannon Vallor)", "기술과 덕",
             "바랄 만한 미래를 위한 철학적 안내", "기술과 덕목들", "기술"]

    def test_저자가_첫_줄이어도_제목과_뒤바뀌지_않는다(self):
        h = epub_export._front_matter_xhtml("Technology and the Virtues",
                                            "Shannon Vallor", self.LINES)
        self.assertIn('<h1 class="fm-title">기술과 덕</h1>', h)
        self.assertIn('class="fm-author">섀넌 밸러(Shannon Vallor)', h)
        self.assertNotIn('class="fm-author">기술<', h)

    def test_제목을_되뇌는_표제지_조각은_버린다(self):
        """"기술과 덕목들"·"기술"은 부제가 아니라 표제지가 되뇐 제목이다."""
        h = epub_export._front_matter_xhtml("Technology and the Virtues",
                                            "Shannon Vallor", self.LINES)
        self.assertIn("바랄 만한 미래를 위한 철학적 안내", h)
        self.assertNotIn("기술과 덕목들", h)

    def test_저자를_모르면_마지막_줄을_저자로_본다(self):
        """논문은 «제목 / 부제 / 지은이» 차례가 많다 — 예전 동작을 지킨다."""
        h = epub_export._front_matter_xhtml("논문", "", [
            "인공지능 시대의 Imago Dei:", "과학과 관여하는 신학을 위한 도전과 기회",
            "마리우스 도로반투(Marius Dorobantu)"])
        self.assertIn('<h1 class="fm-title">인공지능 시대의 Imago Dei:</h1>', h)
        self.assertIn('class="fm-author">마리우스 도로반투(Marius Dorobantu)', h)

    def test_서지정보_한_줄을_만든다(self):
        self.assertEqual(
            epub_export._citation_text({"publisher": "New York: Oxford University Press",
                                        "published": "2018"}),
            "New York: Oxford University Press, 2018.")
        self.assertEqual(epub_export._citation_text({"published": "2018"}), "2018")
        self.assertEqual(epub_export._citation_text({}), "")

    def test_서지정보가_표지에_실린다(self):
        h = epub_export._front_matter_xhtml("책", "저자", ["책", "부제"],
                                            "New York: Oxford University Press, 2018.")
        self.assertIn('class="fm-cite">New York: Oxford University Press, 2018.', h)
