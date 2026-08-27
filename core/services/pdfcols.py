# -*- coding: utf-8 -*-
"""pypdfium2 좌표 기반 다단(N단) → 읽기순서 추출.
- 이미 의존성에 있는 pypdfium2(Apache/BSD) 사용 → PyMuPDF(AGPL) 불필요.
- 띄어쓰기는 실제 공백 문자 유지 + x좌표 간격 보조(깨진 공백 폰트 대응).
- 각 행을 거터(빈 세로 띠)에서 열별로 분할해 컬럼 읽기순서 복원.
논문 2단, 뉴스레터, 1단→2단 혼합, 한글+영어 혼합, 3단 등을 처리한다."""
import re
import statistics
import unicodedata

import pypdfium2 as pdfium

from services import reflowlib


def _kind(ch):
    """'drop'=버림(제어/개행), 'space'=공백, 'broken'=폰트 미매핑 글리프, ''=실제 글자."""
    if ch in ("￾", "￿"):
        # 폰트가 유니코드로 매핑 못한 글리프. 이 문서에선 줄끝 하이픈, 다른
        # 문서에선 공백으로도 쓰인다 → 위치(줄끝/중간)로 _text에서 해석한다.
        return "broken"
    if ch in ("\r", "\n", "\t") or unicodedata.category(ch)[0] == "C":
        return "drop"
    if ch == " " or unicodedata.category(ch)[0] == "Z":
        return "space"
    return ""


def _glyphs(page):
    """글리프 목록 + 페이지크기 + 정상 글리프의 자높이/폭 중앙값.

    튜플은 (x0, ycen, x1, ch, is_space, stream_index, repaired,
    is_broken)이다. 일부 폰트의 잘못된 글리프는 raw 스트림의 같은 줄 안에서
    dominant y 군집의 다음 글리프(없으면 이전 글리프)를 빌려 위치를 복원한다.
    실제 공백 문자는 살려두고(is_space=True), 폭이 깨진 폰트를 위해
    x간격 기반 보조 판정과 병행한다."""
    w, h = page.get_size()
    tp = page.get_textpage()
    n = tp.count_chars()
    if n == 0:
        return w, h, [], 10, 6
    full = tp.get_text_range()
    raw, heights, widths = [], [], []
    line_no = 0
    for i in range(n):
        ch = full[i] if i < len(full) else ""
        if not ch:
            continue
        if ch in ("\r", "\n"):
            line_no += 1
            continue
        k = _kind(ch)
        if k == "drop":
            continue
        l, b, r, t = tp.get_charbox(i, loose=True)   # advance 기준 박스
        x0, x1 = min(l, r), max(l, r)
        y0, y1 = h - max(t, b), h - min(t, b)
        degenerate = (x1 <= x0 or y1 <= y0)
        raw.append({
            "x0": x0, "x1": x1, "y0": y0, "y1": y1,
            "ch": ch, "kind": k, "index": i, "line": line_no,
            "degenerate": degenerate,
        })
        if k == "" and not degenerate:
            heights.append(y1 - y0); widths.append(x1 - x0)
    mh = statistics.median(heights) if heights else 10
    mw = statistics.median(widths) if widths else 6

    # 같은 raw 줄의 정상 실제 글자를 y로 군집화한다. 가장 큰 군집 밖의 정상
    # 글자도 다른 줄의 좌표가 섞인 것으로 보고 퇴화 글리프와 함께 복원한다.
    real_by_line = {}
    for pos, glyph in enumerate(raw):
        if glyph["kind"] == "" and not glyph["degenerate"]:
            real_by_line.setdefault(glyph["line"], []).append(pos)

    dominant = set()
    for positions in real_by_line.values():
        positions.sort(key=lambda pos: (raw[pos]["y0"] + raw[pos]["y1"]) / 2)
        clusters, current = [], []
        previous_y = None
        for pos in positions:
            ycenter = (raw[pos]["y0"] + raw[pos]["y1"]) / 2
            if previous_y is None or ycenter - previous_y <= mh * 0.5:
                current.append(pos)
            else:
                clusters.append(current)
                current = [pos]
            previous_y = ycenter
        clusters.append(current)
        dominant.update(max(clusters, key=len))

    for pos, glyph in enumerate(raw):
        glyph["needs_repair"] = (
            glyph["degenerate"]
            or glyph["kind"] in ("space", "broken")
            or (glyph["kind"] == "" and pos not in dominant)
        )
        glyph["repaired"] = False

    # raw 줄 경계를 넘지 않고 dominant 실제 글자를 O(n)으로 미리 찾는다. x는
    # 참조 글자의 경계에 정확히 맞춰 stream index tie-break가 작동하게 한다.
    next_dominant = [None] * len(raw)
    previous_dominant = [None] * len(raw)
    nearest_by_line = {}
    for pos in range(len(raw) - 1, -1, -1):
        glyph = raw[pos]
        next_dominant[pos] = nearest_by_line.get(glyph["line"])
        if pos in dominant:
            nearest_by_line[glyph["line"]] = pos
    nearest_by_line.clear()
    for pos, glyph in enumerate(raw):
        previous_dominant[pos] = nearest_by_line.get(glyph["line"])
        if pos in dominant:
            nearest_by_line[glyph["line"]] = pos

    for pos, glyph in enumerate(raw):
        if not glyph["needs_repair"]:
            continue
        has_next = next_dominant[pos] is not None
        neighbor_pos = (next_dominant[pos] if has_next
                        else previous_dominant[pos])
        if neighbor_pos is None:
            continue
        neighbor = raw[neighbor_pos]

        glyph["y0"], glyph["y1"] = neighbor["y0"], neighbor["y1"]
        anchor = neighbor["x0"] if has_next else neighbor["x1"]
        glyph["x0"] = glyph["x1"] = anchor
        glyph["repaired"] = True

    gl = []
    for glyph in raw:
        is_sp = (glyph["kind"] == "space")
        gl.append((
            glyph["x0"], (glyph["y0"] + glyph["y1"]) / 2, glyph["x1"],
            " " if is_sp else glyph["ch"], is_sp, glyph["index"],
            glyph["repaired"], glyph["kind"] == "broken",
        ))
    return w, h, gl, mh, mw


