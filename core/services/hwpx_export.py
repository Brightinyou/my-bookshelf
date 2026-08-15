"""위키 노트(마크다운) → 한글(HWPX) 내보내기 (2026-08-09).

DOCX(docx_export.py)와 나란히, 한글 프로그램 사용자를 위해 같은 내용을 편집 가능한
.hwpx 문서로 저장한다. python-hwpx만 사용(Apache-2.0, 순수 파이썬).

python-docx와 달리 동아시아 폰트 폴백 문제가 없다(HWPX는 애초에 한글 워드프로세서
포맷이라 기본 스타일 폰트가 전부 한글 대응 폰트). docx_export.py의 폰트 처리
(_set_ea_font/_add_font_fallback_chain)에 대응하는 코드가 없는 건 그래서다."""
from __future__ import annotations

import json
import re
import tempfile
import shutil
from pathlib import Path

import config as cfg

# 새 문단은 항상 이 스타일 + inherit_style=False로 만든다. inherit_style=True(기본값)면
# 직전 문단(특히 헤딩)의 개요/번호 매김 속성까지 paraPr로 복사돼, 본문 문단이 헤딩의
# 목록 번호를 이어받는 문제가 생긴다(실측 확인됨) — 명시적으로 끊어야 한다.
_BODY_STYLE = "바탕글"

# 문단 사이 간격(pt) — 기본 템플릿의 "바탕글"/"개요 N" 모두 spacing after=0이라
# 문단이 다닥다닥 붙어 보인다(실측 확인, 2026-08-09 사용자 피드백). 문단마다 직접 지정한다.
_PARA_SPACING_PT = 6.0

# 본문 기본 글자 크기(pt) — "바탕글"의 기본값(height=1000=10pt)과 동일하게 명시한다.
# add_run(bold=True)처럼 size를 안 주면 python-hwpx의 ensure_run이 크기 무관하게
# 처음 만든 bold=True 스타일(제목용 20pt)을 재사용해버려 굵은 단어·해시태그 줄이
# 전부 제목 크기로 나오는 문제가 실측으로 확인됐다 — 굵게 쓸 때도 항상 size를 명시한다.
_BODY_SIZE_PT = 10

# HWPX 기본 템플릿은 "개요 1"~"개요 10"이 번호매김만 다르고 글자 크기·굵기는
# "바탕글"과 동일하다(char_pr_id_ref=0 공유, 실측 확인) — DOCX의 Heading 스타일과
# 달리 시각적으로 구분이 안 된다. 레벨별 크기+굵게를 직접 지정해 위계를 준다.
_TITLE_SIZE_PT = 20
_HEADING_SIZES_PT = {1: 17, 2: 15, 3: 13, 4: 12, 5: 12, 6: 12}

# 이모지·픽토그램 — HWP 기본 글꼴은 컬러 이모지 글리프가 없어 흑백 대체 글리프로
# 조악하게 나온다(실측 확인, 2026-08-09 피드백: "이모티콘도 성의없고"). Word는
# 시스템 이모지 폰트로 자연스럽게 나오지만 HWPX는 아니므로, 여기서는 아예 뺀다.
_VARIATION_SELECTOR_16 = chr(0xFE0F)  # 이모지 표시 강제 선택자 — 별도 escape로 명시
_EMOJI_RE = re.compile(
    "[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\U00002600-\U000027BF]+"
    "|" + _VARIATION_SELECTOR_16
)


def _strip_emoji(text: str) -> str:
    return re.sub(r"[ \t]{2,}", " ", _EMOJI_RE.sub("", text)).strip()


def set_hwpx_dir(path_str: str) -> None:
    """~/.config/mybookshelf/config.json의 dirs.hwpx 갱신 — 앱 재시작 후 적용.
    (docx_export.set_docx_dir과 동일한 방식.)"""
    f = cfg.CONFIG_FILE
    try:
        d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except Exception:
        d = {}
    d.setdefault("dirs", {})["hwpx"] = path_str
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _new_paragraph(doc):
    return doc.add_paragraph(text="", include_run=False, style=_BODY_STYLE, inherit_style=False)


def _apply_spacing(doc, **extra) -> None:
    """방금 추가한 문단(마지막 문단)에 문단 간격을 적용. extra로 들여쓰기 등 추가 지정 가능."""
    idx = len(doc.paragraphs) - 1
    doc.styles.apply_paragraph_format(paragraph_index=idx, spacing_after_pt=_PARA_SPACING_PT, **extra)


def _add_inline(paragraph, text: str) -> None:
    """**굵게** 정도만 처리한 인라인 런 추가."""
    for seg in re.split(r"(\*\*[^*]+\*\*)", text):
        if not seg:
            continue
        if seg.startswith("**") and seg.endswith("**"):
            paragraph.add_run(seg[2:-2], bold=True, size=_BODY_SIZE_PT)
        else:
            paragraph.add_run(seg)


