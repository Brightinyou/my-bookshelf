# -*- coding: utf-8 -*-
"""재OCR 검증 규칙 회귀 테스트 — services/ai_ocr.verify.

이 규칙의 일은 **환각을 잡는 것**이라, 느슨해지면 조용히 쓸모가 없어진다.
2026-08-24에 실제로 그런 일이 있었다: "원본이 깨진 쪽"을 봐주려고 넣은 예외가
너무 넓어서 엉뚱한 쪽·지어낸 문장까지 통과시켰다. 그래서 적대 시험을 붙박아 둔다.

임계값 근거는 ai_ocr 머리말과 상수 주석 참고.
"""
import unittest

from services import ai_ocr

CLEAN = ("교육의 본래 역할은 바로 인간이 충분히 인간적일 수 있도록 인도하고 "
         "가르치고 돕는 것이다. 그리고 교육이 지향하는 인간상은 향상된 인간 혹은 "
         "초지능을 지닌 포스트휴먼이 아니라 저마다 자기의 본래 모습을 그대로 "
         "인정받으면서 자신의 역량을 펼칠 수 있는 인간이기 때문이다. ") * 2
# 같은 내용인데 한 글자 낱말이 빠지고 글자가 깨진 불량 레이어
DEGRADED = CLEAN.replace(" 수 ", " ").replace("기술", "기合").replace("교육", "교육u")
OTHER = ("메이야수는 필연성에 관한 시론이라는 책을 출판하면서 사변적 실재론의 "
         "논의를 촉발하였다. 상관주의 비판은 칸트 이후의 철학이 놓인 자리를 다시 "
         "묻는 작업이다. ") * 3


class VerifyTest(unittest.TestCase):
    def test_같은_쪽이면_통과(self):
        status, sim, _ = ai_ocr.verify(CLEAN, DEGRADED)
        self.assertIn(status, ("ok", "unverified"))
        self.assertGreater(sim, ai_ocr.ALIGNMENT_FLOOR)

    def test_엉뚱한_쪽은_잡는다(self):
        status, sim, _ = ai_ocr.verify(CLEAN, OTHER * 2)
        self.assertEqual(status, "warn")
        self.assertLess(sim, ai_ocr.ALIGNMENT_FLOOR)

    def test_지어낸_본문은_잡는다(self):
        fake = "이 장에서는 인공지능의 윤리적 함의를 검토하며 신학적으로 성찰한다. " * 12
        self.assertEqual(ai_ocr.verify(fake, DEGRADED)[0], "warn")

    def test_양쪽_다_비면_빈_쪽(self):
        self.assertEqual(ai_ocr.verify("", "")[0], "ok")

    def test_원본만_있는데_판독이_비면_경고(self):
        self.assertEqual(ai_ocr.verify("", DEGRADED)[0], "warn")

    def test_요약하면_잡는다(self):
        self.assertEqual(ai_ocr.verify(CLEAN[:120], DEGRADED)[0], "warn")

    def test_없는_내용을_덧붙이면_잡는다(self):
        self.assertEqual(ai_ocr.verify(CLEAN + OTHER * 4, DEGRADED)[0], "warn")


if __name__ == "__main__":
    unittest.main()
