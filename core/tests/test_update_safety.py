from pathlib import Path
import unittest
from unittest.mock import patch
from services import updater


class UpdateSafetyTest(unittest.TestCase):
    def test_network_failure_is_not_reported_as_latest(self):
        with patch.object(updater.sys, "platform", "darwin"), \
             patch.object(updater, "_mac_app_bundle", return_value=Path("/Applications/MyBookshelf.app")), \
             patch.object(updater.urllib.request, "urlopen", side_effect=OSError("offline")), \
             patch.object(updater, "append_log"):
            result = updater.check_for_update()
        self.assertFalse(result["available"])
        self.assertIn("offline", result["error"])

    def test_permission_failure_never_starts_helper_or_exits(self):
        with patch.object(updater.sys, "platform", "darwin"), \
             patch.object(updater, "_mac_app_bundle", return_value=Path("/Applications/MyBookshelf.app")), \
             patch.object(updater.os, "access", return_value=False), \
             patch.object(updater, "append_log"), \
             patch.object(updater.subprocess, "Popen") as spawn, \
             patch.object(updater, "_terminate_parent_tree") as terminate:
            self.assertFalse(updater.launch_helper_and_exit(Path("/tmp/update.zip")))
            spawn.assert_not_called()
            terminate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
