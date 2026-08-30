"""장별 분할·합치기·요약 — chapters/<책>/ 폴더 단위 처리."""

import json
import re as _re
from datetime import date
from pathlib import Path

import config as cfg
import llm_providers as llm

from services.common import TXT_SUB, _nfc, append_log
from services.files import find_md, find_txt, txt_dir
from services.translate import DERIVED_SUFFIXES as _DERIVED, find_translation
from services import note_i18n as NI   # 노트 구획 제목(언어별) — 2026-08-31
from services.translate import _split_paragraphs_robust

DONE_DIR = cfg.DONE_DIR


# ─── 챕터 요약 파일 (_wiki.md — 2026-07-03 JSON→MD 전환) ──────────
# LLM 출력은 complete_json으로 형식을 강제하되, 디스크에는 사람이 읽고
# 위키반영 전에 손으로 고칠 수 있는 고정 형식 MD로 저장한다.
# 구형 _wiki.json은 읽기 폴백으로만 지원 (재요약 시 삭제).

_SUMMARY_PREFIX = "> **요약:**"          # 하위 호환용 (직접 비교하지 말 것)


def _author_from_stem(stem: str) -> str:
    """파일명 '제목_저자(_)' 규약에서 저자 추출 — 숫자 포함·과길이면 저자 아님으로 본다."""
    parts = [p.strip() for p in stem.split("_") if p.strip()]
    if len(parts) >= 2:
        last = parts[-1]
        if 1 < len(last) <= 25 and not _re.search(r"\d", last):
            return last
    return ""


def _format_summary_md(book: str, chapter: str, summary: str, body: str, author: str = "") -> str:
    model = llm.effective_wiki_model()
    one_line = " ".join((summary or "").split())
    return (
        "---\n"
        f"book: {book}\n"
        + (f"author: {author}\n" if author else "")
        + f"chapter: {chapter}\n"
        f"model: {model}\n"
        f"generated: {date.today().isoformat()}\n"
        "---\n"
        f"{NI.summary_prefix()} {one_line}\n\n"
        f"{(body or '').strip()}\n"
    )


def parse_summary_md(text: str) -> tuple[str, str]:
    """고정 형식 _wiki.md → (summary, body). 손으로 수정된 파일도 관대하게 파싱:
    요약 줄이 없으면 summary=''이고 전체가 body가 된다."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    lines = text.lstrip("\n").splitlines()
    summary = ""
    body_start = 0
    for i, ln in enumerate(lines):
        _pfx = next((p for p in NI.summary_prefixes() if ln.strip().startswith(p)), "")
        if _pfx:
            summary = ln.strip()[len(_pfx):].strip()
            body_start = i + 1
            break
    body = "\n".join(lines[body_start:]).strip()
    return summary, body


def load_summary_file(path: Path) -> dict | None:
    """요약 파일(_wiki.md 또는 구형 _wiki.json) → {"summary","body"}. 실패 시 None."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix.lower() == ".json":
            d = json.loads(text)
            return d if isinstance(d, dict) else None
        summary, body = parse_summary_md(text)
        if not (summary or body):
            return None
        return {"summary": summary, "body": body}
    except Exception:
        return None


def summary_file_for(ch_path: Path) -> Path | None:
    """챕터 TXT에 대응하는 요약 파일 — _wiki.md 우선, 구형 _wiki.json 폴백."""
    md = ch_path.with_name(ch_path.stem + "_wiki.md")
    if md.exists():
        return md
    js = ch_path.with_name(ch_path.stem + "_wiki.json")
    return js if js.exists() else None


def list_summary_files(ch_dir: Path) -> list[Path]:
    """책 챕터 폴더의 요약 파일 목록 — 같은 챕터는 _wiki.md가 구형 json을 대체."""
    if not ch_dir.exists():
        return []
    by_stem: dict[str, Path] = {}
    for f in ch_dir.glob("*_wiki.json"):
        by_stem[f.stem] = f
    for f in ch_dir.glob("*_wiki.md"):
        by_stem[f.stem] = f
    return [by_stem[k] for k in sorted(by_stem)]


