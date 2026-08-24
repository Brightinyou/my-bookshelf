# -*- coding: utf-8 -*-
"""책 어휘 필터 회귀 테스트 — services/ai_ocr.lexicon_verdict · filter_notes.

이 장치의 존재 이유: 로컬 Vision은 본문 정확도가 LLM보다 낮아 쪽당 열몇 곳을 짚는데
그 대부분이 자기 오독이다. 그런데 두 오독의 성질이 다르다 — AI 오독은 문맥이 만든
**대체**(`결국`·`전개에서`)라 말이 되고, Vision 오독은 글자 모양 **착오**(`김민한`·
`시용동`)라 말이 안 된다. 그래서 책 자신의 어휘로 걸러진다.
실측(『기술신학』 33쪽): 11곳 → 6곳, **진짜 오독 유실 0건**.

★어휘는 **후보를 고르는 데만** 쓴다. 만드는 데 쓰면 `망원경`이 `바벨탑`이 된다.
"""
import unittest

from services import ai_ocr

# 33쪽을 뺀 나머지 쪽에서 실제로 나온 낱말들
CORPUS = ("시몽동의 기술철학에서 규범성의 문제를 다룬다. 김재희는 시몽동을 이렇게 읽는다. "
          "결국 그것은 역설적으로 보인다. 결코 인간이 중심이 아니다. "
          "긴밀한 연결과 천하 만물의 관계를 본다.")


class LexiconVerdictTest(unittest.TestCase):
    def test_말이_안_되는_쪽을_버린다(self):
        # Vision의 글자 모양 착오 — 책 어디에도 없다
        self.assertEqual(ai_ocr.lexicon_verdict(CORPUS, "시몽동", "시용동"), "A")
        self.assertEqual(ai_ocr.lexicon_verdict(CORPUS, "김재희", "김재회"), "A")
        self.assertEqual(ai_ocr.lexicon_verdict(CORPUS, "긴밀한", "김민한"), "A")
        self.assertEqual(ai_ocr.lexicon_verdict(CORPUS, "천하", "천히"), "A")

    def test_어간으로도_가른다(self):
        """조사가 붙어 낱말 통째로는 안 걸리는 자리."""
        self.assertEqual(ai_ocr.lexicon_verdict(CORPUS, "역설적으로", "역선적으로"), "A")

    def test_둘_다_말이_되면_사람에게_넘긴다(self):
        """★가장 중요한 성질 — 진짜 오독을 조용히 버리면 안 된다."""
        self.assertEqual(ai_ocr.lexicon_verdict(CORPUS, "결국", "결코"), "?")

    def test_둘_다_책에_없으면_넘긴다(self):
        self.assertEqual(ai_ocr.lexicon_verdict(CORPUS, "전개에서", "전개체적"), "?")

    def test_어간을_1음절까지_자르지_않는다(self):
        """`긴`8회 대 `김`42회처럼 1음절은 둘 다 흔해서 무력하다 — 통째가 먼저다."""
        self.assertEqual(ai_ocr.lexicon_verdict(CORPUS, "긴밀한", "김민한"), "A")

    def test_사전이_없으면_아무것도_안_버린다(self):
        self.assertEqual(ai_ocr.lexicon_verdict("", "가", "나"), "?")

    def test_심판이_맞은_자리는_남긴다(self):
        """Vision이 옳고 채택본이 틀린 자리 — 절대 버리면 안 된다."""
        self.assertEqual(ai_ocr.lexicon_verdict(CORPUS, "김민한", "긴밀한"), "B")


class FilterNotesTest(unittest.TestCase):
    def test_잡음만_걷어낸다(self):
        notes = [{"before": "", "a": "시몽동", "b": "시용동"},      # Vision 오독
                 {"before": "", "a": "결국", "b": "결코"},          # ★진짜 오독
                 {"before": "", "a": "천하", "b": "천히"}]          # Vision 오독
        kept = ai_ocr.filter_notes(notes, CORPUS)
        self.assertEqual([d["a"] for d in kept], ["결국"])

    def test_사전이_비면_그대로_둔다(self):
        notes = [{"before": "", "a": "가", "b": "나"}]
        self.assertEqual(ai_ocr.filter_notes(notes, ""), notes)


if __name__ == "__main__":
    unittest.main()
