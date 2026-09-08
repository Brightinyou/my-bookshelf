"""Background work survives UI reruns and never calls Streamlit."""
from contextvars import ContextVar
from copy import deepcopy
import threading
import time

_current_state = ContextVar("mybookshelf_job_state", default=None)


def current_state():
    return _current_state.get()


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
        try:
            self.result = fn(self.report)
        except BaseException as exc:
            # All exits must become a terminal result, including framework stop signals.
            self.error = exc
        finally:
            _current_state.reset(token)
            self.done.set()
