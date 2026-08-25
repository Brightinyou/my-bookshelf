# -*- coding: utf-8 -*-
"""재OCR 실행 상태 회귀 테스트 — services/ai_ocr의 심장박동·중단 표시.

2026-08-24에 실제로 사고가 났다. 진행 상태를 프로세스 메모리(`RUNS` 딕셔너리와
살아 있는 스레드 객체)로만 들고 있었더니, 앱을 다시 설치하는 사이 그 딕셔너리가
비면서 **돌고 있는 작업을 중단할 수단이 사라졌다.** 사용자가 «중단»을 눌렀지만
버튼은 비활성이었고 작업은 계속 돌았다.

그래서 상태를 작업 폴더의 파일로 옮겼다. 이 테스트가 지키는 것은 하나다 —
**다른 프로세스에서 건 중단이 보여야 한다.**
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from services import ai_ocr


class RunStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ocr_state_test_"))
        self.out = self.tmp / "책.txt"
        ai_ocr.work_dir(self.out).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _beat(self, **kw):
        # pid 1 은 유닉스에서만 늘 살아 있다(init). 윈도우에서는 없는 PID라
        # "살아 있는 pid" 라는 뜻이 안 된다 — 확실히 도는 프로세스를 쓴다.
        payload = {"beat": time.time(), "pid": os.getpid(), "done": 0, "total": 1}
        payload.update(kw)
        ai_ocr._hb_path(self.out).write_text(json.dumps(payload), encoding="utf-8")

    def test_아무것도_안_돌면_멈춤(self):
        self.assertFalse(ai_ocr.is_running(self.out))

    def test_신선한_심장박동은_도는_것(self):
        self._beat()
        self.assertTrue(ai_ocr.is_running(self.out))

    def test_심장이_멎으면_죽은_것(self):
        self._beat(beat=time.time() - ai_ocr.STALE_AFTER - 10)
        self.assertFalse(ai_ocr.is_running(self.out))

    def test_없는_PID면_죽은_것(self):
        self._beat(pid=999999)
        self.assertFalse(ai_ocr.is_running(self.out))

    def test_다른_프로세스가_건_중단이_보인다(self):
        """이 테스트가 이 파일의 존재 이유다 — 앱이 리로드돼도 중단이 통해야 한다."""
        self.assertFalse(ai_ocr._stop_requested(self.out))
        subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, sys.argv[1]);"
             "from services import ai_ocr; ai_ocr.request_stop(sys.argv[2])",
             str(Path(__file__).resolve().parents[1]), str(self.out)],
            check=True, capture_output=True)
        self.assertTrue(ai_ocr._stop_requested(self.out))

    def test_정리하면_둘_다_사라진다(self):
        self._beat()
        ai_ocr.request_stop(self.out)
        ai_ocr.clear_run_state(self.out)
        self.assertFalse(ai_ocr.is_running(self.out))
        self.assertFalse(ai_ocr._stop_requested(self.out))


if __name__ == "__main__":
    unittest.main()