def chapters_dir(ws_name: str, stem: str) -> Path:
    """v0.9.0: 단일 트리 — ws 인자는 호환용."""
    return cfg.CHAPTERS_DIR / stem


# 파일 이름에 쓸 수 없는 글자. 콜론이 가장 흔하다 — 한국 학술서 제목은 대개
# `주제: 부제` 꼴이라 거의 모든 장 제목에 들어 있다.
_ILLEGAL = _re.compile(r'[/\\:*?"<>|]')
_SPACES = _re.compile(r"\s{2,}")

# 제목이 쓸 수 있는 UTF-8 바이트. 파일 이름 한도(255바이트)에서 순번 `NN_`(3)과
# 가장 긴 접미사 `_bilingual.txt`(14), 그리고 여유를 뺀 값이다.
# ★옛 값은 **50자**였는데 너무 짧았다 — 한글 52자짜리 제목(130바이트)이 잘려
# `…지역 가치로서 ‘` 로 끝나 연구자가 넣은 낱말이 사라졌다(2026-08-25).
MAX_TITLE_BYTES = 180


def _pair_quotes(title: str) -> str:
    """곧은 큰따옴표를 여는/닫는 둥근 따옴표로 짝지어 바꾼다."""
    out, opening = [], True
    for ch in title:
        if ch == '"':
            out.append("\u201c" if opening else "\u201d")
            opening = not opening
        else:
            out.append(ch)
    return "".join(out)


def _cut_bytes(s: str, limit: int) -> str:
    """UTF-8 바이트로 잘라 낸다 — **낱말 한복판에서 자르지 않는다.**

    글자 수로 재면 한글(3바이트)과 영문(1바이트)이 뒤섞인 제목에서 한도를 못 맞춘다."""
    if len(s.encode("utf-8")) <= limit:
        return s
    cut = s.encode("utf-8")[:limit].decode("utf-8", "ignore")
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > limit // 3 else cut).rstrip()


def safe_title(title: str) -> str:
    """제목을 파일 이름으로 쓸 수 있게 다듬는다.

    ★**쓸 수 없는 글자는 지우지 않고 `-`로 바꾼다**(연구자 요청, 2026-08-25).
    예전에는 공백으로 바꿔서 `과제와 전망: 인간과`가 `과제와 전망  인간과`가 됐다 —
    부제가 붙은 자리인지 알 수 없게 되고 공백만 뭉친다. `-`로 두면 원래 제목의
    구조가 남는다: `과제와 전망 - 인간과`."""
    # ★바꾼 자리에만 여백을 준다. `-`로만 바꾸면 `전망-인간과`처럼 붙고, 그렇다고
    # 하이픈 전체를 손보면 **원래 제목에 있던 하이픈까지 망가진다**
    # (`co-evolution` → `co - evolution`).
    # ★곧은 큰따옴표만은 `-`로 바꾸면 흉하다(`"정"` → `- 정 -`). 파일 이름에 쓸 수
    # 있는 **둥근 따옴표로 짝지어** 바꾼다 — 뜻이 그대로 남는다. 곧은 작은따옴표(`'`)는
    # 파일 이름에 써도 되므로 손대지 않는다(윈도우 `explorer /select,"…"`에서도
    # 큰따옴표 안이라 안전하다).
    t = _pair_quotes(title)
    t = _ILLEGAL.sub(" - ", t)
    t = _SPACES.sub(" ", t).strip()
    return _cut_bytes(t, MAX_TITLE_BYTES).strip(" .,:-") or "제목없음"


def _single_chapter_name(stem: str) -> str:
    return f"01_{safe_title(stem)}.txt"


def _is_small_document_for_whole_translation(text: str) -> bool:
    sample = (text or "").strip()
    if not sample:
        return False
    paragraphs = _split_paragraphs_robust(sample, target_chunk=1800, min_para=4)
    return len(sample) <= 120_000 and len(paragraphs) <= 14


