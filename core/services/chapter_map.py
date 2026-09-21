"""장 지도(chapter map) — 분할 결과를 확인·수정하고 그 결과를 남긴다 (2026-08-17).

분할이 조용히 틀리는 사고가 반복됐다. 원인은 분할 알고리즘이 아니라 **결과를
아무도 검사하지 않고 확정한다**는 데 있었다(자세한 내력은 chapter_wiki._recover_lead,
services/toc._toc_skip 주석 참고). 그래서 요약·번역·EPUB으로 넘어가기 전에 사람이
장 목록을 한 번 보고 고칠 수 있게 하고, 고친 결과를 책 폴더에 남긴다.

  3_챕터/<책>/_chapters.json
    {"mode": "visual", "confirmed": true,
     "chapters": [{"n": 1, "title": "서론", "chars": 2153, "source": "user"}]}

수정은 **챕터 파일 자체를 옮기는 방식**이다(문자 위치를 저장해 두었다가 재적용하지
않는다). 파일이 곧 진실이라 다른 단계와 어긋날 여지가 없고, 되돌리기도 파일 단위다.

  · 제목 수정   → 파일 이름만 변경
  · 앞 장에 합치기 → 본문을 앞 장 뒤에 붙이고 파일 삭제
  · 여기서 나누기 → 한 파일을 지정한 줄에서 둘로 자름
  · 목차 붙여넣기 → 전체를 합친 뒤 제목 목록으로 다시 자름 (가장 강력)

본문이 바뀐 장은 그 장의 번역본·요약을 함께 지운다 — 옛 본문으로 만든 요약이
새 본문 옆에 남으면 안 된다.
"""

import json
import re
from pathlib import Path

from services.chapters import (_CHAPTER_DERIVED_SUFFIXES, _chapter_stem_of,
                               chapters_dir, strip_redundant_number)
from services.translate import DERIVED_SUFFIXES as _DERIVED, find_translation
from services.common import append_log

MAP_NAME = "_chapters.json"
LEAD_TITLE = "머리말"
# 논문은 'Introduction' 표제 없이 초록 뒤로 곧장 본문이 온다. 그 덩어리엔 제목·저자·
# 초록·서론이 함께 들어 있어서 '머리말'이라는 이름이 사실과 어긋난다
# (2026-08-26 Dorobantu 논문에서 연구자 지적).
LEAD_TITLE_PAPER = "제목·초록·서론"
LEAD_TITLES = (LEAD_TITLE, LEAD_TITLE_PAPER)
_ABSTRACT_RE = re.compile(r"^\s*Abstract\b|\bAbstract\s*[::]", re.M)


def lead_title_for(lead: str) -> str:
    """앞부분 덩어리의 이름 — 초록이 있으면 논문으로 본다."""
    return LEAD_TITLE_PAPER if _ABSTRACT_RE.search(lead[:3000]) else LEAD_TITLE


# ── 챕터 파일 목록 ────────────────────────────────────────────

def chapter_files(ws_name: str, stem: str) -> list[Path]:
    """원문 챕터 TXT만 번호순으로. 번역본·요약 등 파생물은 뺀다."""
    d = chapters_dir(ws_name, stem)
    if not d.exists():
        return []
    return sorted(
        f for f in d.glob("??_*.txt")
        if not f.stem.endswith(_DERIVED)
    )


def chapter_title(path: Path) -> str:
    return re.sub(r"^\d{2}_", "", path.stem)


# 제목 다듬기는 services/chapters에 하나만 둔다 — 예전에는 같은 규칙이 네 곳에
# 복사돼 있어서 한 곳만 고치면 나머지가 옛 규칙으로 남았다(2026-08-25 실측: 장 제목을
# 늘려 고쳤는데 **다시 분할하니 또 잘렸다** — 분할 코드가 제 사본을 쓰고 있었다).
from services.chapters import MAX_TITLE_BYTES, safe_title as _safe   # noqa: E402,F401


def _drop_derived(ch_path: Path) -> None:
    """이 장의 번역본·요약 등 파생물 삭제 (원문 .txt는 남긴다)."""
    for suf in _CHAPTER_DERIVED_SUFFIXES:
        if suf == ".txt":
            continue
        p = ch_path.with_name(ch_path.stem + suf)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass


def _drop_overview(ws_name: str, stem: str) -> None:
    """장 구성이 바뀌면 책 전체요약도 옛 것이라 버린다."""
    d = chapters_dir(ws_name, stem)
    for p in list(d.glob("*_전체요약.md")) + list(d.glob("*_overview.md")):
        try:
            p.unlink()
        except Exception:
            pass


# ── 번호 다시 매기기 ──────────────────────────────────────────

def _target_stem(i: int, title: str, is_lead: bool) -> tuple[str, int]:
    """i번째(0-기반) 장의 파일 stem. 첫 장이 머리말이면 00을 주어 실제 장 번호가
    1부터 시작하게 한다 (services/chapters.split_book_to_chapters와 같은 규칙)."""
    if i == 0 and is_lead:
        return f"00_{_safe(title)}", 0
    n = i if is_lead else i + 1
    return f"{n:02d}_{_safe(strip_redundant_number(title, n))}", n


