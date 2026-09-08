"""Office text extraction without rasterizing tables or text boxes.

HWP5 record/control sizes follow Hancom's public file format 5.0 specification.
Floating objects use document order, which can differ from visual page order.
"""
from dataclasses import dataclass, field
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib


@dataclass
class Extraction:
    text: str
    method: str
    paragraphs: int = 0
    tables: int = 0
    textboxes: int | None = 0
    images: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def note(self) -> str:
        counts = f"문단 {self.paragraphs} · 표 {self.tables}"
        if self.textboxes is not None:
            counts += f" · 글상자 {self.textboxes}"
        return " · ".join([counts, *self.warnings])


def _name(el) -> str:
    return el.tag.rsplit("}", 1)[-1] if isinstance(el.tag, str) else ""


def _clean(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _xml_text(root, result: Extraction, *, word: bool = False, refs=None) -> str:
    """Visit each selected XML node once; repeated text is intentionally retained."""
    def walk(el):
        name = _name(el)
        if name in {"del", "moveFrom", "instrText", "delText", "header", "footer"}:
            return ""
        if name == "AlternateContent":
            # Word stores the same textbox in Choice and Fallback representations.
            child = next((c for c in el if _name(c) == "Choice"), None)
            if child is None:
                child = next((c for c in el if _name(c) == "Fallback"), None)
            return walk(child) if child is not None else ""
        if name == "t":
            return (el.text or "") + "".join(walk(c) + (c.tail or "") for c in el)
        if name in {"tab"}:
            return "\t"
        if name in {"br", "cr", "lineBreak"}:
            return "\n"
        if name in {"footnoteReference", "endnoteReference"} and refs is not None:
            ident = el.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id", "")
            key = ("footnote" if name == "footnoteReference" else "endnote", ident)
            if key not in refs:
                refs.append(key)
            return f"[^{key[0]}-{ident}]"
        if name in {"pic", "blip", "imagedata"}:
            result.images += 1
        if name in {"ole", "OLEObject", "altChunk"}:
            warning = "포함된 외부 개체의 내용은 별도 확인이 필요합니다"
            if warning not in result.warnings:
                result.warnings.append(warning)
        if name == "p":
            result.paragraphs += 1
        if name == "tbl":
            result.tables += 1
        if name in {"drawText", "txbxContent"}:
            result.textboxes += 1
        body = "".join(walk(c) for c in el)
        if name in {"drawText", "txbxContent", "tbl", "footNote", "endNote"}:
            return "\n" + body.strip("\n") + "\n"
        if name == "tc":
            return body.strip("\n") + "\t"
        if name == "tr":
            return body.rstrip("\t") + "\n"
        if name == "p":
            return body + "\n"
        return body
    return walk(root)


def _finish(result: Extraction) -> Extraction:
    result.text = _clean(result.text)
    if result.images:
        result.warnings.append(f"그림 {result.images}개는 OCR하지 않았습니다 — 그림 안 글자는 별도 확인하세요")
    return result


def extract_hwpx(path: Path) -> Extraction:
    result = Extraction("", "hwpx-xml")
    with zipfile.ZipFile(path) as archive:
        sections = sorted((n for n in archive.namelist()
                           if re.fullmatch(r"Contents/section\d+\.xml", n)),
                          key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
        if not sections:
            raise ValueError("HWPX 본문 구역을 찾지 못했습니다")
        result.text = "\n".join(_xml_text(ET.fromstring(archive.read(n)), result) for n in sections)
    return _finish(result)


def extract_docx(path: Path) -> Extraction:
    result = Extraction("", "docx-xml")
    refs = []
    with zipfile.ZipFile(path) as archive:
        result.text = _xml_text(ET.fromstring(archive.read("word/document.xml")), result,
                                word=True, refs=refs)
        for kind in ("footnote", "endnote"):
            part = f"word/{kind}s.xml"
            if part not in archive.namelist():
                continue
            notes = ET.fromstring(archive.read(part))
            by_id = {n.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id"): n
                     for n in notes}
            for ref_kind, ident in refs:
                if ref_kind == kind and ident in by_id:
                    result.text += f"\n[^{kind}-{ident}]: " + _xml_text(by_id[ident], result, word=True)
    return _finish(result)


def _hwp_paragraph(payload: bytes) -> str:
    if len(payload) % 2:
        raise ValueError("HWP 문단 텍스트 길이가 올바르지 않습니다")
    out = bytearray()
    pos = 0
    while pos < len(payload):
        code = struct.unpack_from("<H", payload, pos)[0]
        if code >= 32:
            out.extend(payload[pos:pos + 2])
            pos += 2
            continue
        size = 16 if 1 <= code <= 23 and code not in (10, 13) else 2
        if pos + size > len(payload):
            raise ValueError("HWP 문단의 제어 코드가 잘렸습니다")
        replacement = {9: "\t", 10: "\n", 13: "\n", 24: "-", 30: " ", 31: " "}.get(code, "")
        out.extend(replacement.encode("utf-16-le"))
        pos += size
    return out.decode("utf-16-le").strip("\n")


def _hwp_records(data: bytes):
    pos = 0
    while pos < len(data):
        if pos + 4 > len(data):
            raise ValueError("HWP 레코드 헤더가 잘렸습니다")
        header = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        tag, level, size = header & 1023, (header >> 10) & 1023, header >> 20
        if size == 4095:
            if pos + 4 > len(data):
                raise ValueError("HWP 확장 레코드 헤더가 잘렸습니다")
            size = struct.unpack_from("<I", data, pos)[0]
            pos += 4
        if pos + size > len(data):
            raise ValueError("HWP 레코드 본문이 잘렸습니다")
        yield tag, level, data[pos:pos + size]
        pos += size


def extract_hwp(path: Path) -> Extraction:
    """Read all PARA_TEXT records, including table-cell and drawing subparagraphs."""
    if zipfile.is_zipfile(path):
        return extract_hwpx(path)
    import olefile
    # Rectangles alone do not establish the number of text-bearing boxes.
    result = Extraction("", "hwp5-records", textboxes=None)
    with olefile.OleFileIO(str(path)) as ole:
        if not ole.exists("FileHeader"):
            raise ValueError("HWP 5.0 파일이 아닙니다. 한글에서 HWPX로 저장해 주세요")
        header = ole.openstream("FileHeader").read()
        if len(header) < 40 or not header.startswith(b"HWP Document File"):
            raise ValueError("HWP 파일 헤더가 올바르지 않습니다")
        flags = struct.unpack_from("<I", header, 36)[0]
        if flags & (2 | 4 | 16 | 256 | 1024):
            raise ValueError("암호·배포용·보안 HWP는 직접 추출할 수 없습니다. 한글에서 편집 가능한 HWPX로 저장해 주세요")
        sections = sorted((p for p in ole.listdir() if len(p) == 2 and p[0] == "BodyText"
                           and re.fullmatch(r"Section\d+", p[1])),
                          key=lambda p: int(p[1][7:]))
        if not sections:
            raise ValueError("HWP 본문 구역을 찾지 못했습니다")
        parts = []
        for section in sections:
            data = ole.openstream(section).read()
            if flags & 1:
                data = zlib.decompress(data, -15)
            for tag, level, payload in _hwp_records(data):
                if tag == 67:
                    parts.append(_hwp_paragraph(payload))
                    result.paragraphs += 1
                elif tag == 77:
                    result.tables += 1
                elif tag in (84, 85):
                    result.images += 1
        result.text = "\n".join(parts)
        result.warnings.append("중첩 문단까지 추출했습니다 — 표·도형의 읽기 순서는 원본과 비교하세요")
    return _finish(result)