def _write_single_chapter_from_text(ws_name: str, stem: str, text: str) -> tuple[Path, bool]:
    ch_dir = chapters_dir(ws_name, stem)
    ch_dir.mkdir(parents=True, exist_ok=True)
    for old in ch_dir.glob("*"):
        if old.is_file():
            try:
                old.unlink()
            except Exception:
                pass
    ch_path = ch_dir / _single_chapter_name(stem)
    ch_path.write_text(text, encoding="utf-8")
    return ch_path, True


def list_done_books() -> list[tuple[str, str, Path]]:
    """(ws, stem, txt_path) — v0.9.0 TXT 폴더의 모든 책 TXT."""
    books: list[tuple[str, str, Path]] = []
    seen: set[str] = set()
    for root in (cfg.TXT_DIR, cfg.TXT_ARCHIVE_DIR):
        if not root.exists():
            continue
        for txt in sorted(root.glob("*.txt")):
            s = _nfc(txt.stem)
            if s not in seen:
                books.append((cfg.WORKSPACES[0], s, txt)); seen.add(s)

    legacy_done = cfg.LEGACY_DONE_DIR
    if legacy_done.exists():
        for ws_dir in sorted(legacy_done.iterdir()):
            if not ws_dir.is_dir() or ws_dir.name.startswith("_"):
                continue
            txt_sub = ws_dir / TXT_SUB
            if txt_sub.exists():
                for txt in sorted(txt_sub.glob("*.txt")):
                    s = _nfc(txt.stem)
                    if s not in seen:
                        books.append((ws_dir.name, s, txt)); seen.add(s)
    return books


# 분할 방식 표시용 라벨 — visual/llm은 설정된 AI 모델을 소비한다 (2026-07-07)
SPLIT_MODE_LABELS = {
    "bookmark": "📑 PDF 북마크",
    "visual":   "🤖 AI 시각판독",
    "heading":  "패턴(MD 헤딩)",
    "toc":      "패턴(목차 복원)",
    "numbered": "패턴(번호 헤딩)",
    "llm":      "🤖 AI 텍스트판정",
    "single":   "단일 본문",
}


# 마지막 분할의 커버리지 경고 {stem: 사람이 읽는 문구} — UI가 성공 메시지에 덧붙인다.
# 로그에만 남기면 사용자는 본문이 빠진 줄 모르고 번역·요약·EPUB까지 그대로 진행한다
# (2026-08-17, 서론이 통째로 빠진 EPUB이 그렇게 만들어졌다).
LAST_SPLIT_WARNING: dict[str, str] = {}


# 챕터 파생물 접미사 — 원문 챕터 TXT 하나에서 파생되는 파일들 (번역·진행·위키)
# 번역본 접미사는 도착언어를 따르므로(2026-08-26) 알려진 언어를 모두 편다.
_CHAPTER_DERIVED_SUFFIXES = (
    (".txt", "_wiki.md", "_wiki.json")
    + tuple(f"{_s}.txt" for _s in _DERIVED)
    + tuple(f"{_s}.partial.md" for _s in _DERIVED)
    + tuple(f"{_s}.progress.json" for _s in _DERIVED)
)


_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}

# 전각 로마숫자(Ⅰ~Ⅹ) → 반각. OCR 텍스트에 섞여 나온다.
_FW_ROMAN_MAP = str.maketrans({
    "Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV", "Ⅴ": "V",
    "Ⅵ": "VI", "Ⅶ": "VII", "Ⅷ": "VIII", "Ⅸ": "IX", "Ⅹ": "X",
})


def _roman_to_int(s: str) -> int | None:
    total = prev = 0
    for ch in reversed(s.upper()):
        v = _ROMAN_VALUES.get(ch)
        if v is None:
            return None
        total += -v if v < prev else v
        prev = max(prev, v)
    return total or None