def _layout_glyphs(chars):
    """공백·복구·미매핑 글리프를 제외한 좌표 통계용 글리프."""
    return [c for c in chars if not c[4] and not c[6] and not c[7]]


def _group_rows(gl, tol):
    """y로 행 묶기 (위→아래). 공백 포함(텍스트 복원용)."""
    gl = sorted(gl, key=lambda c: (c[1], c[0], c[5]))
    rows, cur, cy = [], [], None
    for c in gl:
        if cy is None or abs(c[1] - cy) <= tol:
            cur.append(c)
            cy = sum(x[1] for x in cur) / len(cur)
        else:
            rows.append(cur); cur = [c]; cy = c[1]
    if cur:
        rows.append(cur)
    return rows


def _text(chars, space_gap):
    """실제 공백 문자 + x간격(보조)으로 띄어쓰기 복원.
    미매핑 글리프(￾)는 줄 끝 라틴 문자 뒤면 하이픈(-), 줄 중간 ASCII 단어 조각이면 결합하고,
    그 밖의 줄 중간이면 공백으로 해석한다."""
    chars = sorted(chars, key=lambda c: (c[0], c[5]))   # 동좌표는 스트림 순서로
    n = len(chars)
    next_actual = [None] * n
    following = None
    for idx in range(n - 1, -1, -1):
        next_actual[idx] = following
        if not chars[idx][4] and chars[idx][3] not in ("￾", "￿"):
            following = chars[idx][3]

    out, prev_x1, pending, prev_repaired = [], None, False, False
    for idx, (x0, _y, x1, ch, is_sp, _si, repaired, _broken) in enumerate(chars):
        if is_sp:
            pending = True
            prev_x1 = x1 if prev_x1 is None else max(prev_x1, x1)
            prev_repaired = repaired
            continue
        if ch in ("￾", "￿"):
            next_ch = next_actual[idx]
            joins_ascii_word = bool(
                next_ch is not None and out
                and out[-1].isascii() and out[-1].isalpha()
                and next_ch.isascii() and next_ch.isalpha()
            )
            if next_ch is not None:
                if not joins_ascii_word:
                    pending = True             # 비라틴 줄 중간 → 공백
            elif out and out[-1].isascii() and out[-1].isalpha():
                out.append("-")                # 줄 끝 + 라틴 문자 뒤 → 영어 단어 분철
            # 그 외(한글 등) 줄 끝 → 아무것도 안 함(줄바꿈은 reflow가 공백으로 이음)
            prev_x1 = x1 if prev_x1 is None else max(prev_x1, x1)
            prev_repaired = repaired
            continue
        if prev_x1 is not None:
            if pending:
                out.append(" ")
            elif (not prev_repaired and not repaired
                  and (x0 - prev_x1) > space_gap):
                out.append(" ")                 # 복구 글리프 주변은 gap이 부정확 → 제외
        out.append(ch)
        prev_x1 = max(x0, x1)
        pending = False
        prev_repaired = repaired
    return "".join(out).strip()


