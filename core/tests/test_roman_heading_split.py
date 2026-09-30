# -*- coding: utf-8 -*-
"""로마 숫자로 장을 매긴 글의 분할 — chapter_wiki.

2026-09-25. 바티칸 «Antiqua et Nova» 영문본(I~VI절)을 나눴더니 III·IV장이 II장
안으로 묻혀 5장만 나왔다. 원인이 둘이었다.

  · 규칙 단계가 로마 숫자를 못 본다. `_heading_candidates`의 갈래는 «제N장»·
    «chapter N»·«N. Title» 따위로 **전부 아라비아 숫자**였다. 로마 숫자를 아는
    규칙은 `roman_toc_split` 하나뿐인데, 그쪽은 점선·쪽번호가 붙은 «차례 줄»만
    인정한다(`_clean_toc_title`의 had_leader). 차례 없이 본문에만 절 제목이 선
    글은 규칙 단계를 통째로 지나쳐 LLM 폴백으로 떨어졌다.
  · 그 LLM 폴백은 헤딩 후보를 60자로 잘랐다. 하필 III장(68자)·IV장(67자)이
    그 문헌에서 가장 긴 두 제목이라 후보 목록에서 빠졌다 — 모델이 틀린 게
    아니라 **고를 선택지가 없었다.**

여기서 못 박는 것은 셋이다.
  · 로마 숫자 절 제목을 규칙 단계에서 잡는다(LLM을 부르지 않는다).
  · 긴 절 제목도 LLM 후보에 오른다.
  · «**볼드**»로만 표시된 제목에서 별표가 장 이름에 남지 않는다.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
import unittest

import chapter_wiki as cw

# 바티칸 Antiqua et Nova와 같은 꼴 — 차례 없음, 제목은 볼드, III·IV가 60자 초과.
_SECTIONS = [
    ("I", "**Introduction**"),
    ("II", "**What is Artificial Intelligence?**"),
    ("III", "**Intelligence in the Philosophical and Theological Tradition**"),
    ("IV", "**The Role of Ethics in Guiding the Development and Use of AI**"),
    ("V", "**Specific Questions**"),
    ("VI", "**Concluding Reflections**"),
]
_FILLER = "This paragraph carries the body of the section. " * 60


def _document() -> str:
    out = ["A note of the Dicastery for the Doctrine of the Faith.\n"]
    for roman, title in _SECTIONS:
        out.append(f"{roman}. {title}\n\n{_FILLER}\n")
    return "\n".join(out)


class RomanHeadingCandidateTest(unittest.TestCase):
    def test_로마_숫자_절을_여섯_개_다_잡는다(self):
        cands = cw._heading_candidates(_document())
        self.assertEqual([c["num"] for c in cands], [1, 2, 3, 4, 5, 6])

    def test_볼드_표시는_장_이름에_남지_않는다(self):
        cands = cw._heading_candidates(_document())
        self.assertEqual(cands[0]["title"], "Introduction")
        self.assertNotIn("*", "".join(c["title"] for c in cands))

    def test_긴_제목도_잡는다(self):
        """III·IV가 빠졌던 자리 — 60자를 넘는 제목."""
        cands = cw._heading_candidates(_document())
        third = next(c for c in cands if c["num"] == 3)
        self.assertGreater(len(third["title"]), 55)
        self.assertTrue(third["title"].startswith("Intelligence in the Philosophical"))

    def test_소문자_로마_숫자는_보지_않는다(self):
        """«i.e.»·«v.»(versus)·목록 항목과 구분되지 않는다."""
        txt = "\n\n".join(f"{r}. Some Section Title\n\n{_FILLER}"
                          for r in ("i", "ii", "iii", "iv"))
        self.assertEqual([c for c in cw._heading_candidates(txt) if c["num"] <= 4], [])

    def test_문장으로_끝나는_줄은_장이_아니다(self):
        txt = "\n\n".join(f"{r}. I went there and saw it.\n\n{_FILLER}"
                          for r in ("I", "II", "III"))
        self.assertEqual(cw._heading_candidates(txt), [])


class RomanNumberedSplitTest(unittest.TestCase):
    def test_LLM_없이_규칙만으로_여섯_장으로_갈린다(self):
        chs = cw.numbered_heading_split(_document())
        self.assertIsNotNone(chs)
        self.assertEqual(len(chs), 6)
        self.assertEqual(chs[2][0], "3. Intelligence in the Philosophical and Theological Tradition")

    def test_본문_글자를_잃지_않는다(self):
        chs = cw.numbered_heading_split(_document())
        joined = "".join(body for _t, body in chs)
        self.assertIn(_FILLER.strip()[:40], joined)
        # 각 장이 제 몫의 본문을 갖는다 — 한 장에 몰리지 않는다
        sizes = [len(body) for _t, body in chs]
        self.assertLess(max(sizes) / min(sizes), 2.0)


class LlmCandidateLengthTest(unittest.TestCase):
    def test_후보_길이_상한이_제목_상한과_어긋나지_않는다(self):
        """60자는 학술 절 제목을 자른다 — _heading_candidates의 제목 상한(90)에 맞춘다."""
        self.assertGreaterEqual(cw._LLM_CAND_MAXLEN, 90)


if __name__ == "__main__":
    unittest.main()