def _apply_order(ws_name: str, stem: str,
                 items: list[tuple[str, str | None, Path | None]]) -> None:
    """items = [(제목, 새 본문|None, 기존 파일|None)] 순서대로 파일을 다시 배치한다.

    새 본문이 None이면 기존 파일 내용을 그대로 두고 이름만 바꾼다 — 이때는 그 장의
    번역본·요약도 함께 따라간다. 새 본문이 있으면 그 장의 파생물은 버린다(옛 본문의
    것이라 짝이 안 맞는다).

    이름이 서로 밀리며 겹치는 것을 막으려고 임시 이름을 거쳐 두 단계로 옮긴다."""
    d = chapters_dir(ws_name, stem)
    snapshot = [f for f in sorted(d.iterdir()) if f.is_file()]
    staged: dict[int, list[tuple[Path, str]]] = {}      # k → [(임시경로, 접미사)]
    for k, (_title, _text, src) in enumerate(items):
        if src is None:
            continue
        rows: list[tuple[Path, str]] = []
        for f in snapshot:
            if _chapter_stem_of(f.name) != src.stem:
                continue
            suffix = f.name[len(src.stem):]
            tmp = d / f"~stage{k:03d}~{suffix}"
            f.rename(tmp)
            rows.append((tmp, suffix))
        staged[k] = rows
    is_lead = bool(items) and items[0][0] in LEAD_TITLES
    for k, (title, text, _src) in enumerate(items):
        new_stem, _n = _target_stem(k, title, is_lead)
        if text is None:
            for tmp, suffix in staged.get(k, []):
                tmp.rename(d / (new_stem + suffix))
        else:
            for tmp, suffix in staged.get(k, []):
                tmp.unlink()                            # 파생물까지 통째로 버린다
            (d / f"{new_stem}.txt").write_text(text, encoding="utf-8")


def _renumber(ws_name: str, stem: str) -> None:
    """합치기·나누기 뒤 파일 번호를 1부터 다시 매긴다."""
    files = chapter_files(ws_name, stem)
    _apply_order(ws_name, stem, [(chapter_title(f), None, f) for f in files])


# ── 지도 파일 ────────────────────────────────────────────────

def sync_queue(ws_name: str, stem: str) -> None:
    """이 책의 대기 목록을 현재 챕터 파일 상태에 맞춘다.

    큐는 챕터를 **파일 경로**로 들고 있어서, 이름을 바꾸거나 장을 합치면 옛 경로를
    가리킨 채 남는다. 그러면 대기 목록에서 그 장이 통째로 사라진다(2026-08-17 실측:
    파일 일괄 개명 뒤 문서요약 대기에 머리말만 남았다). 이미 이 책 항목이 들어 있던
    단계에 한해, 아직 처리되지 않은 챕터로 목록을 다시 맞춘다."""
    try:
        import config as cfg
        from services.pipeline_queue import queue_add, queue_list, queue_remove
    except Exception:
        return
    d = chapters_dir(ws_name, stem)
    try:
        book_rel = str(d.relative_to(cfg.BASE_DIR)) + "/"
    except ValueError:
        return
    files = chapter_files(ws_name, stem)
    # 번역본은 접미사가 도착언어를 따르므로 이름이 아니라 find_translation 으로 본다.
    for stage, done_suffix in (("tab3_ready", ""), ("tab4_ready", "_wiki.md")):
        mine = [i for i in queue_list(stage) if i.startswith(book_rel)]
        if not mine:
            continue                      # 이 단계에 없던 책은 새로 넣지 않는다
        queue_remove(stage, mine)
        queue_add(stage, [
            str(f.relative_to(cfg.BASE_DIR)) for f in files
            if not (find_translation(f) if not done_suffix
                    else f.with_name(f.stem + done_suffix).exists())
        ])


def map_path(ws_name: str, stem: str) -> Path:
    return chapters_dir(ws_name, stem) / MAP_NAME


def save_map(ws_name: str, stem: str, mode: str = "", confirmed: bool | None = None,
             source: str = "auto") -> dict:
    """현재 챕터 파일 상태를 지도로 기록. confirmed=None이면 기존 값 유지."""
    prev = load_map(ws_name, stem) or {}
    files = chapter_files(ws_name, stem)
    data = {
        "mode": mode or prev.get("mode", ""),
        "confirmed": prev.get("confirmed", False) if confirmed is None else bool(confirmed),
        "chapters": [
            {"n": i, "title": chapter_title(f), "file": f.name,
             "chars": len(f.read_text(encoding="utf-8", errors="ignore")),
             "source": source}
            for i, f in enumerate(files)
        ],
    }
    for k in ("anthology", "authors"):       # 논문집 표시·글별 저자도 (2026-09-21)
        if k in prev:
            data[k] = prev[k]
    p = map_path(ws_name, stem)
    if files:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def load_map(ws_name: str, stem: str) -> dict | None:
    p = map_path(ws_name, stem)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def is_confirmed(ws_name: str, stem: str) -> bool:
    m = load_map(ws_name, stem)
    return bool(m and m.get("confirmed"))


def confirm(ws_name: str, stem: str) -> None:
    save_map(ws_name, stem, confirmed=True)
    append_log(f"장 구분 확정: {stem}")


# ── 이상 징후 채점 ────────────────────────────────────────────

_HEAD_BAD_END = (".", ",", ";", ":", "!", "?")
_HANGUL_ANY = re.compile(r"[가-힣]")


# ── 장 경계가 분명한 제목 (2026-08-26) ──────────────────────────────
# '결론'·'서론'처럼 **누가 봐도 장이 바뀌는 자리**는 묻지 않고 나눈다. 알려만 주고
# 사람이 누르게 했더니 "너무 번거롭다"는 지적을 받았다(연구자). 다만 아무 제목에나
# 하지는 않는다 — 절 제목까지 장으로 삼으면 책이 잘게 부서진다(『The Artifice of
# Intelligence』 100쪽에 후보 26개). 그래서 **낱말을 못 박아 둔다.**
_BOUNDARY_WORDS = (
    "introduction", "conclusion", "conclusions", "concludingremarks",
    "prologue", "epilogue", "preface", "foreword", "afterword",
    "서론", "결론", "서언", "결어", "머리말", "맺음말", "맺는말",
    "들어가는말", "나가는말", "들어가며", "나가며", "맺으며", "나오는말", "나오며",
    "프롤로그", "에필로그", "후기",
)
# 같은 구실을 하는 낱말끼리 묶는다 — 소논문 모음을 알아보는 데 쓴다 (2026-09-21).
_OPENING_WORDS = frozenset((
    "introduction", "prologue", "preface", "foreword",
    "서론", "서언", "머리말", "들어가는말", "들어가며", "프롤로그",
))
_CLOSING_WORDS = frozenset(w for w in _BOUNDARY_WORDS if w not in _OPENING_WORDS)
# 앞에 붙는 번호(“IV. 결론”, “5. Conclusion”, “제5장 결론”)와 뒤 문장부호는 흘린다.
_BOUNDARY_RE = re.compile(
    r"^(?:제?\d{1,2}[.)장]?|[ivxl]{1,5}[.)])?"
    r"(" + "|".join(_BOUNDARY_WORDS) + r")[.:：]?$")