def _adaptive_space_gap(rows, mw):
    """페이지의 실제 글자 간격 분포에서 '공백' 임계값을 추정한다.
    loose 박스라 어절/단어 내부 간격은 0 이하(겹침)이고, 공백은 뚜렷이 양수다.
    폰트마다 공백 폭이 달라(예: 조밀한 한글 본문 2.8pt) 고정값은 위험하므로
    양수 간격들의 중앙값 절반을 임계로 삼아 두 무리 사이 골짜기에 둔다."""
    gaps = []
    for row in rows:
        reals = sorted(_layout_glyphs(row), key=lambda c: (c[0], c[5]))
        gaps.extend(b[0] - a[2] for a, b in zip(reals, reals[1:]))
    # 단어/어절 사이 공백만 후보로 — 컬럼 거터·블록 사이 큰 간격(> mw*1.5)은 제외해야
    # 중앙값이 부풀지 않는다(2단 페이지에서 특히 중요).
    cand = sorted(g for g in gaps if mw * 0.05 < g < mw * 1.5)
    if not cand:
        return mw * 0.25
    med = cand[len(cand) // 2]
    return min(mw * 0.45, max(mw * 0.1, med * 0.5))


def _cluster(positions, tol):
    """가까운 위치들을 묶어 (중심x, 개수) 목록으로."""
    if not positions:
        return []
    positions = sorted(positions)
    groups, cur = [], [positions[0]]
    for p in positions[1:]:
        if p - cur[-1] <= tol:
            cur.append(p)
        else:
            groups.append(cur); cur = [p]
    groups.append(cur)
    return [(statistics.median(g), len(g)) for g in groups]


_FN_LINE = re.compile(r"^\s*\d{1,3}[\s.)]")
# 하이픈(미매핑 글리프 포함)으로 끊긴 낱말 바로 뒤에 붙은 각주 번호
_HYPH_NOTE = re.compile(r"[a-z￾�-](\d{1,3})\s+[A-Z“‘]")


def _split_note_lines(notes_text: str) -> str:
    """각주 블록 안에서 **번호로 시작하는 줄마다 새 문단**으로 끊는다 (2026-08-27).

    ★여기는 구분선 아래라 각주인 것이 이미 확실하다. 그러니 문서 전체 번호 사슬
    (reflowlib.separate_footnotes)처럼 조심스럽게 볼 이유가 없다 — 번호로 시작하면
    새 각주다. 사슬 방식은 중간에 각주 하나를 놓치면 뒤가 통째로 버려져서, 챕터에
    닿는 각주가 40개 중 15개에 그쳤다.

    각주가 쪽을 걸쳐 이어질 때 첫 줄은 번호 없이 시작하는데, 그 줄은 끊지 않으므로
    앞 각주에 그대로 이어 붙는다 — 쪽 경계 처리는 reflow 쪽에서 이미 한다."""
    # ★각주 번호는 윗첨자라 본문보다 기준선이 높아, 읽기 순서에서 **번호만 한 줄**로
    # 떨어져 나온다. 먼저 그것을 뒷줄에 붙여 '1 David Silver…' 꼴로 되돌린다.
    rows = notes_text.split("\n")
    joined: list[str] = []
    i = 0
    while i < len(rows):
        s = rows[i].strip()
        nxt = rows[i + 1].strip() if i + 1 < len(rows) else ""
        if s.isdigit() and len(s) <= 3 and nxt and not nxt.isdigit():
            joined.append(s + " " + nxt)
            i += 2
            continue
        joined.append(rows[i])
        i += 1
    out: list[str] = []
    for ln in joined:
        if _FN_LINE.match(ln) and out and out[-1].strip():
            out.append("")
        out.append(ln)
    return "\n".join(out)


def _notes_text(page, ymin: float) -> str:
    """각주 영역을 **읽기순서 정렬 없이** 그대로 읽는다 (2026-08-27).

    ★각주는 늘 쪽 아래 한 단으로 놓이므로 다단 정렬이 필요 없다. 오히려 해가 된다 —
    `_reading_order`에 넣었더니 각주 번호(내어쓰기라 x가 왼쪽 끝)를 다른 단으로 보고
    본문과 떼어 놓아, '5' '6' '7' 이 먼저 몰려 나오고 각주 본문이 뒤에 따로 나왔다.

    실제 판면은 **내어쓰기(hanging indent)** 다(실측):
        x=51.0  '5 For reviews of imago Dei interpretations, see …'   ← 각주 시작
        x=79.4  'Artificial Intelligence and the Human Spirit …'      ← 이어지는 줄
        x=51.0  '6 Robert H. Waterson et al., …'                      ← 다음 각주
    그래서 **줄의 시작 x가 가장 왼쪽이면 새 각주**다. 번호를 안 보므로, 각주가 쪽을
    걸쳐 이어질 때(번호 없이 시작) 그 줄이 들여쓰기면 앞 각주에 그대로 이어진다.
    """
    w, h, gl, mh, mw = _glyphs(page)
    ns = [g for g in gl if g[1] >= ymin]
    if not ns:
        return ""
    rows = _group_rows(ns, mh * 0.5)
    items = []
    for row in rows:
        cs = sorted(row, key=lambda c: (c[0], c[5]))
        text = "".join(c[3] for c in cs).strip()
        if text:
            items.append((cs[0][0], text))
    if not items:
        return ""
    left = min(x for x, _ in items)
    out: list[str] = []
    for x, text in items:
        # ★본문 마지막 줄이 각주 첫 줄과 한 행으로 묶여 오는 일이 있다 (2026-08-27).
        # 낱말이 하이픈으로 끊긴 자리 바로 뒤에 각주 번호가 붙는 모양이다 —
        #   'as a result of re￾26 A. V. Yurov, …'   'what dis￾32 "You have made …'
        # 그 각주(9·26·32번)를 통째로 놓치고 있었다. 하이픈 뒤 번호에서 끊는다.
        m = _HYPH_NOTE.search(text)
        if m:
            head, tail = text[:m.start(1)].rstrip(), text[m.start(1):]
            if head:
                out.append(head)
            out.append("")
            out.append(tail)
            continue
        if x <= left + mw * 0.8 and out and out[-1].strip():
            out.append("")               # 새 각주 — 문단을 끊는다
        out.append(text)
    return "\n".join(out)


def _footnote_rule_y(page) -> float | None:
    """각주 구분선의 y 좌표. 없으면 None (2026-08-27).

    ★조판자가 "여기부터 각주"라고 그어 둔 선이다. 논문 14편 실측에서 선각주 문서
    7편을 **전부** 찾아냈다 — 글자 크기·이탤릭 같은 간접 신호는 절반도 못 갈랐다.

    ★**form XObject 안까지 내려가야 한다.** 한글 논문 두 편은 쪽 내용 전체가 form
    하나에 싸여 있어 최상위 객체 목록에는 글자조차 안 보였고, 그래서 1차 측정에서
    "선 없음"으로 잘못 판정했다.

    쪽 아래 절반에 있는 얇고 가로로 긴 도형만 본다. 여럿이면 가장 위(=본문에 가까운
    쪽)를 쓴다 — 그 아래가 통째로 각주다.

    ★돌려주는 값은 **위에서 아래로 재는 좌표**다. PDF 객체 좌표는 쪽 아래가 원점인데
    `_glyphs`의 ycen 은 쪽 위가 원점이라 그대로 비교하면 위아래가 뒤집힌다
    (2026-08-27 — 이것 때문에 각주 대신 본문이 잘려 나왔다)."""
    try:
        import ctypes
        import pypdfium2.raw as pr
    except Exception:
        return None
    L, B, R, T = (ctypes.c_float() for _ in range(4))
    h = page.get_height()
    found: list[float] = []

    def walk(get, count, depth=0):
        if depth > 3:                       # 중첩 form 방어
            return
        for k in range(count):
            o = get(k)
            try:
                t = pr.FPDFPageObj_GetType(o)
            except Exception:
                continue
            if t == 5:                      # form — 안으로
                walk(lambda i, _o=o: pr.FPDFFormObj_GetObject(_o, i),
                     pr.FPDFFormObj_CountObjects(o), depth + 1)
            elif t == 2 and pr.FPDFPageObj_GetBounds(o, L, B, R, T):
                if (R.value - L.value) > 40 and (T.value - B.value) < 3 and B.value < h * 0.5:
                    found.append(B.value)

    try:
        walk(lambda i: pr.FPDFPage_GetObject(page.raw, i),
             pr.FPDFPage_CountObjects(page.raw))
    except Exception:
        return None
    return (h - max(found)) if found else None      # PDF좌표 → 위에서 아래로


def _reading_order(page, ymin=None, ymax=None):
    """페이지 → 읽기순서 텍스트.
    전체폭(제목·초록)과 2단 본문이 한 페이지에 섞여도, 페이지 전역이 아니라
    '여러 행이 공유하는 넓은 세로 간격'으로 거터를 찾아 그 행들만 컬럼 분리한다.
    세로 간격이 크면 문단 경계로 보고 빈 줄을 넣어 문단 구조를 보존한다."""
    w, h, gl, mh, mw = _glyphs(page)
    # ymin/ymax 로 쪽의 한 구간만 읽는다 — 각주 구분선 위아래를 따로 읽을 때 쓴다.
    if ymin is not None:
        gl = [g for g in gl if g[1] >= ymin]
    if ymax is not None:
        gl = [g for g in gl if g[1] < ymax]
    if not gl:
        return ""
    rows = _group_rows(gl, mh * 0.5)
    space_gap = _adaptive_space_gap(rows, mw)
    col_gap = max(mw * 3.25, space_gap * 4, 12.0)  # 컬럼 사이 거터로 볼 최소 간격

    # 1) 각 행의 '넓은 간격'(거터 후보) 중심 x 수집 (전체폭 행은 대부분 후보 없음)
    row_reals, cands = [], []
    for row in rows:
        reals = sorted(_layout_glyphs(row), key=lambda c: (c[0], c[5]))
        row_reals.append((row, reals))
        for a, b in zip(reals, reals[1:]):
            if (b[0] - a[2]) >= col_gap and w * 0.15 < (a[2] + b[0]) / 2 < w * 0.85:
                cands.append((a[2] + b[0]) / 2)

    # 2) 여러 행이 공유하는 위치만 거터로 채택 (전체폭 행의 우연한 간격 배제)
    min_support = max(3, len(rows) // 8)
    boundaries = sorted(cx for cx, n in _cluster(cands, mw * 2) if n >= min_support)

    ncol = len(boundaries) + 1
    cols = [[] for _ in range(ncol)]
    col_lasty = [None] * ncol
    out = []
    out_lasty = None                        # 전체폭/단일 컬럼 흐름의 마지막 y
    para_gap = mh * 1.8                      # 이보다 세로 간격이 크면 문단 경계

    def col_of(x):
        i = 0
        while i < len(boundaries) and x >= boundaries[i]:
            i += 1
        return i

    def flush():
        nonlocal out_lasty
        for i, c in enumerate(cols):
            if any(s.strip() for s in c):
                out.extend(c); out.append("")
            c.clear()
            col_lasty[i] = None
        out_lasty = None

    def emit_full(text, ytop):
        nonlocal out_lasty
        if out_lasty is not None and (ytop - out_lasty) > para_gap:
            out.append("")                  # 문단 경계
        out.append(text)
        out_lasty = ytop

    for row, reals in row_reals:
        if not row:
            continue
        ytop = min(c[1] for c in (reals or row))
        if not reals:
            emit_full(_text(row, space_gap), ytop); continue
        if not boundaries:
            emit_full(_text(row, space_gap), ytop); continue
        # 어떤 거터를 '틈 없이' 가로지르면 전체폭 행(제목·초록 등) → 통째로
        crosses = False
        for b in boundaries:
            l = [c[2] for c in reals if c[2] <= b]
            r = [c[0] for c in reals if c[0] >= b]
            if l and r and (min(r) - max(l)) < col_gap:
                crosses = True
                break
        if crosses:
            flush(); emit_full(_text(row, space_gap), ytop); continue
        # 열별 분배 (+ 세로 간격이 크면 문단 경계 삽입)
        buckets = {}
        for c in row:
            buckets.setdefault(col_of((c[0] + c[2]) / 2), []).append(c)
        for ci in sorted(buckets):
            if col_lasty[ci] is not None and (ytop - col_lasty[ci]) > para_gap:
                cols[ci].append("")
            cols[ci].append(_text(buckets[ci], space_gap))
            col_lasty[ci] = ytop
    flush()
    return "\n".join(out)


def pdf_to_pages(path):
    """PDF → 페이지별 읽기순서 텍스트 리스트. 반환: (pages, skipped)
    안전망①: 특정 페이지에서 예외가 나도 그 페이지만 건너뛰고 나머지는 살린다."""
    pdf = pdfium.PdfDocument(str(path))
    pages, skipped = [], 0
    try:
        for page in pdf:
            try:
                # 각주 구분선이 있으면 위(본문)·아래(각주)를 따로 읽고 빈 줄로 나눈다.
                # 그래야 reflow 가 각주를 본문 문단에 이어 붙이지 않는다 (2026-08-27).
                _ry = _footnote_rule_y(page)
                if _ry is None:
                    pages.append(_reading_order(page))
                else:
                    # 위에서 아래로 재므로 본문이 선 '위'(작은 값), 각주가 '아래'다
                    _body = _reading_order(page, ymax=_ry)
                    _notes = _notes_text(page, _ry)
                    _sep = "\n\n"
                    pages.append(_body + _sep + _notes if (_body and _notes)
                                 else (_body or _notes))
            except Exception:
                pages.append("")
                skipped += 1
    finally:
        pdf.close()
    return pages, skipped


def pdf_to_text(path):
    """PDF → 다단 정렬 + 머리말 제거 + 문장 reflow 된 본문. 반환: (text, skipped_pages)"""
    pages, skipped = pdf_to_pages(path)
    lines = reflowlib.separate_footnotes(reflowlib.strip_page_furniture(pages))
    return reflowlib.reflow("\n".join(lines)), skipped
