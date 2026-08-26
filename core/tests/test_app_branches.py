# -*- coding: utf-8 -*-
"""화면 분기 구조 검사 — pipeline_app.

2026-08-26에 사고가 났다. 「AI 모델은 설정에서 선택합니다」 캡션을 지우는 스크립트가
그 줄 **바로 앞의 `else:` 까지** 함께 지웠다. 그 결과 번역·문서요약 탭의 본문 전체가
`if not (AI 있음):` 안으로 들어가, **AI가 있으면 화면이 통째로 비어 버렸다.**
문법은 멀쩡해서 테스트도 컴파일도 다 통과했고, 연구자가 빈 화면을 보고서야 드러났다.

여기서 못 박는 것: 「AI 없음」 경고 뒤에는 반드시 `else:` 가 오거나, 경고 블록이
곧바로 끝나야 한다 — 본문이 경고와 같은 블록에 딸려 들어가면 안 된다.
"""
import re
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "pipeline_app.py"
_WARN_END = 'icon=":material/warning:")'


class AppBranchTest(unittest.TestCase):
    def test_AI없음_경고_뒤에_본문이_딸려들어가지_않는다(self):
        lines = APP.read_text(encoding="utf-8").split("\n")
        bad = []
        for i, line in enumerate(lines):
            if _WARN_END not in line:
                continue
            warn_indent = len(lines[i]) - len(lines[i].lstrip())
            k = i + 1
            while k < len(lines) and not lines[k].strip():
                k += 1
            if k >= len(lines):
                continue
            nxt = lines[k]
            ind = len(nxt) - len(nxt.lstrip())
            # 경고와 같은 깊이로 이어지는 문장이 여러 줄이면 else 가 빠진 것이다.
            if ind == warn_indent and not nxt.strip().startswith(("return", "st.stop")):
                tail = [l for l in lines[k:k + 6] if l.strip()]
                if len(tail) >= 3:
                    bad.append((i + 1, nxt.strip()[:60]))
        self.assertEqual(bad, [], f"«AI 없음» 경고 뒤에 else 가 빠진 곳: {bad}")


if __name__ == "__main__":
    unittest.main()
