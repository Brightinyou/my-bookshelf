# -*- coding: utf-8 -*-
"""설정의 «AI 연결» 칸 — 저장값을 쓸 수 없을 때 (2026-10-29).

연구자가 Codex CLI를 끄고 Claude만 남겼는데도 «저장된 모델 «gpt-5.6-sol»는 이 컴퓨터의
CLI가 지원하는 목록에 없어…» 경고가 계속 떴다. 저장값은 여전히 Codex·gpt-5.6-sol이었고,
칸은 첫 항목(Claude)을 보여 주기만 해서 그대로 두면 저장이 안 됐다.

여기서 못 박는 것: 저장값을 못 쓰면 칸이 비어 «다시 고르세요»로 뜨고, 무엇이든 고르면
(보이던 Claude 기본이라도) 저장돼 경고가 사라진다.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
import ast
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
import llm_providers as llm


def app_source():
    source = (Path(__file__).parents[1] / "pipeline_app.py").read_text(encoding="utf-8")
    names = {"_ai_option_label", "_ai_options", "_split_opt", "_apply_ai_choice", "_render_model_editor"}
    definitions = "\n\n".join(ast.get_source_segment(source, node)
        for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name in names)
    return '''
import streamlit as st
import llm_providers as llm
from services.i18n import t, tf
''' + definitions + '''
_render_model_editor("ai_default")
'''


class ModelEditorRepickTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "models_cache.json").write_text(json.dumps({"models": [
            {"slug": "gpt-5.6-terra", "visibility": "list"}]}), encoding="utf-8")
        self.on = {"claude_cli"}
        for p in (patch.object(llm, "CONFIG_DIR", root), patch.object(llm, "KEYS_FILE", root / "keys.json"),
                  patch.object(llm, "has_key", side_effect=lambda prov: prov in self.on),
                  patch.object(llm, "claude_model_catalog", return_value=["sonnet", "opus", "haiku"]),
                  patch.object(llm, "cli_configured_model", return_value=""),
                  patch.dict(os.environ, {"CODEX_HOME": str(root)})):
            p.start()
            self.addCleanup(p.stop)

    def app(self):
        return AppTest.from_string(app_source(), default_timeout=10).run()

    def test_꺼진_Codex_저장값이면_칸이_비고_Claude를_고르면_저장된다(self):
        llm.set_wiki_model("codex_cli", "gpt-5.6-sol")
        app = self.app()
        self.assertEqual(len(app.warning), 1)
        self.assertIn("꺼져 있거나", app.warning[0].value)
        box = app.selectbox[0]
        self.assertIsNone(box.value)
        box.select("claude_cli:default").run()
        self.assertEqual(llm.default_provider_model(), ("claude_cli", "default"))
        self.assertEqual(len(app.warning), 0)
        self.assertEqual(app.selectbox[0].value, "claude_cli:default")

    def test_목록에_없는_모델이면_칸이_비고_고르면_경고가_사라진다(self):
        self.on = {"claude_cli", "codex_cli"}
        llm.set_wiki_model("codex_cli", "gpt-5.6-sol")
        app = self.app()
        self.assertEqual(len(app.warning), 1)
        self.assertIn("gpt-5.6-sol", app.warning[0].value)
        self.assertIsNone(app.selectbox[0].value)
        app.selectbox[0].select("codex_cli:gpt-5.6-terra").run()
        self.assertEqual(llm.default_provider_model(), ("codex_cli", "gpt-5.6-terra"))
        self.assertEqual(len(app.warning), 0)

    def test_쓸_수_있는_저장값은_그대로_보인다(self):
        llm.set_wiki_model("claude_cli", "sonnet")
        app = self.app()
        self.assertEqual(len(app.warning), 0)
        self.assertEqual(app.selectbox[0].value, "claude_cli:sonnet")


if __name__ == "__main__":
    unittest.main()
