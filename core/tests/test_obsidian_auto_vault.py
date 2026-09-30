"""앱이 켜질 때 위키 폴더를 옵시디언 보관함으로 등록 (2026-09-30).

설정 창은 옵시디언을 깔기만 해서 obsidian.json 이 없었고, 옵시디언을 열면 «새 보관함
만들기» 화면이 떠 우리 노트를 못 찾았다(Windows Sandbox 실측).
"""
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


if __name__ == "__main__":
    unittest.main()
