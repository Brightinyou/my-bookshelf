# -*- coding: utf-8 -*-
"""각주 복원 회귀 테스트 — services/footnotes.

본문 숫자를 잘못 각주로 바꾸면 되돌릴 수 없다. 그래서 '안 바꾸는 것'을 지키는
시험이 '바꾸는 것'을 지키는 시험만큼 중요하다.
"""
import re
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


class LayoutHintTest(unittest.TestCase):
    """레이아웃 힌트 — 각주가 없다고 알려 준 쪽은 아예 안 본다.

    줄 첫머리 숫자는 쪽번호·러닝헤더에도 흔하다(실측 레비나스 110쪽
    `110 대화의 철학과 세인 철학`). 텍스트만 보고는 각주와 구별할 수 없다.
    """

    RUNNING_HEAD = "본문이 이어진다 어쩌고 저쩌고 계속된다\n\n110 대화의 철학과 세인 철학"

    def test_각주없음_힌트를_주면_건드리지_않는다(self):
        r = footnotes.convert(self.RUNNING_HEAD, has_notes=[False])
        self.assertEqual(r.notes, [])
        self.assertIn("110 대화의 철학과 세인 철학", r.markdown)

    def test_힌트가_없어도_확신도로_걸러진다(self):
        """힌트는 거들 뿐이다 — 본문 참조도 연번도 없으면 어차피 각주로 안 본다."""
        r = footnotes.convert(self.RUNNING_HEAD)
        self.assertEqual(len(r.notes), 0)
        self.assertIn("110 대화의 철학과 세인 철학", r.markdown)

    def test_힌트가_짧아도_망가지지_않는다(self):
        """힌트 목록이 쪽 수보다 짧으면 나머지 쪽은 예전대로 텍스트로만 판단한다."""
        two = (self.RUNNING_HEAD
               + "\f보게 된다.39 이어진다\n\n39 벽돌이 만들어지는 기술 과정에서")
        r = footnotes.convert(two, has_notes=[False])   # 둘째 쪽 힌트 없음
        self.assertEqual(len(r.notes), 1)
        self.assertIn("보게 된다.[^39]", r.markdown)


class ConfidenceTest(unittest.TestCase):
    """확신도 규칙 — 줄 첫머리 숫자를 찾았다고 다 각주는 아니다.

    쪽번호와 러닝헤더가 똑같은 모양이다(실측 레비나스 110쪽
    `110 대화의 철학과 세인 철학`). 본문 참조나 연번, 둘 중 하나는 있어야 한다.
    """

    def test_연번이고_본문참조도_있으면_각주(self):
        t = ("보게 된다.39 그리고 이어진다.40 계속\n\n"
             "39 벽돌이 만들어지는 기술 과정에서\n40 두 번째 각주 내용이 이어진다")
        r = footnotes.convert(t)
        self.assertEqual(len(r.notes), 2)
        self.assertEqual(r.linked, 2)

    def test_연번이고_마침표로_끝나면_본문참조가_없어도_각주(self):
        """연번만으로는 부족하다 — 마침표까지 있어야 한다(러닝헤더와 가르는 조건)."""
        t = ("본문이 이어진다 어쩌고\n\n"
             "39 벽돌이 만들어지는 기술 과정에서 생각할 수 있어야 한다.\n"
             "40 두 번째 각주 내용이 이어진다.")
        r = footnotes.convert(t)
        self.assertEqual(len(r.notes), 2)
        self.assertEqual(r.orphan, [39, 40], "각주로는 보되 참조를 못 찾았다고 남긴다")

    def test_연번이어도_마침표가_없으면_되돌린다(self):
        t = ("본문이 이어진다 어쩌고\n\n"
             "39 벽돌이 만들어지는 기술 과정에서\n40 두 번째 각주 내용이 이어진다")
        r = footnotes.convert(t)
        self.assertEqual(r.notes, [])

    def test_단독이어도_본문참조가_있으면_각주(self):
        t = "보게 된다.39 전통 신학에서는\n\n39 벽돌이 만들어지는 기술 과정에서"
        r = footnotes.convert(t)
        self.assertEqual(len(r.notes), 1)
        self.assertIn("보게 된다.[^39]", r.markdown)

    def test_단독인데_본문참조도_없으면_본문으로_되돌린다(self):
        """러닝헤더를 각주로 떼어 가면 안 된다."""
        t = "본문이 이어진다 어쩌고 저쩌고\n\n110 대화의 철학과 세인 철학"
        r = footnotes.convert(t)
        self.assertEqual(r.notes, [])
        self.assertIn("110 대화의 철학과 세인 철학", r.markdown)
        self.assertNotIn("[^110]", r.markdown)


