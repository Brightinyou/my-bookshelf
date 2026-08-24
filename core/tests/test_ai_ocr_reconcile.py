# -*- coding: utf-8 -*-
"""2회 판독 대조 회귀 테스트 — services/ai_ocr.reconcile.

이 장치의 존재 이유: 유사도 검증이 **낱말 하나 바꿔치기를 못 잡는다.** 실제로
30쪽에서 `망원경`이 `바벨탑`으로 바뀌었는데 쪽 유사도는 0.988이라 ok로 통과했다.
같은 쪽을 두 번 읽으면 모델이 헷갈린 자리에서만 결과가 갈리므로 그 자리가 드러난다.
"""
import unittest

from services import ai_ocr


class ReconcileTest(unittest.TestCase):
    def test_같으면_불일치가_없다(self):
        t = "천문학이라는 과학을 망원경과 같은 기술 대상의 발전과"
        text, diffs = ai_ocr.reconcile([t, t])
        self.assertEqual(diffs, [])
        self.assertEqual(text, t)

    def test_낱말_바꿔치기를_잡는다(self):
        """실제로 났던 사고 — 유사도로는 못 잡던 것."""
        a = "천문학이라는 과학을 망원경과 같은 기술 대상의 발전과"
        b = "천문학이라는 과학을 바벨탑과 같은 기술 대상의 발전과"
        text, diffs = ai_ocr.reconcile([a, b])
        self.assertEqual(len(diffs), 1)
        self.assertIn("망원경", diffs[0]["a"])
        self.assertIn("바벨탑", diffs[0]["b"])
        self.assertEqual(text, a, "첫 판독을 그대로 채택해야 사람이 원문과 대조할 수 있다")

    def test_문장부호_차이는_알리지_않는다(self):
        a = "보게 된다. 전통 신학에서는"
        b = "보게 된다, 전통 신학에서는"
        self.assertEqual(ai_ocr.reconcile([a, b])[1], [])

    def test_공백_차이는_알리지_않는다(self):
        a = "천문학이라는 과학을"
        b = "천문 학이라는  과학을"
        self.assertEqual(ai_ocr.reconcile([a, b])[1], [])

    def test_한쪽이_비면_대조하지_않는다(self):
        text, diffs = ai_ocr.reconcile(["본문이 있다", ""])
        self.assertEqual(text, "본문이 있다")
        self.assertEqual(diffs, [])

    def test_여러_곳이_어긋나면_다_잡는다(self):
        a = "인간이 지배하고 통제하고 독점하는 대상이 아니라 얽혀가는 과정"
        b = "인간이 지배하고 통제하고 도전하는 대상이 아니라 엮여가는 과정"
        self.assertEqual(len(ai_ocr.reconcile([a, b])[1]), 2)

    def test_앞말을_함께_남겨_찾기_쉽게_한다(self):
        a = "과학을 망원경과 같은"
        b = "과학을 바벨탑과 같은"
        d = ai_ocr.reconcile([a, b])[1][0]
        self.assertIn("과학을", d["before"])


if __name__ == "__main__":
    unittest.main()


class JudgeTest(unittest.TestCase):
    """로컬 Vision을 심판으로 쓰는 경로.

    Vision은 **동등한 판독자가 아니다** — 본문 정확도는 LLM이 낫다(실측 30쪽에서
    Vision을 셋째 판독자로 놓으면 불일치 15곳 중 11곳이 Vision 잘못이었다).
    LLM 둘이 갈린 자리에서만 심판으로 쓰면 Vision의 오독은 투표에 들어오지 않는다.
    """

    A = "하나님의 내재하심으로 우리는 통찰을 인간과 베풂이 만들어지는"
    B = "하나님의 기뻐하심으로 우리는 물질을 인간과 벼룩이 만들어지는"
    J = "하나님의 내재하심으로 우리는 물질을 인간과 벽돌이 만들어지는"

    def test_심판이_1차를_지지하면_조용히_넘어간다(self):
        text, diffs = ai_ocr.reconcile([self.A, self.B], self.J)
        self.assertIn("내재하심으로", text)
        self.assertFalse(any("내재하심으로" in d["a"] for d in diffs))

    def test_심판이_2차를_지지하면_갈아_끼운다(self):
        text, _ = ai_ocr.reconcile([self.A, self.B], self.J)
        self.assertIn("물질을", text, "심판이 지지한 쪽으로 본문이 바뀌어야 한다")
        self.assertNotIn("통찰을", text)

    def test_심판도_못_가르면_사람에게_넘긴다(self):
        _, diffs = ai_ocr.reconcile([self.A, self.B], self.J)
        self.assertEqual(len(diffs), 1)
        self.assertIn("베풂이", diffs[0]["a"])
        self.assertIn("벼룩이", diffs[0]["b"])

    def test_심판이_없으면_전부_사람에게(self):
        _, diffs = ai_ocr.reconcile([self.A, self.B])
        self.assertEqual(len(diffs), 3)

    def test_심판이_비어도_망가지지_않는다(self):
        text, diffs = ai_ocr.reconcile([self.A, self.B], "")
        self.assertEqual(text, self.A)
        self.assertEqual(len(diffs), 3)
