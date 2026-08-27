# -*- coding: utf-8 -*-
"""차례 쪽만 뽑은 PDF 회귀 테스트 — services/toc.pages_pdf.

이 장치의 존재 이유: 장 구분이 맞는지는 **차례와 견주어야** 알 수 있는데, 앱 창 안에
끼운 이미지는 작고 확대가 안 된다. 쪽만 뽑아 OS 기본 뷰어로 열면 진짜 별도 창이 뜬다.

★파일 이름이 곧 창 제목이므로 **책 이름이 들어가야** 하고, 이름이 고정이어야 다시
눌러도 창이 늘어나지 않는다.
"""
import tempfile
import unittest
from pathlib import Path

try:
    import pypdfium2 as pdfium
except Exception:
    pdfium = None

from services import toc as toc_svc


@unittest.skipIf(pdfium is None, "pypdfium2 없음")
class PagesPdfTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.pdf = self.tmp / "어떤 책_지은이.pdf"
        doc = pdfium.PdfDocument.new()
        for _ in range(6):
            doc.new_page(300, 400)
        doc.save(str(self.pdf))
        doc.close()

    def test_고른_쪽만_담는다(self):
        out = toc_svc.pages_pdf(self.pdf, [2, 3])
        self.assertIsNotNone(out)
        doc = pdfium.PdfDocument(str(out))
        try:
            self.assertEqual(len(doc), 2)
        finally:
            doc.close()

    def test_책_이름이_파일_이름에_들어간다(self):
        out = toc_svc.pages_pdf(self.pdf, [0])
        self.assertIn("어떤 책_지은이", out.name)
        self.assertIn("차례", out.name)

    def test_같은_이름을_다시_쓴다(self):
        """다시 눌러도 창이 늘어나면 안 된다."""
        a = toc_svc.pages_pdf(self.pdf, [0])
        b = toc_svc.pages_pdf(self.pdf, [1])
        self.assertEqual(a, b)

    def test_범위_밖_쪽은_거른다(self):
        out = toc_svc.pages_pdf(self.pdf, [1, 99, -3])
        doc = pdfium.PdfDocument(str(out))
        try:
            self.assertEqual(len(doc), 1)
        finally:
            doc.close()

    def test_고를_쪽이_없으면_만들지_않는다(self):
        self.assertIsNone(toc_svc.pages_pdf(self.pdf, [99]))
        self.assertIsNone(toc_svc.pages_pdf(self.pdf, []))

    def test_없는_PDF는_조용히_None(self):
        self.assertIsNone(toc_svc.pages_pdf(self.tmp / "없다.pdf", [0]))


if __name__ == "__main__":
    unittest.main()


class 여러쪽차례Test(unittest.TestCase):
    """차례가 두 쪽을 넘으면 이어지는 쪽까지 올린다 (2026-08-27 연구자 지적).

    연구자 말 — "Technology and the Virtues_셰넌 발러 책의 경우는 목차페이지가
    2페이지 이상이라 마지막을 눈으로 검증하지 못했어".

    예전 _add() 는 (i, i+1) 딱 두 쪽만 올렸다. 표제(CONTENTS)는 첫 쪽에만 있으므로
    이어짐은 «쪽번호로 끝나는 줄이 여럿» 으로 판정한다.
    """

    @staticmethod
    def _page(lines):
        return "\n".join(lines)

    def _doc(self, pages):
        return "\f".join(pages)

    def test_세쪽짜리_차례를_끝까지_올린다(self):
        toc_pg = self._page(["CONTENTS", "Introduction ... 1", "Chapter One ... 11",
                             "Chapter Two ... 33", "Chapter Three ... 55"])
        cont = self._page(["Chapter Four ... 77", "Chapter Five ... 99",
                           "Chapter Six ... 120", "Notes ... 145", "Index ... 190"])
        cont2 = self._page(["Appendix A ... 201", "Appendix B ... 210",
                            "Bibliography ... 220", "Credits ... 240", "More ... 250"])
        body = self._page(["본문이 시작된다. 아주 긴 문장이 이어진다.", "두 번째 문단이다."])
        got = toc_svc.toc_page_candidates(self._doc(["표지", toc_pg, cont, cont2, body, body]))
        self.assertEqual(got, [1, 2, 3], "차례 세 쪽이 모두 올라와야 한다")

    def test_본문에서_멈춘다(self):
        """차례가 한 쪽뿐이면 본문까지 끌어오지 않는다 — 바로 다음 쪽만 덤으로."""
        toc_pg = self._page(["CONTENTS", "Introduction ... 1", "Chapter One ... 11",
                             "Chapter Two ... 33"])
        body = self._page(["본문이 시작된다. 아주 긴 문장이 이어진다.", "두 번째 문단이다.",
                           "세 번째 문단."])
        got = toc_svc.toc_page_candidates(self._doc(["표지", toc_pg, body, body, body]))
        self.assertEqual(got, [1, 2], "차례 쪽과 그 다음 쪽까지만")


if __name__ == "__main__":
    unittest.main()
