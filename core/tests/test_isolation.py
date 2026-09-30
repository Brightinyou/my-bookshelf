"""테스트가 실제 설정·자료 폴더를 쓰지 않는지 지킨다 (2026-09-30)."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
import unittest  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class IsolationTest(unittest.TestCase):
    def test_config_and_data_live_in_temp_root(self):
        import config as cfg
        import llm_providers as llm
        root = _isolation.ROOT.resolve()
        for path in (cfg.CONFIG_DIR, cfg.BASE_DIR, cfg.CHAPTERS_DIR, cfg.WIKI_DIR, llm.KEYS_FILE):
            self.assertTrue(Path(path).resolve().is_relative_to(root), path)

    def test_every_test_module_imports_isolation_first(self):
        here = Path(__file__).resolve().parent
        for p in sorted(here.glob("test_*.py")):
            head = p.read_text(encoding="utf-8").split("import _isolation", 1)[0]
            self.assertIn("import _isolation", p.read_text(encoding="utf-8"), p.name)
            for mod in ("import config", "import llm_providers", "from services", "import pipeline_app"):
                self.assertNotIn(mod, head, f"{p.name}: {mod} 가 _isolation 보다 앞")


if __name__ == "__main__":
    unittest.main()
