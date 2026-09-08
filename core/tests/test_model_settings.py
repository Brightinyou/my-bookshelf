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
                  patch.object(llm, "has_key", return_value=True)):
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
        ]}))
        with patch.dict(os.environ, {"CODEX_HOME": str(root)}):
            self.assertIn("available-model", llm.model_choices("codex_cli"))
            self.assertNotIn("hidden-model", llm.model_choices("codex_cli"))
            self.assertEqual(llm.model_label("codex_cli", "available-model"), "Available Model")
            (root / "models_cache.json").write_text("invalid")
            self.assertIn("default", llm.model_choices("codex_cli"))

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
