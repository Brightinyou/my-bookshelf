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

    # ── 2026-08-27: «다시 읽으려고 눌렀는데 작동을 안해» ───────────────────
    # 눌러도 아무 일이 없던 까닭이 둘이었다. 여기서 둘 다 못 박는다.

    def test_실패로_끝나면_도는_중이_아니다(self):
        """오류가 적혔는데도 «도는 중»이면 화면이 진행바에 갇혀 오류를 못 보여 준다.

        화면 코드가 `if 도는중: 진행바 / elif 오류: 오류표시` 라서, 심장박동이
        신선한 채 error 만 얹히면 **영원히 진행바만 돈다.**
        """
        self._beat(error="RuntimeError: 공급자를 쓸 수 없습니다")
        self.assertFalse(ai_ocr.is_running(self.out))
        self.assertEqual(ai_ocr.status(self.out).get("error"),
                         "RuntimeError: 공급자를 쓸 수 없습니다")

    def test_시작하면_곧바로_도는_것으로_보인다(self):
        """start_background 는 **갈래를 띄우기 전에** 첫 심장박동을 찍어야 한다.

        예전에는 clear_run_state() 가 박동을 지운 채 돌아왔다. 버튼을 누른 뒤
        화면이 다시 그려지는 시점엔 박동이 없어 is_running()=False → 진행바도
        오류도 없이 «아무 일도 안 일어난» 것처럼 보였다.
        """
        started = []

        def _fake_reocr(*a, **kw):
            started.append(True)
            time.sleep(0.5)          # 화면이 다시 그려질 만큼은 살아 있게

        real = ai_ocr.reocr
        ai_ocr.reocr = _fake_reocr
        try:
            ai_ocr.start_background(self.tmp / "책.pdf", self.out, "codex_cli",
                                    pages=[1, 2, 3])
            # 갈래가 아직 아무것도 안 했더라도 이미 «도는 중»이어야 한다
            self.assertTrue(ai_ocr.is_running(self.out))
            self.assertEqual(ai_ocr.status(self.out).get("total"), 3)
            self.assertEqual(ai_ocr.status(self.out).get("provider"), "codex_cli")
        finally:
            ai_ocr.reocr = real
            time.sleep(0.6)
        self.assertTrue(started)


if __name__ == "__main__":
    unittest.main()
