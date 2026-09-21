# -*- coding: utf-8 -*-
"""해설·참고문헌·번호 절 — 『시간과 타자』(레비나스, 강영안 옮김) 사례 (2026-09-21).

책 뒤에 옮긴이의 「해설: 레비나스의 철학」이 소논문처럼 붙어 있고(1.~5. 절 뒤에
「6. 맺음말」), 그 뒤에 30쪽짜리 「관계문헌」이 온다. 예전에는
  · 해설이 4강에 붙고,
  · 「6. 맺음말」만 장이 되고(경계 낱말 자동 분할),
  · 「관계문헌」이 그 장에 딸려 번역·요약 대상이 됐다.

지키는 것:
  · 번호 절이 줄지어 선 장에서는 그 꼴의 「6. 맺음말」을 가르지 않는다.
  · 「관계문헌」류는 뒷부속으로 알아보고 번역·요약 대기열에서 뺀다.
  · 시각 판독 없이도 마지막 장 꼬리의 「관계문헌」은 제 이름으로 떼어진다.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

import config as cfg
from services import chapter_map as cmap
from services import toc

WS = "default"
BOOK = "시간과 타자"


class NumberedSectionGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="numsec_"))
        self._prev = cfg.CHAPTERS_DIR
        cfg.CHAPTERS_DIR = self.tmp
        self.d = self.tmp / BOOK
        self.d.mkdir(parents=True)

    def tearDown(self):
        cfg.CHAPTERS_DIR = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name, *paras):
        (self.d / name).write_text("\n\n".join(paras) + "\n", encoding="utf-8")

    def test_번호_절_행렬의_맺음말은_가르지_않는다(self):
        self._write("05_해설.txt", "해설 첫머리. " * 20,
                    "1. 레비나스 철학의 근본 물음", "본문. " * 20,
                    "2. 존재 부조리의 경험과 주체의 출현", "본문. " * 20,
                    "3. 향유, 거주 및 노동", "본문. " * 20,
                    "6. 맺음말", "정리. " * 20)
        self.assertEqual(cmap.auto_split_known_headings(WS, BOOK), [])

    def test_로마_숫자_절_행렬도_같다(self):
        self._write("01_논문.txt", "머리. " * 20, "II. 선행 연구", "본문. " * 20,
                    "III. 분석", "본문. " * 20, "IV. 논의", "본문. " * 20, "V. 나가는 말", "정리. " * 20)
        self.assertEqual(cmap.auto_split_known_headings(WS, BOOK), [])

    def test_홀로_선_번호_결론은_예전처럼_가른다(self):
        self._write("01_본문.txt", "본문. " * 20, "IV. 결론", "정리하면. " * 20)
        self.assertEqual(cmap.auto_split_known_headings(WS, BOOK), ["IV. 결론"])

    def test_numbering_style(self):
        self.assertEqual(cmap.numbering_style("6. 맺음말"), "arabic")
        self.assertEqual(cmap.numbering_style("V. 나가는 말"), "roman")
        self.assertEqual(cmap.numbering_style("Ⅳ. 결론"), "fw")
        self.assertEqual(cmap.numbering_style("제 3 강 노동"), "jang")
        self.assertEqual(cmap.numbering_style("해설"), "")


class BackmatterTest(unittest.TestCase):
    def test_뒷부속_제목을_알아본다(self):
        for t in ("관계문헌", "참고 문헌", "찾아보기", "색인", "References", "Bibliography",
                  "부록: 참고문헌", "Works Cited"):
            self.assertTrue(cmap.is_backmatter_title(t), t)
        for t in ("해설", "부록", "제4강 향수 있음과 타인과의 관계", "6. 맺음말", "머리말"):
            self.assertFalse(cmap.is_backmatter_title(t), t)

    def test_마지막_장_꼬리의_관계문헌은_제_이름으로_떼어진다(self):
        txt = ("표지와 머리말. " * 40 + "\f제 1강\n" + "본문. " * 400 + "\f제 2강\n" + "본문. " * 400
               + "\f제 3강\n" + "본문. " * 1000 + "\f관계문헌\n" + "강영안, 「레비나스 철학에서 주체성과 타자」. " * 40)
        offs = toc._page_offsets(txt)
        chs = toc._split_at(txt, [(offs[1], "제1강"), (offs[2], "제2강"), (offs[3], "제3강")])
        self.assertEqual([t for t, _ in chs], ["머리말", "제1강", "제2강", "제3강", "관계문헌"])
        self.assertNotIn("관계문헌", chs[3][1])


class QueueSkipTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bmq_"))
        self._prev = (cfg.CHAPTERS_DIR, cfg.BASE_DIR)
        cfg.BASE_DIR = self.tmp
        cfg.CHAPTERS_DIR = self.tmp / "ch"
        d = cfg.CHAPTERS_DIR / BOOK
        d.mkdir(parents=True)
        (d / "01_제1강.txt").write_text("본문. " * 20, encoding="utf-8")
        (d / "02_해설.txt").write_text("본문. " * 20, encoding="utf-8")
        (d / "03_관계문헌.txt").write_text("문헌. " * 20, encoding="utf-8")

    def tearDown(self):
        cfg.CHAPTERS_DIR, cfg.BASE_DIR = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_대기열_맞추기가_참고문헌을_뺀다(self):
        from unittest.mock import patch
        from services import pipeline_queue as pq
        added: dict[str, list] = {}
        book_rel = str((cfg.CHAPTERS_DIR / BOOK).relative_to(cfg.BASE_DIR)) + "/"
        with patch.object(pq, "queue_list", return_value=[book_rel + "01_제1강.txt"]), \
             patch.object(pq, "queue_remove"), \
             patch.object(pq, "queue_add", side_effect=lambda st, items: added.setdefault(st, []).extend(items)):
            cmap.sync_queue(WS, BOOK)
        names = [Path(x).name for x in added.get("tab3_ready", [])]
        self.assertEqual(names, ["01_제1강.txt", "02_해설.txt"])


if __name__ == "__main__":
    unittest.main()
