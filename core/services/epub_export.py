"""챕터 TXT(원문 또는 번역본) → EPUB 3 전자책, 책 한 권을 파일 하나로 합쳐서 저장.

요약(_wiki.md)이 아니라 본문 전체를 담는다 — 챕터별로 번역본(_ko.txt)이 있으면
그걸, 없으면 원문 그대로 쓴다. 외부 라이브러리 없이 표준 zipfile만 사용
(이 프로젝트가 지금까지 해온 대로: PyMuPDF 대신 pypdfium2, python-docx만 사용해
시스템 의존성을 늘리지 않는 방침과 동일)."""
from __future__ import annotations

import html
import json
import re
import uuid
import zipfile
from pathlib import Path

import config as cfg

from services.translate import DERIVED_SUFFIXES as _DERIVED, find_translation
from services.chapters import _author_from_stem, chapters_dir


def set_epub_dir(path_str: str) -> None:
    """~/.config/mybookshelf/config.json의 dirs.epub 갱신 — 앱 재시작 후 적용.
    (DOCX/HWPX 저장 폴더 설정과 동일한 방식.)"""
    f = cfg.CONFIG_FILE
    try:
        d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except Exception:
        d = {}
    d.setdefault("dirs", {})["epub"] = path_str
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_name(stem: str) -> str:
    return re.sub(r'[/\\:*?"<>|]', "_", stem).strip() or "book"


def _split_title_author(stem: str) -> tuple[str, str]:
    """'제목_저자' 또는 '제목_저자_' 관례에서 제목·저자 분리 — 실패하면 stem 전체를 제목으로."""
    author = _author_from_stem(stem)
    if author:
        trimmed = stem.rstrip("_")
        if trimmed.endswith(author):
            title = trimmed[: -len(author)].rstrip("_").strip()
            if title:
                return title, author
    return stem, ""


_HANGUL_RE = re.compile(r"[가-힣]")


def _chapter_source_text(ch_path: Path, engine: str = "", clean: bool = False,
                          progress_cb=None, prefix: str = "") -> str:
    """번역본(_ko.txt) > 자간정리본(_clean.txt) > 원문 순으로 고른다.
    번역은 그 자체로 OCR 잡음을 흡수하므로 정리 대상이 아니다 — 원문에만 적용.

    clean=False가 기본이다(2026-08-14): 자간정리는 EPUB 생성과 분리된 별도 단계라
    (clean_book_chapters) 여기서는 이미 만들어진 _clean.txt를 쓰기만 한다. 그래서
    EPUB 생성 자체는 한글책이든 영어책이든 항상 즉시 끝난다.

    prefix는 진행 표시 앞에 붙일 문구('챕터 3/15 · ') — 진행 표시가 placeholder
    하나를 덮어쓰는 구조라, 매 메시지가 챕터 맥락을 같이 들고 있어야 어느 챕터를
    처리 중인지 보인다(2026-08-14)."""
    ko = find_translation(ch_path)            # 도착언어 무관(예전 _ko.txt 포함)
    if ko:
        return ko.read_text(encoding="utf-8", errors="ignore")
    clean_path = ch_path.with_name(ch_path.stem + "_clean.txt")
    if clean and engine and not clean_path.exists():
        from services.translate import clean_chapter_ko
        _inner_cb = None
        if progress_cb:
            def _inner_cb(idx, total, joined_n, spaced_n, unknown_n):
                progress_cb(f"{prefix}자간정리 줄바꿈 {idx}/{total} "
                            f"(붙임 {joined_n}·공백 {spaced_n}·미판정 {unknown_n})")
        clean_chapter_ko(ch_path, engine, progress_cb=_inner_cb)
    if clean_path.exists():
        return clean_path.read_text(encoding="utf-8", errors="ignore")
    return ch_path.read_text(encoding="utf-8", errors="ignore")


def chapter_files(ws_name: str, stem: str) -> list[Path]:
    """책 한 권의 본문 챕터 TXT — 파생물(_ko/_wiki/_bilingual/_clean)은 뺀다."""
    ch_dir = chapters_dir(ws_name, stem)
    if not ch_dir.exists():
        return []
    return sorted(f for f in ch_dir.glob("??_*.txt")
                  if not f.stem.endswith(_DERIVED))


