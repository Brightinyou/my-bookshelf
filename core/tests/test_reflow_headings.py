# -*- coding: utf-8 -*-
"""홀로 선 제목 보존 회귀 테스트 — services/reflowlib.reflow.

2026-08-25에 사고가 났다. Dorobantu 논문의 `Conclusion`이 앞 문단에 먹혀
"...I am strong.”36 Conclusion Although AI..." 가 되었고, 장 분할이 결론 장을
통째로 놓쳤다. 원인은 reflow가 **빈 줄로만** 문단을 나누는데 PDF 텍스트층에는
제목 앞뒤에 빈 줄이 없다는 것.

여기서 못 박는 것은 둘이다.
  · 라틴문자 제목은 제 문단으로 남는다.
  · **한글 본문은 예전과 똑같이 이어 붙는다** — 한글은 어절 경계 줄바꿈이 흔해
    짧은 줄이 널려 있어서, 제목으로 오인하면 본문이 조각난다.
"""
import unittest

from services import reflowlib


def _para(*rows):
    return "\n".join(rows)


LONG = ("Modern developments in evolutionary and cognitive science have increasingly "
        "challenged the view that humans are")
LONG2 = ("Although AI does not, in principle, challenge our theological understanding "
         "of human distinctiveness, our attitude")


class ReflowHeadingTest(unittest.TestCase):
    def _paras(self, text):
        return [p.strip() for p in reflowlib.reflow(text).split("\n\n") if p.strip()]

    def test_홀로_선_영문_제목은_제_문단으로_남는다(self):
        text = _para(LONG, "distinctive creatures indeed.", "Conclusion", LONG2, "raises an alarm.")
        self.assertIn("Conclusion", self._paras(text))

    def test_각주_번호가_붙어_있어도_제목을_알아본다(self):
        """실제 원문이 이 모양이었다 — 앞줄이 `strong.”36` 으로 끝난다."""
        text = _para(LONG, "then I am strong.”36", "Conclusion", LONG2, "raises an alarm.")
        self.assertIn("Conclusion", self._paras(text))

    def test_한글_짧은_줄은_제목으로_오인하지_않는다(self):
        rows = ["기술의 발생적·관계적 관점은 신학적 사유와 실천 역시 물질화의 과정에서",
                "분리되어 있지 않다는 통찰을 통하여 영혼의 구원과 타락한 세계라는",
                "이원론적 분리를 넘어",
                "세계와 그 세계를 형성하고 있는 만물까지도 하나님의 내재하심으로 읽혀",
                "가는 과정이라는 것을 인식하게 한다."]
        paras = self._paras(_para(*rows))
        self.assertEqual(len(paras), 1, f"한글 본문이 쪼개졌다: {paras}")

    def test_앞붙이_상투어는_제목이_아니다(self):
        text = _para(LONG, "of robotics and AI.", "Keywords Moral consideration",
                     LONG2, "raises an alarm.")
        self.assertNotIn("Keywords Moral consideration", self._paras(text))

    def test_참고문헌_조각은_제목이_아니다(self):
        text = _para(LONG, "see the discussion below.", "Technol. 33, 705–715 (2020)",
                     LONG2, "raises an alarm.")
        self.assertNotIn("Technol. 33, 705–715 (2020)", self._paras(text))

    def test_한글_문서_안의_라틴_조각은_건드리지_않는다(self):
        """문서 단위 게이트. 한글 책 판권지의 영문 원제·표 조각이 제목으로 걸려
        나왔었다('OmtKiolagy fora', 'In progress'). 한글 문서는 통째로 예전 동작."""
        ko = "한국어 본문이 길게 이어지는 문단이다. 이 문장은 충분히 길어야 한다. " * 8
        text = _para(ko, "앞 문장이 이렇게 끝난다.", "In progress", ko, "끝난다.")
        self.assertNotIn("In progress", self._paras(text))

    def test_문장_한복판의_짧은_줄은_건드리지_않는다(self):
        """앞줄이 문장으로 닫히지 않았으면 제목일 리 없다 — 그냥 이어 붙는다."""
        text = _para(LONG, "challenged the view that humans", "Are We Still Special",
                     LONG2, "raises an alarm.")
        self.assertNotIn("Are We Still Special", self._paras(text))


if __name__ == "__main__":
    unittest.main()