def strip_redundant_number(title: str, n: int) -> str:
    """장 제목 앞의 번호가 파일 순번과 같으면 떼어낸다 (2026-08-17).

    파일 이름은 `01_제목.txt` 꼴이고 순번(01)은 정렬·목록 조회에 쓰이므로 남긴다.
    그런데 분할기들이 제목에도 번호를 붙여 와서(`toc_split`의 `f"{num}. {text}"` 등)
    `01_1. 1장.txt`처럼 같은 숫자가 세 번 반복됐다. 순번과 **같은 번호일 때만** 떼며,
    떼고 나서 남는 게 없으면 원래 제목을 그대로 둔다(`1.` → 그대로).
    로마숫자(`I.`·전각 `Ⅰ.`)와 `1장 서론` 꼴도 같은 기준으로 처리하고,
    `1. 1. 성서와 철학`처럼 두 겹으로 붙은 경우까지 반복해서 벗긴다.
    번호가 순번과 다르면(`04_4. 7. Study 5`의 `7.`) 책의 실제 절 번호이므로 남긴다."""
    t = title.strip()
    for _ in range(3):
        base = t
        t = t.translate(_FW_ROMAN_MAP)
        for pat, conv in (
            (r"^(\d{1,3})\s*[.):]\s*(.+)$", int),                 # "1. 제목"
            (r"^(\d{1,3})\s+(\S.*)$", int),                       # "1 제목"
            (r"^([IVXLCivxlc]{1,6})\s*[.):]\s*(.+)$", _roman_to_int),   # "I. 제목"
            (r"^제?\s*(\d{1,3})\s*장\s*[.:)]?\s+(.+)$", int),      # "1장 제목"
        ):
            m = _re.match(pat, t)
            if m:
                try:
                    val = conv(m.group(1))
                except Exception:
                    val = None
                if val == n:
                    t = m.group(2).strip()
                    break
        if t == base:
            break
    return t or title.strip()


def _chapter_stem_of(name: str) -> str | None:
    """챕터 파일 이름에서 원문 챕터 stem을 되찾는다. 챕터 파생물이 아니면 None."""
    if not _re.match(r"^\d{2}_", name):
        return None
    for suf in sorted(_CHAPTER_DERIVED_SUFFIXES, key=len, reverse=True):
        if name.endswith(suf):
            return name[: -len(suf)]
    return None


def _purge_stale_chapter_files(ch_dir: Path, new_stems: set[str],
                                changed_stems: set[str] | None = None) -> None:
    """이전 분할이 남긴 챕터 파일 정리.

    두 가지를 지운다 (2026-08-17):
    1. 이번 분할이 만들지 않은 챕터 stem의 파일 전부 — 재분할로 장 번호가 밀리면
       (예: 서론이 복구돼 01_II→02_II) 옛 파일이 남아 같은 장이 두 벌씩 잡히고
       EPUB·위키에 중복 장이 실린다.
    2. 이름은 같지만 본문이 바뀐 장(changed_stems)의 **파생물**(번역본·요약) —
       옛 본문으로 만든 요약이 새 본문 옆에 남으면 내용이 어긋난다.
    전체요약처럼 챕터 파생물이 아닌 파일은 여기서 건드리지 않는다."""
    changed_stems = changed_stems or set()
    for f in ch_dir.iterdir():
        if not f.is_file():
            continue
        stem = _chapter_stem_of(f.name)
        if stem is None:
            continue
        if stem in new_stems:
            # 본문이 바뀐 장은 파생물만 버리고 방금 쓴 원문(.txt)은 남긴다
            if not (stem in changed_stems and f.name != f"{stem}.txt"):
                continue
        try:
            f.unlink()
        except Exception:
            pass