def chapters_needing_clean(ws_name: str, stem: str) -> list[Path]:
    """자간정리가 필요한 챕터 — 번역본도 완성된 정리본도 아직 없는 한글 원문 챕터.
    진행 파일(_clean.progress.json)이 남아 있으면 판정을 일부만 받은 것이라 다시 대상이
    된다 — 이어서 남은 줄바꿈만 묻는다."""
    out = []
    for ch in chapter_files(ws_name, stem):
        if find_translation(ch):
            continue        # 번역본이 있으면 EPUB은 그걸 쓴다
        if (ch.with_name(ch.stem + "_clean.txt").exists()
                and not ch.with_name(ch.stem + "_clean.progress.json").exists()):
            continue        # 이미 끝까지 정리됨
        sample = ch.read_text(encoding="utf-8", errors="ignore")[:2000]
        if len(_HANGUL_RE.findall(sample)) / max(len(sample), 1) >= 0.3:
            out.append(ch)
    return out


def clean_book_chapters(ws_name: str, stem: str, engine: str,
                         progress_cb=None) -> tuple[bool, str]:
    """책 한 권의 한글 원문 챕터를 자간정리해 _clean.txt로 남긴다. (ok, msg).
    EPUB 생성에서 떼어낸 별도 단계다 — 오래 걸리는 AI 작업을 여기서 끝내두면
    EPUB 버튼은 항상 즉시 끝나고, 중간에 멈춰도 이미 정리된 챕터는 남는다."""
    targets = chapters_needing_clean(ws_name, stem)
    if not targets:
        return True, "자간정리할 한글 원문 챕터 없음"
    if not engine or ":" not in engine:
        return False, "사용 가능한 AI 없음"
    ok_n, fail = 0, []
    for i, ch in enumerate(targets, 1):
        _prefix = f"챕터 {i}/{len(targets)} — {ch.stem} · "
        _inner_cb = None
        if progress_cb:
            def _inner_cb(idx, total, joined_n, spaced_n, unknown_n, _p=_prefix):
                progress_cb(f"{_p}줄바꿈 {idx}/{total} "
                            f"(붙임 {joined_n}·공백 {spaced_n}·미판정 {unknown_n})")
            progress_cb(f"{_prefix}시작")
        _ok, _msg = clean_chapter_ko_lazy(ch, engine, progress_cb=_inner_cb)
        if _ok:
            ok_n += 1
        else:
            fail.append(f"{ch.stem}: {_msg}")
    if fail:
        return False, f"{ok_n}/{len(targets)}장 정리 · 실패 {len(fail)}: " + " / ".join(fail[:2])
    return True, f"{ok_n}장 자간정리 완료"


def clean_chapter_ko_lazy(ch_path: Path, engine: str, progress_cb=None):
    """services.translate를 함수 안에서 불러온다 — 모듈 로딩 순환을 피하려는 기존 방식 그대로."""
    from services.translate import clean_chapter_ko
    return clean_chapter_ko(ch_path, engine, progress_cb=progress_cb)


_CSS = """@namespace epub "http://www.idpf.org/2007/ops";
body { font-family: "Noto Serif KR", "Apple SD Gothic Neo", "Malgun Gothic", serif;
       line-height: 1.7; margin: 1.2em; }
h1 { font-size: 1.4em; text-align: center; margin: 2.5em 0 1.8em; }
p { margin: 0 0 1em; text-indent: 1em; }
nav ol { list-style: none; padding-left: 0; }
nav li { margin: 0.5em 0; }

/* 각주 — 팝업을 지원하는 읽개(애플 북스·Thorium 등)는 aside를 본문에 안 보이게
   두었다가 번호를 누르면 띄운다. 지원하지 않는 읽개에서는 장 끝에 모아 보여
   준다. 그래서 `display:none`을 쓰지 않는다 — 그러면 옛 읽개에서 각주가 통째로
   사라진다. */
a.noteref { text-decoration: none; }
a.noteref sup { font-size: 0.75em; vertical-align: super; }
section.footnotes { margin-top: 2.5em; border-top: 1px solid #999; padding-top: 1em;
                    font-size: 0.9em; }
aside.footnote p { text-indent: 0; margin: 0 0 0.5em; }
a.backref { text-decoration: none; margin-left: 0.3em; }
/* 표지 면 — 제목·저자·서지정보 (2026-08-27) */
.fm-title { margin: 3em 0 0.6em; font-size: 1.6em; line-height: 1.35;
            text-align: center; }
.fm-sub { margin: 0 0 0.8em; font-size: 1.15em;
          text-align: center; text-indent: 0; }
.fm-author { margin: 0 0 1.2em; font-size: 1.05em;
             text-align: right; text-indent: 0; }
.fm-cite { margin: 0; font-size: 0.9em; color: #555; line-height: 1.6;
           text-align: center; text-indent: 0; }
"""


