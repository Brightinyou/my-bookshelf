"""앱이 켜질 때 위키 폴더를 옵시디언 보관함으로 등록 (2026-09-30).

설정 창은 옵시디언을 깔기만 해서 obsidian.json 이 없었고, 옵시디언을 열면 «새 보관함
만들기» 화면이 떠 우리 노트를 못 찾았다(Windows Sandbox 실측).
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
from pathlib import Path
from unittest import mock
import json
import tempfile
import unittest

from services import wiki


class AutoRegisterWikiVaultTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.cfgf = tmp / "obsidian" / "obsidian.json"
        self.folder = tmp / "wiki"
        self.prefs = {"use_obsidian": True}
        patches = [
            mock.patch.object(wiki, "_obsidian_config", return_value=self.cfgf),
            mock.patch.object(wiki.llm, "get_pref",
                              side_effect=lambda k, d=None: self.prefs.get(k, d)),
            mock.patch.object(wiki, "obsidian_installed", return_value=True),
            mock.patch.object(wiki, "obsidian_running", return_value=False),
            mock.patch.object(wiki, "append_log"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def _vaults(self):
        return json.loads(self.cfgf.read_text(encoding="utf-8"))["vaults"]

    def test_registers_and_opens_when_it_is_the_only_vault(self):
        self.assertEqual(wiki.auto_register_wiki_vault(self.folder), "registered")
        (v,) = self._vaults().values()
        self.assertEqual(Path(v["path"]), self.folder.resolve())
        self.assertTrue(v["open"])
        self.assertTrue(self.folder.is_dir())

    def test_does_not_steal_open_from_existing_vaults(self):
        self.cfgf.parent.mkdir(parents=True)
        self.cfgf.write_text(json.dumps({"vaults": {"a": {"path": "C:/other", "ts": 1, "open": True}}}),
                             encoding="utf-8")
        self.assertEqual(wiki.auto_register_wiki_vault(self.folder), "registered")
        vaults = self._vaults()
        self.assertEqual(len(vaults), 2)
        self.assertTrue(vaults["a"]["open"])
        self.assertEqual(sum(1 for v in vaults.values() if v.get("open")), 1)

    def test_already_registered_is_left_alone(self):
        wiki.auto_register_wiki_vault(self.folder)
        before = self.cfgf.read_text(encoding="utf-8")
        self.assertEqual(wiki.auto_register_wiki_vault(self.folder), "already")
        self.assertEqual(self.cfgf.read_text(encoding="utf-8"), before)

    def test_skips_while_obsidian_is_running(self):
        """켜진 채로 고치면 옵시디언이 닫히며 덮어쓸 수 있다 — 다음에 켤 때 한다."""
        with mock.patch.object(wiki, "obsidian_running", return_value=True):
            self.assertEqual(wiki.auto_register_wiki_vault(self.folder), "running")
        self.assertFalse(self.cfgf.exists())

    def test_nothing_when_obsidian_off_or_missing(self):
        self.prefs["use_obsidian"] = False
        self.assertEqual(wiki.auto_register_wiki_vault(self.folder), "off")
        self.prefs["use_obsidian"] = True
        with mock.patch.object(wiki, "obsidian_installed", return_value=False):
            self.assertEqual(wiki.auto_register_wiki_vault(self.folder), "no_app")
        self.assertFalse(self.cfgf.exists())


class ObsidianRunningTest(unittest.TestCase):
    """tasklist 는 Sandbox 에서 떠 있는 옵시디언을 «없음»으로 읽었다 (2026-09-30)."""

    def test_unreadable_process_list_counts_as_running(self):
        with mock.patch.object(wiki.sys, "platform", "win32"), \
             mock.patch.object(wiki, "_windows_process_names", return_value=None):
            self.assertTrue(wiki.obsidian_running())

    def test_reads_names_from_the_process_list(self):
        with mock.patch.object(wiki.sys, "platform", "win32"):
            with mock.patch.object(wiki, "_windows_process_names", return_value={"explorer.exe"}):
                self.assertFalse(wiki.obsidian_running())
            with mock.patch.object(wiki, "_windows_process_names",
                                   return_value={"explorer.exe", "obsidian.exe"}):
                self.assertTrue(wiki.obsidian_running())

    @unittest.skipUnless(wiki.sys.platform == "win32", "Windows 전용")
    def test_real_snapshot_sees_this_process(self):
        import os
        import sys
        names = wiki._windows_process_names()
        self.assertIsNotNone(names)
        self.assertIn(os.path.basename(sys.executable).lower(), names)


class AppStartupHookTest(unittest.TestCase):
    def test_hook_runs_before_the_first_st_stop(self):
        """첫 화면(작업 메뉴)이 st.stop() 으로 끝나 뒤에 둔 등록이 안 불렸다(Sandbox 실측)."""
        src = (Path(__file__).resolve().parents[1] / "pipeline_app.py").read_text(encoding="utf-8")
        import re
        hook = src.index("auto_register_wiki_vault(WIKI_DIR)")
        first_stop = re.search(r"^\s+st\.stop\(\)", src, re.M).start()   # 주석 속 글자는 빼고
        self.assertLess(hook, first_stop)


if __name__ == "__main__":
    unittest.main()
