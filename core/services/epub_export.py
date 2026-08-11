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


def _chapter_source_text(ch_path: Path, engine: str = "", clean: bool = False) -> str:
    """번역본(_ko.txt)이 있으면 그걸, 없으면 원문(요청 시 AI 자간정리 후) 그대로.
    번역은 이미 그 자체로 OCR 잡음을 흡수하므로 정리 대상이 아니다 — 원문에만 적용."""
    ko = ch_path.with_name(ch_path.stem + "_ko.txt")
    if ko.exists():
        return ko.read_text(encoding="utf-8", errors="ignore")
    if clean and engine:
        from services.translate import clean_chapter_ko
        clean_path = ch_path.with_name(ch_path.stem + "_clean.txt")
        if not clean_path.exists():
            clean_chapter_ko(ch_path, engine)
        if clean_path.exists():
            return clean_path.read_text(encoding="utf-8", errors="ignore")
    return ch_path.read_text(encoding="utf-8", errors="ignore")


_CSS = """@namespace epub "http://www.idpf.org/2007/ops";
body { font-family: "Noto Serif KR", "Apple SD Gothic Neo", "Malgun Gothic", serif;
       line-height: 1.7; margin: 1.2em; }
h1 { font-size: 1.4em; text-align: center; margin: 2.5em 0 1.8em; }
p { margin: 0 0 1em; text-indent: 1em; }
nav ol { list-style: none; padding-left: 0; }
nav li { margin: 0.5em 0; }
"""


def _chapter_xhtml(title: str, text: str) -> str:
    paras = [html.escape(p.strip()).replace("\n", "<br/>")
             for p in re.split(r"\n\s*\n", text) if p.strip()]
    body = "\n".join(f"<p>{p}</p>" for p in paras) or "<p></p>"
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">\n'
        f"<head><title>{html.escape(title)}</title>"
        '<link rel="stylesheet" type="text/css" href="../styles/style.css"/></head>\n'
        f"<body>\n<h1>{html.escape(title)}</h1>\n{body}\n</body>\n</html>"
    )


def build_epub_from_chapters(ws_name: str, stem: str, out_dir: Path,
                              engine: str = "", clean: bool = False) -> tuple[bool, str]:
    """책 한 권 분량 챕터 TXT를 한 EPUB로 합친다. (ok, 저장 경로 또는 오류 메시지).
    clean=True면 번역본이 없는 한글 원문 챕터에 AI 자간정리를 적용(engine 필요)."""
    ch_dir = chapters_dir(ws_name, stem)
    if not ch_dir.exists():
        return False, "챕터 폴더 없음"
    chapters = sorted(
        f for f in ch_dir.glob("??_*.txt")
        if not f.stem.endswith(("_ko", "_wiki", "_bilingual", "_clean"))
    )
    if not chapters:
        return False, "챕터 없음"

    title_disp, author = _split_title_author(stem)
    book_id = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_DNS, f'mybookshelf-epub-{stem}')}"

    manifest_items, spine_items, nav_items, ncx_points, text_entries = [], [], [], [], []
    first_text = ""
    for i, ch_path in enumerate(chapters, 1):
        ch_title = re.sub(r"^\d+_", "", ch_path.stem)
        text = _chapter_source_text(ch_path, engine=engine, clean=clean)
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