_FN_DEF = re.compile(r"^\[\^([^\]]+)\]:\s*(.+)$", re.M)
_FN_REF = re.compile(r"\[\^([^\]]+)\]")


def _with_footnotes(text: str) -> tuple[str, str]:
    """본문을 EPUB3 각주로 바꾼다 — (본문 HTML, 각주 HTML) (2026-08-25 연구자 요청).

    ★Markdown 쪽에서 이미 하고 있던 일을 EPUB에서도 한다. 지금까지 EPUB은 각주를
    **본문 아래 맨숫자 덩어리**로 흘려보냈다. `epub:type="noteref"`/`"footnote"`를
    쓰면 읽는 이가 번호를 눌러 **그 자리에서 각주를 펴 볼 수 있다**(애플 북스·
    Thorium 등은 팝업으로 띄운다). 학위논문 자료에서 각주는 본문만큼 중요하다.

    각주를 찾는 일은 services/footnotes.convert가 이미 한다 — 그 결과(Markdown)를
    받아 표시만 바꾼다. **찾는 규칙을 두 벌로 만들지 않는다.**"""
    body_md, defs = _footnote_parts(text)
    body, used = _link_body(_body_html(body_md), defs)
    # 정의 순서를 지키고, 표시를 못 찾은 각주는 되돌아가기 화살표만 뺀다
    return body, _notes_section([(k, v, k in used) for k, v in defs.items()])


def _fid(k: str) -> str:
    """각주 번호를 XML id로 쓸 수 있게 다듬는다."""
    return re.sub(r"[^0-9A-Za-z_-]", "_", k)


def _footnote_parts(text: str) -> tuple[str, dict]:
    """(각주를 걷어낸 본문 Markdown, {번호: 각주 본문})."""
    try:
        from services import footnotes as _fn
        md = _fn.convert(text).markdown
    except Exception:
        md = text
    defs = {k: v.strip() for k, v in _FN_DEF.findall(md)}
    return _FN_DEF.sub("", md).strip(), defs


def _body_html(body_md: str) -> str:
    paras = [html.escape(p.strip()).replace("\n", "<br/>")
             for p in re.split(r"\n\s*\n", body_md) if p.strip()]
    return "\n".join(f"<p>{p}</p>" for p in paras) or "<p></p>"


def _link_body(body: str, defs: dict) -> tuple[str, list[str]]:
    """본문의 [^N]을 각주 링크로 바꾼다. (바뀐 본문, 실제로 쓰인 번호들 — 나온 순서)"""
    used: list[str] = []

    def _ref(m):
        k = m.group(1)
        if k not in defs:
            return m.group(0)
        if k not in used:
            used.append(k)
        return (f'<a epub:type="noteref" href="#fn-{_fid(k)}" id="ref-{_fid(k)}" '
                f'class="noteref"><sup>{html.escape(k)}</sup></a>')
    return _FN_REF.sub(_ref, body), used


def _notes_section(items: list[tuple[str, str, bool]]) -> str:
    """[(번호, 본문, 되돌아가기 화살표를 달까)] → 각주 구역 HTML."""
    if not items:
        return ""
    notes = "\n".join(
        f'<aside epub:type="footnote" id="fn-{_fid(k)}" class="footnote">'
        f'<p><sup>{html.escape(k)}</sup> {html.escape(v)}'
        + (f' <a href="#ref-{_fid(k)}" class="backref">↩</a>' if back else "")
        + "</p></aside>"
        for k, v, back in items)
    return f'\n<section epub:type="footnotes" class="footnotes">\n{notes}\n</section>'