def split_book_to_chapters(ws_name: str, stem: str, allow_short: bool = False) -> tuple[int, str, str]:
    """장 분리 실행. 챕터 TXT 파일 저장. (저장 수, 오류 메시지, 분할 방식) 반환."""
    try:
        import chapter_wiki as _cw
    except ImportError:
        return 0, "chapter_wiki 임포트 실패", ""
    txt_p = find_txt(DONE_DIR, ws_name, stem)
    md_p  = find_md(DONE_DIR, ws_name, stem)
    md_text  = md_p.read_text(encoding="utf-8", errors="ignore")  if md_p  else None
    txt_text = txt_p.read_text(encoding="utf-8", errors="ignore") if txt_p else None
    if not md_text and not txt_text:
        return 0, "TXT/MD 파일 없음", ""
    source_text = txt_text or md_text or ""
    if _is_small_document_for_whole_translation(source_text) and not allow_short:
        return 0, "짧은 문서 감지", ""
    # 원본 PDF가 보관돼 있으면 Tier 0(북마크·시각 판독) 경로에 전달
    pdf_p = cfg.PDF_DIR / f"{stem}.pdf"
    if not pdf_p.exists():                       # 마이그레이션 전 안전망
        pdf_p = cfg.LEGACY_DONE_DIR / ws_name / "pdf" / f"{stem}.pdf"
    mode, chapters = _cw.chapter_split(md_text, txt_text,
                                       pdf_path=pdf_p if pdf_p.exists() else None)
    if (mode == "single" or not chapters) and allow_short:
        ch_path, _ = _write_single_chapter_from_text(ws_name, stem, source_text)
        return 1, f"단일장으로 저장됨 → {ch_path.name}", "single"
    if mode == "single" or not chapters:
        return 0, "장 구조 감지 안 됨 — 단일 본문입니다 (기존 위키 생성 탭을 쓰세요)", "single"
    ch_dir = chapters_dir(ws_name, stem)
    ch_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    real_i = 0
    new_stems: set[str] = set()
    changed_stems: set[str] = set()
    _prev_stems = {f.stem for f in ch_dir.glob("??_*.txt")
                   if not f.stem.endswith(_DERIVED)}
    for idx, (title, body) in enumerate(chapters):
        # 자동 생성된 "머리말"(첫 장 표시 이전 본문, _split_at 참고)은 실제 장이 아니므로
        # 01번을 차지하면 안 된다 — 그러면 진짜 1장(Introduction 등)이 02번으로 밀린다.
        # 00번을 따로 줘서 읽는 순서(정렬)는 유지하되 실제 장 번호는 1부터 시작하게
        # 한다(2026-08-12).
        if idx == 0 and title == "머리말":
            prefix = "00"
            disp = title
        else:
            real_i += 1
            prefix = f"{real_i:02d}"
            disp = strip_redundant_number(title, real_i)
        safe = safe_title(disp)
        ch_file = ch_dir / f"{prefix}_{safe}.txt"
        # 같은 이름이라도 내용이 바뀌었으면 그 장의 번역본·요약은 옛 본문의 것이다.
        # 남겨두면 새 본문과 짝이 안 맞는 요약이 위키·EPUB에 실린다 (2026-08-17).
        if ch_file.exists() and ch_file.read_text(encoding="utf-8", errors="ignore") != body:
            changed_stems.add(f"{prefix}_{safe}")
        ch_file.write_text(body, encoding="utf-8")
        new_stems.add(f"{prefix}_{safe}")
        saved += 1
    _purge_stale_chapter_files(ch_dir, new_stems, changed_stems)
    # 장 구성이나 본문이 바뀌었으면 책 전체요약도 옛 챕터로 만든 것이라 버린다
    # — 다음 요약 단계에서 새로 만든다.
    if changed_stems or _prev_stems - new_stems or new_stems - _prev_stems:
        for _ov in list(ch_dir.glob("*_전체요약.md")) + list(ch_dir.glob("*_overview.md")):
            try:
                _ov.unlink()
            except Exception:
                pass
    # 커버리지 자기진단 — 챕터에 담긴 분량이 원문에 크게 못 미치면 유실 의심
    # (각주·러닝헤더 오탐으로 첫 장 이전이 통째로 버려진 사고, 2026-07-08).
    # 기준을 60%→85%로 올린다: 서론 하나(전체의 5%)가 통째로 빠진 사고가 95%
    # 커버리지라 경고 없이 지나갔다 (2026-08-17, chapter_wiki._recover_lead 참고).
    coverage = sum(len(b) for _t, b in chapters) / max(1, len(source_text))
    LAST_SPLIT_WARNING.pop(stem, None)
    # 원본 PDF가 있는데도 차례(북마크·시각) 판독이 아니라 본문 추정으로 나뉜 경우.
    # 이때 나온 장 구분은 자주 엉뚱하다 — 여러 학자의 글을 엮은 책이 목차 12편 대신
    # 4덩어리로 뭉개진 사고(2026-08-17). 본문은 다 담기므로 커버리지로는 안 잡힌다.
    if pdf_p.exists() and mode not in ("bookmark", "visual"):
        LAST_SPLIT_WARNING[stem] = ("PDF 차례를 읽지 못해 본문 추정으로 나눴습니다 — "
                                    "장 구분이 맞는지 확인하세요(기록 파일에 이유가 남습니다)")
        append_log(f"WARN: 장분할이 차례 판독 없이 진행됨 — {stem} (분할={mode})")
    if coverage < 0.85:
        LAST_SPLIT_WARNING[stem] = f"본문의 {coverage:.0%}만 챕터에 담겼습니다 — 앞뒤 일부가 빠졌을 수 있습니다"
        append_log(f"WARN: 장분할 커버리지 {coverage:.0%} — {stem}: 본문 일부가 챕터에 담기지 않았을 수 있음 (분할={mode})")
    # '결론'·'서론'처럼 장 경계가 분명한 제목이 장 안에 홀로 서 있으면 바로 나눈다
    # (2026-08-26). 알려만 주고 사람이 누르게 했더니 번거롭다는 지적을 받았다.
    # 자동으로 나누는 낱말은 chapter_map._BOUNDARY_WORDS 로 못 박아 두었다.
    try:
        from services.chapter_map import auto_split_known_headings
        _auto = auto_split_known_headings(ws_name, stem)
        if _auto:
            append_log(f"장분할: 경계 제목에서 자동으로 나눔 — {stem}: {', '.join(_auto)}")
    except Exception as e:
        append_log(f"WARN: 경계 제목 자동 분할 실패 — {stem} ({type(e).__name__})")
    # 장 지도 기록 — 확인 화면이 이걸 읽고, 사람이 고치면 여기에 남는다 (2026-08-17)
    try:
        from services.chapter_map import save_map
        save_map(ws_name, stem, mode=mode, confirmed=False, source="auto")
    except Exception as e:
        append_log(f"WARN: 장 지도 기록 실패 — {stem} ({type(e).__name__})")
    return saved, "", mode


