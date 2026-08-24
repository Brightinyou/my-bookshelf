# -*- coding: utf-8 -*-
"""이어하기 회귀 테스트 — 빈 판독 파일을 '읽은 쪽'으로 세지 않는다.

이 장치의 존재 이유: 판독이 통째로 비면 0바이트 파일이 남는다. 그것이 `warn`으로
기록되면 `status != "failed"` 조건을 통과해 **재실행 때마다 영원히 건너뛰어진다.**
실제로 59쪽이 전체 재실행 두 번을 그렇게 빠져나갔다(2026-08-25).

★**진짜 빈 쪽은 건드리지 않는다** — 간지·백지는 `verify()`가 `ok`("빈 쪽")로
판정하고, 그 쪽의 0바이트는 맞는 답이다(10쪽).
"""
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest import mock

from services import ai_ocr


class ResumeTest(unittest.TestCase):
    def _run_targets(self, rows, files):
        """reocr을 판독 직전까지만 돌려 'todo'가 무엇이었는지 잡아낸다."""
        tmp = Path(tempfile.mkdtemp())
        out = tmp / "책.txt"
        wd = ai_ocr.work_dir(out)
        wd.mkdir(parents=True, exist_ok=True)
        (wd / "_report.json").write_text(
            json.dumps([asdict(ai_ocr.PageResult(**r)) for r in rows]), encoding="utf-8")
        for name, body in files.items():
            (wd / name).write_text(body, encoding="utf-8")
        seen: list[int] = []

        def fake_one(batch):
            seen.extend(batch)
            return [ai_ocr.PageResult(pg, "ok", 10, 10, 0.9) for pg in batch]

        with mock.patch.object(ai_ocr, "page_count", return_value=3), \
             mock.patch.object(ai_ocr, "render_page", side_effect=AssertionError("렌더 금지")), \
             mock.patch.object(ai_ocr, "assemble", return_value=out):
            # _one은 지역 함수라 바꿔치기할 수 없다 — read_pages를 막아 대신 잡는다
            with mock.patch.object(ai_ocr, "base_page_text", return_value="x" * 200), \
                 mock.patch.object(ai_ocr, "read_pages", side_effect=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("판독 금지"))):
                res = ai_ocr.reocr(Path("없는.pdf"), out, "codex_cli", workers=1)
        return {r.page for r in res if r.status == "failed"}

    def test_빈_파일에_warn이면_다시_읽는다(self):
        rows = [{"page": 1, "status": "ok", "chars": 10, "base_chars": 10},
                {"page": 2, "status": "warn", "chars": 0, "base_chars": 800},
                {"page": 3, "status": "ok", "chars": 10, "base_chars": 10}]
        files = {"p0001.txt": "본문", "p0002.txt": "", "p0003.txt": "본문"}
        redone = self._run_targets(rows, files)
        self.assertIn(2, redone)          # 빈 쪽만 다시 읽는다
        self.assertNotIn(1, redone)
        self.assertNotIn(3, redone)

    def test_진짜_빈_쪽은_다시_읽지_않는다(self):
        """간지·백지는 status=ok — 0바이트가 맞는 답이다."""
        rows = [{"page": 1, "status": "ok", "chars": 10, "base_chars": 10},
                {"page": 2, "status": "ok", "chars": 0, "base_chars": 0, "note": "빈 쪽"},
                {"page": 3, "status": "ok", "chars": 10, "base_chars": 10}]
        files = {"p0001.txt": "본문", "p0002.txt": "", "p0003.txt": "본문"}
        self.assertEqual(self._run_targets(rows, files), set())

    def test_failed은_파일이_있어도_다시_읽는다(self):
        rows = [{"page": 1, "status": "failed", "chars": 0, "base_chars": 800},
                {"page": 2, "status": "ok", "chars": 10, "base_chars": 10},
                {"page": 3, "status": "ok", "chars": 10, "base_chars": 10}]
        files = {"p0001.txt": "옛 본문", "p0002.txt": "본문", "p0003.txt": "본문"}
        self.assertIn(1, self._run_targets(rows, files))


if __name__ == "__main__":
    unittest.main()