# 다른 장에 정의가 있는 각주 번호를 본문에서 찾아낼 때 쓰는 잣대.
# services/footnotes._REF_IN_TEXT 와 같되 **뒤에 한글이 와도 인정**한다 — 번역본은
# 「…강함이라.”36라고 선택한」처럼 번호 뒤에 곧바로 한글이 붙는 일이 흔하다.
_ADOPT_REF = re.compile(r"(?<=[.,!?)\]”’\"'가-힣])(\d{1,3})(?=[\s.,)\]”’가-힣]|$)")


def _adopt_missing_refs(parts: list[tuple[str, dict]],
                        defs_all: dict) -> list[tuple[str, dict]]:
    """어느 장에서도 표시를 못 찾은 각주를, 본문에서 그 번호를 찾아 이어 준다.

    ★services/footnotes.convert 는 **같은 글 안에 정의가 있는 번호만** 표시로
    바꾼다. 논문 PDF는 쪽 아래 각주가 다음 장 제목 뒤로 밀려 나오는 일이 흔해서
    표시는 앞 장에, 정의는 뒷 장에 갈리곤 한다. Dorobantu 논문이 그랬다 —
    「…우리를 동물과 구별한다.34」는 03장에, 그 정의는 04장에 있었다.

    책 전체를 한 덩어리로 변환해 보기도 했는데 본문이 뒤섞여 못 쓴다(실측: 49k →
    25k자). 그래서 장별 변환은 그대로 두고, **정의는 있는데 표시가 어디에도 없는
    번호**만 골라 본문에서 그 자리를 찾아 붙인다. 대상이 좁아 오검출 위험이 적다 —
    이미 각주로 확인된 번호이고, 번호마다 첫 자리 한 곳에만 붙인다.
    """
    marked = set()
    for body_md, _defs in parts:
        marked.update(_FN_REF.findall(body_md))
    want = {k for k in defs_all if k not in marked}
    if not want:
        return parts

    out: list[tuple[str, dict]] = []
    for body_md, defs in parts:
        def _sub(m):
            k = m.group(1)
            if k in want:
                want.discard(k)             # 번호마다 첫 자리 한 곳만
                return f"[^{k}]"
            return m.group(0)
        out.append((_ADOPT_REF.sub(_sub, body_md), defs))
    return out


def _book_chapter_bodies(parts: list[tuple[str, dict]]) -> list[tuple[str, str]]:
    """책 전체를 한꺼번에 보고 장별 (본문 HTML, 각주 HTML)을 만든다.

    ★각주를 **제 표시가 있는 장으로 데려온다** (2026-08-27 연구자 보고 —
    "이펍책의 23, 33, 34, 35, 36번이 각주와 연결안되어 있어").

    지금까지는 장마다 따로 각주를 맞췄다. 그런데 논문 PDF는 쪽 아래 각주가
    **다음 장 제목 뒤로 밀려** 나오는 일이 흔하다. Dorobantu 논문이 그랬다 —
    34·35·36번 표시는 03장 끝에 있는데 그 정의는 04장 첫머리에 실렸다. 장별로
    맞추니 서로 만나지 못해 표시는 [^34] 그대로 남고 각주는 홀로 떠 있었다.

    이제 정의는 책 전체에서 모으고, 각주는 **표시를 만난 장에** 싣는다. 그러면
    링크가 같은 파일 안에서 닫히므로 되돌아가기 화살표도 제대로 걸린다.
    어느 장에서도 표시를 못 찾은 정의는 제가 실렸던 장에 그대로 남겨 둔다 —
    내용을 잃지 않기 위해서다(화살표만 뺀다).
    """
    defs_all: dict = {}
    for _body_md, defs in parts:
        for k, v in defs.items():
            defs_all.setdefault(k, v)
    # 장이 갈리며 표시를 잃은 각주를 본문에서 찾아 이어 준다
    parts = _adopt_missing_refs(parts, defs_all)

    bodies, used_per_ch, claimed = [], [], set()
    for body_md, _defs in parts:
        body, used = _link_body(_body_html(body_md), defs_all)
        bodies.append(body)
        used_per_ch.append(used)
        claimed.update(used)

    out: list[tuple[str, str]] = []
    for idx, (_body_md, defs) in enumerate(parts):
        items = [(k, defs_all[k], True) for k in used_per_ch[idx]]
        items += [(k, v, False) for k, v in defs.items() if k not in claimed]
        out.append((bodies[idx], _notes_section(items)))
    return out


