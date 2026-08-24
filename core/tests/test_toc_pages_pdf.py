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
