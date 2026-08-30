# -*- coding: utf-8 -*-
"""위키 생성기가 원본 TXT를 찾는 방법 — chapter_wiki.

2026-08-30에 «Wiki 생성»을 눌러도 아무 일이 없다는 신고가 들어왔다. 화면에는
«✅ 백그라운드 시작»이 뜨는데 노트는 만들어지지 않았고, 흔적은 로그에만 있었다.

    RuntimeError: 소스 없음: 01_시간과 타자_임마누엘 레비나스 (재처리 필요)

원인은 둘이었다.
  · 화면은 목록에서 고른 TXT 경로를 `--file`로 넘겼는데, main()이 그 경로를 버리고
    이름만 뽑아 `process_book`에 넘겼다. 건네받은 파일을 한 번도 열지 않았다.
  · 이름으로 찾는 `find_txt`는 `*/1_txt/`와 `raw/processed/`만 봤다. 둘 다 v0.9.0에서
    쓰기를 멈춘 옛 자리라 지금 설치본에는 파일이 하나도 없다. 실제 TXT는 2_변환TXT와
    3_챕터/<책>/ 에 있다.

여기서 못 박는 것은 둘이다.
  · find_txt는 지금 쓰는 폴더에서 찾는다.
  · 부른 쪽이 파일 경로를 건네주면 process_book은 이름으로 다시 찾지 않는다.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import chapter_wiki as cw
import config as cfg
import gemini_wiki as gw


class WikiSourceLookupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wikisrc_"))
        self.txt_dir = self.tmp / "2_변환TXT"
        self.chapters_dir = self.tmp / "3_챕터"
        self.legacy = self.tmp / "legacy"
        for d in (self.txt_dir, self.chapters_dir, self.legacy):
            d.mkdir(parents=True, exist_ok=True)
        self._patches = [
            mock.patch.object(cfg, "TXT_DIR", self.txt_dir),
            mock.patch.object(cfg, "CHAPTERS_DIR", self.chapters_dir),
            mock.patch.object(cw, "DONE_DIR", self.legacy),
            mock.patch.object(gw, "SRC_DIR", self.legacy / "processed"),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_변환TXT_폴더에서_찾는다(self):
        """이게 이 파일의 존재 이유다 — 옛 폴더만 보면 언제나 None이었다."""
        f = self.txt_dir / "어떤 책.txt"
        f.write_text("본문", encoding="utf-8")
        self.assertEqual(cw.find_txt("어떤 책"), f)

    def test_챕터_폴더에서도_찾는다(self):
        book = self.chapters_dir / "어떤 책"
        book.mkdir()
        f = book / "01_어떤 책.txt"
        f.write_text("본문", encoding="utf-8")
        self.assertEqual(cw.find_txt("01_어떤 책"), f)

    def test_없으면_None(self):
        self.assertIsNone(cw.find_txt("없는 책"))

    def test_건네받은_경로를_이름조회보다_먼저_쓴다(self):
        """UI가 고른 파일이 이름으로는 안 찾아져도 그대로 처리해야 한다."""
        f = self.tmp / "어디에도 등록 안 된.txt"
        f.write_text("본문", encoding="utf-8")
        self.assertIsNone(cw.find_txt(f.stem))   # 이름으로는 못 찾는 자리

        sentinel = {"mode": "single"}
        with mock.patch.object(cw, "find_layout_md", return_value=None), \
             mock.patch.object(cw, "chapter_split", return_value=("single", [])), \
             mock.patch.object(cw, "_single_pass", return_value=sentinel) as single:
            out = cw.process_book(f.stem, "auto", txt_path=str(f))

        self.assertEqual(out, sentinel)
        single.assert_called_once_with(f.stem, f)

    def test_경로도_이름도_없으면_소스없음(self):
        with mock.patch.object(cw, "find_layout_md", return_value=None):
            with self.assertRaises(RuntimeError) as e:
                cw.process_book("없는 책", "auto")
        self.assertIn("소스 없음", str(e.exception))


if __name__ == "__main__":
    unittest.main()
