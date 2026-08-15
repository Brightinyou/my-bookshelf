"""PDF/DOCX/HWP/HWPX → TXT 변환 (pypdfium2 좌표 추출 + pdftotext 폴백,
office 문서는 python-docx·rhwp) + TXT 단독 처리."""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import config as cfg

from services.common import PDF_SUB, _nfc, append_log
from services.files import md_dir, txt_dir
from services.pipeline_queue import queue_add
from services import pdfcols, reflowlib

UPLOAD_TMP = cfg.UPLOAD_TMP
DONE_DIR   = cfg.DONE_DIR
FAILED_DIR = cfg.FAILED_DIR

# 텍스트 레이어가 없는 이미지 전용(스캔) 문서를 만났을 때의 신호 문구.
# _do_ocr_only가 이 값을 보고 needs_ocr 플래그를 세워 UI에서 OCR 안내 팝업을 띄운다.
OCR_REQUIRED_MSG = "이미지 전용 문서입니다 — TXT 분리를 위해서는 OCR 사전 처리 작업이 필요합니다."

# PDF 외에 텍스트 추출을 지원하는 오피스 문서 형식 (2026-07-25).
#   .docx        python-docx (이미 DOCX 내보내기용으로 씀)
#   .hwp/.hwpx   rhwp (Rust 기반 한글 문서 파서의 파이썬 바인딩)
OFFICE_EXTS = {".docx", ".hwp", ".hwpx"}
NO_TEXT_MSG = "문서에서 텍스트를 추출하지 못했습니다 (빈 문서이거나 내용이 이미지로만 되어 있을 수 있습니다)."
# 옛 OLE2 복합문서(.doc, HWP 5.0 등)를 확장자만 .docx로 잘못 저장한 경우 감지용
# (2026-07-25) — DOCX는 ZIP(PK\x03\x04)이므로 OLE2 서명(D0 CF 11 E0)이면 진짜 docx가 아니다.
_OLE2_SIG = b"\xd0\xcf\x11\xe0"
MISLABELED_MSG = "실제로는 .docx(ZIP) 형식이 아닙니다 — 옛 .doc나 한글(HWP) 파일을 확장자만 .docx로 저장했을 수 있습니다. 원본 프로그램에서 실제 형식을 확인해 주세요."


def _docx_to_text(path: Path) -> str:
    with open(path, "rb") as f:
        head = f.read(4)
    if head == _OLE2_SIG:
        raise ValueError(MISLABELED_MSG)
    from docx import Document
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


_IMAGE_PLACEHOLDER_RE = re.compile(r"^!\[[^\]]*\]\([^)]*\)$", re.MULTILINE)


def _hwp_to_text(path: Path) -> str:
    """HWP/HWPX → 텍스트. IR(to_ir) 기반 마크다운으로 표·목록·각주/미주를
    구조 보존해 뽑는다 — 평문 extract_text()는 표를 뭉갠다. IR 실패/빈 결과
    시에만 extract_text()로 안전망 폴백."""
    import rhwp
    doc = rhwp.parse(str(path))
    try:
        md = doc.to_ir().to_markdown()
    except Exception as e:
        append_log(f"WARN: {path.suffix} IR 변환 실패({type(e).__name__}), 평문 폴백")
        return doc.extract_text()
    # 이미지 자체는 텍스트 파이프라인에서 다루지 않음 — bin:// placeholder만 제거
    md = _IMAGE_PLACEHOLDER_RE.sub("", md)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md if md else doc.extract_text()


