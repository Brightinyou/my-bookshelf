"""문서출력 화면 — 한 책에 같은 제목의 장이 둘일 때 (2026-09-30 연구자 PC 실측).

「인공지능과 만남_윤리적 인간학적 탐구_…」에 「00_머리말」·「02_머리말」이 있었다. 장별
Wiki 버튼 key 가 «책 이름 앞 20글자 + 장 제목»이라 겹쳐 StreamlitDuplicateElementKey 가
나고, 화면이 «화면 구성 중…»에서 멈췄다. 제목으로 파일을 다시 찾아서 두 번째 버튼은
첫 번째 머리말을 가리키기도 했다.
"""
from pathlib import Path
from unittest.mock import patch
import os
import shutil
import unittest

import config as cfg
import llm_providers as llm

APP = Path(__file__).parents[1] / "pipeline_app.py"


class SourceTest(unittest.TestCase):
    def test_buttons_use_chapter_index_and_real_file(self):
        src = APP.read_text(encoding="utf-8")
        self.assertIn('key=f"ch5w_{_it5[\'key\']}_{_ci5}"', src)
        self.assertIn('zip(_it5["ch_names"], _it5["ch_files"])', src)
        self.assertNotIn("_ch5_dir.glob(f\"??_{_cn5}.txt\")", src)


def _data_is_isolated() -> bool:
    """MYBOOKSHELF_CONFIG_DIR 만으로는 부족하다 — 그 config.json 에 base_dir 가 없으면
    BASE_DIR 은 실제 ~/Documents/My Bookshelf 다(2026-09-30 실측: 시험 책이 연구자의
    실제 챕터 폴더에 만들어졌다가 지워졌다). 실제 폴더면 돌리지 않는다."""
    real = (Path.home() / "Documents" / "My Bookshelf").resolve()
    return bool(os.environ.get("MYBOOKSHELF_CONFIG_DIR")) and cfg.BASE_DIR.resolve() != real


@unittest.skipUnless(_data_is_isolated(), "requires isolated test config with its own base_dir")
class RenderTest(unittest.TestCase):
    BOOK = "중복장 시험책_같은 머리말이 두 번 나오는 책"

    def setUp(self):
        from services.pipeline_queue import queue_add, queue_remove
        queue_add("tab5_ready", [self.BOOK])
        self.addCleanup(queue_remove, "tab5_ready", [self.BOOK])
        self.dir = cfg.CHAPTERS_DIR / self.BOOK
        self.dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, self.dir, True)
        for nn in ("00", "02"):
            (self.dir / f"{nn}_머리말.txt").write_text(f"머리말 {nn}", encoding="utf-8")
            (self.dir / f"{nn}_머리말_wiki.md").write_text(
                f"---\nbook: {self.BOOK}\nchapter: 머리말\n---\n> **요약:** 머리말 {nn}\n\n본문 {nn}\n",
                encoding="utf-8")
        (self.dir / "01_본문.txt").write_text("본문", encoding="utf-8")
        for p in (patch.object(llm, "has_key", return_value=True),
                  patch.object(llm, "default_provider_model", return_value=("codex_cli", "default"))):
            p.start()
            self.addCleanup(p.stop)

    def test_export_view_renders_and_each_preface_has_its_own_button(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(APP), default_timeout=30)
        app.session_state["_update_info"] = {}
        app.session_state["_update_result"] = {}
        app.session_state["active_view"] = "5_wiki"
        app.run()
        self.assertFalse(app.exception, [x.message for x in app.exception])
        keys = [b.key for b in app.button if b.key and b.key.startswith(f"ch5w_{self.BOOK}_")]
        self.assertEqual(sorted(keys), [f"ch5w_{self.BOOK}_0", f"ch5w_{self.BOOK}_2"])


if __name__ == "__main__":
    unittest.main()