def _chapter_xhtml_parts(title: str, body: str, notes: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">\n'
        f"<head><title>{html.escape(title)}</title>"
        '<link rel="stylesheet" type="text/css" href="../styles/style.css"/></head>\n'
        f"<body>\n<h1>{html.escape(title)}</h1>\n{body}{notes}\n</body>\n</html>"
    )


def _chapter_xhtml(title: str, text: str) -> str:
    body, notes = _with_footnotes(text)
    return _chapter_xhtml_parts(title, body, notes)


_CITATION_RE = re.compile(
    r"\(\s*(?:19|20)\d{2}\s*\)|"          # (2022)
    r"(?:19|20)\d{2}\s*[),]|"             # 2022) · 2022,
    r"\d{1,4}\s*[–—-]\s*\d{1,4}"          # 175–196 (쪽 범위)
)


def _front_lines(text: str, limit: int = 5) -> list[str]:
    """논문·책 첫머리에서 **제목·저자·서지정보 줄들**을 뽑는다 (2026-08-27).

    맨 앞 문단들 가운데 짧은 것이 곧 제목·부제·저자·저널 서지다. 초록이 시작되면
    거기서 멈춘다 — 그 뒤는 본문이다. 파일명은 사람이 붙인 것이라 'ImagoDei-in-the-
    Age-of-AI_CPOSAT2022' 처럼 읽기 나쁜 경우가 많아, 본문에서 뽑는 편이 낫다."""
    out: list[str] = []
    for para in text.split("\n\n"):
        s = " ".join(para.split())
        if not s:
            continue
        if re.match(r"^(초록|요약|Abstract|ABSTRACT)\b|^(초록|Abstract)\s*[::]", s):
            break
        if len(s) > 200:
            break
        out.append(s)
        if len(out) >= limit:
            break
    return out


def _book_meta(ws_name: str, stem: str) -> dict:
    """전체요약 파일 머리말에서 서지정보를 읽는다 — {author, published, publisher}.

    ★앱은 이미 표제지·판권면에서 저자·출판일·출판사를 뽑아 «_전체요약.md» 머리말에
    적어 둔다(chapters.build_overview). EPUB이 그걸 다시 짐작할 까닭이 없다
    (2026-08-27 연구자 요청 — "서지정보를 메타정보로 넣으면 더 좋겠다").
    요약을 아직 안 돌린 책은 이 파일이 없다 — 그러면 빈 dict 이고, 표지는 예전처럼
    본문 앞머리에서 뽑는다."""
    try:
        from services.chapters import overview_file_for
        p = overview_file_for(ws_name, stem)
        if not p.exists():
            return {}
        head = p.read_text(encoding="utf-8", errors="ignore").split("---")
        if len(head) < 2:
            return {}
        out = {}
        for ln in head[1].splitlines():
            m = re.match(r"^(author|published|publisher|category)\s*:\s*(.+)$", ln.strip())
            if m:
                out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
        return out
    except Exception:
        return {}


def _citation_text(meta: dict) -> str:
    """«뉴욕: 옥스퍼드 대학교 출판부, 2018.» 꼴의 서지 한 줄."""
    pub, year = meta.get("publisher", ""), meta.get("published", "")
    if pub and year:
        return f"{pub}, {year}."
    return (pub or year or "").strip()


def _norm(s: str) -> str:
    """견주기용 — 공백·괄호·구두점을 털어 낸다."""
    return re.sub(r"[\s()\[\]{}·,.:;'\"“”‘’-]", "", s).lower()


