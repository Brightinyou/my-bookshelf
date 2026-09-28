from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import json
import os
import threading
import unittest
from unittest.mock import patch
import llm_providers as llm


class ModelSettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        for p in (patch.object(llm, "CONFIG_DIR", root), patch.object(llm, "KEYS_FILE", root / "keys.json"),
                  patch.object(llm, "has_key", return_value=True),
                  # 실제 ~/.codex 캐시를 읽지 않게 — 비어 있으면 모델 거르기를 안 한다
                  patch.dict(os.environ, {"CODEX_HOME": str(root)})):
            p.start()
            self.addCleanup(p.stop)

    def test_custom_model_and_task_override_survive_reload(self):
        llm.set_wiki_model("codex_cli", "my-account-model")
        llm.set_task_model("translate", "claude_cli", "sonnet")
        llm.set_task_model("summary", "codex_cli", "summary-model")
        self.assertEqual(llm.default_provider_model(), ("codex_cli", "my-account-model"))
        self.assertEqual(llm.task_provider_model("translate"), ("claude_cli", "sonnet"))
        self.assertEqual(llm.wiki_provider_model(), ("codex_cli", "summary-model"))
        self.assertIn("my-account-model", llm.model_choices("codex_cli"))
        llm.set_task_model("translate")
        self.assertEqual(llm.task_provider_model("translate"), llm.default_provider_model())

    def test_codex_parallel_results_do_not_mix(self):
        barrier = threading.Barrier(3)
        paths = set()
        def run(args, prompt, **kwargs):
            path = Path(args[args.index("-o") + 1])
            paths.add(path)
            path.write_text(prompt, encoding="utf-8")
            barrier.wait(timeout=5)
            return 0, "", "model: selected-model"
        with patch.object(llm, "codex_cli_path", return_value="codex"), patch.object(llm, "_run_cli_safe", side_effect=run):
            with ThreadPoolExecutor(max_workers=3) as pool:
                actual = list(pool.map(lambda x: llm._codex_cli("selected-model", "", x), ["A", "B", "C"]))
        self.assertEqual(actual, ["A", "B", "C"])
        self.assertEqual(len(paths), 3)
        self.assertTrue(all(not p.exists() for p in paths))

    def test_bad_model_does_not_silently_fall_back(self):
        with patch.object(llm, "codex_cli_path", return_value="codex"), patch.object(llm, "_run_cli_safe", return_value=(1, "", "model not supported")) as run:
            with self.assertRaises(RuntimeError):
                llm._codex_cli("unavailable", "", "test")
            self.assertEqual(run.call_count, 1)
            self.assertIn("unavailable", run.call_args.args[0])

    def test_claude_default_inherits_config(self):
        with patch.object(llm, "claude_cli_path", return_value="claude"), patch.object(llm, "_run_cli_safe", return_value=(0, "OK", "")) as run:
            self.assertEqual(llm._claude_cli("default", "", "test"), "OK")
            self.assertNotIn("--model", run.call_args.args[0])

    def test_unavailable_selected_provider_is_not_silently_replaced(self):
        llm.set_wiki_model("codex_cli", "selected-model")
        with patch.object(llm, "has_key", return_value=False):
            self.assertEqual(llm.default_provider_model(), ("codex_cli", "selected-model"))

    def test_codex_catalog_adds_visible_models_and_skips_hidden(self):
        root = Path(self.tmp.name)
        (root / "models_cache.json").write_text(json.dumps({"models": [
            {"slug": "available-model", "display_name": "Available Model", "visibility": "list"},
            {"slug": "hidden-model", "visibility": "hide"},
        ]}), encoding="utf-8")
        with patch.dict(os.environ, {"CODEX_HOME": str(root)}):
            self.assertIn("available-model", llm.model_choices("codex_cli"))
            self.assertNotIn("hidden-model", llm.model_choices("codex_cli"))
            self.assertEqual(llm.model_label("codex_cli", "available-model"), "Available Model")
            (root / "models_cache.json").write_text("invalid", encoding="utf-8")
            self.assertIn("default", llm.model_choices("codex_cli"))

    def _catalog(self, models):
        (Path(self.tmp.name) / "models_cache.json").write_text(json.dumps({"models": models}), encoding="utf-8")

    def test_codex_choices_are_only_this_computers_catalog(self):
        self._catalog([{"slug": "gpt-new", "visibility": "list"}])
        llm.set_task_model("summary", "codex_cli", "gpt-old")
        choices = llm.model_choices("codex_cli")
        self.assertEqual(choices, ["default", "gpt-new"])
        # 저장된 모델이 이 컴퓨터 목록에 없으면 부르기 전에 CLI 기본으로 돌린다
        self.assertEqual(llm.task_provider_model("summary"), ("codex_cli", "default"))
        self.assertEqual(llm.unsupported_saved_model("summary"), "gpt-old")
        llm.set_task_model("summary", "codex_cli", "gpt-new")
        self.assertEqual(llm.task_provider_model("summary"), ("codex_cli", "gpt-new"))
        self.assertEqual(llm.unsupported_saved_model("summary"), "")

    def test_retired_codex_model_is_dropped_and_upcoming_is_labelled(self):
        self._catalog([
            {"slug": "gpt-gone", "visibility": "list", "upgrade": {"retirement_at": "2020-01-01T00:00:00Z"}},
            {"slug": "gpt-soon", "display_name": "GPT Soon", "visibility": "list",
             "upgrade": {"retirement_at": "2999-10-14T19:00:00Z"}},
        ])
        self.assertNotIn("gpt-gone", llm.model_choices("codex_cli"))
        self.assertEqual(llm.model_label("codex_cli", "gpt-soon"), "GPT Soon (2999-10-14 종료 예정)")

    def test_claude_choices_are_cli_aliases_and_stale_saved_model_falls_back(self):
        llm._CLAUDE_ALIASES_CACHE.clear()
        self.addCleanup(llm._CLAUDE_ALIASES_CACHE.clear)
        help_new = "--model <model> Provide an alias for the latest model (e.g. 'fable', 'opus', or 'sonnet') or"
        with patch.object(llm, "claude_cli_path", return_value="claude-new"), \
             patch.object(llm, "_run_cli_safe", return_value=(0, help_new, "")):
            self.assertEqual(llm.model_choices("claude_cli"), ["default", "fable", "opus", "sonnet", "haiku"])
            llm.set_task_model("summary", "claude_cli", "claude-3-opus-old")
            self.assertEqual(llm.task_provider_model("summary"), ("claude_cli", "default"))
            self.assertEqual(llm.unsupported_saved_model("summary"), "claude-3-opus-old")
        # 옛 CLI는 fable을 모른다 — 도움말에 없으면 목록에도 없다
        with patch.object(llm, "claude_cli_path", return_value="claude-old"), \
             patch.object(llm, "_run_cli_safe", return_value=(0, "--model <model> Model for the session", "")):
            self.assertNotIn("fable", llm.model_choices("claude_cli"))
            llm.set_task_model("summary", "claude_cli", "fable")
            self.assertEqual(llm.task_provider_model("summary"), ("claude_cli", "default"))

    def test_parallel_preferences_preserve_model_and_api_key(self):
        llm.save_key("openai", "test-only-placeholder")
        llm.set_wiki_model("codex_cli", "default")
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda i: llm.set_pref(f"layout_test_{i}", i), range(30)))
        self.assertEqual(llm.saved_key("openai"), "test-only-placeholder")
        self.assertEqual(llm.default_provider_model(), ("codex_cli", "default"))
        self.assertTrue(all(llm.get_pref(f"layout_test_{i}") == i for i in range(30)))


if __name__ == "__main__":
    unittest.main()
