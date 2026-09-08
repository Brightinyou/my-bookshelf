from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from services.jobs import BackgroundJob, current_state
from services import pipeline_queue as q


class JobStorageTest(unittest.TestCase):
    def test_background_state_is_detached_from_ui_and_completion_is_reported(self):
        release = threading.Event()
        source = {"books": ["old"]}
        def work(progress):
            current_state()["books"].append("new")
            progress(1, 2)
            release.wait(2)
            return True, "done"
        job = BackgroundJob(work, source).start()
        self.assertEqual(source, {"books": ["old"]})
        release.set()
        self.assertTrue(job.done.wait(3))
        self.assertEqual(job.progress, (1, 2))
        self.assertEqual(job.state["books"], ["old", "new"])
        self.assertEqual(job.result, (True, "done"))
        self.assertIsNone(current_state())

    def test_nonstandard_worker_exit_still_has_terminal_state(self):
        def work(progress):
            raise SystemExit("stopped")
        job = BackgroundJob(work).start()
        self.assertTrue(job.done.wait(3))
        self.assertIsInstance(job.error, SystemExit)

    def test_concurrent_queue_updates_do_not_drop_items(self):
        with tempfile.TemporaryDirectory() as root, patch.object(q, "_QUEUE_FILE", Path(root) / "queue.json"):
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda i: q.queue_add("tab3_ready", [str(i)]), range(50)))
            self.assertEqual(set(q.queue_list("tab3_ready")), {str(i) for i in range(50)})
            q._QUEUE_FILE.write_text("broken", encoding="utf-8")
            with self.assertRaises(ValueError):
                q.queue_add("tab3_ready", ["new"])
            self.assertEqual(q._QUEUE_FILE.read_text(encoding="utf-8"), "broken")


if __name__ == "__main__":
    unittest.main()
