# -*- coding: utf-8 -*-
"""MD를 직접 올렸을 때 분할이 원본을 찾는 자리 — services.files.find_md.

2026-09-25에 바티칸 «Antiqua et Nova» 영문 MD를 올렸더니 «분할 대기 (1권)»에는
멀쩡히 떠 있는데 「분할 처리」도 「다음단계로 이동」도 이 말만 뱉고 끝났다.

    바티칸_Antiqua-et-Nova_영문원문_20250128: TXT/MD 파일이 없습니다.

저장하는 곳과 찾는 곳이 어긋나 있었다.
  · 업로드(convert._do_ocr_only)는 MD를 TXT와 같은 1_txt/에 둔다.
  · 목록(pipeline_app)은 1_txt/의 *.txt와 *.md를 둘 다 훑는다 — 그래서 보인다.
  · 그런데 find_md는 구버전 보관 폴더(_구버전보관/2_md)와 워크스페이스 루트만 봤다.
    지금 쓰는 자리를 한 번도 안 봤으니 화면에 보이는 책을 실행이 못 찾았다.

여기서 못 박는 것은 둘이다.
  · find_md는 지금 쓰는 1_txt/에서 먼저 찾는다 — find_txt와 같은 순서로.
  · 분할이 끝나 1_txt/완료/로 옮겨진 뒤에도 찾는다(_archive_split_source가 .md도 옮긴다).
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import config as cfg
from services.files import find_md, find_txt

STEM = "바티칸_Antiqua-et-Nova_영문원문_20250128"


class FindMdSourceLookupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="findmd_"))
        self.txt_dir = self.tmp / "2_변환TXT"
        self.archive = self.txt_dir / "완료"
        self.legacy_keep = self.tmp / "_구버전보관"
        self.ws_root = self.tmp / "ws"
        for d in (self.txt_dir, self.archive, self.legacy_keep, self.ws_root):
            d.mkdir(parents=True, exist_ok=True)
        self._patches = [
            mock.patch.object(cfg, "TXT_DIR", self.txt_dir),
            mock.patch.object(cfg, "TXT_ARCHIVE_DIR", self.archive),
            mock.patch.object(cfg, "LEGACY_KEEP", self.legacy_keep),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_직접_올린_md를_1_txt에서_찾는다(self):
        """업로드가 두는 자리 = 실행이 찾는 자리."""
        src = self.txt_dir / f"{STEM}.md"
        src.write_text("I. **Introduction**\n", encoding="utf-8")
        self.assertEqual(find_md(self.ws_root, "My Bookshelf", STEM), src)

    def test_분할_뒤_완료_폴더로_옮겨져도_찾는다(self):
        arch = self.archive / f"{STEM}.md"
        arch.write_text("I. **Introduction**\n", encoding="utf-8")
        self.assertEqual(find_md(self.ws_root, "My Bookshelf", STEM), arch)

    def test_없으면_None(self):
        self.assertIsNone(find_md(self.ws_root, "My Bookshelf", STEM))

    def test_txt와_같은_자리를_본다(self):
        """find_txt와 find_md의 1순위가 갈라지면 같은 사고가 되풀이된다."""
        (self.txt_dir / f"{STEM}.txt").write_text("a", encoding="utf-8")
        (self.txt_dir / f"{STEM}.md").write_text("b", encoding="utf-8")
        self.assertEqual(
            find_txt(self.ws_root, "My Bookshelf", STEM).parent,
            find_md(self.ws_root, "My Bookshelf", STEM).parent,
        )


if __name__ == "__main__":
    unittest.main()
