# -*- coding: utf-8 -*-
"""본문에 녹아든 각주 되돌리기 — services/footnotes.split_inline_notes.

이 장치의 존재 이유(연구자 보고, 2026-08-25): 판독 프롬프트가 "한 문단은 한 줄로"를
강조한 탓에 모델이 **각주까지 본문 문단에 이어 붙였다.** 실측 『기술신학』 373쪽 중
105쪽(28%)이 그랬다:

    …도취되지 않고 11 이기상, "현대 기술의 본질," 454. 12 박찬국, … 13 하이데거, … 44.

★**번호가 오름차순으로 둘 이상 이어질 때만** 가른다. 하나뿐이면 본문 속 숫자와
구별할 수 없다 — 잘못 가르면 본문이 각주로 떨어져 나가고 그건 되돌릴 수 없다.
그래서 테스트의 절반이 **'안 가르는 것'**을 지킨다.
"""
import unittest

from services.footnotes import split_inline_notes


class SplitInlineNotesTest(unittest.TestCase):
    def test_이어진_각주를_제_줄로_되돌린다(self):
        line = ('기술 이해를 비판한다. 하이데거는 생산성에 도취되지 않고 '
                '11 이기상, "현대 기술의 본질," 『강연과 논문』, 454. '
                '12 박찬국, "니힐리즘의 극복," 『강연과 논문』, 406. '
                '13 하이데거, 『강연과 논문』, 44.')
        got = split_inline_notes(line).split("\n")
        self.assertTrue(got[0].endswith("도취되지 않고"))
        self.assertEqual(got[1], "")                       # 본문과 각주 사이 빈 줄
        self.assertTrue(got[2].startswith("11 이기상"))
        self.assertTrue(got[3].startswith("12 박찬국"))
        self.assertTrue(got[4].startswith("13 하이데거"))

    def test_글자를_잃지_않는다(self):
        line = ('본문이다. 11 저자, 『책』, 12. 12 다른저자, 『다른책』, 34.')
        import re
        a = re.sub(r"\s", "", line)
        b = re.sub(r"\s", "", split_inline_notes(line))
        self.assertEqual(a, b)

    # ── 아래는 '건드리지 않는 것'을 지킨다 ──────────────────────
    def test_번호가_하나뿐이면_안_가른다(self):
        line = "그는 1998년 11 월에 태어났다고 적혀 있다."
        self.assertEqual(split_inline_notes(line), line)

    def test_이어지지_않는_숫자는_안_가른다(self):
        line = "표 3 에서 보듯 사례 47 은 예외이며 결과는 분명하다."
        self.assertEqual(split_inline_notes(line), line)

    def test_각주답게_끝나지_않으면_안_가른다(self):
        """서지사항은 쪽수나 마침표로 끝난다 — 아니면 본문일 공산이 크다."""
        line = "제 11 장과 제 12 장을 견주어 보면 차이가 드러나는데"
        self.assertEqual(split_inline_notes(line), line)

    def test_본문_속_참조번호를_각주로_보지_않는다(self):
        """★실측 17쪽에서 이걸 놓쳐 본문을 찢었다.

        본문 참조는 문장부호·글자 **바로 뒤에 공백 없이** 붙고(`주장하였다.11`),
        각주 항목은 공백으로 떨어져 시작한다(`… 11 이기상,`)."""
        line = ("그는 위협이라 주장하였다.11 하이데거는 인간이 사물을 지배하게 되었다고 "
                "자만하지만 인류는 예속되었고12 기술을 도구로 생각하는 한 본질을 "
                "간과하게 될 것이라고 지적하였다.13 그는 오히려 기술을 대상화하는 생각을 비판한다.")
        self.assertEqual(split_inline_notes(line), line)

    def test_본문_참조와_각주가_한_줄에_섞여도_각주만_가른다(self):
        line = ("주장하였다.11 하이데거는 지배하게 되었다고 자만하지만 예속되었고12 "
                "간과하게 될 것이라고 지적하였다.13 그는 비판한다. "
                "11 이기상, 『강연과 논문』, 454. 12 박찬국, 『강연과 논문』, 406. "
                "13 하이데거, 『강연과 논문』, 44.")
        got = split_inline_notes(line).split("\n")
        self.assertIn("주장하였다.11", got[0])          # 본문 참조는 본문에 남는다
        self.assertTrue(got[0].rstrip().endswith("비판한다."))
        self.assertTrue(got[2].startswith("11 이기상"))
        self.assertEqual(len([g for g in got if g.strip()]), 4)

    def test_이미_제_줄에_있으면_그대로_둔다(self):
        page = "본문이다.\n\n11 저자, 『책』, 12.\n12 다른저자, 『다른책』, 34."
        self.assertEqual(split_inline_notes(page), page)

    def test_본문만_있는_쪽은_그대로(self):
        page = "이것은 각주가 없는 평범한 본문이다. 숫자도 없다."
        self.assertEqual(split_inline_notes(page), page)


if __name__ == "__main__":
    unittest.main()
