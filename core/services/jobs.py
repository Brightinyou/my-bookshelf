"""Background work survives UI reruns and never calls Streamlit."""
from contextvars import ContextVar
from copy import deepcopy
import threading
import time

_current_state = ContextVar("mybookshelf_job_state", default=None)
_current_job = ContextVar("mybookshelf_job", default=None)


def current_state():
    return _current_state.get()


def stop_requested() -> bool:
    """중단을 눌렀는가 — 한 항목이 오래 걸리는 처리기가 사이사이 물어본다.

    이 통로가 없으면 «현재 항목 후 중단»이 말 그대로 항목 경계에서만 듣는다.
    챕터 하나가 수백 단락이면 눌러도 몇 시간 뒤에나 멈췄다 (2026-09-09).
    """
    job = _current_job.get()
    return bool(job is not None and job.stop_after)


class BackgroundJob:
    def __init__(self, fn, state=None):
        self.state = deepcopy(state or {})
        self.started_at = time.time()
        self.done = threading.Event()
        self.progress = ()
        self.result = None
        self.error = None
        self.stop_after = False
        self._thread = threading.Thread(target=self._run, args=(fn,), daemon=True)

    def start(self):
        self._thread.start()
        return self

    def report(self, *args):
        self.progress = args

    def _run(self, fn):
        token = _current_state.set(self.state)
        job_token = _current_job.set(self)
        try:
            self.result = fn(self.report)
        except BaseException as exc:
            # All exits must become a terminal result, including framework stop signals.
            self.error = exc
        finally:
            _current_job.reset(job_token)
            _current_state.reset(token)
            self.done.set()
