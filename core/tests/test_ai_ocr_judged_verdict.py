# -*- coding: utf-8 -*-
"""심판에게 되묻는 판정 회귀 테스트 — services/ai_ocr.judged_verdict.

이 장치의 존재 이유: 유사도 하나로는 **"AI가 환각을 봤나, 기준선이 깨졌나"**를
구분할 수 없다. 실측(『기술신학』) 51·210·217·261·264·314쪽이 유사도 0.35~0.54로
경고가 붙었는데 **여섯 쪽 모두 AI가 옳았다**(AI↔Vision 0.936~0.977).

기존 `garble_rate` 관문으로는 못 걸렀다 — 이 책의 불량 레이어는 글자가 깨진 게
아니라 1음절 낱말이 빠진 것이라 깨짐률이 1.9~14.6으로 임계 15에 못 미친다.
"""
import unittest

from services import ai_ocr

AI = "인간과 기술의 관계론적 관점은 기술이 그 자체로 발전한 것이 아니라 하나님이 부여하신"
VISION = "인간과 기술의 관계론적 관점은 기술이 그 자체로 발전한 것이 아니라 하나님이 부여하신"


class JudgedVerdictTest(unittest.TestCase):
    def test_심판이_뒷받침하면_경고를_내린다(self):
        st, note = ai_ocr.judged_verdict(
            "warn", 0.35, "원본과 유사도 0.35 (임계 0.55) — 환각·쪽 어긋남 의심", AI, VISION)
        self.assertEqual(st, "unverified")
        self.assertIn("로컬 판독과 일치", note)

    def test_심판도_어긋나면_경고를_그대로_둔다(self):
        """★진짜 환각을 조용히 통과시키면 안 된다."""
        st, _ = ai_ocr.judged_verdict(
            "warn", 0.35, "원본과 유사도 0.35 — 환각·쪽 어긋남 의심",
            AI, "전혀 다른 내용이 적힌 쪽이며 겹치는 낱말이 없다")
        self.assertEqual(st, "warn")

    def test_심판이_없으면_그대로_둔다(self):
        st, _ = ai_ocr.judged_verdict("warn", 0.35, "원본과 유사도 0.35", AI, "")
        self.assertEqual(st, "warn")

    def test_분량_경고는_심판이_답할_문제가_아니다(self):
        """유사도는 통과했는데 분량이 어긋난 쪽 — 심판이 뒷받침해도 경고를 남긴다."""
        st, _ = ai_ocr.judged_verdict(
            "warn", 0.92, "분량이 원본의 30% — 요약했거나 일부를 빠뜨렸을 수 있습니다",
            AI, VISION)
        self.assertEqual(st, "warn")

    def test_경고가_아니면_건드리지_않는다(self):
        for st0 in ("ok", "check", "unverified", "failed"):
            st, note = ai_ocr.judged_verdict(st0, 0.9, "", AI, VISION)
            self.assertEqual((st, note), (st0, ""))

    def test_판독이_비었으면_그대로_둔다(self):
        st, _ = ai_ocr.judged_verdict("warn", 0.0, "판독 결과가 비어 있습니다", "", VISION)
        self.assertEqual(st, "warn")


if __name__ == "__main__":
    unittest.main()
