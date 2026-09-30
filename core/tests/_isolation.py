"""테스트가 사용자의 실제 설정·자료 폴더를 건드리지 않게 한다 (2026-09-30).

★왜: MYBOOKSHELF_CONFIG_DIR 만 바꾸는 테스트가 몇 개 있었지만 대부분은 아무것도
바꾸지 않아서
  · test_translation_names 가 실제 ~/.config/mybookshelf/keys.json 을 고쳤다가
    되돌렸고(도는 동안 앱을 쓰거나 테스트가 멈추면 설정이 바뀐 채 남는다),
  · test_ui_improvements 가 실제 «3_챕터» 에 ui-test 폴더를 남겼고,
  · PC 에서는 실제 로그(upload.log)에 줄이 쌓였다.
config.json 에 base_dir 가 없으면 설정 폴더만 바꿔도 자료 폴더는 실제
~/Documents/My Bookshelf 그대로라는 것도 함정이었다.

모든 테스트 모듈이 다른 무엇보다 먼저 이 모듈을 불러온다. config·llm_providers 는
불러오는 순간 경로를 정하므로 **그 전에** 환경변수를 맞춰야 한다. 여러 번 불러도
한 번만 준비한다(같은 프로세스의 모든 테스트가 같은 임시 폴더를 쓴다).
"""
from __future__ import annotations

import atexit
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

_FLAG = "MYBOOKSHELF_TEST_ROOT"

if not os.environ.get(_FLAG):
    for _mod in ("config", "llm_providers"):
        if _mod in sys.modules:
            raise RuntimeError(f"{_mod} 가 격리 전에 이미 불러와졌습니다 — "
                               "테스트 모듈 맨 위에서 _isolation 을 먼저 불러오세요.")
    ROOT = Path(tempfile.mkdtemp(prefix="mybookshelf-test-"))
    (ROOT / "config").mkdir()
    (ROOT / "data").mkdir()
    (ROOT / "config" / "config.json").write_text(
        json.dumps({"base_dir": str(ROOT / "data")}, ensure_ascii=False), encoding="utf-8")
    os.environ[_FLAG] = str(ROOT)
    os.environ["MYBOOKSHELF_CONFIG_DIR"] = str(ROOT / "config")
    os.environ.pop("MYBOOKSHELF_WIKI_DIR", None)
    atexit.register(shutil.rmtree, ROOT, True)
else:
    ROOT = Path(os.environ[_FLAG])
