# -*- coding: utf-8 -*-
"""학술지 PDF의 각주·쪽 부속물 회귀 테스트 — 2026-09-21.

실측 대상: 『Tyndale Bulletin』 47:1 Paul, 'Genesis 4:17-24'. 이 논문을 전자책으로
펴면 쪽마다 머리글과 발행처 주소가 문단으로 끼어들고, 각주 23개 중 5개만 잡혔다.
원인이 넷이었고 서로 다른 자리에 있었다 — 아래 시험이 넷을 각각 지킨다.

★이 파일이 지키려는 것은 «떼어내는 것»만이 아니다. 잘못 떼어낸 본문은 되찾을 수
없으므로 «안 떼는 것»을 지키는 시험을 같은 수로 둔다.
"""
import unittest

from services import footnotes
from services import epub_export


class 붙은각주번호(unittest.TestCase):
    """위첨자가 본문 글자에 붙어 추출되는 판 — `1Jub. 4:9-32`."""

    def test_번호가_붙어_있어도_각주로_본다(self):
        page = ("도시의 논증들이라고 그는 말한다.1 이어서 필론은\f"
                "1Jub. 4:9-32, esp. v. 17.\n"
                "2Philo, De Posteritate Caini 72-117.")
        r = footnotes.convert(page)
        self.assertEqual({n.num for n in r.notes}, {1, 2})

    def test_연도는_각주가_아니다(self):
        self.assertIsNone(footnotes._NOTE_LINE.match("1996 was a turning point"))

    def test_쪽번호만_있는_줄은_각주가_아니다(self):
        self.assertIsNone(footnotes._NOTE_LINE.match("146"))

    def test_소문자로_이어지면_각주가_아니다(self):
        """`1st century`의 1을 각주로 보면 본문이 찢어진다."""
        self.assertIsNone(footnotes._NOTE_LINE.match("1st century sources"))


class 위첨자번호(unittest.TestCase):
    """번역기가 각주 번호를 위첨자 글자로 옮겨 놓는다 — `¹`은 `\\d`가 아니다."""

    def test_위첨자를_보통숫자로_되돌린다(self):
        self.assertEqual(footnotes.normalize_superscripts("기록하였다.¹ 따라서"),
                         "기록하였다.1 따라서")

    def test_거듭제곱은_건드리지_않는다(self):
        """앞에 숫자가 붙은 위첨자는 각주가 아니다."""
        self.assertEqual(footnotes.normalize_superscripts("면적은 10²이다"), "면적은 10²이다")

    def test_위첨자_각주도_찾아_연결한다(self):
        page = ("달의 순서를 책에 기록하였다.¹ 그래서 연도를 셀 수 있다.\f"
                "¹ Jub. 4:9-32, 특히 v. 17.\n"
                "² 희년서는 연대기에 큰 관심을 두었다.")
        r = footnotes.convert(page)
        self.assertEqual({n.num for n in r.notes}, {1, 2})
        self.assertIn("기록하였다.[^1]", r.markdown)


class 쪽부속물(unittest.TestCase):
    """쪽마다 되풀이되는 머리글·쪽번호·발행처 도장."""

    BOOK = ["머리글 아래 본문이 온다.\fPAUL: Genesis 4:17-24\n145\n"
            "첫째 쪽 본문이다.\nhttps://tyndalebulletin.org/\f"
            "PAUL: Genesis 4:17-24\n146\n둘째 쪽 본문이다.\n"
            "https://tyndalebulletin.org/\fPAUL: Genesis 4:17-24\n147\n"
            "셋째 쪽 본문이다.\nhttps://tyndalebulletin.org/"]

    def test_머리글과_도장을_본문에서_걷어낸다(self):
        furn, stamps = footnotes.book_furniture(self.BOOK)
        r = footnotes.convert(self.BOOK[0], furniture=furn, stamps=stamps)
        self.assertNotIn("PAUL: Genesis", r.markdown)
        self.assertNotIn("tyndalebulletin.org", r.markdown)

    def test_본문은_한_글자도_잃지_않는다(self):
        furn, stamps = footnotes.book_furniture(self.BOOK)
        r = footnotes.convert(self.BOOK[0], furniture=furn, stamps=stamps)
        for 본문 in ("첫째 쪽 본문이다.", "둘째 쪽 본문이다.", "셋째 쪽 본문이다."):
            self.assertIn(본문, r.markdown)

    def test_본문에_들러붙은_머리글은_앞머리만_뗀다(self):
        """줄째로 지우면 본문을 잃는다 — 확정된 머리글 토막만 떼어낸다."""
        book = [self.BOOK[0] + "\fPAUL: Genesis 4:17-24붙어 나온 본문이다."]
        furn, stamps = footnotes.book_furniture(book)
        r = footnotes.convert(book[0], furniture=furn, stamps=stamps)
        self.assertIn("붙어 나온 본문이다.", r.markdown)
        self.assertNotIn("PAUL: Genesis", r.markdown)

    def test_되풀이되지_않는_주소는_본문으로_남긴다(self):
        """한 번만 나오는 주소는 본문이 인용한 것일 수 있다."""
        one = "본문이다. 자세한 것은 아래를 보라.\nhttps://example.org/only-once"
        r = footnotes.convert(one)
        self.assertIn("example.org/only-once", r.markdown)

    def test_책_전체로_세야_짧은_장이_걸린다(self):
        """★학술지는 머리글이 짝·홀 쪽에서 번갈아 나온다. 3쪽짜리 장만 보면
        각각 1~2회뿐이라 되풀이 문턱에 영영 못 미친다."""
        짧은장 = ("160\nTYNDALE BULLETIN 47:1 (1996)\n첫 쪽.\f"
                  "PAUL: Genesis 4:17-24\n161\n둘째 쪽.\f"
                  "162\nTYNDALE BULLETIN 47:1 (1996)\n셋째 쪽.")
        self.assertEqual(footnotes._running_heads(짧은장.split("\f")), set())   # 혼자서는 못 센다
        furn, _ = footnotes.book_furniture(self.BOOK + [짧은장])
        r = footnotes.convert(짧은장, furniture=furn)
        self.assertNotIn("PAUL: Genesis", r.markdown)
        self.assertIn("둘째 쪽.", r.markdown)


class 쪽구분보존(unittest.TestCase):
    """★`strip_running_headers`가 쪽 구분(`\\f`)을 먹던 버그 — 모든 책에 듣던 것."""

    def test_머리글을_걷어내도_쪽_구분은_남는다(self):
        text = "첫 쪽 본문.\n\n둘째 문단.\f둘째 쪽 본문.\n\n넷째 문단."
        out, _ = epub_export.strip_running_headers(text, "01_Sample")
        self.assertEqual(out.count("\f"), 1,
                         "쪽 구분이 사라지면 각주도 머리글도 찾을 수 없다")

    def test_쪽_구분이_사라지면_머리글을_못_찾는다(self):
        """왜 위 시험이 필요한지를 못박아 둔다."""
        pages = ["A: 제목\n본문", "A: 제목\n본문", "A: 제목\n본문"]
        self.assertTrue(footnotes._running_heads(pages))          # 쪽이 나뉘면 찾는다
        self.assertFalse(footnotes._running_heads(["\n".join(pages)]))  # 한 덩이면 못 찾는다


if __name__ == "__main__":
    unittest.main()
