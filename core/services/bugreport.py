"""오류 보고 — 로그 묶음을 만들어 개발자에게 메일로 보내게 돕는다 (2026-10-30 연구자 요청).

"오류 발생시 로그파일과 함께 개발자에게 이메일할 수 있도록." 메일 링크(mailto)로는
파일을 붙일 수 없다. 그래서 세 가지를 한꺼번에 한다.
  1. 로그를 모아 개인 정보를 가린 zip 을 로그 폴더 아래 reports 폴더에 저장한다.
  2. 메일 프로그램에 개발자 주소·제목·요약을 채운 새 메일을 연다.
  3. 탐색기(Finder)에서 그 zip 을 골라 보여 준다 — 메일에 끌어다 붙이면 된다.
보내는 일은 사용자가 직접 한다. 책 본문은 로그에 원래 들어가지 않고, 컴퓨터 사용자
이름·메일·전화번호는 문제 도우미와 같은 규칙(helper.redact)으로 가린다.
"""
from __future__ import annotations

import os
import platform
import re
import subprocess
import sys
import tempfile
import webbrowser
import zipfile
from datetime import datetime
from pathlib import Path

import config as cfg
from services import helper
from services.common import append_log
from version import APP_VERSION

# 로그 한 파일에서 묶음에 넣는 최대 줄 수 — 메일 첨부로 무리가 없을 만큼
_TAIL_LINES = 3000
# «오류»로 보는 로그 줄. 앱은 실패를 append_log("ERROR: …")·"…실패…"로 남긴다.
_ERROR_LINE = re.compile(r"ERROR|Traceback|Exception|오류|실패|경고:")
# 실패를 다룬 줄이지만 오류가 아닌 것 — «(무시)» 표시가 붙은 확인 실패 등
_NOT_ERROR = re.compile(r"\(무시\)|실패보존 0|실패 0")


def log_files() -> list[tuple[str, Path]]:
    """묶음에 넣을 로그 — (zip 안 이름, 경로). 없는 파일은 뺀다."""
    cands = [("upload.log", cfg.LOG_FILE),
             ("pipeline_results.json", cfg.RESULTS_FILE),
             ("update_windows.log", Path(tempfile.gettempdir()) / "mybookshelf_update.log"),
             ("update_mac.log",
              Path.home() / "Library/Application Support/MyBookshelf/update.log"),
             ("install.log", Path(cfg.__file__).resolve().parent.parent / "install.log")]
    try:   # 위키 생성 로그는 날짜별 파일 — 가장 최근 것 하나
        wiki_logs = sorted(Path(cfg.WIKI_LOG_DIR).glob("gemini_wiki_*.log"))
        if wiki_logs:
            cands.append((wiki_logs[-1].name, wiki_logs[-1]))
    except OSError:
        pass
    return [(name, p) for name, p in cands if p and Path(p).is_file()]


def _tail(path: Path, n: int = _TAIL_LINES) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return f"(읽지 못함: {exc})"
    return "\n".join(lines[-n:])


def _tail_bytes(path: Path, max_bytes: int = 512 * 1024) -> list[str]:
    """파일 끝부분만 읽는다 — 오류 알림은 화면을 다시 그릴 때마다 묻는데, 앱 로그는
    몇 MB까지 자란다."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_bytes))
            data = f.read()
    except OSError:
        return []
    lines = data.decode("utf-8", errors="replace").splitlines()
    return lines[1:] if size > max_bytes else lines     # 잘린 첫 줄은 버린다


def recent_errors(n: int = 15) -> list[str]:
    """앱 로그에서 최근 오류 줄 — 화면에 보여 주고 메일 본문에 넣는다(가린 뒤)."""
    lines = _tail_bytes(Path(cfg.LOG_FILE))
    hits = [ln for ln in lines if _ERROR_LINE.search(ln) and not _NOT_ERROR.search(ln)]
    return [helper.redact(ln)[:300] for ln in hits[-n:]]


def last_error_stamp() -> str:
    """가장 최근 오류 줄의 시각 «[YYYY-MM-DD HH:MM:SS]» — 새 오류가 생겼는지 가릴 때 쓴다."""
    errs = recent_errors(1)
    m = re.match(r"\[([^\]]+)\]", errs[0]) if errs else None
    return m.group(1) if m else ""


def environment() -> str:
    return "\n".join([f"앱: {APP_VERSION}",
                      f"운영체제: {platform.platform()}",
                      f"파이썬: {platform.python_version()}",
                      f"만든 때: {datetime.now():%Y-%m-%d %H:%M:%S}"])


def build_bundle(note: str = "") -> Path:
    """가린 로그와 환경 정보를 담은 zip 을 만들고 경로를 돌려준다."""
    out_dir = Path(cfg.LOG_DIR) / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"mybookshelf_error_report_{datetime.now():%Y%m%d_%H%M%S}.zip"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", helper.redact(
            "My Bookshelf 오류 보고 묶음\n\n"
            + environment() + "\n\n## 사용자 설명\n" + (note.strip() or "(없음)") + "\n"))
        for name, path in log_files():
            z.writestr(name, helper.redact(_tail(path)))
    append_log(f"오류 보고 묶음 저장: {dest.name}")
    return dest


def mail_title() -> str:
    return f"[My Bookshelf 오류 보고] {APP_VERSION}"


def mail_body(note: str, bundle: Path | None) -> str:
    lines = ["## 무슨 일이 있었나요", note.strip() or "(설명 없음)", "",
             "## 환경", environment()]
    errs = recent_errors(8)
    if errs:
        lines += ["", "## 최근 오류 기록"] + errs
    lines += ["", "## 첨부",
              (f"로그 묶음 파일을 이 메일에 붙여 주세요: {bundle.name}" if bundle
               else "앱의 «설정 → 오류 보고»에서 로그 묶음을 저장해 붙여 주세요.")]
    return helper.redact("\n".join(lines))


def mail_url(note: str, bundle: Path | None) -> str:
    return helper.mailto_url(mail_title(), mail_body(note, bundle))


def open_mail(url: str) -> bool:
    """기본 메일 프로그램에 새 메일을 연다. 앱 창(WebView) 안의 링크는 mailto 를
    처리하지 못하는 일이 있어, 서버(같은 컴퓨터) 쪽에서 운영체제에 넘긴다."""
    try:
        if sys.platform == "win32":
            os.startfile(url)                       # noqa: S606 — 사용자가 누른 단추
        elif sys.platform == "darwin":
            subprocess.Popen(["open", url])
        else:
            webbrowser.open(url)
        return True
    except Exception as exc:
        append_log(f"메일 프로그램 열기 실패: {type(exc).__name__} {str(exc)[:80]}")
        return False


def reveal(path: Path) -> None:
    """탐색기(Finder)에서 파일을 골라 보여 준다 — 메일에 끌어다 붙이기 쉽게."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", f"/select,{path}"])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except Exception as exc:
        append_log(f"보고 묶음 위치 열기 실패: {type(exc).__name__} {str(exc)[:80]}")
