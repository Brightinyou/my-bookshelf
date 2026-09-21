# -*- coding: utf-8 -*-
"""장 구분 편집 작업창 — services/ui_chapter_wide (2026-09-21).

지키는 것:
  · 장이 **전부** 한 번에 펼쳐진다 (접힌 선택 상자가 아니다).
  · 제목 칸에서 고치면 바로 파일 이름이 바뀐다.
  · − 는 앞 장에 합치고, ＋ 는 쪽 번호가 붙은 후보에서 골라 새 장을 끼워 넣는다.
  · 절 제목 장은 표시되고 한 단추로 모두 합쳐진다.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

import config as cfg
from services import chapter_map as cmap

WS = "default"
BOOK = "논문집"

APP = '''
import streamlit as st
import config as cfg
from pathlib import Path
cfg.CHAPTERS_DIR = Path(st.session_state["chapters_dir"])
cfg.TXT_DIR = Path(st.session_state["txt_dir"])
cfg.TXT_ARCHIVE_DIR = cfg.TXT_DIR / "done"
from services.ui_chapter_wide import chapter_workbench
chapter_workbench("default", "논문집", key="wb")
'''


class ChapterWorkbenchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb_"))
        self._prev = (cfg.CHAPTERS_DIR, cfg.TXT_DIR, cfg.TXT_ARCHIVE_DIR)
        cfg.CHAPTERS_DIR = self.tmp / "ch"
        cfg.TXT_DIR = self.tmp / "txt"
        cfg.TXT_ARCHIVE_DIR = cfg.TXT_DIR / "done"
        self.d = cfg.CHAPTERS_DIR / BOOK
        self.d.mkdir(parents=True)
        cfg.TXT_ARCHIVE_DIR.mkdir(parents=True)
        self.p1 = "논문 하나의 본문입니다. " * 15
        self.p2 = "논문 둘의 본문입니다. " * 15
        # 원본 6쪽. 챕터는 공백만 다르게 이어 붙인 것이라 쪽을 셀 수 있다.
        pages = [self.p1, "I. 들어가는 말\n" + self.p1, "V. 나가는 말\n" + self.p1,
                 "둘째 논문\n" + self.p2, "새 절 제목\n" + self.p2, "I. 들어가며\n" + self.p1]
        (cfg.TXT_ARCHIVE_DIR / f"{BOOK}.txt").write_text("\f".join(pages), encoding="utf-8")
        (self.d / "01_첫 논문.txt").write_text(self.p1 + "\n", encoding="utf-8")
        (self.d / "02_I. 들어가는 말.txt").write_text("I. 들어가는 말\n\n" + self.p1 + "\n", encoding="utf-8")
        (self.d / "03_V. 나가는 말.txt").write_text("V. 나가는 말\n\n" + self.p1 + "\n", encoding="utf-8")
        (self.d / "04_둘째 논문.txt").write_text(
            "둘째 논문\n\n" + self.p2 + "\n\n새 절 제목\n\n" + self.p2 + "\n", encoding="utf-8")
        (self.d / "05_I. 들어가며.txt").write_text("I. 들어가며\n\n" + self.p1 + "\n", encoding="utf-8")

    def tearDown(self):
        cfg.CHAPTERS_DIR, cfg.TXT_DIR, cfg.TXT_ARCHIVE_DIR = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def app(self):
        app = AppTest.from_string(APP, default_timeout=15)
        app.session_state["chapters_dir"] = str(cfg.CHAPTERS_DIR)
        app.session_state["txt_dir"] = str(cfg.TXT_DIR)
        return app.run()

    def _titles(self):
        return [cmap.chapter_title(f) for f in cmap.chapter_files(WS, BOOK)]

    def test_모든_장이_한꺼번에_펼쳐지고_쪽이_보인다(self):
        app = self.app()
        self.assertFalse(app.exception, [x.message for x in app.exception])
        titles = [w.value for w in app.text_input if str(w.key).startswith("wb_t_")]
        self.assertEqual(titles, ["첫 논문", "I. 들어가는 말", "V. 나가는 말", "둘째 논문", "I. 들어가며"])
        shown = [m.value for m in app.markdown]
        self.assertIn("1쪽", shown)
        self.assertIn("4–5쪽", shown)
        self.assertIn("6쪽", shown)
        self.assertTrue(any("절 제목이 장으로" in w.value for w in app.warning))

    def test_제목을_고치면_파일_이름이_바뀐다(self):
        app = self.app()
        app.text_input(key="wb_t_01_첫 논문").set_value("첫 논문 — 고친 제목").run()
        self.assertFalse(app.exception, [x.message for x in app.exception])
        self.assertEqual(self._titles()[0], "첫 논문 — 고친 제목")

    def test_빼기는_앞_장에_합친다(self):
        app = self.app()
        self.assertTrue(app.button(key="wb_minus_01_첫 논문").disabled)
        app.button(key="wb_minus_02_I. 들어가는 말").click().run()
        self.assertEqual(self._titles(), ["첫 논문", "V. 나가는 말", "둘째 논문", "I. 들어가며"])
        body = cmap.chapter_files(WS, BOOK)[0].read_text(encoding="utf-8")
        self.assertEqual(body.count("논문 하나의 본문입니다."), 30)
        self.assertIn("I. 들어가는 말", body)                 # 본문 글자를 잃지 않는다

    def test_절_제목_장을_한_단추로_모두_합친다(self):
        app = self.app()
        app.button(key="wb_merge_sect").click().run()
        self.assertEqual(self._titles(), ["첫 논문", "둘째 논문"])
        self.assertFalse(any("절 제목이 장으로" in w.value for w in app.warning))
        self.assertTrue(any("3개 장을 앞 장에 합쳤습니다" in s.value for s in app.success))

    def test_더하기는_쪽이_붙은_후보에서_골라_새_장을_끼운다(self):
        app = self.app()
        app.button(key="wb_plus_04_둘째 논문").click().run()
        app.text_input(key="wb_q_04_둘째 논문").set_value("새 절").run()
        pick = app.selectbox(key="wb_pick_04_둘째 논문")
        self.assertEqual(len(pick.options), 1)
        self.assertTrue(pick.format_func(0).startswith("5쪽 · 새 절 제목"))
        app.text_input(key="wb_nt_04_둘째 논문").set_value("끼워 넣은 장").run()
        app.button(key="wb_do_04_둘째 논문").click().run()
        self.assertFalse(app.exception, [x.message for x in app.exception])
        self.assertEqual(self._titles(), ["첫 논문", "I. 들어가는 말", "V. 나가는 말",
                                          "둘째 논문", "끼워 넣은 장", "I. 들어가며"])
        files = cmap.chapter_files(WS, BOOK)
        self.assertTrue(files[4].read_text(encoding="utf-8").startswith("새 절 제목"))


class PopupArgsTest(unittest.TestCase):
    def test_popup_flag_parsing(self):
        import desktop
        self.assertIsNone(desktop._popup_args([]))
        self.assertIsNone(desktop._popup_args(["--popup"]))
        self.assertEqual(desktop._popup_args(["--popup", "http://x/?view=chapter_editor"]),
                         ("http://x/?view=chapter_editor", desktop.APP_TITLE))
        self.assertEqual(desktop._popup_args(["--popup", "http://x/", "--title", "편집"]),
                         ("http://x/", "편집"))


class CandidateOrderTest(unittest.TestCase):
    """후보가 많으면 제목답게 생긴 줄을 앞에 세운다 (2026-09-21 실측: 기본 후보가 문장 조각)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cand_"))
        self._prev = cfg.CHAPTERS_DIR
        cfg.CHAPTERS_DIR = self.tmp
        d = self.tmp / BOOK
        d.mkdir(parents=True)
        lines = ["본문 첫 줄입니다 " * 3]
        for k in range(200):                       # OCR 본문처럼 짧은 줄이 널려 있다
            lines.append(f"조각 {k} 예상하였고 전문가들은")
            if k in (50, 120):
                lines.append(f"{'II' if k == 50 else 'III'}. 진짜 절 제목 {k}")
        (d / "01_장.txt").write_text("\n\n".join(lines) + "\n", encoding="utf-8")

    def tearDown(self):
        cfg.CHAPTERS_DIR = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_제목다운_줄만_앞에_보인다(self):
        from services.ui_chapter_wide import _candidates
        cands, total, heads_only = _candidates(WS, BOOK, 0, "")
        self.assertTrue(heads_only)
        self.assertGreater(total, 100)
        self.assertEqual([s for _, s in cands], ["II. 진짜 절 제목 50", "III. 진짜 절 제목 120"])

    def test_찾기가_있으면_다_보인다(self):
        from services.ui_chapter_wide import _candidates
        cands, _total, heads_only = _candidates(WS, BOOK, 0, "조각 7")
        self.assertFalse(heads_only)
        self.assertTrue(all("조각 7" in s for _, s in cands))


if __name__ == "__main__":
    unittest.main()
