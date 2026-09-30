"""구독 CLI 이어받기 (2026-09-30 연구자 요청).

한 구독 AI 가 사용량 한도에 걸리면 켜 둔 다른 구독 AI 로 같은 요청을 넘긴다. API 키로는
넘기지 않는다. 이어받을 때만 앞 번역 견본·용어 목록을 지시문에 붙인다.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
from pathlib import Path
from unittest import mock
import json
import tempfile
import unittest

import llm_providers as llm
from services import translate as tr

LIMIT = RuntimeError("You've hit your usage limit. Upgrade to Pro or try again later.")


class FailoverTest(unittest.TestCase):
    def setUp(self):
        llm._exhausted.clear()
        llm._last_switch.clear()
        self.calls = []
        self.limited = set()
        patches = [
            mock.patch.object(llm, "failover_enabled", return_value=True),
            mock.patch.object(llm, "default_provider_model", return_value=("codex_cli", "gpt-x")),
            mock.patch.object(llm, "backup_provider_model", return_value=("claude_cli", "sonnet")),
            mock.patch.object(llm, "has_key", return_value=True),
            mock.patch.object(llm, "_complete_once", side_effect=self._fake),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(llm._exhausted.clear)

    def _fake(self, provider, model, system, prompt, **kw):
        self.calls.append((provider, model, system))
        if provider in self.limited:
            raise LIMIT
        return f"{provider} answer"

    def test_limit_moves_to_the_other_subscription_ai_with_style_extra(self):
        self.limited = {"codex_cli"}
        out = llm.complete("codex_cli", "gpt-x", "SYS", "text", fallback_system_extra="STYLE")
        self.assertEqual(out, "claude_cli answer")
        self.assertEqual([c[0] for c in self.calls], ["codex_cli", "claude_cli"])
        self.assertEqual(self.calls[0][2], "SYS")                 # 평소 지시문은 그대로
        self.assertTrue(self.calls[1][2].endswith("STYLE"))       # 이어받을 때만 견본
        self.assertEqual(llm.last_call(), {"provider": "claude_cli", "model": "sonnet",
                                           "switched_from": "codex_cli"})
        self.assertTrue(llm.is_exhausted("codex_cli"))

    def test_exhausted_ai_rests_instead_of_being_asked_every_paragraph(self):
        self.limited = {"codex_cli"}
        llm.complete("codex_cli", "gpt-x", "SYS", "p1")
        self.calls.clear()
        llm.complete("codex_cli", "gpt-x", "SYS", "p2")
        self.assertEqual([c[0] for c in self.calls], ["claude_cli"])

    def test_both_limited_raises_the_original_limit(self):
        self.limited = {"codex_cli", "claude_cli"}
        with self.assertRaises(RuntimeError) as ctx:
            llm.complete("codex_cli", "gpt-x", "SYS", "text")
        self.assertTrue(llm.usage_limit_error(ctx.exception))

    def test_other_errors_do_not_switch(self):
        with mock.patch.object(llm, "_complete_once", side_effect=RuntimeError("network down")):
            with self.assertRaises(RuntimeError):
                llm.complete("codex_cli", "gpt-x", "SYS", "text")
        self.assertFalse(llm.is_exhausted("codex_cli"))

    def test_never_switches_for_api_keys_or_when_off(self):
        self.limited = {"openai"}
        with self.assertRaises(RuntimeError):
            llm.complete("openai", "gpt-4o", "SYS", "text")
        self.limited = {"codex_cli"}
        with mock.patch.object(llm, "failover_enabled", return_value=False):
            with self.assertRaises(RuntimeError):
                llm.complete("codex_cli", "gpt-x", "SYS", "text")
        self.assertEqual({c[0] for c in self.calls}, {"openai", "codex_cli"})

    def test_complete_json_switches_without_waiting(self):
        def fake_json(provider, model, system, prompt, **kw):
            if provider == "codex_cli":
                raise LIMIT
            return {"by": provider}
        with mock.patch.object(llm, "_complete_json_once", side_effect=fake_json), \
             mock.patch.object(llm.time, "sleep") as sleep:
            self.assertEqual(llm.complete_json("codex_cli", "gpt-x", "", "p"), {"by": "claude_cli"})
        sleep.assert_not_called()

    def test_json_retry_loop_gives_up_on_limit_immediately(self):
        with mock.patch.object(llm, "_codex_cli", side_effect=LIMIT) as cli, \
             mock.patch.object(llm.time, "sleep") as sleep:
            with self.assertRaises(RuntimeError):
                llm._complete_json_once("codex_cli", "gpt-x", "", "p")
        self.assertEqual(cli.call_count, 1)
        sleep.assert_not_called()

    def test_priority_list_for_the_status_display(self):
        self.assertEqual(llm.priority_list(), [("codex_cli", "gpt-x"), ("claude_cli", "sonnet")])
        with mock.patch.object(llm, "failover_enabled", return_value=False):
            self.assertEqual(llm.priority_list(), [("codex_cli", "gpt-x")])

    def test_backup_must_be_a_subscription_cli(self):
        with self.assertRaises(ValueError):
            llm.set_backup_provider_model("openai", "gpt-4o")


class StyleMemoryTest(unittest.TestCase):
    def setUp(self):
        tr._style_scope = ""
        tr.style_memory_reset("book-a")
        self.addCleanup(tr.style_memory_reset, "")

    def test_collects_terms_from_first_mentions(self):
        terms = tr.collect_terms("레비나스(Levinas)는 타자성(alterity)을 말한다. 다시 타자성(otherness).")
        self.assertEqual(terms["Levinas"], "레비나스")
        self.assertEqual(terms["alterity"], "타자성")

    def test_extra_has_samples_and_terms_only_after_translation(self):
        self.assertEqual(tr.fallback_style_extra("ko"), "")
        long_ko = "타자성(alterity)은 " + "주체의 한계를 드러낸다. " * 10
        tr.style_memory_add("Alterity reveals ...", long_ko)
        extra = tr.fallback_style_extra("ko")
        self.assertIn("alterity = 타자성", extra)
        self.assertIn("주체의 한계를 드러낸다", extra)

    def test_new_book_resets_and_seeds_from_its_translated_chapters(self):
        tr.style_memory_add("x", "무관한(Unrelated) " + "문장이다. " * 30)
        tr.style_memory_reset("book-b", ["신학(theology)은 " + "하나님을 말한다. " * 20])
        extra = tr.fallback_style_extra("ko")
        self.assertIn("theology = 신학", extra)
        self.assertNotIn("Unrelated", extra)


class ChapterRecordsTakeoverTest(unittest.TestCase):
    """이어받은 구간이 번역 결과(상태 파일)와 결과 문구에 남는다."""

    def test_switch_range_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = Path(tmp) / "Some Book"
            book.mkdir()
            ch = book / "01_Intro.txt"
            ch.write_text("\n\n".join(
                f"This is English paragraph number {i} about theology and ethics in the modern world."
                for i in range(1, 5)), encoding="utf-8")
            n = {"i": 0}

            def fake_complete(provider, model, system, prompt, max_tokens=8192, fallback_system_extra=""):
                n["i"] += 1
                switched = n["i"] >= 3
                llm._call.info = {"provider": "claude_cli" if switched else provider,
                                  "model": "sonnet" if switched else model,
                                  "switched_from": provider if switched else ""}
                return f"이것은 현대 세계의 신학과 윤리에 관한 {n['i']}번째 한국어 단락이다."

            with mock.patch.object(tr.llm, "complete", side_effect=fake_complete), \
                 mock.patch.object(tr, "target_language", return_value="ko"), \
                 mock.patch.object(tr, "translate_title", return_value="들어가며"), \
                 mock.patch.object(tr, "append_log"), \
                 mock.patch.object(tr.jobs, "stop_requested", return_value=False):
                ok, msg = tr.translate_one_chapter(ch, "codex_cli:gpt-x")
            self.assertTrue(ok, msg)
            self.assertIn("이어받음", msg)
            status = json.loads((book / "01_Intro_ko.status.json").read_text(encoding="utf-8"))
            (sw,) = status["ai_switches"]
            self.assertEqual((sw["from"], sw["to"]), ("codex_cli", "claude_cli"))
            self.assertLess(sw["first"], sw["last"] + 1)


if __name__ == "__main__":
    unittest.main()


def _data_is_isolated() -> bool:
    import os
    import config as cfg
    real = (Path.home() / "Documents" / "My Bookshelf").resolve()
    return bool(os.environ.get("MYBOOKSHELF_CONFIG_DIR")) and cfg.BASE_DIR.resolve() != real


@unittest.skipUnless(_data_is_isolated(), "requires isolated test config with its own base_dir")
class SettingsRenderTest(unittest.TestCase):
    """설정: 한 칸 AI 연결 · 이어받기 스위치 · 2순위, 위쪽 표시에 1순위 › 2순위."""

    def setUp(self):
        prefs = {"cli_failover": False, "cli_backup": None, "ai_onboarding_dismissed": True}
        self.prefs = prefs
        patches = [
            mock.patch.object(llm, "has_key", side_effect=lambda p: p in llm.CLI_PROVIDERS),
            mock.patch.object(llm, "get_pref", side_effect=lambda k, d=None: prefs.get(k, d) if k in prefs else d),
            mock.patch.object(llm, "set_pref", side_effect=lambda k, v: prefs.__setitem__(k, v)),
            mock.patch.object(llm, "default_provider_model", return_value=("codex_cli", "gpt-x")),
            mock.patch.object(llm, "task_provider_model", return_value=("codex_cli", "gpt-x")),
            mock.patch.object(llm, "model_choices",
                              side_effect=lambda p: ["gpt-x"] if p == "codex_cli" else ["default", "sonnet"]),
            mock.patch.object(llm, "cli_configured_model", return_value=""),
            mock.patch.object(llm, "codex_model_catalog", return_value={"gpt-x": "GPT-X"}),
            mock.patch.object(llm, "supported_model", side_effect=lambda p, m: m),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _app(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).parents[1] / "pipeline_app.py"), default_timeout=30)
        app.session_state["_update_info"] = {}
        app.session_state["_update_result"] = {}
        app.session_state["active_view"] = "settings"
        return app

    def test_one_box_switch_backup_and_priority_display(self):
        app = self._app()
        app.run()
        self.assertFalse(app.exception, [x.message for x in app.exception])
        box = app.selectbox(key="ai_default_conn")
        self.assertTrue(any(o.endswith("· GPT-X") for o in box.options))
        self.assertTrue(any("Sonnet" in o for o in box.options))    # 연결과 모델이 한 칸에
        app.toggle(key="cli_failover_toggle").set_value(True).run()
        self.assertTrue(self.prefs["cli_failover"])
        backup = app.selectbox(key="cli_backup_choice")
        self.assertTrue(all("Claude" in o for o in backup.options))  # 1순위와 다른 구독 CLI 만
        idx = next(i for i, o in enumerate(backup.options) if o.endswith("Claude Sonnet"))
        backup.select_index(idx).run()
        self.assertEqual(self.prefs["cli_backup"], {"provider": "claude_cli", "model": "sonnet"})
        chip = next(m.value for m in app.markdown if m.value.startswith("<span class=\"status-chip\""))
        self.assertIn("GPT-X › Claude Sonnet", chip)
        self.assertFalse(app.exception, [x.message for x in app.exception])
