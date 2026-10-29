# -*- coding: utf-8 -*-
"""업로드 처리 뒤 rerun 검사 — pipeline_app.

2026-10-29: 번역 탭에 TXT를 끌어다 놓아도 '번역 대기'에 보이지 않고, 다른 메뉴에
갔다 와야 들어와 있었다. 업로드 처리 블록 끝의 `st.rerun()`이 조건 없이 불려서,
파일을 계속 들고 있는 업로더 때문에 매 실행이 거기서 멈추고 아래 대기 목록까지
내려가지 못했다. 요약 탭도 같았다.

여기서 못 박는 것: `if <업로더 값>:` 블록 바로 아래 깊이에 `st.rerun()`이 있으면 안
된다 — 새로 등록한 게 있을 때(안쪽 if)만 rerun해야 한다.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
import ast
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "pipeline_app.py"


def _is_call(node, attr):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == attr and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "st")


class UploadRerunTest(unittest.TestCase):
    def test_업로드_블록은_조건_없이_rerun하지_않는다(self):
        tree = ast.parse(APP.read_text(encoding="utf-8"))
        uploaders = {
            n.targets[0].id for n in ast.walk(tree)
            if isinstance(n, ast.Assign) and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name) and _is_call(n.value, "file_uploader")
        }
        self.assertGreaterEqual(len(uploaders), 5, uploaders)
        checked, bad = set(), []
        for n in ast.walk(tree):
            if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id in uploaders:
                checked.add(n.test.id)
                for stmt in n.body:
                    if isinstance(stmt, ast.Expr) and _is_call(stmt.value, "rerun"):
                        bad.append(f"{n.test.id} (줄 {stmt.lineno})")
        self.assertEqual(checked, uploaders)
        self.assertEqual(bad, [], "업로드 블록에서 조건 없는 st.rerun(): " + ", ".join(bad))


if __name__ == "__main__":
    unittest.main()
