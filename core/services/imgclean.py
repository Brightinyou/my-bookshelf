"""imgclean.py — 판독 전에 이미지에서 밑줄을 걷어낸다 (2026-08-25)

**넷을 재서 하나만 남겼다.** 30쪽(형광펜+굵은 밑줄) 기준 Apple Vision 판독으로 측정:

| 전처리                    | 유사도 | 오독 |
|---------------------------|--------|------|
| 원본                      | 0.974  | 16   |
| 형광펜 제거(초록 채널)    | 0.974  | 16   | ← 효과 정확히 0
| **밑줄 제거**             | **0.995** | **4** | ← 유일한 이득
| CLAHE 대비 정규화         | 0.974  | 16   |
| 적응 이진화               | 0.928  | —    | ← 해로움(`벽돌이` 유실)

★**형광펜은 계산이 맞아도 이득이 없었다.** 형광펜 색은 RGB(228,230,23)이라 파랑
채널에서 배경(23)이 글자(46)보다 어둡다 — 대비가 뒤집힌다. 표준 회색조는 파랑을
11% 섞으므로 형광펜 구역 대비가 172→150으로 깎인다. 그런데 Vision 출력은 글자
수까지 **완전히 동일**했다. 자체 전처리가 이미 그 일을 한다. 그래서 안 한다.

★**이진화하지 않는다.** 원본 회색조에 흰색으로 칠하기만 한다.

★**밑줄 제거로 사라진 오독**: 의원론적→이원론적 · 신화적→신학적 · 문진화의→물질화의
· 통찬을→통찰을 · 연동하게→열등하게 · 성찬을→성찰을 · 창조신화적→창조신학적.
이것이 예전에 "Vision 자신의 오독"이라며 Vision을 판독자에서 심판으로 강등시킨
바로 그 목록이었다 — **Vision의 한계가 아니라 밑줄 탓이었다.**

★**cv2를 쓰지 않는다.** opencv는 119MB이고 이 앱의 의존성이 아니다. numpy(pandas가
이미 끌고 온다)만으로 같은 일을 한다 — 결과는 오히려 조금 나았다(0.9918/5 →
0.9948/4).
"""
from __future__ import annotations

from pathlib import Path

# 밑줄로 볼 가로 연속 길이 = 글자 높이의 몇 배인가.
# 한글 획은 글자 높이를 넘지 않으므로 2.5배면 획과 밑줄이 갈린다.
UNDERLINE_LEN_RATIO = 2.5
# 이만큼 위에 잉크가 있으면 밑줄이 아니라 글자의 일부로 본다.
INK_ABOVE_PX = 3


def _otsu(gray) -> int:
    """오츠 문턱값 — 히스토그램만으로 구한다."""
    import numpy as np
    hist = np.bincount(gray.ravel(), minlength=256).astype(float)
    p = hist / hist.sum()
    w0 = np.cumsum(p)
    w1 = 1.0 - w0
    m = np.cumsum(p * np.arange(256))
    with np.errstate(invalid="ignore", divide="ignore"):
        var = (m[-1] * w0 - m) ** 2 / (w0 * w1)
    return int(np.nanargmax(var))


def _char_height(ink) -> int:
    """글자 높이 = 잉크가 있는 가로줄 덩어리의 중앙값.

    ★**책마다 다르므로 고정값을 쓰면 안 된다.** 줄 간격에서 같은 교훈을 얻었다 —
    스캔본은 줄이 미세하게 기울어 책마다 값이 널뛴다."""
    import numpy as np
    runs: list[int] = []
    cur = 0
    for has_ink in ink.any(axis=1):
        if has_ink:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    return int(np.median(runs)) if runs else 20


def strip_underlines(rgb):
    """밑줄만 지운 회색조 배열을 돌려준다. (배열, 지운 화소 수, 글자 높이)

    ★**정교하게 만들수록 나빠졌다.** "세로 잉크 기둥이 두꺼우면 글자 획이니
    남긴다"는 보호 규칙을 5·8·12px로 넣어 보니 0.992 → 0.989/0.990으로 **떨어졌다.**
    밑줄 조각을 남기는 손해가 획이 조금 상하는 손해보다 크다. 단순한 규칙을 쓴다."""
    import numpy as np
    gray = rgb[:, :, 1] if getattr(rgb, "ndim", 2) == 3 else rgb   # 초록 채널이 가장 또렷하다
    ink = gray < _otsu(gray)
    ch = _char_height(ink)
    width = max(30, int(ch * UNDERLINE_LEN_RATIO))

    # 가로 열림(opening) = 침식 후 팽창. 여기서 끝나는 연속 잉크 길이를 먼저 잰다.
    c = np.cumsum(ink, axis=1)
    z = np.where(~ink, c, 0)
    runlen = c - np.maximum.accumulate(z, axis=1)
    long_tail = runlen >= width                      # 침식
    grown = long_tail.copy()                         # 팽창 — 두 배씩 늘려 log번만 돈다
    step = 1
    while step < width:
        s = min(step, width - step)
        grown[:, :-s] |= grown[:, s:]
        step += s

    above = np.zeros_like(ink)
    above[INK_ABOVE_PX:] = ink[:-INK_ABOVE_PX]
    erase = grown & ink & ~above                     # 위에 잉크가 없는 밑줄 화소만

    out = gray.copy()
    out[erase] = 255
    return out, int(erase.sum()), ch


def clean_file(path: Path) -> dict:
    """이미지 파일을 제자리에서 정리한다. 못 하면 조용히 원본을 둔다.

    ★**깨끗한 쪽은 건드리지 않는다**(실측 45쪽: 지운 화소 42개 = 0.002%, 판독
    결과 완전 동일). 이득은 표시가 심한 쪽에서만 난다(30쪽 오독 16 → 4)."""
    try:
        import numpy as np
        from PIL import Image
    except Exception:
        return {"ok": False, "reason": "numpy/Pillow 없음"}
    try:
        with Image.open(path) as im:
            rgb = np.array(im.convert("RGB"))
        cleaned, erased, ch = strip_underlines(rgb)
        if erased:
            Image.fromarray(cleaned).save(path, quality=85)
        return {"ok": True, "erased": erased, "char_height": ch}
    except Exception as e:
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"}
