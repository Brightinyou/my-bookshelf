# -*- coding: utf-8 -*-
"""파일 옮기기 회귀 테스트 — services/convert._move_over.

2026-08-26 윈도우에서 앱이 통째로 멎었다:
    PermissionError: [WinError 32] 다른 프로세스가 파일을 사용 중
이미 변환해 둔 PDF를 다시 변환할 때였다. 원인이 둘 겹쳐 있었다 —
목적지에 같은 이름이 있어 os.rename이 실패해 **복사 경로**로 내려갔고,
그 파일을 미리보기 창이 붙들고 있었다.

여기서 못 박는 것: **목적지에 같은 이름이 있어도 옮겨진다.**
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from services.convert import _move_over


class MoveOverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mv_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_목적지가_비어_있으면_그냥_옮긴다(self):
        src, dst = self.tmp / "a.txt", self.tmp / "b.txt"
        src.write_text("새 내용", encoding="utf-8")
        _move_over(src, dst)
        self.assertFalse(src.exists())
        self.assertEqual(dst.read_text(encoding="utf-8"), "새 내용")

    def test_목적지에_같은_이름이_있어도_덮어쓴다(self):
        """이게 이 파일의 존재 이유다 — 다시 변환하면 늘 이 상황이 된다."""
        src, dst = self.tmp / "a.txt", self.tmp / "b.txt"
        src.write_text("새 내용", encoding="utf-8")
        dst.write_text("옛 내용", encoding="utf-8")
        _move_over(src, dst)
        self.assertFalse(src.exists())
        self.assertEqual(dst.read_text(encoding="utf-8"), "새 내용")

    def test_잠긴_목적지는_몇_번_다시_해_본다(self):
        """윈도우에서만 재현되는 상황이라, 여기서는 '예외를 삼키지 않는다'만 본다."""
        src = self.tmp / "a.txt"
        src.write_text("x", encoding="utf-8")
        with self.assertRaises(OSError):
            _move_over(src, self.tmp / "없는폴더" / "b.txt", tries=2)


if __name__ == "__main__":
    unittest.main()