def office_to_txt(path: Path) -> tuple[Path | None, str, str]:
    """DOCX/HWP/HWPX → TXT 변환. 반환: (txt_path 또는 None, err, note)."""
    suf = path.suffix.lower()
    try:
        if suf == ".docx":
            text = _docx_to_text(path)
        elif suf in (".hwp", ".hwpx"):
            text = _hwp_to_text(path)
        else:
            return None, f"지원하지 않는 형식입니다: {suf}", ""
    except Exception as e:
        append_log(f"WARN: {suf} 추출 실패 ({type(e).__name__}) {str(e)[:160]}")
        return None, f"{suf} 파일을 읽지 못했습니다 ({type(e).__name__}: {str(e)[:160]})", ""
    if not text.strip():
        return None, NO_TEXT_MSG, ""
    txt_path = Path(tempfile.gettempdir()) / (path.stem + ".txt")
    txt_path.write_text(text, encoding="utf-8")
    return txt_path, "", ""


def _no_window_kwargs() -> dict:
    """Windows에서 콘솔 창이 뜨지 않도록 하는 subprocess 옵션."""
    if sys.platform == "win32":
        _si = subprocess.STARTUPINFO()
        _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        _si.wShowWindow = 0  # SW_HIDE
        return {"creationflags": subprocess.CREATE_NO_WINDOW, "startupinfo": _si,
                "stdin": subprocess.DEVNULL}
    return {}


def _pdftotext_fallback(pdf_path: Path) -> str:
    """pypdfium2 추출이 실패했을 때의 폴백 — pdftotext(기본 모드) + reflow."""
    pdftotext = cfg.PDFTOTEXT
    if not pdftotext or not Path(pdftotext).exists():
        return ""
    tmp = Path(tempfile.gettempdir()) / (pdf_path.stem + ".fallback.txt")
    try:
        r = subprocess.run([pdftotext, str(pdf_path), str(tmp)],
                           capture_output=True, text=True, **_no_window_kwargs())
        if r.returncode != 0 or not tmp.exists():
            return ""
        raw = tmp.read_text(encoding="utf-8", errors="ignore")
        return reflowlib.clean_default_text(raw)
    except Exception as e:
        append_log(f"WARN: pdftotext 폴백 실패 ({type(e).__name__}) {str(e)[:120]}")
        return ""
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


_LONG_TOKEN_MIN = 26


def _token_health(text: str) -> float:
    """비정상적으로 긴(붙어버린) 토큰의 비율 — 낮을수록 띄어쓰기가 정상(0~1)."""
    toks = text.split()
    if not toks:
        return 1.0
    longs = sum(1 for w in toks if len(w) >= _LONG_TOKEN_MIN)
    return longs / len(toks)


def pdf_to_txt(pdf_path: Path, fast: bool = True) -> tuple[Path | None, Path | None, str, str]:
    """텍스트 레이어가 있는 PDF를 TXT로 변환한다. (2026-07-11 좌표 기반으로 개편)
    1차: pypdfium2 좌표 기반 다단 추출(논문·뉴스레터·한글+영어·N단 처리).
    2차(안전망②): 결과가 비정상이거나 비면 pdftotext 폴백과 비교해 나은 쪽 채택.
    반환: (txt_path, md_path, err, note) — note는 사용자에게 알릴 상황 설명(있을 때)."""
    txt_path = Path(tempfile.gettempdir()) / (pdf_path.stem + ".txt")

    text, skipped = "", 0
    try:
        text, skipped = pdfcols.pdf_to_text(pdf_path)
    except Exception as e:
        append_log(f"WARN: 좌표 추출 실패 → pdftotext 폴백 ({type(e).__name__}) {str(e)[:120]}")

    used_fallback = False
    # 안전망②: 좌표 추출 결과가 비정상(띄어쓰기 붕괴 등)이면 pdftotext와 품질 비교 → 나은 쪽
    if text.strip() and _token_health(text) > 0.03:
        fb = _pdftotext_fallback(pdf_path)
        if fb.strip() and _token_health(fb) < _token_health(text):
            text, used_fallback = fb, True
            append_log(f"좌표 추출 품질 저하 감지 → pdftotext 결과 채택: {pdf_path.name}")

    # 좌표 추출이 아예 비면 폴백
    if not text.strip():
        text = _pdftotext_fallback(pdf_path)
        used_fallback = bool(text.strip())

    # 실질 내용이 없으면 텍스트 레이어가 없는 이미지 전용(스캔) 문서 → OCR 선행 필요
    if not text.strip():
        return None, None, OCR_REQUIRED_MSG, ""

    notes = []
    if skipped:
        notes.append(f"읽지 못한 {skipped}개 페이지를 건너뛰었습니다")
    if used_fallback:
        notes.append("레이아웃이 복잡해 대체 추출 방식을 사용했습니다(다단 정렬이 다를 수 있음)")

    txt_path.write_text(text, encoding="utf-8")
    return txt_path, None, "", " · ".join(notes)


