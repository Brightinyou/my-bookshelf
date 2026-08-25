# -*- coding: utf-8 -*-
"""쪽 경계 각주 재배치 회귀 테스트 — services/footnotes.reflow_pages.

이 장치의 존재 이유(연구자 지적, 2026-08-25): 책은 쪽 아래에 각주를 두므로 문장이
쪽을 넘어가면 판독 결과가 이렇게 된다.

    …주목할 것은 소위 ‘제본스의 역        ← 문장이 중간에 끊긴다
    37 위의 책, 12.\\f설’인데, 영국의 경제학자…   ← 각주에 본문이 딱 붙는다

**문장이 완성되지 않으면 사람도 AI도 검증하지 못한다.** 그래서 끊긴 본문을 다음 쪽
첫 문단과 먼저 잇고, 각주 덩어리는 그 뒤로 내린다.

★붙일지 띄울지는 **책 어휘로** 가른다 — 한국어 책은 어절 한복판에서도 줄이 바뀐다.
★판독이 틀렸을 때는 일부러 띄워 **눈에 띄게** 한다.
"""
import unittest

from services import footnotes as fn

SEP = fn.PAGE_SEP


class EndsMidSentenceTest(unittest.TestCase):
    def test_문장이_끝났으면_거짓(self):
        for s in ("이것이 끝이다.", "정말인가?", "그가 말했다.”", "(주의)"):
            self.assertFalse(fn.ends_midsentence(s), s)

    def test_중간에_끊겼으면_참(self):
        for s in ("소위 ‘제본스의 역", "그리고 우리는", "…낼 수"):
            self.assertTrue(fn.ends_midsentence(s), s)


class JoinAcrossBreakTest(unittest.TestCase):
    LEX = "제본스의 역설을 가리킨다. 이 역설은 널리 알려져 있다."

    def test_책에_있는_말이면_붙인다(self):
        got = fn.join_across_break("소위 ‘제본스의 역", "설’인데, 영국의", self.LEX)
        self.assertIn("역설’인데", got)

    def test_책에_없으면_띄운다(self):
        """★오독(`설`→`철`)일 때는 붙이지 않아야 눈에 띈다."""
        got = fn.join_across_break("소위 ‘제본스의 역", "철’인데, 영국의", self.LEX)
        self.assertIn("역 철’인데", got)

    def test_사전이_없으면_공백으로_잇는다(self):
        self.assertEqual(fn.join_across_break("앞말", "뒷말"), "앞말 뒷말")

    def test_영문_하이픈_분철(self):
        self.assertEqual(fn.join_across_break("coop-", "eration"), "cooperation")
        self.assertEqual(fn.join_across_break("High-", "Level"), "High-Level")


class ReflowPagesTest(unittest.TestCase):
    LEX = "제본스의 역설을 가리킨다."

    def _pages(self):
        p1 = ("이것이 바로 제1 기계시대의 시작이었다. "
              "이 제1 기계시대로의 전환에서 주목할 것은 소위 ‘제본스의 역\n"
              "36 브린욜프슨 & 맥아피, 『제2의 기계시대』, 11.\n"
              "37 위의 책, 12.")
        p2 = "설’인데, 영국의 경제학자 윌리엄 제본스가 발견한 역설을 가리킨다.\n\n다음 문단이다."
        return p1 + SEP + p2

    def test_끊긴_문장을_이어_붙인다(self):
        got = fn.reflow_pages(self._pages(), lexicon=self.LEX)
        self.assertIn("제본스의 역설’인데", got)

    def test_각주는_이어붙인_문장_뒤로_내려간다(self):
        got = fn.reflow_pages(self._pages(), lexicon=self.LEX)
        page1 = got.split(SEP)[0]
        self.assertLess(page1.index("역설’인데"), page1.index("36 브린욜프슨"))

    def test_각주_뒤에_빈_줄이_있다(self):
        got = fn.reflow_pages(self._pages(), lexicon=self.LEX)
        self.assertIn("12.", got)
        self.assertNotIn("12.설", got)          # 각주에 본문이 딱 붙지 않는다
        self.assertIn("\n\n36 브린욜프슨", got)  # 본문과 각주 사이에도 빈 줄

    def test_가져간_문단을_두_번_쓰지_않는다(self):
        """★다음 쪽이 한 문단뿐이면 남는 게 없다 — 그때 통째로 다시 실리면 안 된다."""
        text = ("문장이 중간에 끊긴다 그리고\n37 위의 책, 12."
                + SEP + "이어지는 한 문단뿐이다.")
        got = fn.reflow_pages(text, lexicon="")
        self.assertEqual(got.count("이어지는 한 문단뿐이다."), 1)

    def test_각주가_없는_쪽은_글을_건드리지_않는다(self):
        """쪽 구분자 앞뒤 줄바꿈만 붙고 **글자는 그대로**여야 한다.

        ★`\f`만 넣으면 화면에서 보이지 않아 앞 쪽 끝과 다음 쪽 첫 줄이 한 줄처럼
        붙는다(`…44.기술의 본질에 대해`) — 그래서 줄바꿈을 함께 둔다."""
        text = "본문만 있는 쪽이다." + SEP + "다음 쪽도 본문뿐이다."
        got = fn.reflow_pages(text)
        self.assertEqual(got, "본문만 있는 쪽이다.\n" + SEP + "\n다음 쪽도 본문뿐이다.")
        self.assertEqual(got.replace("\n", ""), text)      # 글자는 그대로

    def test_문장이_끝난_쪽은_잇지_않는다(self):
        text = ("문장이 여기서 끝난다.\n37 위의 책, 12."
                + SEP + "새 문단이 시작된다.")
        got = fn.reflow_pages(text, lexicon="")
        self.assertIn("새 문단이 시작된다.", got.split(SEP)[1])


if __name__ == "__main__":
    unittest.main()
