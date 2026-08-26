# -*- coding: utf-8 -*-
"""화면 언어 결정 순서 — services/i18n.

2026-08-26에 사고가 났다. 설치하면서 **한국어를 골랐는데 영어로 떴다.**
원인은 우선순위였다: `config.json`의 "lang"이 인스톨러가 남긴 `app_lang.txt`보다
위였는데, config.json은 설치 폴더 밖(~/.config/mybookshelf/)에 있어 **재설치해도
남는다.** 그래서 예전에 앱에서 고른 언어가 방금 설치하며 고른 언어를 계속 눌렀다.

여기서 못 박는 것은 둘이다.
  · 방금 설치하며 고른 언어가 예전 설정을 이긴다.
  · 그러나 **한 번만** 이긴다 — 앱에서 언어를 바꾸면 재시작해도 그대로여야 한다.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import config as cfg
from services import i18n


class UiLangTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="uilang_"))
        self._cfg_file, self._app_lang = cfg.CONFIG_FILE, i18n._APP_LANG_FILE
        self._env = os.environ.pop("MYBOOKSHELF_LANG", None)
        cfg.CONFIG_FILE = self.tmp / "config.json"
        i18n._APP_LANG_FILE = self.tmp / "app_lang.txt"
        i18n._lang_cache = None

    def tearDown(self):
        cfg.CONFIG_FILE, i18n._APP_LANG_FILE = self._cfg_file, self._app_lang
        if self._env is not None:
            os.environ["MYBOOKSHELF_LANG"] = self._env
        i18n._lang_cache = None
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _restart(self):
        i18n._lang_cache = None
        return i18n.get_lang()

    def test_설치하며_고른_언어가_예전_설정을_이긴다(self):
        """이게 이 파일의 존재 이유다."""
        cfg.CONFIG_FILE.write_text(json.dumps({"lang": "en"}), encoding="utf-8")
        i18n._APP_LANG_FILE.write_text("ko", encoding="utf-8")
        self.assertEqual(self._restart(), "ko")

    def test_설치_선택은_한_번만_듣는다(self):
        cfg.CONFIG_FILE.write_text(json.dumps({"lang": "en"}), encoding="utf-8")
        i18n._APP_LANG_FILE.write_text("ko", encoding="utf-8")
        self._restart()
        self.assertFalse(i18n._APP_LANG_FILE.exists(), "읽었으면 지워야 한다")
        i18n.set_lang("en")
        self.assertEqual(self._restart(), "en", "앱에서 바꾼 언어가 되돌아가면 안 된다")

    def test_설치_선택은_config에_옮겨_적힌다(self):
        i18n._APP_LANG_FILE.write_text("ko", encoding="utf-8")
        self._restart()
        self.assertEqual(json.loads(cfg.CONFIG_FILE.read_text(encoding="utf-8"))["lang"], "ko")

    def test_아무것도_없으면_한국어(self):
        self.assertEqual(self._restart(), "ko")

    def test_환경변수가_가장_우선(self):
        cfg.CONFIG_FILE.write_text(json.dumps({"lang": "ko"}), encoding="utf-8")
        os.environ["MYBOOKSHELF_LANG"] = "en"
        try:
            self.assertEqual(self._restart(), "en")
        finally:
            os.environ.pop("MYBOOKSHELF_LANG", None)

    def test_이상한_값은_무시된다(self):
        i18n._APP_LANG_FILE.write_text("zz", encoding="utf-8")
        self.assertEqual(self._restart(), "ko")


if __name__ == "__main__":
    unittest.main()
