"""쪽 레이아웃 — 본문과 각주가 나뉘는 자리를 찾는다 (2026-08-24).

**왜.** 각주는 본문보다 글씨가 작아서 판독이 더 자주 틀린다. 실측(『기술신학』
30쪽 각주 39): `벽돌이`→`변혁이`·`변들이`, `흙이라는`→`휴이라는`,
`물질을`→`통찰을`. 학위논문에서 각주는 서지사항이라 이런 오독이 치명적이다.

각주 영역만 알면 **그 부분만 크게 렌더해서** 따로 읽힐 수 있다. 본문은 싸게,
각주는 정확하게.

**어떻게 찾는가.** 사용자 관찰("각주 글씨가 작으니 한 줄에 글자가 더 많다")을
글자수가 아니라 **줄 간격**으로 재면 확실하다. 실측:

    본문 줄 간격  31 ~ 33
    각주 줄 간격  20 ~ 21

글꼴 크기(`get_charbox` 높이)는 **못 쓴다** — 이 책들의 텍스트 레이어는 OCR로
구워진 것이라 글자 높이가 0으로 나온다. 반면 줄의 y좌표는 멀쩡하다.

각주는 늘 쪽 아래에 있으므로 **아래에서부터** 간격이 좁은 구간을 찾는다.
"""

from dataclasses import dataclass
from pathlib import Path
import statistics

# 각주 줄로 보려면 본문 줄 간격의 몇 배 이내여야 하는가 (실측 20/31 ≈ 0.65)
NARROW_RATIO = 0.8
# 이만큼은 이어져야 각주 블록으로 본다 — 한 줄짜리 우연을 거른다
MIN_NOTE_LINES = 2
# 쪽의 이 비율보다 위에서 시작하면 각주가 아니다(본문 한복판의 표·인용문 오탐 방지)
MAX_NOTE_TOP = 0.55


@dataclass
class PageLayout:
    height: float                 # 쪽 높이(pt)
    note_top: float | None = None  # 각주 영역의 위 경계(pt, 아래가 0)
    body_gap: float = 0.0
    note_gap: float = 0.0
    note_lines: int = 0

    @property
    def has_notes(self) -> bool:
        return self.note_top is not None


def _text_lines(pdf_path: Path, index0: int, lock=None) -> tuple[list[float], float]:
    """(줄의 y좌표 목록, 쪽 높이). 글자가 4자 미만인 줄은 잡음이라 버린다."""
    import pypdfium2 as pdfium
    ctx = lock if lock is not None else _NullLock()
    with ctx:
        doc = pdfium.PdfDocument(str(pdf_path))
        try:
            page = doc[index0]
            height = page.get_size()[1]
            tp = page.get_textpage()
            raw: list[float] = []
            for i in range(tp.count_chars()):
                try:
                    box = tp.get_charbox(i, loose=False)
                except Exception:
                    continue
                raw.append(box[1])
            return _cluster_lines(raw), height
        except Exception:
            return [], 0.0
        finally:
            doc.close()


def _cluster_lines(ys: list[float], min_chars: int = 4) -> list[float]:
    """글자들의 y좌표를 '줄'로 묶는다.

    ★스캔본은 줄이 미세하게 기울어 있어 **같은 줄 글자의 y가 몇 pt씩 다르다.**
    정수로 반올림만 하면 한 줄이 여러 줄로 쪼개지고, 그 쪼개진 것들 사이의 아주
    작은 간격(1~2pt)이 '좁은 간격'으로 잡혀 각주로 오인된다 (2026-08-24 실측:
    책마다 각주/본문 간격 비율이 0.05~0.78로 널뛰었다 — 0.05가 이 오인이다).

    그래서 두 번 훑는다. 먼저 아주 좁은 폭으로 묶어 줄 간격의 눈대중을 얻고,
    그 간격의 일부를 허용 오차로 삼아 다시 묶는다. 책마다 줄 간격이 다르므로
    **절대값을 쓰지 않는다.**"""
    if not ys:
        return []
    ys = sorted(ys)

    def _group(tol: float) -> list[tuple[float, int]]:
        out: list[tuple[float, int]] = []
        start, count = ys[0], 1
        for y in ys[1:]:
            if y - start <= tol:
                count += 1
            else:
                out.append((start, count))
                start, count = y, 1
        out.append((start, count))
        return out

    rough = _group(2.0)
    if len(rough) < 3:
        return [y for y, n in rough if n >= min_chars]
    gaps = sorted(rough[i + 1][0] - rough[i][0] for i in range(len(rough) - 1))
    typical = gaps[len(gaps) // 2] or 2.0
    fine = _group(max(2.0, typical * 0.35))
    return [y for y, n in fine if n >= min_chars]


class _NullLock:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def analyze(pdf_path: Path, index0: int, lock=None) -> PageLayout:
    """한 쪽의 본문/각주 경계를 찾는다. 각주가 없으면 note_top=None."""
    ys, height = _text_lines(pdf_path, index0, lock)
    lay = PageLayout(height=height)
    if len(ys) < 6 or not height:
        return lay
    gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    body_gap = statistics.median(gaps)
    lay.body_gap = body_gap
    if body_gap <= 0:
        return lay

    # 좁은 간격이 이어지는 구간을 모은다. ★맨 아래 줄은 대개 **쪽번호**라 그 위와의
    # 간격이 넓다(실측 30쪽: 75 → 20·21·20 → 78). 그래서 "gaps[0]부터 좁아야 한다"고
    # 보면 언제나 실패한다. 넓은 간격을 건너뛰고 좁은 구간을 찾아야 한다.
    runs: list[tuple[int, int]] = []      # (시작 gap 인덱스, 길이)
    i = 0
    while i < len(gaps):
        if gaps[i] < body_gap * NARROW_RATIO:
            j = i
            while j < len(gaps) and gaps[j] < body_gap * NARROW_RATIO:
                j += 1
            runs.append((i, j - i))
            i = j
        else:
            i += 1
    # 각주는 쪽 아래에 있으므로 **가장 아래(인덱스가 작은)** 구간부터 본다
    for start, length in runs:
        if length < MIN_NOTE_LINES:
            continue
        top = ys[start + length]          # 그 블록의 가장 위 줄
        if top > height * MAX_NOTE_TOP:   # 너무 위면 본문 속 표·인용문이다
            continue
        lay.note_gap = statistics.median(gaps[start:start + length])
        lay.note_lines = length + 1
        lay.note_top = top
        return lay
    return lay


def crop_for_notes(lay: PageLayout, pad: float = 8.0) -> tuple[float, float, float, float]:
    """각주 영역만 남기는 crop 값 (left, bottom, right, top) — 위쪽만 잘라낸다.

    pypdfium2의 crop은 '각 변에서 얼마나 잘라낼지'를 pt로 받는다."""
    if not lay.has_notes:
        return (0.0, 0.0, 0.0, 0.0)
    cut_top = max(0.0, lay.height - lay.note_top - pad)
    return (0.0, 0.0, 0.0, cut_top)
