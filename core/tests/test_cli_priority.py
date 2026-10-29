# -*- coding: utf-8 -*-
"""구독 AI 우선순위는 사용자가 정한다 (2026-10-29 연구자 요청).

예전에는 설치에서 Claude·Codex 를 둘 다 고르면 무조건 Codex 가 1순위였고, 다시 설치하면
고쳐 둔 순위도 덮어썼다. 앱은 1순위를 꺼 두면 그 꺼진 AI 로 불러 실패했다.

여기서 못 박는 것:
  · 1순위를 꺼 두면 2순위로, 2순위도 없으면 켜 둔 다른 구독 CLI 로 실행한다(API 키로는 안 넘긴다).
  · 설정에서 순위를 바꿀 수 있고, 구독 CLI 를 하나 더 켜면 순위를 묻는다.
  · 설치 스크립트는 둘 다 고르면 순위를 묻거나 저장된 순위를 지킨다 — 무조건 Codex 가 아니다.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
import llm_providers as llm

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "core" / "pipeline_app.py"


class _Prefs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.on = {"claude_cli", "codex_cli"}
        for p in (patch.object(llm, "CONFIG_DIR", root), patch.object(llm, "KEYS_FILE", root / "keys.json"),
                  patch.object(llm, "has_key", side_effect=lambda prov: prov in self.on),
                  patch.object(llm, "claude_model_catalog", return_value=["sonnet", "opus", "haiku"]),
                  patch.object(llm, "cli_configured_model", return_value=""),
                  patch.dict(os.environ, {"CODEX_HOME": str(root)})):
            p.start()
            self.addCleanup(p.stop)


class PriorityFallbackTest(_Prefs):
    def test_꺼진_1순위_대신_2순위로_실행한다(self):
        llm.set_wiki_model("codex_cli", "gpt-x")
        llm.set_backup_provider_model("claude_cli", "sonnet")
        self.assertEqual(llm.default_provider_model(), ("codex_cli", "gpt-x"))
        self.on = {"claude_cli"}
        self.assertEqual(llm.default_provider_model(), ("claude_cli", "sonnet"))
        self.assertEqual(llm.saved_provider_model(), ("codex_cli", "gpt-x"))   # 저장값은 그대로

    def test_2순위가_없으면_켜_둔_다른_구독_CLI(self):
        llm.set_wiki_model("codex_cli", "gpt-x")
        self.on = {"claude_cli"}
        self.assertEqual(llm.default_provider_model(), ("claude_cli", "default"))

    def test_API_키로는_넘기지_않는다(self):
        llm.set_wiki_model("codex_cli", "gpt-x")
        self.on = {"openai"}
        self.assertEqual(llm.default_provider_model(), ("codex_cli", "gpt-x"))

    def test_꺼진_작업별_AI는_기본_순위를_따른다(self):
        llm.set_wiki_model("claude_cli", "opus")
        llm.set_task_model("translate", "codex_cli", "gpt-x")
        self.on = {"claude_cli"}
        self.assertEqual(llm.task_provider_model("translate"), ("claude_cli", "opus"))

    def test_순위를_바꿔도_각자_고른_모델은_따라간다(self):
        llm.set_wiki_model("codex_cli", "gpt-x")
        llm.set_backup_provider_model("claude_cli", "sonnet")
        llm.set_cli_priority("claude_cli")
        self.assertEqual(llm.saved_provider_model(), ("claude_cli", "sonnet"))
        self.assertEqual(llm.backup_provider_model(), ("codex_cli", "gpt-x"))
        with self.assertRaises(ValueError):
            llm.set_cli_priority("openai")


def _app_source(body: str) -> str:
    source = APP.read_text(encoding="utf-8")
    names = {"_ai_option_label", "_ai_options", "_split_opt", "_render_failover_settings",
             "_render_cli_priority_question", "_apply_backup_choice"}
    definitions = "\n\n".join(ast.get_source_segment(source, node)
        for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name in names)
    return "import streamlit as st\nimport llm_providers as llm\nfrom services.i18n import t, tf\n" \
        + definitions + "\n" + body


class PrioritySettingsUiTest(_Prefs):
    def test_하나_더_켜면_순위를_묻고_고른_대로_저장한다(self):
        llm.set_wiki_model("codex_cli", "gpt-x")
        app = AppTest.from_string(_app_source(
            'if not st.session_state.get("_seeded"):\n'
            '    st.session_state["_seeded"] = st.session_state["_ask_cli_priority"] = True\n'
            '_render_cli_priority_question()\n'),
            default_timeout=10).run()
        self.assertEqual(len(app.info), 1)
        app.button(key="ask_priority_claude_cli").click().run()
        self.assertEqual(llm.saved_provider_model(), ("claude_cli", "default"))
        self.assertEqual(llm.backup_provider_model(), ("codex_cli", "gpt-x"))
        app.run()   # AppTest 는 st.rerun() 으로 끊긴 실행의 요소를 남겨 둬서 한 번 더 그린다
        self.assertEqual(len(app.info), 0)

    def test_설정에서_2순위가_늘_보이고_순위를_바꿀_수_있다(self):
        llm.set_wiki_model("codex_cli", "default")
        app = AppTest.from_string(_app_source("_render_failover_settings()\n"), default_timeout=10).run()
        self.assertFalse(llm.failover_enabled())
        box = app.selectbox(key="cli_backup_choice")          # 이어받기를 안 켜도 보인다
        self.assertTrue(all(o.startswith("Claude") for o in box.options))
        app.button(key="cli_priority_swap").click().run()
        self.assertEqual(llm.saved_provider_model()[0], "claude_cli")
        self.assertEqual(llm.backup_provider_model()[0], "codex_cli")
        self.assertFalse(app.exception, [x.message for x in app.exception])

    def test_보이는_글자로_넘어온_2순위는_오류_없이_버린다(self):
        """연구자 화면: «ValueError: 이어받을 AI 는 구독 CLI 만 고를 수 있습니다» (2026-10-29).
        화면이 보낸 글자가 지금 목록에 없으면 Streamlit selectbox 의 deserialize 는 원래 값
        대신 그 글자(«Claude CLI · Claude Opus»)를 돌려준다 — 그 값이 콜백에 들어온 경우."""
        llm.set_wiki_model("codex_cli", "default")
        llm.set_backup_provider_model("claude_cli", "sonnet")
        app = AppTest.from_string(_app_source(
            'if not st.session_state.get("_seeded"):\n'
            '    st.session_state["_seeded"] = True\n'
            '    st.session_state["cli_backup_choice"] = "Claude CLI · Claude Opus"\n'
            '    _apply_backup_choice()\n'
            '_render_failover_settings()\n'), default_timeout=10).run()
        self.assertFalse(app.exception, [x.message for x in app.exception])
        self.assertEqual(llm.backup_provider_model(), ("claude_cli", "sonnet"))   # 저장값 유지
        self.assertEqual(app.selectbox(key="cli_backup_choice").value, "claude_cli:sonnet")

    def test_AI_이름이_아닌_값은_나누지_않는다(self):
        ns = {}
        exec(_app_source(""), ns)
        self.assertEqual(ns["_split_opt"]("claude_cli:sonnet"), ("claude_cli", "sonnet"))
        for bad in ("Claude CLI · Claude Opus", "", None, "claude_cli:", "x:y"):
            self.assertEqual(ns["_split_opt"](bad), ("", ""), bad)


class InstallerPriorityTest(unittest.TestCase):
    def read(self, rel, enc="utf-8"):
        return (ROOT / rel).read_text(encoding=enc)

    def test_둘_다_고르면_무조건_Codex가_아니다(self):
        win = self.read("dev/installer/windows_setup_extras.ps1", "utf-8-sig")
        self.assertNotIn("Codex is the default AI", win)
        self.assertIn("Ask-First", win)
        self.assertIn("pref_cli_backup", win)
        mac = self.read("dev/installer/mac_setup_extras.sh")
        self.assertNotIn("기본 작업 AI는 Codex", mac)
        self.assertIn("어느 AI 를 먼저 쓸까요?", mac)
        for rel, enc in (("install-mybookshelf.ps1", "utf-8-sig"), ("install-mybookshelf.sh", "utf-8")):
            s = self.read(rel, enc)
            self.assertIn("pref_cli_backup", s, rel)
            self.assertNotIn("$prov = if ($codexReady) { 'codex_cli' } else { 'claude_cli' }\n        $prefs['wiki_provider']", s)
        self.assertIn("[ValidateSet('','claude','codex')] [string] $First", self.read("install-mybookshelf.ps1", "utf-8-sig"))
        self.assertIn("--first)", self.read("install-mybookshelf.sh"))


if __name__ == "__main__":
    unittest.main()
