# -*- coding: utf-8 -*-
"""장 구분 채팅 회귀 테스트 — services/chapter_chat.

이 장치의 존재 이유: 텍스트 변환 다음으로 문제가 가장 많이 생기는 곳이 장별 분할인데,
지금은 무엇이 잘못됐는지 사람이 표에서 찾아야 한다. 말로 접수하게 한다.

★설계의 핵심은 **모델이 실행하지 않는 것**이다. 모델은 정해진 목록에서 의도만 고르고,
사실 확인(장 분량·후보 줄)과 실행은 앱이 한다. 그래서 테스트의 절반이
**'멋대로 하지 않는가'**를 지킨다 — 못 알아들으면 unknown, 근거가 없으면 ok=False.
"""
import tempfile
import unittest
from pathlib import Path

from services import chapter_chat as cc
from services import chapter_map as cmap


class InterpretRuleTest(unittest.TestCase):
    def test_마지막_장을_짚는다(self):
        it = cc.interpret_rule("마지막 챕터가 분할이 안 된 것 같아", 12)
        self.assertEqual(it.intent, "split")
        self.assertEqual(it.chapter, 12)

    def test_번호로_짚는다(self):
        it = cc.interpret_rule("5장을 4장에 붙여줘", 12)
        self.assertEqual((it.intent, it.chapter), ("merge", 5))

    def test_제목_바꾸기(self):
        it = cc.interpret_rule("2장 제목을 '서론'으로 바꿔줘", 12)
        self.assertEqual(it.intent, "rename")
        self.assertEqual(it.title, "서론")

    def test_따옴표_안의_말을_검색어로_가져온다(self):
        it = cc.interpret_rule("‘정든 인공지능과’ 앞에서 새 장으로 나눠줘", 12)
        self.assertEqual(it.intent, "split")
        self.assertEqual(it.query, "정든 인공지능과")

    def test_다시_나누기(self):
        self.assertEqual(cc.interpret_rule("처음부터 다시 나눠줘", 5).intent, "resplit")

    def test_못_알아들으면_지어내지_않는다(self):
        """틀린 의도로 장을 자르면 파생물까지 지워져 되돌리기 어렵다."""
        for msg in ("오늘 날씨 어때", "고마워요", "음..."):
            self.assertEqual(cc.interpret_rule(msg, 5).intent, "unknown", msg)


class PlanTest(unittest.TestCase):
    def setUp(self):
        self.ws = "testws"
        self.stem = "책"
        self.tmp = tempfile.mkdtemp()
        d = Path(self.tmp) / self.stem
        d.mkdir(parents=True)
        # 1·2장은 짧고 3장은 아주 길다 — '덜 나뉜 장'의 모양
        (d / "01_서론.txt").write_text("가" * 1000, encoding="utf-8")
        (d / "02_본론.txt").write_text("나" * 1000, encoding="utf-8")
        (d / "03_결론.txt").write_text(
            "다" * 500 + "\n제4장 새로운 시작\n" + "라" * 4000, encoding="utf-8")
        self._orig = cmap.chapter_files
        cmap.chapter_files = lambda ws, stem: sorted(d.glob("??_*.txt"))
        self._orig_rf = cmap.review_findings
        cmap.review_findings = lambda ws, stem: []

    def tearDown(self):
        cmap.chapter_files = self._orig
        cmap.review_findings = self._orig_rf

    def test_상태는_실행하지_않는다(self):
        p = cc.plan(self.ws, self.stem, cc.Intent(intent="status"))
        self.assertFalse(p.ok)
        self.assertEqual(p.action, "none")
        self.assertIn("3개 장", p.message)

    def test_나누기_제안에_근거가_붙는다(self):
        """★앱이 사실을 확인했다는 것을 사람이 볼 수 있어야 한다."""
        p = cc.plan(self.ws, self.stem, cc.Intent(intent="split", chapter=3))
        self.assertTrue(p.ok)
        self.assertEqual(p.action, "split")
        self.assertTrue(any("중앙값" in e for e in p.evidence))
        self.assertIn("at", p.params)

    def test_검색어로_자리를_짚는다(self):
        p = cc.plan(self.ws, self.stem,
                    cc.Intent(intent="split", chapter=3, query="새로운 시작"))
        self.assertTrue(p.ok)
        self.assertIn("새로운 시작", p.message)

    def test_못_찾으면_실행하지_않고_되묻는다(self):
        p = cc.plan(self.ws, self.stem,
                    cc.Intent(intent="split", chapter=3, query="없는말없는말"))
        self.assertFalse(p.ok)
        self.assertIn("찾지 못했", p.message)

    def test_첫_장은_앞에_붙일_수_없다(self):
        p = cc.plan(self.ws, self.stem, cc.Intent(intent="merge", chapter=1))
        self.assertFalse(p.ok)

    def test_없는_장은_거절한다(self):
        p = cc.plan(self.ws, self.stem, cc.Intent(intent="split", chapter=99))
        self.assertFalse(p.ok)
        self.assertIn("없습니다", p.message)

    def test_장을_안_짚으면_되묻는다(self):
        p = cc.plan(self.ws, self.stem, cc.Intent(intent="split", chapter=None))
        self.assertFalse(p.ok)

    def test_제목_없이_이름을_못_바꾼다(self):
        p = cc.plan(self.ws, self.stem, cc.Intent(intent="rename", chapter=2))
        self.assertFalse(p.ok)

    def test_다시_나누기는_위험을_알린다(self):
        p = cc.plan(self.ws, self.stem, cc.Intent(intent="resplit"))
        self.assertTrue(p.ok)
        self.assertTrue(any("지워지고" in e for e in p.evidence))

    def test_ok가_아니면_apply가_아무것도_안_한다(self):
        ok, msg = cc.apply(self.ws, self.stem, cc.Proposal(action="split", ok=False))
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
