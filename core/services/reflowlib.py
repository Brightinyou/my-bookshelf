# -*- coding: utf-8 -*-
"""추출 텍스트 후처리: 반복 머리말/쪽번호/세로텍스트 제거 + 문장 reflow.
pdfcols(좌표 추출)와 pdftotext 폴백 양쪽에서 공용으로 쓴다."""
import re
import statistics
from collections import Counter

_HANGUL = re.compile(r"[가-힣]")

# 페이지 경계 표시(사설영역 문자, 실제 문서에 나올 일이 없다). reflow()의 strip()에
# 삼켜지지 않도록 공백이 아닌 문자를 쓰고, reflow 마지막에 실제 \f로 치환한다 —
# 장분할(toc.py)이 원본 쪽 번호를 문자 위치로 되짚는 데 \f를 쓰기 때문 (2026-08-09).
_PAGE_MARK = ""


# ── 홀로 선 제목 살리기 (2026-08-26) ─────────────────────────────────────
# reflow()는 빈 줄로만 문단을 나눈다. 그런데 PDF 텍스트층에는 제목 앞뒤에 빈 줄이
# 없어서, 제 줄에 선 제목이 앞 문단에 먹힌다. 실제로 Dorobantu 논문의 `Conclusion`이
# "...I am strong.”36 Conclusion Although AI..." 로 뭉개졌고, 그래서 장 분할이
# 결론 장을 통째로 놓쳤다(2026-08-25 확인).
#
# ★라틴문자에만 적용한다. 한글은 어절 경계 줄바꿈이 흔해 짧은 줄이 널려 있고,
# 스캔 한글책은 텍스트층 자체가 못 쓸 것이라 이 경로로 오지도 않는다
# (한글 스캔본은 ai_ocr → footnotes.reflow_pages 라는 다른 경로).
#
# 영문 9편 실측(2026-08-26, strip_page_furniture 뒤): 후보 51개 중 48개가 진짜
# 제목(94%). 오탐 3개가 전부 앞붙이·참고문헌이라 아래 두 정규식으로 막는다.
_FOOTNOTE_TAIL = re.compile(r'([.?!”"’\'])\d{1,3}\s*$')   # …strong.”36 → …strong.”
_CLOSERS = ('.', '?', '!', '”', '"', '’', ':')
# 앞붙이 상투어 — 'Keywords Moral consideration', 'Cover Design: LUCAS Art & Design'
_FRONT_MATTER = re.compile(r"^(Keywords?|Cover|DOI|ISBN|ISSN|Copyright|Editors?|Translated)\b", re.I)
# 인용 조각 — 'Technol. 33, 705–715 (2020)'
_CITATIONISH = re.compile(r"\(\d{4}\)|\d+\s*[–-]\s*\d+|^\S+\.\s*\d")


def _is_latin_heading(s: str, prev: str, nxt: str, med: float) -> bool:
    """이 줄이 홀로 선 라틴문자 제목인가 — 문단에 합치지 말아야 하는가."""
    if _HANGUL.search(s):
        return False
    if not (2 <= len(s) <= med * 0.55):
        return False
    if s.rstrip().endswith(('.', ',', ';', ':')):
        return False
    if not s[:1].isupper():
        return False
    if not (nxt[:1].isupper() or nxt[:1].isdigit()):
        return False
    if _FRONT_MATTER.match(s) or _CITATIONISH.search(s):
        return False
    # 앞줄이 문장으로 닫혀 있어야 한다. 각주 번호가 붙어 있으면 걷어내고 본다.
    return _FOOTNOTE_TAIL.sub(r"\1", prev).rstrip().endswith(_CLOSERS)


