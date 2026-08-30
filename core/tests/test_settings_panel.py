# -*- coding: utf-8 -*-
"""설정 화면 구조 검사 — pipeline_app.

2026-08-30에 두 가지가 함께 났다.

1. 설정 화면을 «목록 → 개별 편집기»로 새로 짜면서 예전 «한 화면에 전부» 블록을
   지우지 않았다. 새 블록이 언제나 `st.stop()`으로 끝나 옛 블록은 265줄짜리 죽은
   코드가 됐고, 거기에 넣은 수정(Codex→Claude 검증 토글)은 화면에 나오지 않았다.
   문법도 테스트도 멀쩡했다 — 실행되지 않는 코드였을 뿐이다.
2. 폴더 편집기가 `compact_docx_active_dir` 같은 이름에 저장했는데, 정작
   `_current_docx_dir()`은 `docx5_active_dir`을 읽는다. 폴더를 바꿔도 그 세션에는
   반영되지 않고 앱을 다시 켜야 했다.

여기서 못 박는 것은 둘이다.
  · 위젯 key는 파일 전체에서 겹치지 않는다 (같은 화면이 두 벌 남으면 여기서 걸린다).
  · 폴더 편집기가 저장하는 세션 키는 `_current_*_dir()`이 읽는 그 이름이어야 한다.
"""
import collections
import re
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "pipeline_app.py"


class SettingsPanelTest(unittest.TestCase):
    def setUp(self):
        self.src = APP.read_text(encoding="utf-8")

    def test_위젯_key가_겹치지_않는다(self):
        """같은 화면이 두 벌 남아 있으면 key가 겹쳐서 여기서 드러난다."""
        keys = re.findall(r'key="([^"{}]+)"', self.src)
        dup = sorted(k for k, n in collections.Counter(keys).items() if n > 1)
        self.assertEqual(dup, [], f"중복된 위젯 key: {dup}")

    def test_설정_화면은_한_벌만_있다(self):
        self.assertEqual(
            self.src.count('_settings_panel = st.session_state.get("settings_panel"'), 1,
            "설정 화면을 그리는 블록이 둘 이상이다 — 뒤엣것은 st.stop() 때문에 죽은 코드다.",
        )

    def test_폴더_편집기가_Tab5가_읽는_세션키에_저장한다(self):
        """`_current_*_dir()`이 읽는 이름으로 저장해야 그 세션에 바로 반영된다."""
        readers = dict(re.findall(
            r'def _current_(\w+)_dir\(\).*?st\.session_state\.get\("(\w+)"\)',
            self.src, re.S))
        writers = dict(re.findall(
            r'_render_folder_setting\("compact_(\w+)".*?session_key="(\w+)"',
            self.src, re.S))
        self.assertEqual(sorted(writers), ["docx", "epub", "hwpx", "wiki"])
        for kind, session_key in writers.items():
            self.assertEqual(session_key, readers.get(kind),
                             f"{kind} 폴더 편집기가 엉뚱한 세션 키에 저장한다: {session_key}")


if __name__ == "__main__":
    unittest.main()
