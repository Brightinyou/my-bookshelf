"""로컬 OCR(Apple Vision) — AI 판독을 견줄 '둘째 눈' (2026-08-24).

**왜 둘째 눈이 필요한가.** LLM 판독은 같은 쪽을 두 번 읽으면 다르게 읽는다
(services/ai_ocr.reconcile 머리말 참고). 그래서 두 번 읽어 견주는데, 두 번 다
LLM이면 **구독 한도를 두 배 쓰고 실패 양상도 비슷하다.**

Apple Vision은 그 자리에 더 맞다:
  · 공짜다 — 로컬이라 한도를 안 쓴다.
  · 빠르다 — 한 쪽 1초 남짓(LLM은 10초대).
  · **결정적이다** — 같은 이미지면 같은 답. 그래서 견주는 기준으로 삼을 수 있다.
  · **실패 양상이 다르다** — 이게 핵심이다. 같은 종류의 판독기 둘을 견주면 같은
    자리에서 같이 틀리지만, 성격이 다른 둘은 서로의 구멍을 비춘다.

실측(『기술신학』 30쪽, LLM이 틀렸던 낱말들): `벽돌이`·`망원경`·`독점`·
`내재하심`·`얽혀`를 **Vision이 전부 맞혔다**(1.1초). 반대로 Vision은 줄 순서를
뒤섞고 각주 번호를 흘리는데, 낱말 단위로 견주는 데는 걸림돌이 안 된다.

**본문으로 채택하지는 않는다.** 문단·각주 구조는 LLM 판독이 훨씬 낫다. Vision은
어디가 미심쩍은지 알려주는 데만 쓴다.

의존성 주의: `ocrmac`은 python3.12에만 깔려 있고 앱은 3.14로 돈다. 그래서 같은
프로세스에서 import하지 못하고 **다른 파이썬을 subprocess로 부른다.** 없으면
조용히 건너뛴다 — 둘째 눈은 있으면 좋은 것이지 없다고 멈출 일이 아니다.
"""

import json
import shutil
import subprocess
from pathlib import Path

# ocrmac이 깔린 파이썬 후보. 앱이 도는 3.14에는 없다.
_PY_CANDIDATES = (
    "/usr/local/bin/python3.12",
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12",
    "/opt/homebrew/bin/python3.12",
)
_TIMEOUT = 120

_SNIPPET = """
import json, sys
from ocrmac import ocrmac
out = []
for p in sys.argv[1:]:
    try:
        res = ocrmac.OCR(p, language_preference=["ko-KR", "en-US"],
                         recognition_level="accurate").recognize()
        out.append(" ".join(r[0] for r in res))
    except Exception:
        out.append("")
print(json.dumps(out, ensure_ascii=False))
"""

_cached_python: str | None = None
_checked = False


def python_with_ocrmac() -> str | None:
    """ocrmac을 import할 수 있는 파이썬 경로. 한 번 찾으면 기억한다."""
    global _cached_python, _checked
    if _checked:
        return _cached_python
    _checked = True
    cands = [p for p in _PY_CANDIDATES if Path(p).exists()]
    for extra in ("python3.12", "python3"):
        found = shutil.which(extra)
        if found and found not in cands:
            cands.append(found)
    for py in cands:
        try:
            r = subprocess.run([py, "-c", "import ocrmac"], capture_output=True, timeout=20)
            if r.returncode == 0:
                _cached_python = py
                return py
        except Exception:
            continue
    return None


def available() -> bool:
    return python_with_ocrmac() is not None


def read(images: list[Path], timeout: int = _TIMEOUT) -> list[str]:
    """이미지들을 Vision으로 읽는다. 못 읽으면 빈 문자열 — 절대 예외를 올리지 않는다.

    둘째 눈이 없다고 판독 자체가 멈추면 안 된다."""
    py = python_with_ocrmac()
    if not py or not images:
        return ["" for _ in images]
    try:
        r = subprocess.run([py, "-c", _SNIPPET, *[str(i) for i in images]],
                           capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return ["" for _ in images]
        out = json.loads((r.stdout or "").strip().splitlines()[-1])
        return list(out) + [""] * (len(images) - len(out))
    except Exception:
        return ["" for _ in images]