def _author_line(lines: list[str], author: str) -> tuple[str, list[str]]:
    """앞머리 줄들에서 **저자 줄**을 골라내 (저자 줄, 나머지)로 돌려준다.

    ★표제지의 첫 줄이 저자인 책이 많다 (2026-08-27 연구자 지적 — 『기술과 덕』
    표지에 "제목 아래 저자가 이름이 아니라 '기술'로 나와 있어"). 예전에는 첫 줄을
    제목, 마지막 줄을 저자로 못박아서, 첫 줄이 저자인 책은 **제목과 저자가 통째로
    뒤바뀌고** 표제지에서 흘러나온 조각("기술")이 저자로 찍혔다.

    파일 이름과 전체요약이 알려 주는 저자를 잣대로 삼아, 그 이름이 든 줄을
    저자로 집어낸다. 원문 줄에는 "섀넌 밸러(Shannon Vallor)"처럼 두 표기가 함께
    있는 일이 많아 그 줄을 그대로 쓰는 편이 낫다."""
    if not author:
        return "", lines
    key = _norm(author)
    if not key:
        return "", lines
    for i, s in enumerate(lines):
        n = _norm(s)
        if key and (key in n or n in key):
            return s, lines[:i] + lines[i + 1:]
    return "", lines


def _front_matter_xhtml(title: str, author: str, lines: list[str],
                        citation: str = "") -> str:
    """책 맨 앞에 놓을 표지 면 — 제목·부제·저자·서지정보 (2026-08-27 연구자 요청).

    제목·부제·서지는 가운데, 저자는 오른쪽 정렬(연구자 요청)."""
    parts: list[str] = []
    author_line, rest = _author_line(list(lines), author)
    if not author_line and not author and len(rest) >= 2:
        # 저자를 달리 알 길이 없으면 예전처럼 **마지막 줄**을 저자로 본다.
        # 논문은 «제목 / 부제 / 지은이» 차례로 적히는 일이 많다.
        author_line, rest = rest[-1], rest[:-1]
    if rest:
        head = rest[0]
        parts.append(f'<h1 class="fm-title">{html.escape(head)}</h1>')
        # 표제지가 제목을 여러 번 되뇌는 책이 많다("기술과 덕" → "기술과 덕목들" →
        # "기술"). 제목에 먹히거나 제목을 머금은 줄은 부제가 아니므로 버린다.
        hk = _norm(head)
        for s in rest[1:]:
            n = _norm(s)
            if not n or n in hk or hk in n:
                continue
            cls = "fm-cite" if _CITATION_RE.search(s) else "fm-sub"
            parts.append(f'<p class="{cls}">{html.escape(s)}</p>')
    else:
        parts.append(f'<h1 class="fm-title">{html.escape(title)}</h1>')
    if author_line or author:
        parts.append(f'<p class="fm-author">{html.escape(author_line or author)}</p>')
    if citation:
        parts.append(f'<p class="fm-cite">{html.escape(citation)}</p>')
    body = "\n    ".join(parts)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">\n'
        '  <head>\n'
        f'    <title>{html.escape(title)}</title>\n'
        '    <link rel="stylesheet" type="text/css" href="../styles/style.css"/>\n'
        '  </head>\n'
        '  <body epub:type="frontmatter">\n'
        f'    {body}\n'
        '  </body>\n'
        '</html>\n'
    )