def _norm_head(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def boundary_word(line: str) -> str:
    """이 줄이 '여기서 장이 바뀐다'가 분명한 제목이면 그 핵심 낱말, 아니면 빈 문자열.

    핵심 낱말을 돌려주는 이유는 **한 권에 한 번만 나누기 위해서**다. 번호가 붙은
    「1. Introduction」과 그냥 「Introduction」은 같은 것으로 봐야 한다."""
    s = line.strip()
    if not (2 <= len(s) <= 40):
        return ""
    m = _BOUNDARY_RE.match(_norm_head(s))
    return m.group(1) if m else ""


def is_boundary_heading(line: str) -> bool:
    return bool(boundary_word(line))


def section_heading_hits(ws_name: str, stem: str) -> list[tuple[int, int, str, str]]:
    """장 안에 홀로 선 경계 제목 전부 — [(장 순번, 문자위치, 줄, 핵심 낱말)].

    장의 맨 앞(pos 0)도 센다. 이미 그 제목으로 갈라진 장이 있으면 그것도 이 책이
    어떤 모양인지를 말해 주는 증거이기 때문이다."""
    hits: list[tuple[int, int, str, str]] = []
    for i, f in enumerate(chapter_files(ws_name, stem)):
        try:
            body = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        lines = body.splitlines(keepends=True)
        pos = 0
        for k, raw in enumerate(lines):
            s = raw.strip()
            prev_blank = (k == 0) or not lines[k - 1].strip()
            next_blank = (k + 1 >= len(lines)) or not lines[k + 1].strip()
            w = boundary_word(s) if (s and prev_blank and next_blank) else ""
            if w:
                hits.append((i, pos, s, w))
            pos += len(raw)
    return hits


def anthology_evidence(hits: list[tuple[int, int, str, str]]) -> str:
    """이 책이 **소논문 모음**(논문집·학술지)이라는 증거. 없으면 빈 문자열.

    ★2026-09-21 『기술윤리』(HTSN 논문집) 실측. 논문마다 「I. 들어가는 말」·「V. 나가는
    말」이 있는데 auto_split_known_headings 가 낱말마다 한 번씩 갈라서 「들어가는 말」·
    「나가는 말」·「들어가며」·「맺는말」·「나가며」가 제각기 장이 됐고, 그 앞의 논문
    제목 장은 본문 97자짜리 빈 껍데기가 됐다. 한 권에 서론이 하나라야 서론이 장이다.

    판정: 같은 구실(여는 말/맺는 말)의 낱말이 **둘 이상 다른 꼴**로 나오거나, 같은
    낱말이 **세 번 이상** 서 있으면 모음집이다. 두 번은 장 안에 남은 목차나 러닝헤더일
    수 있어(『서양철학사』「머 리 말」×2) 그대로 둔다 — 그 경우는 한 번만 가르는
    기존 규칙이 맞다."""
    for family, label in ((_OPENING_WORDS, "여는 말"), (_CLOSING_WORDS, "맺는 말")):
        words = [h[3] for h in hits if h[3] in family]
        if not words:
            continue
        distinct = sorted(set(words), key=words.index)
        if len(distinct) >= 2 or len(words) >= 3:
            shown = "·".join(f"「{h[2]}」" for h in hits if h[3] in family)[:120]
            return f"{label} 제목이 {len(words)}번 나옵니다 ({shown})"
    return ""


def note_authors(ws_name: str, stem: str, authors: dict[str, str]) -> bool:
    """시각 판독이 읽은 글별 저자를 장 지도에 남기고, 저자가 둘 이상 다르면 논문집으로
    표시한다 (2026-09-21). 제목만으로는 못 알아보는 모음집(절 제목이 「서론」 하나뿐인
    학술지 등)도 이 표시로 잡힌다. 논문집이면 True."""
    m = load_map(ws_name, stem) or {}
    distinct = {a.strip() for a in authors.values() if a and a.strip()}
    if not distinct:
        return bool(m.get("anthology"))
    m["authors"] = dict(authors)
    m["anthology"] = len(distinct) >= 2
    p = map_path(ws_name, stem)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    if m["anthology"]:
        append_log(f"장분할: 글마다 저자가 달라 논문집으로 봄 — {stem} (저자 {len(distinct)}명)")
    return m["anthology"]


def is_anthology(ws_name: str, stem: str) -> str:
    """이 책이 소논문 모음이라는 근거 — 장 지도의 저자 표시 또는 절 제목 반복. 없으면 ''."""
    m = load_map(ws_name, stem) or {}
    if m.get("anthology"):
        n = len({a for a in (m.get("authors") or {}).values() if a})
        return f"글마다 저자가 다릅니다 ({n}명)"
    return anthology_evidence(section_heading_hits(ws_name, stem))


def section_title_chapters(ws_name: str, stem: str) -> list[int]:
    """제목이 「들어가는 말」·「나가며」 같은 **절 제목뿐인 장**의 순번(0-기반).

    모음집이 이미 잘못 갈라진 뒤에 부르는 용도다 — 편집 창에서 한 번에 앞 장에
    합치거나, 확인 화면에서 경고한다. 첫 장(0)은 뺀다: 합칠 앞 장이 없고, 책 전체의
    머리말이면 장으로 두는 것이 맞다."""
    files = chapter_files(ws_name, stem)
    words = [boundary_word(chapter_title(f)) for f in files]
    m = load_map(ws_name, stem) or {}
    if not m.get("anthology") and not anthology_evidence(
            [(i, 0, chapter_title(f), w) for i, (f, w) in enumerate(zip(files, words)) if w]):
        return []
    return [i for i, w in enumerate(words) if i > 0 and w]


def auto_split_known_headings(ws_name: str, stem: str, max_splits: int = 8) -> list[str]:
    """장 **안에** '결론'·'서론' 같은 제목이 홀로 서 있으면 거기서 나눈다.

    ★자동으로 나누는 것은 이 낱말들뿐이다(_BOUNDARY_WORDS). 그 밖의 제목처럼 보이는
    줄은 missed_headings()가 알려만 주고 사람이 «✂️ 장 나누기»에서 고른다.

    제목이 홀로 선 문단이어야 한다 — 앞뒤가 빈 줄이라야 본문 한가운데의 낱말과
    구별된다. 장의 맨 앞이면(at=0) 이미 경계이므로 건드리지 않는다.

    나눈 제목들을 돌려준다. 무한히 도는 것을 막으려고 횟수를 제한한다."""
    made: list[str] = []
    # ★소논문 모음이면 아예 손대지 않는다 (2026-09-21) — anthology_evidence 주석 참고.
    #   논문마다 있는 「들어가는 말」은 절 제목이지 장이 아니다.
    _why = is_anthology(ws_name, stem)
    if _why:
        append_log(f"장분할: 소논문 모음으로 보여 경계 제목 자동 분할을 건너뜀 — {stem}: {_why}")
        return []
    # ★같은 낱말로는 한 번만 나눈다 (2026-08-26 실측). 안 막았더니 『서양철학사』가
    # 「머 리 말」에서 두 번, 『영국감리교』가 「1. Introduction」과 「Introduction」
    # 에서 두 번 갈렸다 — 장 안에 남은 목차나 러닝헤더가 다시 걸린 것이다.
    used: set[str] = set()
    for _ in range(max_splits):
        hit = None
        for i, f in enumerate(chapter_files(ws_name, stem)):
            try:
                body = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lines = body.splitlines(keepends=True)
            pos = 0
            for k, raw in enumerate(lines):
                s = raw.strip()
                prev_blank = (k == 0) or not lines[k - 1].strip()
                next_blank = (k + 1 >= len(lines)) or not lines[k + 1].strip()
                _w = boundary_word(s) if (pos > 0 and s and prev_blank and next_blank) else ""
                if _w and _w not in used:
                    hit = (i, pos, s.strip(), _w)
                    break
                pos += len(raw)
            if hit:
                break
        if not hit:
            break
        i, at, title, word = hit
        if not split_chapter(ws_name, stem, i, at, title):
            break
        used.add(word)
        made.append(title)
    return made


def missed_headings(ws_name: str, stem: str, limit: int = 5) -> list[tuple[int, str]]:
    """장 **안에** 제목처럼 홀로 선 문단들 — 새 장이 여기서 시작할 만하다.

    ★2026-08-26. reflow가 라틴문자 제목을 제 문단으로 남기게 고쳤더니(reflowlib),
    한 줄짜리 짧은 문단은 대개 절 제목이 됐다. 그런데 장 목록은 **시각 판독**이
    만들고, 그것이 놓친 제목은 아무도 줍지 않았다 — Dorobantu 논문의 `Conclusion`이
    본문에 제 줄로 서 있는데도 결론 장이 생기지 않았다.

    자동으로 나누지는 않는다. 절 제목까지 장으로 삼으면 책이 잘게 부서진다
    (실측: 『The Artifice of Intelligence』 100쪽에 후보 26개). **알려만 주고**
    나눌지는 «✂️ 장 나누기»에서 사람이 고른다.

    ★첫 판은 너무 시끄러웠다(2026-08-26 실측): 저자명·판권지·러닝헤더·문장 조각이
    섞여 나왔다. 그래서 네 가지를 막는다.
      · 앞부분 덩어리(00장)는 통째로 건너뛴다 — 거기가 판권지·초록·저자 자리다.
      · 숫자가 든 줄은 뺀다 — 러닝헤더('AI and Ethics (2025) 5:5527–5533')와 인용.
      · 40자를 넘으면 뺀다 — 'According to Kant, anyone who violates rights does not'
        같은 문장 조각이 걸린다.
      · 책 안에서 두 번 이상 나오는 줄은 뺀다 — 살아남은 러닝헤더."""
    files = chapter_files(ws_name, stem)
    # ★한글 책에서는 보지 않는다 (2026-08-26). 제목을 살려 두는 reflow 규칙 자체가
    # 라틴 문서 전용이라, 한글 책의 한 줄짜리 라틴 문단은 제목이 아니라 미주의 인용
    # 조각이다 — 실측에서 'Publishing Company'·'Doubleday'·'Books.)' 가 걸려 나왔다.
    sample = "".join(f.read_text(encoding="utf-8", errors="ignore")[:2000] for f in files[:5])
    if sample and len(_HANGUL_ANY.findall(sample)) / len(sample) > 0.15:
        return []
    seen: dict[str, int] = {}
    found: list[tuple[int, str]] = []
    for i, f in enumerate(files):
        # 앞부분 덩어리(00_…)는 판권지·초록·저자 자리라 제목처럼 보이는 줄이 널려 있다.
        # ★목록의 첫 항목이 아니라 **파일 이름**으로 가린다 — 앞부분 덩어리가 없는
        # 책은 01부터 시작하는데, 첫 항목을 건너뛰면 멀쩡한 1장을 안 보게 된다.
        if f.stem[:2] == "00":
            continue
        title = chapter_title(f).strip()
        try:
            body = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for para in body.split("\n\n"):
            s = para.strip()
            if "\n" in s or not (2 <= len(s) <= 40):
                continue                       # 여러 줄이면 본문, 길면 문장 조각
            if s.endswith(_HEAD_BAD_END) or _HANGUL_ANY.search(s):
                continue                       # 한글 제목 규칙은 아직 없다
            if any(c.isdigit() for c in s):
                continue                       # 러닝헤더·인용
            if not s[:1].isupper() or s == title:
                continue
            seen[s] = seen.get(s, 0) + 1
            found.append((i, s))
    out = [(i, s) for i, s in found if seen[s] == 1]
    return out[:limit]


def review_findings(ws_name: str, stem: str) -> list[str]:
    """장 구분이 수상한 이유들. 비어 있으면 그냥 넘어가도 되는 분할이다."""
    files = chapter_files(ws_name, stem)
    if not files:
        return ["챕터 없음"]
    m = load_map(ws_name, stem) or {}
    mode = m.get("mode", "")
    out: list[str] = []
    # 사람이 목차를 넣어 나눈 것(toc_paste)은 추정이 아니다 — 경고 대상에서 뺀다
    if mode and mode not in ("bookmark", "visual", "toc_paste"):
        out.append("PDF 차례를 읽지 못해 본문 추정으로 나뉘었습니다")
    sizes = sorted(len(f.read_text(encoding="utf-8", errors="ignore")) for f in files)
    body = [s for s in sizes if s > 0]
    if len(body) >= 3:
        med = body[len(body) // 2]
        if med and body[-1] > med * 3:
            out.append(f"장 분량이 고르지 않습니다 (가장 큰 장이 중앙값의 {body[-1] / med:.1f}배)")
    if len(files) <= 4:
        out.append(f"장이 {len(files)}개뿐입니다 — 목차와 견주어 보세요")
    numeric = [f for f in files if re.fullmatch(r"제?\s*\d+\s*장|Chapter\s*\d+|\d+", chapter_title(f).strip(), re.I)]
    if numeric:
        out.append(f"제목이 번호뿐인 장이 {len(numeric)}개 있습니다")
    # 소논문 모음이 절 제목에서 갈라진 흔적 (2026-09-21 『기술윤리』)
    sect = section_title_chapters(ws_name, stem)
    if sect:
        names = "·".join(f"「{chapter_title(files[i])}」" for i in sect[:4])
        out.append(f"「들어가는 말」·「나가는 말」 같은 절 제목이 장으로 잡혀 있습니다 "
                   f"({len(sect)}개: {names}{' …' if len(sect) > 4 else ''}) — "
                   f"넓은 편집 창에서 앞 장에 합치세요")
    shells = [f for f in files
              if f.stem[:2] != "00" and len(f.read_text(encoding="utf-8", errors="ignore")) < 300]
    if shells:
        out.append(f"본문이 거의 없는 장이 {len(shells)}개 있습니다 (300자 미만) — 제목만 남은 껍데기일 수 있습니다")
    # ★«01장 안에 제목처럼 보이는 줄이 있습니다 — 장 나누기에서 …» 경고는 뺐다
    #   (2026-08-27). 그 «✂️ 장 나누기»를 같은 날 화면에서 걷어냈으므로, 남겨 두면
    #   있지도 않은 단추를 찾으라고 시키는 꼴이 된다. 논문 한 편에 다섯 줄씩 붙어
    #   실제로 화면을 덮었다. missed_headings() 자체는 남겨 둔다 — 판정은 멀쩡하고
    #   나중에 다시 쓸 자리가 생길 수 있다.
    return out


# ── 수정 동작 ────────────────────────────────────────────────

def rename_chapter(ws_name: str, stem: str, idx: int, new_title: str) -> bool:
    """제목만 바꾼다 — 본문이 그대로이므로 요약·번역본도 함께 따라간다."""
    files = chapter_files(ws_name, stem)
    if not (0 <= idx < len(files)) or not new_title.strip():
        return False
    src = files[idx]
    prefix = src.stem[:2]
    new_stem = f"{prefix}_{_safe(new_title)}"
    if new_stem == src.stem:
        return True
    d = src.parent
    for f in sorted(d.iterdir()):
        if _chapter_stem_of(f.name) == src.stem:
            target = d / (new_stem + f.name[len(src.stem):])
            if not target.exists():
                f.rename(target)
    sync_queue(ws_name, stem)
    save_map(ws_name, stem, source="user")
    return True


def merge_up(ws_name: str, stem: str, idx: int) -> bool:
    """이 장을 앞 장 뒤에 붙인다. 첫 장에는 쓸 수 없다."""
    files = chapter_files(ws_name, stem)
    if not (1 <= idx < len(files)):
        return False
    merged = (files[idx - 1].read_text(encoding="utf-8", errors="ignore").rstrip()
              + "\n\n" + files[idx].read_text(encoding="utf-8", errors="ignore").lstrip())
    # 흡수되는 장의 파일(원문·번역본·요약)은 먼저 치운다 — _apply_order는 items에
    # 없는 파일을 건드리지 않으므로 남겨두면 옛 이름 그대로 떠돈다
    for f in sorted(files[idx].parent.iterdir()):
        if f.is_file() and _chapter_stem_of(f.name) == files[idx].stem:
            f.unlink()
    items: list[tuple[str, str | None, Path | None]] = []
    for i, f in enumerate(files):
        if i == idx:
            continue                                   # 이 장은 앞 장에 흡수
        title = chapter_title(f)
        items.append((title, merged, f) if i == idx - 1 else (title, None, f))
    _apply_order(ws_name, stem, items)
    _drop_overview(ws_name, stem)
    sync_queue(ws_name, stem)
    save_map(ws_name, stem, source="user")
    return True


def split_candidates(ws_name: str, stem: str, idx: int, limit: int = 40,
                     query: str = "") -> tuple[list[tuple[int, str]], int]:
    """이 장 안에서 '새 장이 시작될 만한 줄' 후보 ([(문자위치, 줄)], 후보 총수).

    후보는 보통 수백~수천 줄이라 다 보여줄 수 없어 **문서 전체에 고르게** 솎아
    낸다. 그런데 솎아 내면 정작 필요한 한 줄이 빠진다 — 『기술신학』에서 10장
    첫 줄(`정든 인공지능과`)이 후보 1,025개 중 493번째였는데 limit을 400까지
    올려도 표집에서 계속 빠졌다(2026-08-24). 그래서 **검색어**를 받는다:
    검색어가 있으면 솎아 내지 않고 그 말이 든 줄만 앞에서부터 보여 준다."""
    files = chapter_files(ws_name, stem)
    if not (0 <= idx < len(files)):
        return [], 0
    text = files[idx].read_text(encoding="utf-8", errors="ignore")
    out: list[tuple[int, str]] = []
    pos = 0
    for raw in text.splitlines(True):
        s = re.sub(r"\s+", " ", raw).strip()
        if pos > 200 and 2 <= len(s) <= 60 and not re.search(r"[.?!。,]$", s):
            out.append((pos, s))
        pos += len(raw)
    q = re.sub(r"\s+", "", (query or "")).lower()
    if q:                                     # 검색 — 표집하지 않는다
        out = [(p, s) for p, s in out if q in re.sub(r"\s+", "", s).lower()]
    total = len(out)
    if total > limit:                         # 문서 전체에 고르게
        step = total / limit
        out = [out[int(i * step)] for i in range(limit)]
    return out, total


def split_chapter(ws_name: str, stem: str, idx: int, at: int, new_title: str = "") -> bool:
    """이 장을 문자 위치 at에서 둘로 자른다."""
    files = chapter_files(ws_name, stem)
    if not (0 <= idx < len(files)):
        return False
    text = files[idx].read_text(encoding="utf-8", errors="ignore")
    if not (0 < at < len(text)):
        return False
    head, tail = text[:at].rstrip(), text[at:].lstrip()
    if not head or not tail:
        return False
    title = new_title.strip() or (tail.splitlines()[0].strip()[:50] if tail.splitlines() else "") or "새 장"
    items: list[tuple[str, str | None, Path | None]] = []
    for i, f in enumerate(files):
        if i == idx:
            items.append((chapter_title(f), head, f))   # 앞부분 — 본문이 바뀌므로 파생물 폐기
            items.append((title, tail, None))           # 뒷부분 — 새 장
        else:
            items.append((chapter_title(f), None, f))
    _apply_order(ws_name, stem, items)
    _drop_overview(ws_name, stem)
    sync_queue(ws_name, stem)
    save_map(ws_name, stem, source="user")
    return True


_TOC_DROP_LINE = re.compile(r"^(차\s*례|목\s*차|contents)\b", re.I)
# 장 표시 — OCR이 '제'를 '체·쩨·쩌'로 읽는 일이 잦다
# "제3장 |", "1강연", "2 講" 등 — 강연은 강보다 먼저 봐야 "연"이 남지 않는다
_TOC_CH_MARK = re.compile(r"^[제체쩨쩌]?\s*\d{1,2}\s*(?:강연|강좌|장|부|편|강|과|화)\s*[^\w가-힣]*\s*")
_TOC_TAIL_CJK = re.compile(r"(?<=[가-힣\s])\s+[一-鿿々〆々〆]{1,5}\s*$")


def parse_toc_text(raw: str) -> list[str]:
    """붙여넣은 차례에서 장 제목만 추려낸다.

    떼는 것: 점선+쪽번호(`… 55`), 끝 쪽번호, `제3장 |` 같은 장 표시와 구분 기호,
    그리고 OCR이 쪽번호를 한자처럼 읽어 남긴 꼬리(`정의의 장소 召口`의 `召口`).
    장 번호를 떼는 이유는 이 제목으로 **본문을 찾아야** 하기 때문이다 — 본문 헤딩에는
    보통 번호 표기가 다르게 찍힌다. 파일 이름의 번호는 어차피 순번이 붙는다."""
    titles: list[str] = []
    for line in (raw or "").splitlines():
        s = re.sub(r"\s+", " ", line).strip()
        if not s or _TOC_DROP_LINE.match(s):
            continue
        s = re.sub(r"\s*[.·ㆍ…]{2,}\s*\S{0,6}$", "", s).strip()       # 점선 + 쪽번호
        s = _TOC_CH_MARK.sub("", s).strip()                           # "제3장 |" 등
        s = re.sub(r"[_\-]?\s*[\d\s]{1,8}$", "", s).strip()             # 끝 쪽번호
        s = _TOC_TAIL_CJK.sub("", s).strip()                          # 한자로 깨진 쪽번호
        s = s.strip(" .·ㆍ…•∙·|:!$}{gi_■□▪●◆※~-")
        # 한글이든 라틴 문자든 '낱말'이 두 자 이상 남아야 제목으로 본다
        if 2 <= len(s) <= 80 and re.search(r"[가-힣]{2}|[A-Za-z]{3}", s):
            titles.append(s)
    return titles


def parse_toc_entries(raw: str) -> list[tuple[str, int | None]]:
    """차례를 [(제목, 인쇄된 쪽번호|None)]로 읽는다.

    제목만 쓰는 parse_toc_text와 달리 **쪽번호를 버리지 않는다**. 본문 헤딩이 OCR로
    깨져 제목을 못 찾는 장은 쪽번호로 자리를 잡을 수 있기 때문이다 (2026-08-17)."""
    out: list[tuple[str, int | None]] = []
    for line in (raw or "").splitlines():
        s = re.sub(r"\s+", " ", line).strip()
        if not s or _TOC_DROP_LINE.match(s):
            continue
        page = None
        m = re.search(r"(?:[.·ㆍ…_\-]{1,}|\s)\s*(\d{1,4})\s*$", s)
        if m:
            page = int(m.group(1))
        titles = parse_toc_text(s)
        if titles:
            out.append((titles[0], page))
    return out


def _source_text(ws_name: str, stem: str) -> tuple[str, list[int]]:
    """(본문, 쪽 시작 문자위치 목록). 보관된 원본 TXT를 우선 쓴다 — 거기에만 쪽
    구분자(\\f)가 남아 있어 쪽번호로 자리를 잡을 수 있다. 없으면 현재 챕터를 잇는다."""
    try:
        import config as cfg
        from services.toc import _page_offsets
        for c in (cfg.TXT_ARCHIVE_DIR / f"{stem}.txt", cfg.TXT_DIR / f"{stem}.txt"):
            if c.exists():
                t = c.read_text(encoding="utf-8", errors="ignore")
                if "\f" in t:
                    return t, _page_offsets(t)
    except Exception:
        pass
    files = chapter_files(ws_name, stem)
    return "\n\n".join(f.read_text(encoding="utf-8", errors="ignore").strip() for f in files), []


def _page_of(page_offsets: list[int], pos: int) -> int:
    """문자 위치가 몇 번째 쪽(0-기반)인지."""
    import bisect
    return max(0, bisect.bisect_right(page_offsets, pos) - 1)


class PageMap:
    """챕터 파일의 자리를 **원본 쪽 번호**로 옮겨 준다 (2026-09-21).

    챕터 파일에는 쪽 구분자(\f)가 없다 — 그것은 보관된 원본 TXT에만 남아 있다.
    그런데 챕터를 죄다 이으면 공백만 빼고 원본과 글자가 같다(『기술윤리』 실측
    232,450자 일치). 그래서 **공백 아닌 글자를 세어** 자리를 맞춘다: 챕터 i의 pos는
    "앞 챕터들의 글자 수 + 이 챕터에서 pos까지의 글자 수"번째 글자이고, 원본에서
    그 글자가 몇 쪽에 있는지는 \f 위치로 안다.

    글자 수가 안 맞으면(재판독·손편집으로 원본과 어긋난 책) `ok`가 False이고 쪽은
    모른다고 한다 — 틀린 쪽 번호는 안 보여 주는 것보다 나쁘다."""

    def __init__(self, ws_name: str, stem: str):
        text, offsets = _source_text(ws_name, stem)
        self.ok = False
        self._page_offsets = offsets
        self._src_idx: list[int] = []
        self._starts: list[int] = []          # 챕터별 첫 글자의 전체 순번
        self._lens: list[int] = []
        if not offsets or len(offsets) < 2:
            return
        self._src_idx = [i for i, c in enumerate(text) if not c.isspace()]
        total = 0
        for f in chapter_files(ws_name, stem):
            body = f.read_text(encoding="utf-8", errors="ignore")
            n = sum(1 for c in body if not c.isspace())
            self._starts.append(total)
            self._lens.append(n)
            total += n
        self.ok = bool(self._src_idx) and total == len(self._src_idx)

    @property
    def page_count(self) -> int:
        return len(self._page_offsets)

    def _page_of_nth(self, nth: int) -> int:
        nth = max(0, min(nth, len(self._src_idx) - 1))
        return _page_of(self._page_offsets, self._src_idx[nth]) + 1     # 1-기반

    def page_at(self, idx: int, text_before: str) -> int | None:
        """챕터 idx 안에서, text_before(그 자리까지의 본문) 다음 글자가 있는 쪽."""
        if not self.ok or not (0 <= idx < len(self._starts)):
            return None
        k = sum(1 for c in text_before if not c.isspace())
        return self._page_of_nth(self._starts[idx] + k)

    def chapter_range(self, idx: int) -> tuple[int, int] | None:
        """(첫 쪽, 끝 쪽). 본문이 없는 장은 첫 쪽만 같은 값으로."""
        if not self.ok or not (0 <= idx < len(self._starts)):
            return None
        start = self._page_of_nth(self._starts[idx])
        end = self._page_of_nth(self._starts[idx] + max(self._lens[idx] - 1, 0))
        return start, max(start, end)


def apply_toc(ws_name: str, stem: str, entries: list[tuple[str, int | None]],
              manual_offset: int | None = None) -> tuple[bool, str]:
    """차례(제목+쪽번호)로 책을 다시 나눈다.

    두 경로를 함께 쓴다 (2026-08-17):
      · 제목 퍼지 탐색 — OCR 오탈자를 견디지만 헤딩이 심하게 깨지면 못 찾는다.
      · 쪽번호 — 인쇄 쪽번호와 PDF 쪽이 어긋나므로 보정값(앵커)이 필요하다.
    앵커는 **제목으로 찾은 장들에서 스스로 구한다** — (그 장이 있는 실제 쪽) 빼기
    (차례에 적힌 쪽)의 중앙값. 그래서 사용자가 따로 입력할 필요가 없다.
    제목으로 못 찾은 장은 그 앵커로 자리를 잡고, 찾은 장은 두 값이 크게 어긋나면
    보고에 적어 사람이 확인하게 한다."""
    entries = [(t.strip(), p) for t, p in entries if t and t.strip()]
    if len(entries) < 2:
        return False, "제목이 2개 이상 필요합니다"
    text, page_offsets = _source_text(ws_name, stem)
    if not text.strip():
        return False, "본문을 찾지 못했습니다"
    try:
        from services.toc import _locate_titles
    except Exception as e:
        return False, f"제목 탐색기 불러오기 실패: {e}"

    located = {t: p for p, t in _locate_titles(text, entries)}
    # 앵커 추정 — 제목으로 찾은 장에서 (실제 쪽 − 차례 쪽)의 중앙값
    offset = manual_offset
    diffs = [_page_of(page_offsets, located[t]) - p
             for t, p in entries if t in located and p and page_offsets]
    if offset is None and len(diffs) >= 3:
        offset = sorted(diffs)[len(diffs) // 2]

    marks: list[tuple[int, str]] = []
    by_page = corrected = 0
    for title, page in entries:
        pos = located.get(title)
        guess = None
        if page and offset is not None and page_offsets:
            pi = page + offset
            if 0 <= pi < len(page_offsets):
                guess = page_offsets[pi]
        if pos is None:
            if guess is None:
                continue
            marks.append((guess, title))
            by_page += 1
            continue
        # 제목이 찾아졌더라도 차례의 쪽번호와 크게 어긋나면 그 자리는 본문 헤딩이
        # 아니라 러닝헤더·색인일 가능성이 크다(실측: 마지막 장이 책 끝의 머리글에
        # 걸려 78바이트짜리 장이 됐다). 보정값은 여러 장의 중앙값이라 한 번의 퍼지
        # 매칭보다 믿을 만하므로, 이럴 땐 쪽번호 쪽을 택한다 (2026-08-19).
        if guess is not None and abs(_page_of(page_offsets, pos) - (page + offset)) > 1:
            marks.append((guess, title))
            corrected += 1
            continue
        marks.append((pos, title))

    marks = sorted({(p, t) for p, t in marks}, key=lambda x: x[0])
    dedup: list[tuple[int, str]] = []
    for p, t in marks:
        if dedup and p - dedup[-1][0] < 500:
            continue
        dedup.append((p, t))
    if len(dedup) < 2:
        return False, f"본문에서 찾은 제목이 {len(dedup)}개뿐입니다 — 제목 표기를 본문과 맞춰 보세요"

    _write_chapters(ws_name, stem, text, dedup)
    missing = len(entries) - len(dedup)
    msg = f"{len(dedup)}장으로 다시 나눴습니다 (제목으로 {len(dedup) - by_page - corrected}개"
    msg += f", 쪽번호로 {by_page}개" if by_page else ""
    msg += f", 쪽번호로 바로잡음 {corrected}개" if corrected else ""
    msg += ")"
    if offset is not None:
        msg += f" · 쪽 보정 {offset:+d}"
    if missing > 0:
        msg += f" · 못 찾은 제목 {missing}개"
    append_log(f"장 구분 수정(차례): {stem} — {len(dedup)}/{len(entries)}장, "
               f"쪽번호 사용 {by_page}, 바로잡음 {corrected}, 보정 {offset}")
    return True, msg


def _write_chapters(ws_name: str, stem: str, text: str,
                    marks: list[tuple[int, str]]) -> None:
    """옛 챕터를 모두 지우고 marks(문자위치, 제목)대로 다시 쓴다."""
    d = chapters_dir(ws_name, stem)
    d.mkdir(parents=True, exist_ok=True)
    for f in sorted(d.iterdir()):
        if f.is_file() and _chapter_stem_of(f.name):
            f.unlink()
    bounds = [p for p, _t in marks] + [len(text)]
    lead = text[:bounds[0]].strip()
    if lead and len(lead) >= 300:
        (d / f"00_{_safe(lead_title_for(lead))}.txt").write_text(lead, encoding="utf-8")
    for i, (_p, title) in enumerate(marks):
        body = text[bounds[i]:bounds[i + 1]].strip()
        (d / f"{i + 1:02d}_{_safe(strip_redundant_number(title, i + 1))}.txt").write_text(
            body, encoding="utf-8")
    _renumber(ws_name, stem)
    _drop_overview(ws_name, stem)
    sync_queue(ws_name, stem)
    save_map(ws_name, stem, mode="toc_paste", confirmed=False, source="user")


def apply_titles(ws_name: str, stem: str, titles: list[str]) -> tuple[bool, str]:
    """제목 목록으로 책 전체를 다시 자른다 — 현재 챕터를 합친 본문에서 제목을 찾는다."""
    files = chapter_files(ws_name, stem)
    if not files:
        return False, "챕터 없음"
    titles = [t.strip() for t in titles if t and t.strip()]
    if len(titles) < 2:
        return False, "제목이 2개 이상 필요합니다"
    text = "\n\n".join(f.read_text(encoding="utf-8", errors="ignore").strip() for f in files)
    try:
        from services.toc import _locate_titles
    except Exception as e:
        return False, f"제목 탐색기 불러오기 실패: {e}"
    marks = _locate_titles(text, [(t, None) for t in titles])
    marks = sorted({(p, t) for p, t in marks}, key=lambda x: x[0])
    dedup: list[tuple[int, str]] = []
    for p, t in marks:
        if dedup and p - dedup[-1][0] < 500:
            continue
        dedup.append((p, t))
    if len(dedup) < 2:
        return False, f"본문에서 찾은 제목이 {len(dedup)}개뿐입니다 — 제목 표기를 본문과 맞춰 보세요"
    d = chapters_dir(ws_name, stem)
    for f in sorted(d.iterdir()):                 # 옛 챕터·파생물 전부 정리
        if f.is_file() and _chapter_stem_of(f.name):
            f.unlink()
    bounds = [p for p, _t in dedup] + [len(text)]
    lead = text[:bounds[0]].strip()
    if lead and len(lead) >= 300:
        (d / f"00_{_safe(lead_title_for(lead))}.txt").write_text(lead, encoding="utf-8")
    for i, (_p, title) in enumerate(dedup):
        body = text[bounds[i]:bounds[i + 1]].strip()
        (d / f"{i + 1:02d}_{_safe(strip_redundant_number(title, i + 1))}.txt").write_text(
            body, encoding="utf-8")
    _renumber(ws_name, stem)
    _drop_overview(ws_name, stem)
    sync_queue(ws_name, stem)
    save_map(ws_name, stem, mode="toc_paste", confirmed=False, source="user")
    found, asked = len(dedup), len(titles)
    msg = f"{found}장으로 다시 나눴습니다"
    if found < asked:
        msg += f" (제목 {asked - found}개는 본문에서 못 찾아 건너뜀)"
    append_log(f"장 구분 수정(목차 붙여넣기): {stem} — {found}/{asked}장")
    return True, msg
