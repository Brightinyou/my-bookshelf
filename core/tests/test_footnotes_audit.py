# -*- coding: utf-8 -*-
"""각주 번호 연속성 점검 — services/footnotes.audit_sequence.

연구자의 판단을 그대로 규칙으로 옮긴 것이다(2026-08-25):
"각주로는 4 다음 6이 잡히는데 … 그러면 5는 어디선가 사라진 것이다."

각주 번호는 글 안에서 **연속**이므로 빠진 번호는 곧 **놓친 각주**다. 사람은 눈으로
알아채지만 373쪽을 다 훑을 수는 없다.

★**고치지 않고 알리기만 한다.** 빠진 자리를 자동으로 메우려면 각주가 어디서 끝나고
본문이 어디서 다시 시작하는지 알아야 하는데 그건 확신할 수 없는 판단이다.
"""
import unittest

from services import footnotes as fn

SEP = fn.PAGE_SEP


class AuditSequenceTest(unittest.TestCase):
    def _page(self, *notes):
        body = "본문이 여기 있고 이어진다."
        return body + "\n" + "\n".join(f"{n} 저자, 『책 이름』, {n * 10}." for n in notes)

    def test_빠진_번호를_짚는다(self):
        text = self._page(3) + SEP + self._page(6, 7)
        gaps = fn.audit_sequence(text)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["missing"], [4, 5])
        self.assertEqual(gaps[0]["after"], 3)

    def test_이어지면_아무것도_안_짚는다(self):
        text = self._page(3, 4) + SEP + self._page(5, 6)
        self.assertEqual(fn.audit_sequence(text), [])

    def test_장이_바뀌며_1로_돌아가는_것은_넘어간다(self):
        text = self._page(37, 38) + SEP + self._page(1, 2)
        self.assertEqual(fn.audit_sequence(text), [])

    def test_너무_크게_벌어지면_장이_바뀐_것으로_본다(self):
        """15보다 크게 뛰면 같은 글의 연번으로 보기 어렵다 — 헛경고를 내지 않는다."""
        text = self._page(3) + SEP + self._page(80)
        self.assertEqual(fn.audit_sequence(text), [])

    def test_각주가_없다고_잰_쪽은_보지_않는다(self):
        text = self._page(3) + SEP + self._page(6)
        self.assertEqual(fn.audit_sequence(text, has_notes=[True, False]), [])

    def test_각주가_없는_글은_조용하다(self):
        self.assertEqual(fn.audit_sequence("본문뿐이다." + SEP + "여기도 본문뿐."), [])


if __name__ == "__main__":
    unittest.main()
