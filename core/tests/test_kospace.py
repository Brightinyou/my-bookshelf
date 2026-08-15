# -*- coding: utf-8 -*-
"""자간정리(줄바꿈 복원) 회귀 테스트 — services/kospace.py.

핵심 불변식은 하나다: AI가 무엇을 답하든, 또 아무 답도 못 받든, 결과물의
공백 아닌 글자는 원문과 한 글자도 달라지지 않는다. 예전 방식이 사후 검증
(_clean_is_valid)으로 지키던 것을 지금은 설계로 지키므로 여기서 못 박아 둔다.
"""
import random
import re
import unittest

from services import kospace


def strip_ws(s):
    return re.sub(r"\s+", "", s)


# 인쇄된 줄 하나가 한 줄, 줄 사이는 빈 줄 — 스캔 PDF에서 뽑은 본문의 실제 모양.
SAMPLE = "\n\n".join([
    "지지하는 교수들은 연속적 연결성이 어떻게 생산성과 기억 용량을 증대시킬",
    "수 있는지를 강조했다. 사이보그들이 유별나게 보일 수도 있지만 이런 기술",
    "이 어떠한 두려움도 야기해서는 안 된다고들 얘기했다. 그것은 날로 복잡해",
    "지는 정보 환경에 대비한 도구일 뿐이었다.",          # 여백을 남기고 끝난 줄 = 문단 끝
    "MIT에서는 그 사이보그들이 달성하려는 것에 대해 많은 논의가 있었다. 그",
    "들은 물리적 세계와 가상 세계에서 동시에 살아가는 존재가 되려 했다.",
])


class PlanTests(unittest.TestCase):
    def test_full_width_line_is_asked_short_line_ends_paragraph(self):
        lines, kinds = kospace.plan(SAMPLE)
        self.assertEqual(len(lines), 6)
        self.assertEqual(len(kinds), 5)
        # 여백까지 꽉 찬 줄 뒤는 문단 끝일 수 없으므로 AI에게 묻는다
        self.assertIsNone(kinds[0])
        self.assertIsNone(kinds[1])
        self.assertIsNone(kinds[2])
        # 눈에 띄게 짧은 마지막 줄 = 문단 경계
        self.assertEqual(kinds[3], kospace.PARA)
        self.assertEqual(kospace.pending_indexes(kinds), [0, 1, 2, 4])

    def test_single_line_has_no_breaks(self):
        lines, kinds = kospace.plan("한 줄뿐인 본문")
        self.assertEqual(lines, ["한 줄뿐인 본문"])
        self.assertEqual(kinds, [])

    def test_empty_text(self):
        self.assertEqual(kospace.plan(""), ([], []))
        self.assertEqual(kospace.render([], []), "")


class RenderTests(unittest.TestCase):
    def test_join_and_space_decisions_apply(self):
        lines, kinds = kospace.plan(SAMPLE)
        kinds[0] = kospace.SPACE     # 증대시킬 / 수  → 띄어야 함
        kinds[1] = kospace.JOIN      # 기술 / 이      → 붙여야 함
        kinds[2] = kospace.JOIN      # 복잡해 / 지는  → 붙여야 함
        out = kospace.render(lines, kinds)
        self.assertIn("증대시킬 수 있는지를", out)
        self.assertIn("이런 기술이 어떠한", out)
        self.assertIn("날로 복잡해지는 정보", out)

    def test_paragraph_boundary_becomes_blank_line(self):
        lines, kinds = kospace.plan(SAMPLE)
        out = kospace.render(lines, kinds)
        # 문단이 인쇄된 줄이 아니라 진짜 문단 단위로 흐른다 (EPUB <p> 품질)
        self.assertEqual(len([p for p in out.split("\n\n") if p.strip()]), 2)

    def test_content_never_changes_whatever_the_answers(self):
        lines, kinds = kospace.plan(SAMPLE)
        rng = random.Random(20260814)
        for _ in range(50):
            trial = [k if k is not None else rng.choice([kospace.JOIN, kospace.SPACE])
                     for k in kinds]
            self.assertEqual(strip_ws(kospace.render(lines, trial)), strip_ws(SAMPLE))

    def test_unanswered_break_falls_back_to_space(self):
        """판정을 못 받으면(None) 공백 — 손대기 전 원문과 같은 상태라 안전하다."""
        lines, kinds = kospace.plan(SAMPLE)
        out = kospace.render(lines, kinds)          # 아무 답도 채우지 않음
        self.assertIn("증대시킬 수 있는지를", out)
        self.assertEqual(strip_ws(out), strip_ws(SAMPLE))


class AnswerParsingTests(unittest.TestCase):
    def test_parses_expected_and_sloppy_forms(self):
        self.assertEqual(
            kospace.parse_answers("1:J\n2:S\n 3 : j \n4. S\n5) J", 5),
            {1: "J", 2: "S", 3: "J", 4: "S", 5: "J"},
        )

    def test_ignores_out_of_range_and_garbage(self):
        self.assertEqual(kospace.parse_answers("0:J\n99:S\n2:S\nhello", 3), {2: "S"})

    def test_missing_answers_are_simply_absent(self):
        self.assertEqual(kospace.parse_answers("", 4), {})
        self.assertEqual(set(kospace.parse_answers("1:J\n3:S", 4)), {1, 3})

    def test_questions_carry_context_on_both_sides(self):
        lines, kinds = kospace.plan(SAMPLE)
        q = kospace.format_questions(lines, kospace.pending_indexes(kinds)[:2])
        rows = q.split("\n")
        self.assertEqual(len(rows), 2)
        for n, row in enumerate(rows, 1):
            self.assertTrue(row.startswith(f"{n}. "))
            self.assertIn("⏎", row)


if __name__ == "__main__":
    unittest.main()
