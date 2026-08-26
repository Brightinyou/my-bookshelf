# -*- coding: utf-8 -*-
"""번역본 파일 이름 규칙 — services/translate.

2026-08-26 이전에는 도착언어와 무관하게 늘 `_ko.txt`였다. 한국어→스페인어처럼
한국어가 도착언어가 아닐 때 이름이 사실과 어긋나서 바꿨다.

여기서 못 박는 것은 둘이다.
  · 새로 만드는 번역본은 도착언어를 따른다.
  · **이미 만들어 둔 `_ko.txt`는 계속 찾아진다** — 도착언어를 바꿔도 예전
    번역본이 사라지면 안 된다(실제로 47챕터가 그 이름으로 저장돼 있다).
"""
import tempfile
import unittest
from pathlib import Path

from services import translate as tr


class TranslationNameTest(unittest.TestCase):
    def setUp(self):
        self.prev = tr.target_language()
        self.tmp = Path(tempfile.mkdtemp(prefix="trname_"))
        self.ch = self.tmp / "01_Some Chapter.txt"
        self.ch.write_text("body", encoding="utf-8")

    def tearDown(self):
        tr.set_target_language(self.prev)

    def test_도착언어가_한국어면_예전과_같은_이름(self):
        tr.set_target_language("ko")
        self.assertEqual(tr.translated_path(self.ch).name, "01_Some Chapter_ko.txt")

    def test_도착언어를_바꾸면_이름도_바뀐다(self):
        tr.set_target_language("es")
        self.assertEqual(tr.translated_path(self.ch).name, "01_Some Chapter_es.txt")

    def test_예전_ko_번역본은_도착언어가_달라도_찾아진다(self):
        """이게 이 파일의 존재 이유다 — 기존 번역본이 미아가 되면 안 된다."""
        old = self.ch.with_name(self.ch.stem + "_ko.txt")
        old.write_text("옛 번역본", encoding="utf-8")
        tr.set_target_language("es")
        self.assertEqual(tr.find_translation(self.ch), old)
        self.assertTrue(tr.has_translation(self.ch))

    def test_현재_도착언어_번역본이_있으면_그것을_먼저(self):
        self.ch.with_name(self.ch.stem + "_ko.txt").write_text("ko", encoding="utf-8")
        es = self.ch.with_name(self.ch.stem + "_es.txt")
        es.write_text("es", encoding="utf-8")
        tr.set_target_language("es")
        self.assertEqual(tr.find_translation(self.ch), es)

    def test_번역본이_없으면_None(self):
        tr.set_target_language("ko")
        self.assertIsNone(tr.find_translation(self.ch))

    def test_파생물_판정은_모든_언어_접미사를_안다(self):
        for stem in ("01_x_ko", "01_x_es", "01_x_ja", "01_x_wiki",
                     "01_x_bilingual", "01_x_clean"):
            self.assertTrue(tr.is_derived(stem), stem)
        self.assertFalse(tr.is_derived("01_Some Chapter"))


if __name__ == "__main__":
    unittest.main()
