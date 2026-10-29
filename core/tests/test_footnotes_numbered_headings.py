import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
import unittest

from services import footnotes
from services import epub_export as ex

_PROSE = ("이 문단은 본문 산문이다. 세계와의 관계는 여러 층위에서 형성되며, 그 관계의 질은 "
          "사회적 조건에 따라 달라진다. ") * 8          # 한 문단 400자 이상


def _chapter() -> str:
    """쪽 구분 없는 번역본 한 장 — 번호 붙은 절 제목 아래로 긴 본문이 이어진다."""
    return "\n\n".join([
        "장 첫머리 문단이다. " + _PROSE,
        "1 첫째 절: 몸과 세계",
        _PROSE, _PROSE,
        "2 둘째 절: 일상과 리듬",
        _PROSE,
        "3 셋째 절: 제도적 요인",
        _PROSE, _PROSE, _PROSE,
    ])


class NumberedHeadingIsNotFootnoteTest(unittest.TestCase):
    """번호 붙은 절 제목을 각주로 보고 본문을 삼키지 않는다 (2026-10-30, 로자 『Resonance』 EPUB)."""

    def test_절_제목_사슬은_각주가_아니다(self):
        head, notes = footnotes._split_notes(_chapter())
        self.assertEqual(notes, [])
        self.assertEqual(head, _chapter())

    def test_EPUB_본문에_글이_모두_남는다(self):
        body, defs = ex._footnote_parts(_chapter())
        self.assertEqual(defs, {})
        self.assertEqual(body.count("이 문단은 본문 산문이다."), _chapter().count("이 문단은 본문 산문이다."))

    def test_쪽_아래_진짜_각주는_그대로_잡힌다(self):
        page = "\n".join([
            "본문 문장이 이어진다.1 다른 문장도 있다.2",
            "",
            "1 홍길동, 『세계와 관계』(서울: 출판사, 2020), 12.",
            "2 위의 책, 34.",
        ])
        head, notes = footnotes._split_notes(page)
        self.assertEqual([n for n, _ in notes], [1, 2])
        self.assertIn("본문 문장이 이어진다.", head)

    def test_여러_줄로_이어진_긴_각주도_받는다(self):
        long_note = "3 " + "각주 설명이 길게 이어진다. " * 30          # 빈 줄 없이 한 덩어리
        page = "본문이다.3\n\n" + long_note + "\n4 짧은 각주다."
        _head, notes = footnotes._split_notes(page)
        self.assertEqual([n for n, _ in notes], [3, 4])


if __name__ == "__main__":
    unittest.main()