# ─── TXT 단독 처리 (번역·위키 생략) ─────────────────────────

def _do_ocr_only(uf, ws_name: str, fast: bool = False) -> dict:
    """PDF/DOCX/HWP/HWPX → TXT 변환만 수행. fast=True이면 PDF는 pdftotext 직접 추출."""
    dest = UPLOAD_TMP / uf.name
    _src = getattr(uf, "_p", None)
    if not (_src and Path(_src).resolve() == dest.resolve()):
        uf.seek(0)
        with open(dest, "wb") as f:
            f.write(uf.read())
    _suf = dest.suffix.lower()
    if _suf not in {".pdf", *OFFICE_EXTS}:
        txt_dir(DONE_DIR, ws_name).mkdir(parents=True, exist_ok=True)
        final = txt_dir(DONE_DIR, ws_name) / dest.name
        shutil.move(str(dest), str(final))
        append_log(f"TXT 직접 업로드: {final.name}")
        queue_add("tab2_ready", [_nfc(Path(final).stem)])   # → 장별분할 큐
        return {"ok": True, "name": uf.name, "txt_path": str(final), "md_path": "", "error": ""}
    if _suf == ".pdf":
        txt_path, md_src, err, note = pdf_to_txt(dest, fast=fast)
    else:
        txt_path, err, note = office_to_txt(dest)
        md_src = None
    if not txt_path:
        _needs_ocr = (err == OCR_REQUIRED_MSG)
        try: shutil.move(str(dest), str(FAILED_DIR / uf.name))
        except Exception: pass
        append_log(f"{'OCR 필요' if _needs_ocr else 'ERROR: TXT 변환 실패'} — {uf.name}: {err}")
        return {"ok": False, "name": uf.name, "txt_path": "", "md_path": "",
                "error": err, "needs_ocr": _needs_ocr, "note": ""}
    orig_save_dir2 = cfg.PDF_DIR   # 원본 보관 폴더 — PDF 외 오피스 문서 원본도 여기 보관
    orig_save_dir2.mkdir(parents=True, exist_ok=True)
    final_orig = orig_save_dir2 / uf.name
    shutil.move(str(dest), str(final_orig))
    txt_dir(DONE_DIR, ws_name).mkdir(parents=True, exist_ok=True)
    final_txt = txt_dir(DONE_DIR, ws_name) / txt_path.name   # 항상 1_txt/에 저장
    shutil.move(str(txt_path), str(final_txt))
    if md_src and md_src.exists():
        md_dir(DONE_DIR, ws_name).mkdir(parents=True, exist_ok=True)
        final_md = md_dir(DONE_DIR, ws_name) / md_src.name
        shutil.move(str(md_src), str(final_md))
    else:
        final_md = None
    append_log(f"TXT 변환 완료: {uf.name} → {Path(final_txt).name}"
               + (f" ({note})" if note else ""))
    queue_add("tab2_ready", [_nfc(Path(final_txt).stem)])   # → 장별분할 큐 등록
    return {"ok": True, "name": uf.name, "txt_path": str(final_txt),
            "md_path": str(final_md) if final_md else "", "error": "", "note": note}