def _merge_chapter_folder(ws_name: str, stem: str, prefer_ko: bool = False) -> tuple[bool, Path | None, str]:
    """챕터 폴더를 하나의 TXT로 다시 합친다. prefer_ko=True면 각 챕터의 _ko.txt 우선."""
    ch_dir = chapters_dir(ws_name, stem)
    if not ch_dir.exists():
        return False, None, "챕터 폴더 없음"
    chapters = sorted(
        [f for f in ch_dir.glob("??_*.txt") if not f.stem.endswith(_DERIVED)],
        key=lambda p: p.name,
    )
    if not chapters:
        return False, None, "합칠 챕터가 없음"
    out_dir = txt_dir(DONE_DIR, ws_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (f"{stem}__merged_ko.txt" if prefer_ko else f"{stem}__merged.txt")
    parts: list[str] = [f"# {stem}", ""]
    used_ko = 0
    for ch in chapters:
        body_path = (find_translation(ch) or ch) if prefer_ko else ch
        if body_path != ch:
            used_ko += 1
        title = _re.sub(r"^\d+_", "", ch.stem)
        parts += [f"## {title}", body_path.read_text(encoding="utf-8", errors="ignore").strip(), ""]
    out_path.write_text("\n".join(parts).strip() + "\n", encoding="utf-8")
    return True, out_path, f"{len(chapters)}개 챕터 합침" + (f" · 번역본 {used_ko}개 사용" if used_ko else "")


# ─── 책 전체요약 (_overview.md — 2026-07-07) ─────────────────
# 장별 _wiki.md들을 합쳐 책 전체 요약·개요·분류를 생성해 사람이 읽고 고칠 수
# 있는 파일로 저장한다. 위키반영은 이 파일이 있으면 재생성 없이 그대로 쓴다.

def overview_file_for(ws_name: str, stem: str) -> Path:
    """전체요약 파일 경로 — 책 제목 포함 (2026-07-07 개명: _overview.md → <책>_전체요약.md).
    stem은 40자로 잘라 경로 길이 초과(WinError 206) 방지. `*_wiki.md` 글롭과 안 겹침."""
    safe = _re.sub(r'[/\\:*?"<>|]', " ", stem).strip()[:40].strip(" .,:-")
    return chapters_dir(ws_name, stem) / f"{safe or '책'}_전체요약.md"


def find_overview_file(ws_name: str, stem: str) -> Path | None:
    """전체요약 파일 탐색 — 새 이름 우선, 구형 _overview.md 폴백."""
    new = overview_file_for(ws_name, stem)
    if new.exists():
        return new
    legacy = chapters_dir(ws_name, stem) / "_overview.md"
    return legacy if legacy.exists() else None


def load_overview_file(path: Path) -> dict | None:
    """_overview.md → {"category","author","summary","intro"}. 실패 시 None."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        m = _re.search(r"(?m)^category:\s*(.+)$", text[:400])
        category = m.group(1).strip() if m else "기타"
        ma = _re.search(r"(?m)^author:\s*(.+)$", text[:400])
        mm = _re.search(r"(?m)^model:\s*(.+)$", text[:400])
        mp = _re.search(r"(?m)^published:\s*(.+)$", text[:400])
        mpub = _re.search(r"(?m)^publisher:\s*(.+)$", text[:400])
        summary, intro = parse_summary_md(text)
        if not (summary or intro):
            return None
        return {"category": category, "summary": summary, "intro": intro,
                "author": ma.group(1).strip() if ma else "",
                "published_date": mp.group(1).strip().strip('"') if mp else "",
                "publisher": mpub.group(1).strip().strip('"') if mpub else "",
                "model": mm.group(1).strip() if mm else ""}
    except Exception:
        return None


def summarize_book_overview(ws_name: str, stem: str) -> tuple[bool, str]:
    """장별 요약들을 합쳐 책 전체요약 생성 → _overview.md 저장. (ok, msg)."""
    try:
        import chapter_wiki as _cw
    except ImportError:
        return False, "chapter_wiki 임포트 실패"
    ch_dir = chapters_dir(ws_name, stem)
    sections = []
    for i, jf in enumerate(list_summary_files(ch_dir), 1):
        d = load_summary_file(jf)
        if d is None:
            continue
        title = _re.sub(r"^\d+_", "", jf.stem.replace("_wiki", ""))
        sections.append({"idx": i, "title": title, "summary": d.get("summary", "")})
    if not sections:
        return False, "장별 요약 없음 — 챕터 요약을 먼저 실행하세요"
    # 서지 정보(저자·출판사·출판일) 추출용 — 표제지·판권면은 분할 전 '원본 전체 txt'
    # 앞·뒤에 있으므로 그것을 우선 사용하고, 없으면 첫/끝 챕터 txt로 폴백한다.
    head_text = ""
    _orig = None
    try:
        _want = _nfc(stem + ".txt")
        if cfg.TXT_DIR.exists():
            _orig = next((p for p in cfg.TXT_DIR.rglob("*.txt") if _nfc(p.name) == _want), None)
    except Exception:
        _orig = None
    try:
        if _orig is not None:
            _full = _orig.read_text(encoding="utf-8", errors="ignore")
            head_text = (_full[:3500] + "\n…\n" + _full[-1500:]).strip()
        else:
            _txts = [f for f in sorted(ch_dir.glob("??_*.txt")) if not f.stem.endswith(_DERIVED)]
            if _txts:
                _h = _txts[0].read_text(encoding="utf-8", errors="ignore")[:3500]
                _t = _txts[-1].read_text(encoding="utf-8", errors="ignore")[-2000:]
                head_text = (_h + "\n…\n" + _t).strip()
    except Exception:
        head_text = ""
    try:
        ov = _cw.generate_overview(stem, sections, head_text=head_text)
    except Exception as e:
        return False, str(e)[:200]
    summary = " ".join((ov.get("summary") or "").split())
    intro = (ov.get("intro") or "").strip()
    if not (summary or intro):
        return False, "전체요약 응답이 비었습니다"
    model = llm.effective_wiki_model()
    author = (ov.get("author") or "").strip() or _author_from_stem(stem)
    published = (ov.get("published_date") or "").strip()
    publisher = (ov.get("publisher") or "").strip()
    # '#키워드 — 해설' 한 줄씩 — 줄바꿈 보존 (2026-07-09)
    keywords = "\n".join(ln.strip() for ln in (ov.get("keywords") or "").splitlines() if ln.strip())
    out = overview_file_for(ws_name, stem)
    legacy = chapters_dir(ws_name, stem) / "_overview.md"
    if legacy.exists():                # 구형 파일은 새 이름으로 대체
        try:
            legacy.unlink()
        except Exception:
            pass
    out.write_text(
        "---\n"
        f"book: {stem}\n"
        + (f"author: {author}\n" if author else "")
        + f"category: {ov.get('category', '기타')}\n"
        + (f"published: {published}\n" if published else "")
        + (f'publisher: "{publisher.replace(chr(34), chr(39))}"\n' if publisher else "")
        + f"model: {model}\n"
        f"generated: {date.today().isoformat()}\n"
        "---\n"
        f"{NI.summary_prefix()} {summary}\n\n"
        f"{intro}\n"
        + (f"\n{NI.md_heading('keywords')}\n{keywords}\n" if keywords else ""),
        encoding="utf-8",
    )
    return True, summary[:120]


def summarize_one_chapter(ch_path: Path, book_stem: str) -> tuple[bool, str]:
    """단일 챕터 TXT → 요약 생성 후 _wiki.md 저장. (ok, summary snippet)."""
    try:
        import chapter_wiki as _cw
    except ImportError:
        return False, "chapter_wiki 임포트 실패"
    try:
        ko_path = find_translation(ch_path)     # 도착언어 무관 — 있으면 번역본을 요약한다
        src = (ko_path or ch_path).read_text(encoding="utf-8", errors="ignore")
        chap_title = _re.sub(r"^\d+_", "", ch_path.stem)
        data = _cw.generate_chapter(book_stem, chap_title, src)
        if not isinstance(data, dict):
            raise RuntimeError("요약 응답이 JSON 객체가 아님")
        if not (data.get("summary") and data.get("body")):
            keys = ", ".join(sorted(map(str, data.keys()))) or "없음"
            raise RuntimeError(f"요약 응답 필드 부족(summary/body 없음, keys={keys})")
        author = (data.get("author") or "").strip() or _author_from_stem(book_stem)
        (ch_path.with_name(ch_path.stem + "_wiki.md")).write_text(
            _format_summary_md(book_stem, chap_title, data["summary"], data["body"], author),
            encoding="utf-8",
        )
        legacy = ch_path.with_name(ch_path.stem + "_wiki.json")
        if legacy.exists():           # 재요약 시 구형 json 정리 (md가 대체)
            try:
                legacy.unlink()
            except Exception:
                pass
        return True, (data.get("summary") or "")[:120]
    except Exception as e:
        msg = str(e)[:300]
        try:
            append_log(f"ERROR: 장별 요약 실패 - {ch_path.name} ({type(e).__name__}) {msg}")
        except Exception:
            pass
        return False, msg[:200]