def note_md_to_hwpx(md: str, out_path: Path, *, meta: dict | None = None) -> Path:
    """마크다운 노트 문자열을 .hwpx로 변환해 out_path에 저장."""
    import hwpx

    doc = hwpx.HwpxDocument.new()
    # 헤딩용 굵게+큰 글자 스타일을 미리 만들어 둔다 — "개요 N" 스타일 자체는
    # 번호매김만 다르고 글자 서식은 바탕글과 같아서(실측 확인) 직접 지정해야 한다.
    _heading_chars = {lv: doc.styles.ensure_run(bold=True, size=sz) for lv, sz in _HEADING_SIZES_PT.items()}

    # ── frontmatter 분리 → 제목·서지 헤더 (docx_export.note_md_to_docx와 동일 로직) ──
    body = md
    fm: dict[str, str] = {}
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", md, re.S)
    if m:
        for line in m.group(1).splitlines():
            mm = re.match(r"^(\w+):\s*(.*)$", line)
            if mm:
                fm[mm.group(1)] = mm.group(2).strip().strip('"')
        body = m.group(2)
    fm.update(meta or {})
    body = _strip_emoji(body)

    title = _strip_emoji(fm.get("title") or (meta or {}).get("title") or "")
    if title:
        # add_heading()이 아니라 일반 문단 + 큰 굵은 글자로 — add_heading을 쓰면 본문의
        # 첫 "# " 헤딩(레벨 1)과 개요 번호를 공유해 "1. 제목" 다음이 "2. 첫 헤딩"으로
        # 어긋난다(실측 확인). 제목은 번호 없이 크게만 보이면 된다.
        _p = _new_paragraph(doc)
        _p.add_run(title, bold=True, size=_TITLE_SIZE_PT)
        _apply_spacing(doc, spacing_before_pt=4.0)
    _bib = " · ".join(
        _strip_emoji(x) for x in [fm.get("author", ""), fm.get("published", ""), fm.get("publisher", "")] if x
    )
    if _bib:
        _p = _new_paragraph(doc)
        _p.add_run(_bib, italic=True, size=10)
        _apply_spacing(doc)

    # ── 본문 라인 단위 변환 ──
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1
            continue
        # 표(| ... |) — 연속 파이프 줄 묶기 (구분선 |---| 은 건너뜀)
        if ln.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not re.match(r"^\s*:?-{2,}", cells[0] if cells else ""):
                    rows.append(cells)
                i += 1
            if rows:
                ncol = max(len(r) for r in rows)
                tbl = doc.add_table(len(rows), ncol)
                for r_idx, r in enumerate(rows):
                    for c_idx in range(ncol):
                        tbl.set_cell_text(r_idx, c_idx, r[c_idx] if c_idx < len(r) else "")
            continue
        # 헤딩 (HWPX 개요는 1~10수준 — 마크다운 최대 6과 그대로 맞음)
        h = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if h:
            _lvl = len(h.group(1))
            doc.add_heading(h.group(2), level=_lvl, char_pr_id_ref=_heading_chars[_lvl])
            _apply_spacing(doc, spacing_before_pt=10.0)
            i += 1
            continue
        # 인용 — 왼쪽 들여쓰기로 구분 (HWPX엔 Word의 Intense Quote 같은 내장 스타일 없음)
        if ln.lstrip().startswith(">"):
            _p = _new_paragraph(doc)
            _add_inline(_p, ln.lstrip()[1:].strip())
            _apply_spacing(doc, indent_left_mm=8.0)
            i += 1
            continue
        # 키워드 해시태그 줄 (#키워드 — 해설)
        if ln.lstrip().startswith("#") and not ln.lstrip().startswith("##"):
            _p = _new_paragraph(doc)
            _p.add_run(ln.strip(), bold=True, size=_BODY_SIZE_PT)
            _apply_spacing(doc)
            i += 1
            continue
        # 불릿
        if re.match(r"^\s*[-*]\s+", ln):
            _p = _new_paragraph(doc)
            _add_inline(_p, re.sub(r"^\s*[-*]\s+", "", ln))
            _idx = len(doc.paragraphs) - 1
            doc.styles.apply_list_format(paragraph_index=_idx, kind="bullet")
            _apply_spacing(doc)
            i += 1
            continue
        # 일반 문단
        _p = _new_paragraph(doc)
        _add_inline(_p, ln)
        _apply_spacing(doc)
        i += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save_to_path(str(out_path))
    return out_path


def build_hwpx_from_chapter_summaries(ws_name: str, stem: str, out_dir: Path) -> tuple[bool, str]:
    """챕터 요약 → 허브 노트(임시 생성) → .hwpx. (ok, path or msg)."""
    from services.wiki import build_wiki_from_chapter_summaries
    from services.docx_export import _safe_name

    tmp = Path(tempfile.mkdtemp(prefix="mb_hwpx_"))
    try:
        ok, msg = build_wiki_from_chapter_summaries(ws_name, stem, wiki_dir=tmp)
        if not ok:
            return False, msg
        md_path = Path(msg)
        if not md_path.exists():
            return False, "노트 생성 실패"
        md = md_path.read_text(encoding="utf-8")
        out_path = out_dir / (_safe_name(stem) + ".hwpx")
        note_md_to_hwpx(md, out_path)
        return True, str(out_path)
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:150]}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
