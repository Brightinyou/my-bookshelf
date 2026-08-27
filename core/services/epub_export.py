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
.fm-title { margin: 3em 0 0.6em; font-size: 1.6em; line-height: 1.35; }
.fm-author { margin: 0 0 1.2em; font-size: 1.05em; }
.fm-cite { margin: 0; font-size: 0.9em; color: #555; line-height: 1.6; }
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
    try:
        from services import footnotes as _fn
        md = _fn.convert(text).markdown
    except Exception:
        md = text
    defs = {k: v.strip() for k, v in _FN_DEF.findall(md)}
    body_md = _FN_DEF.sub("", md).strip()

    paras = [html.escape(p.strip()).replace("\n", "<br/>")
             for p in re.split(r"\n\s*\n", body_md) if p.strip()]
    body = "\n".join(f"<p>{p}</p>" for p in paras) or "<p></p>"

    def _ref(m):
        k = m.group(1)
        if k not in defs:
            return m.group(0)
        kid = re.sub(r"[^0-9A-Za-z_-]", "_", k)
        return (f'<a epub:type="noteref" href="#fn-{kid}" id="ref-{kid}" '
                f'class="noteref"><sup>{html.escape(k)}</sup></a>')
    body = _FN_REF.sub(_ref, body)

    notes = "\n".join(
        f'<aside epub:type="footnote" id="fn-{re.sub(r"[^0-9A-Za-z_-]", "_", k)}" '
        f'class="footnote"><p><sup>{html.escape(k)}</sup> {html.escape(v)} '
        f'<a href="#ref-{re.sub(r"[^0-9A-Za-z_-]", "_", k)}" class="backref">↩</a></p></aside>'
        for k, v in defs.items())
    return body, (f'\n<section epub:type="footnotes" class="footnotes">\n{notes}\n</section>'
                  if notes else "")


def _chapter_xhtml(title: str, text: str) -> str:
    body, notes = _with_footnotes(text)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">\n'
        f"<head><title>{html.escape(title)}</title>"
        '<link rel="stylesheet" type="text/css" href="../styles/style.css"/></head>\n'
        f"<body>\n<h1>{html.escape(title)}</h1>\n{body}{notes}\n</body>\n</html>"
    )


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


def _front_matter_xhtml(title: str, author: str, lines: list[str]) -> str:
    """책 맨 앞에 놓을 표지 면 — 제목·저자·서지정보 (2026-08-27 연구자 요청)."""
    parts: list[str] = []
    if lines:
        parts.append(f'<h1 class="fm-title">{html.escape(lines[0])}</h1>')
        for s in lines[1:]:
            cls = "fm-cite" if _CITATION_RE.search(s) else "fm-author"
            parts.append(f'<p class="{cls}">{html.escape(s)}</p>')
    else:
        parts.append(f'<h1 class="fm-title">{html.escape(title)}</h1>')
        if author:
            parts.append(f'<p class="fm-author">{html.escape(author)}</p>')
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
    book_id = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_DNS, f'mybookshelf-epub-{stem}')}"

    manifest_items, spine_items, nav_items, ncx_points, text_entries = [], [], [], [], []
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
        text_entries.append((f"OEBPS/text/{fname}", _chapter_xhtml(ch_title, text)))
        manifest_items.append(
            f'<item id="chap{i:03d}" href="text/{fname}" media-type="application/xhtml+xml"/>')
        spine_items.append(f'<itemref idref="chap{i:03d}"/>')
        esc_title = html.escape(ch_title)
        nav_items.append(f'<li><a href="text/{fname}">{esc_title}</a></li>')
        ncx_points.append(
            f'<navPoint id="np{i}" playOrder="{i}"><navLabel><text>{esc_title}</text></navLabel>'
            f'<content src="text/{fname}"/></navPoint>')

    # ★표지 면을 맨 앞에 둔다 (2026-08-27 연구자 요청: "책/논문 제목, 저자,
    # 서지정보까지 제일 처음에 표시해 주면 좋겠다").
    text_entries.insert(0, ("OEBPS/text/front.xhtml",
                            _front_matter_xhtml(title_disp, author,
                                                _front_lines(first_text))))
    manifest_items.insert(
        0, '<item id="front" href="text/front.xhtml" media-type="application/xhtml+xml"/>')
    spine_items.insert(0, '<itemref idref="front"/>')

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
        '  </metadata>\n'
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
