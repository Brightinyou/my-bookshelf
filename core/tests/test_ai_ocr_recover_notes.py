# -*- coding: utf-8 -*-
"""빠진 각주 되찾기 회귀 테스트 — services/ai_ocr.recover_notes.

연구자 제안(2026-08-25): 뭉개진 글에서 각주의 경계를 추리해 메우는 것보다,
**어느 쪽에 몇 번 각주가 빠졌는지 아는 채로 그 쪽을 다시 읽는 편**이 확실하다.
모델에게 무엇을 찾아야 하는지 알려 주는 것이기 때문이다.

★**나아졌을 때만 바꾼다.** 다시 읽었는데 여전히 없거나 글이 크게 줄었으면 옛 판독을
그대로 둔다 — 고치려다 멀쩡한 쪽을 망치면 안 된다. 그래서 테스트의 절반이
'안 바꾸는 것'을 지킨다.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from services import ai_ocr


def _page(*notes, body="본문이 여기 있고 충분히 길게 이어진다. 그리고 더 이어진다."):
    return body + "\n" + "\n".join(f"{n} 저자, 『책 이름』, {n * 10}." for n in notes)


class RecoverNotesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "책.txt"
        self.wd = ai_ocr.work_dir(self.out)
        self.wd.mkdir(parents=True, exist_ok=True)
        # 1쪽 각주 3 · 2쪽 각주 6,7 → 4·5가 빠졌다
        (self.wd / "p0001.txt").write_text(_page(3), encoding="utf-8")
        (self.wd / "p0002.txt").write_text(_page(6, 7), encoding="utf-8")

    def _run(self, fake_text):
        with mock.patch.object(ai_ocr, "page_count", return_value=2), \
             mock.patch.object(ai_ocr, "render_page",
                               side_effect=lambda *a, **k: self.tmp / "x.jpg"), \
             mock.patch.object(Path, "unlink", lambda *a, **k: None), \
             mock.patch.object(ai_ocr, "read_pages", return_value=[fake_text]) as rp:
            rows = ai_ocr.recover_notes(Path("없는.pdf"), self.out, "codex_cli")
        return rows, rp

    def test_빠진_번호를_프롬프트에_실어_보낸다(self):
        rows, rp = self._run(_page(4, 5, 6, 7))
        self.assertEqual(rows[0]["want"], [4, 5])
        hint = rp.call_args.kwargs.get("hint", "")
        self.assertIn("4·5", hint)
        self.assertIn("각주", hint)

    def test_찾아오면_갈아_끼운다(self):
        rows, _ = self._run(_page(4, 5, 6, 7))
        self.assertTrue(rows[0]["ok"])
        self.assertEqual(rows[0]["got"], [4, 5])
        self.assertIn("4 저자", (self.wd / "p0002.txt").read_text(encoding="utf-8"))

    # ── 아래는 '안 바꾸는 것'을 지킨다 ──────────────────────────
    def test_못_찾으면_옛_판독을_그대로_둔다(self):
        before = (self.wd / "p0002.txt").read_text(encoding="utf-8")
        rows, _ = self._run(_page(6, 7))
        self.assertFalse(rows[0]["ok"])
        self.assertEqual((self.wd / "p0002.txt").read_text(encoding="utf-8"), before)

    def test_글이_크게_줄면_바꾸지_않는다(self):
        """번호는 찾았어도 본문이 날아갔으면 나아진 것이 아니다."""
        before = (self.wd / "p0002.txt").read_text(encoding="utf-8")
        rows, _ = self._run("4 저자, 『책』, 40.\n5 저자, 『책』, 50.")
        self.assertFalse(rows[0]["ok"])
        self.assertEqual((self.wd / "p0002.txt").read_text(encoding="utf-8"), before)

    def test_판독이_실패해도_넘어간다(self):
        with mock.patch.object(ai_ocr, "page_count", return_value=2), \
             mock.patch.object(ai_ocr, "render_page",
                               side_effect=lambda *a, **k: self.tmp / "x.jpg"), \
             mock.patch.object(Path, "unlink", lambda *a, **k: None), \
             mock.patch.object(ai_ocr, "read_pages", side_effect=RuntimeError("끊김")):
            rows = ai_ocr.recover_notes(Path("없는.pdf"), self.out, "codex_cli")
        self.assertFalse(rows[0]["ok"])
        self.assertIn("RuntimeError", rows[0]["note"])

    def test_끊긴_곳이_없으면_아무것도_안_한다(self):
        (self.wd / "p0002.txt").write_text(_page(4, 5), encoding="utf-8")
        with mock.patch.object(ai_ocr, "page_count", return_value=2), \
             mock.patch.object(ai_ocr, "read_pages") as rp:
            self.assertEqual(ai_ocr.recover_notes(Path("없는.pdf"), self.out, "codex_cli"), [])
        rp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