def strip_page_furniture(pages):
    """반복 머리말/꼬리말·쪽번호·세로(회전) 텍스트를 제거한 라인 리스트.
    페이지 경계마다 _PAGE_MARK를 심어 이후 reflow에서도 원본 쪽 경계가 살아남게 한다."""
    # 1) 페이지 가장자리에서 반복되는 머리말/꼬리말 수집
    edges = Counter()
    for pg in pages:
        ne = [l.strip() for l in pg.split("\n") if l.strip()]
        for l in ne[:2] + ne[-2:]:
            edges[l] += 1
    thr = max(3, len(pages) // 2)
    repeated = {l for l, n in edges.items() if n >= thr and len(l) < 90}

    flat = []
    for pg in pages:
        flat.extend(pg.split("\n"))

    # 2) 전체 스트림에서 다시 드러난 반복 줄 집계(컬럼분리·회전으로 조각난 것 포함)
    freq = Counter(l.strip() for l in flat if l.strip())

    out = []
    seen = set()   # 반복 콘텐츠 줄은 '첫 등장만' 유지 → 제목/저자가 러닝헤더로도
                   # 반복될 때, 첫 페이지의 진짜 제목은 살리고 이후 헤더만 제거한다.
    for pi, pg in enumerate(pages):
        for l in pg.split("\n"):
            s = l.strip()
            if not s:
                out.append("")
                continue
            if re.fullmatch(r"\d{1,4}", s):                 # 단독 쪽번호 → 항상 제거
                continue
            if _is_vertical_noise(s):                       # 세로(회전) 텍스트 흔적
                continue
            if (s in repeated) or (len(s) < 90 and freq[s] >= 3):
                if s in seen:
                    continue                                # 두 번째 이후 = 러닝헤더/꼬리말
                seen.add(s)                                 # 첫 등장 = 실제 콘텐츠로 유지
            out.append(l)
        if pi < len(pages) - 1:
            out.append(_PAGE_MARK)
    return out


# ── 쪽 아래 각주 떼어 내기 (2026-08-26) ────────────────────────────────
# PDF 각주는 쪽 아래에 번호 순으로 모여 있는데, 그 줄들 사이에 빈 줄이 없어서
# reflow가 앞 본문 문단에 통째로 이어 붙였다. 그래서 EPUB 각주 변환기가 「연속 번호가
# 늘어선 묶음」을 못 찾았다 — 각주 40개짜리 논문에서 7개만 문단으로 남았고, 그나마
# '3 Psalm 8:4. 4 Genesis 1:26.' 처럼 둘이 한 문단에 뭉쳐 있었다.
#
# 규칙은 판면 구조를 그대로 쓴다: **쪽 끝에서 번호가 커지며 이어지는 줄들**이 각주다.
# 본문 한가운데의 숫자 시작 줄은 이 조건에 안 걸린다.
_FN_START = re.compile(r"^\s*(\d{1,3})[\s.)]")


def _footnote_block_start(rows: list[str]) -> int | None:
    """이 쪽에서 각주 묶음이 시작되는 줄 번호. 없으면 None.

    쪽 안의 '번호로 시작하는 줄'을 모아, **끝까지 이어지며 번호가 커지는 구간**을
    찾는다. 마지막 각주가 쪽 끝 가까이 있어야 한다 — 그래야 판면 아래의 각주다."""
    marks = [(i, int(m.group(1)))
             for i, r in enumerate(rows)
             if (m := _FN_START.match(r)) and len(r.strip()) <= 300]
    if not marks:
        return None
    # 마지막 각주가 쪽 끝에서 너무 멀면 본문 속 숫자다
    if marks[-1][0] < len(rows) * 0.4:
        return None
    start = len(marks) - 1
    while start > 0 and marks[start - 1][1] < marks[start][1]:
        start -= 1
    return marks[start][0]


def separate_footnotes(lines: list[str]) -> list[str]:
    """각주 줄 앞에 빈 줄을 넣어 **제 문단으로** 서게 한다.

    strip_page_furniture 가 심어 둔 쪽 경계(_PAGE_MARK)로 쪽을 가른 뒤 쪽마다 본다."""
    # ★라틴 문서에만 건다 (2026-08-26 실측). 한글 책에 그대로 걸었더니 문단이
    # 2→259, 4→123 으로 터졌다 — 번호 매김 목록·쪽 아래 잔줄이 죄다 각주로 잡힌다.
    # 한글 스캔본은 원래 ai_ocr → footnotes.reflow_pages 라는 다른 경로에서 각주를
    # 다루므로 여기서 손댈 이유도 없다. 한글용 규칙은 실측한 뒤에 따로 넣는다.
    _joined = "\n".join(lines)
    if _joined and len(_HANGUL.findall(_joined)) / len(_joined) > 0.15:
        return list(lines)
    out: list[str] = []
    seg: list[str] = []

    def _flush(seg: list[str]) -> None:
        rows = [r for r in seg if r.strip()]
        s = _footnote_block_start(rows) if rows else None
        if s is None:
            out.extend(seg)
            return
        # rows 는 빈 줄을 뺀 목록이라, seg 안에서 몇 번째 줄인지 되짚는다
        # (값이 같은 줄이 있을 수 있어 identity 로 찾으면 안 된다).
        nth, begin = 0, len(seg)
        for i, r in enumerate(seg):
            if r.strip():
                if nth == s:
                    begin = i
                    break
                nth += 1
        for i, r in enumerate(seg):
            if i >= begin and _FN_START.match(r):
                out.append("")            # 각주마다 제 문단으로
            out.append(r)

    for l in lines:
        if l.strip() == _PAGE_MARK:
            _flush(seg)
            out.append(l)
            seg = []
        else:
            seg.append(l)
    _flush(seg)
    return out


def _is_vertical_noise(s: str) -> bool:
    """회전된 세로 텍스트는 글자마다 공백이 낀
    'V o l . : ( 0 1 2 )' 또는 한 글자짜리 줄로 나오는 경향이 있다."""
    toks = s.split()
    if len(toks) >= 6 and sum(len(t) for t in toks) / len(toks) <= 1.3:
        return True
    return False


def reflow(text: str) -> str:
    """물리적 줄바꿈을 문장/문단 단위로 재결합.

    ★홀로 선 라틴문자 제목은 합치지 않고 제 문단으로 남긴다(_is_latin_heading 참고).
    합쳐 버리면 장 분할이 그 절을 영영 못 찾는다."""
    all_rows = [r.strip() for r in text.split("\n")
                if r.strip() and r.strip() != _PAGE_MARK]
    med = statistics.median([len(r) for r in all_rows]) if all_rows else 0.0
    # ★제목 규칙은 **문서 단위로 라틴 문서에만** 건다 (2026-08-26).
    # 줄 단위로만 걸었더니 한글 책의 판권지·표에서 라틴 조각이 걸려 나왔다
    # ('OmtKiolagy fora', 'In progress'). 글자가 상하지는 않지만 근거 없는 분리다.
    # 한글 문서용 규칙(번호 매김·종결어미)은 아직 없으므로 있을 때까지는 예전
    # 동작 그대로 둔다 — 안 건드리는 것이 가장 안전하다.
    if len(_HANGUL.findall(text)) / max(1, len(text)) > 0.15:
        med = 0.0
    paras = re.split(r"\n[ \t]*\n", text)
    out = []
    for para in paras:
        rows = [r.strip() for r in para.split("\n") if r.strip()]
        if not rows:
            continue
        buf = ""
        for i, row in enumerate(rows):
            # 문단 한가운데 홀로 선 제목이면 여기서 끊는다. 문단 첫/끝 줄은 이미
            # 경계에 있으므로 볼 필요가 없다.
            if med and 0 < i < len(rows) - 1 and row != _PAGE_MARK:
                prev = next((rows[j] for j in range(i - 1, -1, -1)
                             if rows[j] != _PAGE_MARK), "")
                nxt = next((rows[j] for j in range(i + 1, len(rows))
                            if rows[j] != _PAGE_MARK), "")
                if prev and nxt and _is_latin_heading(row, prev, nxt, med):
                    if buf:
                        out.append(buf)
                        buf = ""
                    out.append(row)                     # 제목은 제 문단으로 남긴다
                    continue
            if not buf:
                buf = row
                continue
            prev_ch, nxt_ch = buf[-1], row[0]
            if prev_ch == "-":
                if nxt_ch.islower():                    # coop-\neration → cooperation
                    buf = buf[:-1] + row
                else:                                   # High-\nLevel → High-Level
                    buf += row
            else:
                # 한글 포함 모든 스크립트: 공백 결합이 가장 안전.
                # (한글은 어절 경계 줄바꿈이 흔해 붙이면 단어가 뭉친다)
                buf += " " + row
        if buf:
            out.append(buf)
    return "\n\n".join(out).replace(_PAGE_MARK, "\f")


def clean_default_text(raw: str) -> str:
    """폼피드(\\f)로 페이지가 나뉜 raw 텍스트 → 정리된 본문 (pdftotext 폴백용)."""
    pages = raw.split("\f")
    lines = separate_footnotes(strip_page_furniture(pages))
    return reflow("\n".join(lines))