class SequenceAndPeriodTest(unittest.TestCase):
    """연번은 책 전체로 잇고, 마침표로 러닝헤더와 가른다.

    사용자 관찰 둘:
      · "앞서 각주로 확인한 번호의 다음 숫자가 각주로 이어져야 한다"
      · "보통 각주는 마침표로 끝난다 — 책 인용도, 문장도"
    이 둘을 함께 봐야 한다. 러닝헤더도 쪽마다 번호가 2씩 늘어 연번처럼 보이지만
    (110·112·114) 마침표가 없다.
    """

    def test_쪽마다_하나씩이어도_연번이면_잇는다(self):
        """쪽 안에서는 늘 '단독'이라, 책 전체를 훑어야 연번인 줄 안다."""
        t = ("본문 어쩌고\n\n39 첫 각주 내용이 여기 있다."
             "\f본문 저쩌고\n\n40 두 번째 각주 내용이다."
             "\f본문 그러하다\n\n41 세 번째 각주 내용이다.")
        self.assertEqual(len(footnotes.convert(t).notes), 3)

    def test_연번처럼_보여도_마침표가_없으면_러닝헤더다(self):
        t = ("본문 어쩌고\n\n110 대화의 철학과 세인 철학"
             "\f본문 저쩌고\n\n112 대화의 철학과 세인 철학")
        r = footnotes.convert(t)
        self.assertEqual(r.notes, [])
        self.assertIn("110 대화의 철학과 세인 철학", r.markdown)

    def test_서지사항도_마침표로_끝난다(self):
        t = ("본문 어쩌고\n\n58 시몽동, 『기술적 대상들』, 71-73."
             "\f본문 저쩌고\n\n59 황수영, “시몽동의 기술철학,” 86.")
        self.assertEqual(len(footnotes.convert(t).notes), 2)

    def test_본문참조가_있으면_마침표가_없어도_각주(self):
        """본문 참조는 가장 강한 신호라 마침표 없이도 통과한다."""
        t = "보게 된다.39 전통 신학에서는\n\n39 각주인데 마침표가 없다"
        self.assertEqual(len(footnotes.convert(t).notes), 1)


class 머리글오인Test(unittest.TestCase):
    """쪽머리글을 각주로 오인하던 것 (2026-08-27 연구자 보고).

    연구자 말 — "각주와 본문이 혼재된 것 같아", "각주가 아니라 미주인데".

    『기술과 덕』은 미주(尾註)를 쓰는 책이라 각주가 하나도 없어야 한다. 그런데
    쪽머리글이 「2 TECHNOLOGY AND THE VIRTUES …」처럼 «번호 + 글» 꼴이라 각주
    후보가 되고, 쪽번호가 각주 번호로, **그 쪽 본문 전체(1,600~2,000자)가 각주
    본문으로** 빨려 들어갔다.

    통과한 까닭은 판정의 마지막 관문이 «가까운 본문에 그 숫자가 있는가» 하나뿐이기
    때문이다. 번호 중복도 구분선도 요구하지 않는다. 이 책엔 진짜 미주 표시
    (…불과하다.2,6)가 있어 2·4·8이 마침표 뒤에 나왔고, 그래서 우연히 뚫렸다.
    """

    @staticmethod
    def _book(n_pages=6):
        """쪽마다 「<쪽번호> TECHNOLOGY AND THE VIRTUES <본문>」로 시작하는 책."""
        pages = []
        for i in range(1, n_pages + 1):
            pages.append(
                f"{i} TECHNOLOGY AND THE VIRTUES "
                f"이것은 {i}쪽의 본문이다. 미주 표시가 문장 끝에 붙는다.2 "
                "그리고 논의가 이어진다. 다시 한 문장을 더 쓴다. 충분히 길게 쓴다.")
        return "\f".join(pages)

    def test_머리글은_각주가_아니다(self):
        md = footnotes.convert(self._book()).markdown
        self.assertEqual(re.findall(r"(?m)^\[\^[^\]]+\]:", md), [],
                         "미주만 있는 책에서 각주가 만들어지면 안 된다")

    def test_본문을_한_글자도_잃지_않는다(self):
        src = self._book()
        md = footnotes.convert(src).markdown
        squash = lambda s: re.sub(r"\s", "", s)
        self.assertEqual(len(squash(md)), len(squash(src)),
                         "각주로 잘못 떼면 본문이 사라진다 — 되돌릴 수 없다")
        self.assertIn("TECHNOLOGY AND THE VIRTUES", md)

    def test_진짜_각주는_그대로_잡는다(self):
        """머리글 잣대가 멀쩡한 각주까지 물면 안 된다."""
        page1 = ("TECHNOLOGY AND THE VIRTUES 본문이 이어진다. 여기에 각주가 붙는다.1 "
                 "그리고 문장이 더 이어진다.\n\n1 Alasdair MacIntyre, After Virtue, 187.")
        page2 = ("TECHNOLOGY AND THE VIRTUES 다음 쪽 본문이다. 또 각주가 붙는다.2 "
                 "이어지는 문장.\n\n2 Shannon Vallor, Technology and the Virtues, 46.")
        md = footnotes.convert(page1 + "\f" + page2).markdown
        self.assertIn("[^1]:", md)
        self.assertIn("[^2]:", md)