def build_epub_from_chapters(ws_name: str, stem: str, out_dir: Path,
                              engine: str = "", clean: bool = False,
                              progress_cb=None) -> tuple[bool, str]:
    """책 한 권 분량 챕터 TXT를 한 EPUB로 합친다. (ok, 저장 경로 또는 오류 메시지).
    번역본(_ko.txt)·자간정리본(_clean.txt)이 있으면 그걸 쓰고, 없으면 원문 그대로다.
    clean=True로 부르면 정리본이 없는 한글 챕터를 그 자리에서 정리하지만(engine 필요),
    기본은 False다 — 자간정리는 clean_book_chapters로 떼어낸 별도 단계이고, 그래야
    EPUB 생성이 항상 즉시 끝난다(2026-08-14).
    progress_cb(text: str)가 있으면 챕터 진행을 실시간으로 알려준다."""
    if not chapters_dir(ws_name, stem).exists():
        return False, "챕터 폴더 없음"
    chapters = chapter_files(ws_name, stem)
    if not chapters:
        return False, "챕터 없음"

    title_disp, author = _split_title_author(stem)
    # 표제지·판권면에서 뽑아 둔 서지정보 — 있으면 파일 이름보다 정확하다
    meta = _book_meta(ws_name, stem)
    author = meta.get("author") or author
    citation = _citation_text(meta)
    book_id = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_DNS, f'mybookshelf-epub-{stem}')}"

    manifest_items, spine_items, nav_items, ncx_points, text_entries = [], [], [], [], []
    chapter_parts: list[tuple[str, dict]] = []   # 장별 (본문 md, 각주 정의)
    chapter_slots: list[tuple[str, str]] = []    # 장별 (파일 이름, 제목)
    first_text = ""
    for i, ch_path in enumerate(chapters, 1):
        # 부(部)가 지정된 책은 "제1부 원리론 · 정의와 평등"처럼 앞에 부를 붙인다
        try:
            from services.chapter_map import display_title as _disp_title
            ch_title = _disp_title(ws_name, stem, ch_path)
        except Exception:
            ch_title = re.sub(r"^\d+_", "", ch_path.stem)
        # 본문이 번역돼 있으면(=_ko.txt 존재) 제목도 번역본을 우선 쓴다 — "번역제목 (원제)"
        # 형태로, 번역 사이드카(_title_ko.txt, translate_one_chapter가 만듦)가 없으면
        # 원제 그대로(2026-08-11 — 본문은 번역됐는데 제목만 영문으로 남던 문제 수정).
        _ko_txt_path = find_translation(ch_path)
        if _ko_txt_path:
            # 사이드카 이름도 본문 번역본과 같은 언어 접미사를 쓴다.
            _suf = _ko_txt_path.stem[len(ch_path.stem):]
            _title_ko_path = ch_path.with_name(ch_path.stem + "_title" + _suf + ".txt")
            if _title_ko_path.exists():
                _ko_title = _title_ko_path.read_text(encoding="utf-8", errors="ignore").strip()
                if _ko_title:
                    ch_title = f"{_ko_title} ({ch_title})"
        _prefix = f"챕터 {i}/{len(chapters)} — {ch_title} · "
        if progress_cb:
            progress_cb(f"{_prefix}본문 읽는 중")
        text = _chapter_source_text(ch_path, engine=engine, clean=clean,
                                     progress_cb=progress_cb, prefix=_prefix)
        if i == 1:
            first_text = text
        fname = f"chap{i:03d}.xhtml"
        # ★각주는 책 전체를 본 뒤에 붙인다 — 표시와 정의가 다른 장에 갈릴 수 있어서
        #   (아래 _book_chapter_bodies 주석 참고). 여기서는 재료만 모아 둔다.
        chapter_parts.append(_footnote_parts(text))
        chapter_slots.append((f"OEBPS/text/{fname}", ch_title))
        manifest_items.append(
            f'<item id="chap{i:03d}" href="text/{fname}" media-type="application/xhtml+xml"/>')
        spine_items.append(f'<itemref idref="chap{i:03d}"/>')
        esc_title = html.escape(ch_title)
        nav_items.append(f'<li><a href="text/{fname}">{esc_title}</a></li>')
        ncx_points.append(
            f'<navPoint id="np{i}" playOrder="{i}"><navLabel><text>{esc_title}</text></navLabel>'
            f'<content src="text/{fname}"/></navPoint>')

    # 책 전체를 본 뒤에 장별 본문·각주를 만든다 — 표시와 정의가 다른 장에 갈려도
    # 이어 붙기 위해서다.
    for (fname, ch_title), (body, notes) in zip(chapter_slots,
                                                _book_chapter_bodies(chapter_parts)):
        text_entries.append((fname, _chapter_xhtml_parts(ch_title, body, notes)))

    # ★표지 면을 맨 앞에 둔다 (2026-08-27 연구자 요청: "책/논문 제목, 저자,
    # 서지정보까지 제일 처음에 표시해 주면 좋겠다").
    text_entries.insert(0, ("OEBPS/text/front.xhtml",
                            _front_matter_xhtml(title_disp, author,
                                                _front_lines(first_text), citation)))
    manifest_items.insert(
        0, '<item id="front" href="text/front.xhtml" media-type="application/xhtml+xml"/>')
    spine_items.insert(0, '<itemref idref="front"/>')

    # ★언어는 **책 단위로** 본다 (2026-08-27). 예전에는 첫 장 앞 2,000자의 한글
    #   비율만 봤는데, 그 자리는 표제지·판권면이라 영문 주소와 출판사 이름으로
    #   가득하다. 실측(『기술과 덕』) — 본문이 한국어인데 0.28로 갈려 en 이 됐다.
    #   여러 장을 골고루 뽑아 보는 detect_book 이 이미 있으니 그걸 쓴다.
    lang = ""
    try:
        from services import langdetect as _ld
        _texts = [find_translation(c) or c for c in chapters]
        lang, _conf = _ld.detect_book(_texts)
    except Exception:
        lang = ""
    if not lang:
        sample = first_text[:2000]
        lang = "ko" if len(_HANGUL_RE.findall(sample)) / max(len(sample), 1) >= 0.3 else "en"

    creator_tag = f"<dc:creator>{html.escape(author)}</dc:creator>" if author else ""
    # 저작권 있는 책 전문이 그대로 담기므로, 파일 자체에도 개인 사용 한정 안내를
    # 남겨둔다(공유·배포돼도 출처가 따라가도록, 2026-08-11).
    rights_text = "개인적인 사용 목적으로만 제작됨 — 배포·공유 금지 (저작권 보호 대상)"
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">\n'
        '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'    <dc:identifier id="bookid">{book_id}</dc:identifier>\n'
        f'    <dc:title>{html.escape(title_disp)}</dc:title>\n'
        f'    {creator_tag}\n'
        f'    <dc:language>{lang}</dc:language>\n'
        f'    <dc:rights>{html.escape(rights_text)}</dc:rights>\n'
        # 서지정보를 메타정보로 남긴다 (2026-08-27 연구자 요청 — "서지정보를
        # 메타정보로 넣으면 더 좋겠다"). 읽개·서재 앱이 출판사·출판연도로 정렬하고
        # 찾을 수 있고, 파일만 따로 돌아다녀도 출처가 함께 간다.
        + (f'    <dc:publisher>{html.escape(meta["publisher"])}</dc:publisher>\n'
           if meta.get("publisher") else "")
        + (f'    <dc:date>{html.escape(meta["published"])}</dc:date>\n'
           if meta.get("published") else "")
        + (f'    <dc:source>{html.escape(citation)}</dc:source>\n' if citation else "")
        + (f'    <dc:subject>{html.escape(meta["category"])}</dc:subject>\n'
           if meta.get("category") else "")
        + '  </metadata>\n'
        '  <manifest>\n'
        '    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>\n'
        '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>\n'
        '    <item id="css" href="styles/style.css" media-type="text/css"/>\n'
        + "\n".join(f"    {m}" for m in manifest_items) + "\n"
        '  </manifest>\n'
        '  <spine toc="ncx">\n'
        + "\n".join(f"    {s}" for s in spine_items) + "\n"
        '  </spine>\n'
        '</package>'
    )

    nav_xhtml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">\n'
        '<head><title>Contents</title></head>\n'
        '<body>\n<nav epub:type="toc" id="toc"><h1>Contents</h1><ol>\n'
        + "\n".join(nav_items) + "\n</ol></nav>\n</body>\n</html>"
    )

    ncx = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n'
        f'<head><meta name="dtb:uid" content="{book_id}"/></head>\n'
        f'<docTitle><text>{html.escape(title_disp)}</text></docTitle>\n'
        '<navMap>\n' + "\n".join(ncx_points) + "\n</navMap>\n</ncx>"
    )

    container_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        '  <rootfiles><rootfile full-path="OEBPS/content.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles>\n'
        '</container>'
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (_safe_name(title_disp) + ".epub")
    tmp_path = out_path.with_name(out_path.name + ".tmp")
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
            z.writestr("META-INF/container.xml", container_xml)
            z.writestr("OEBPS/content.opf", opf)
            z.writestr("OEBPS/nav.xhtml", nav_xhtml)
            z.writestr("OEBPS/toc.ncx", ncx)
            z.writestr("OEBPS/styles/style.css", _CSS)
            for arcname, content in text_entries:
                z.writestr(arcname, content)
        tmp_path.replace(out_path)
        return True, str(out_path)
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        return False, f"{type(e).__name__}: {str(e)[:150]}"
