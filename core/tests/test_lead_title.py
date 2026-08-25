# -*- coding: utf-8 -*-
"""앞부분 덩어리의 장 이름 — chapter_wiki._lead_title.

논문은 `Introduction` 표제 없이 초록 뒤로 곧장 본문이 오는 일이 흔하다. 그 덩어리엔
제목·저자·초록·서론이 함께 들어 있어서 '머리말'이라는 이름이 사실과 어긋난다
(2026-08-25 Dorobantu 논문에서 연구자 지적).
"""
import unittest

import chapter_wiki


class LeadTitleTest(unittest.TestCase):
    def test_초록이_있으면_제목초록서론(self):
        lead = ("Imago Dei in the Age of Artificial Intelligence\n\n"
                "Marius Dorobantu\n\n"
                "Abstract: Modern developments in evolutionary and cognitive science "
                "have increasingly challenged the view that humans are distinctive.\n\n"
                + "본문이 이어진다. " * 60)
        self.assertEqual(chapter_wiki._lead_title(lead), "제목·초록·서론")

    def test_초록이_없으면_머리말(self):
        lead = "어떤 책의 앞머리 글이다. " * 60
        self.assertEqual(chapter_wiki._lead_title(lead), "머리말")

    def test_서론_표시가_있으면_그것을_따른다(self):
        lead = "I. 들어가는 말\n\n" + "본문이 충분히 이어진다. " * 60
        self.assertNotIn(chapter_wiki._lead_title(lead), ("머리말", "제목·초록·서론"))


if __name__ == "__main__":
    unittest.main()
