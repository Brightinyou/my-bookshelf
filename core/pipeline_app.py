#!/usr/bin/env python3
"""My Bookshelf — PDF→Wiki 파이프라인 (Streamlit GUI)"""

import json
import os
import hashlib
from difflib import SequenceMatcher
import shutil
import ssl
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parent
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import pandas as pd
import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

import config as cfg
import llm_providers as llm
from version import APP_VERSION

# ── 처리 로직 서비스 (2026-07-03 pipeline_app.py에서 분리) ──
# UI 코드가 기존 이름 그대로 쓰도록 명시적으로 재노출한다.
from services import ai_ocr
from services import chapter_map as cmap
from services import textquality
from services import toc as toc_svc
from services import wiki as wiki_svc
from services.common import (
    DEFAULT_WS, MD_SUB, PAUSE_DIR, PDF_SUB, TRANS_SUB, TXT_SUB,
    _PathAsUpload, _nfc, _save_json_atomic, append_log, is_paused,
    load_pipeline_results, notify, open_path, open_pdf_view, pause_flag_path, read_log,
    save_pipeline_results, set_paused,
)
from services.files import (
    _bilingual_candidates, _ko_block_count, _move_unassigned_to_ws,
    _parse_bilingual_block, _save_bilingual_atomic, _save_en_ko_split,
    collect_cross_ws_cache, find_bilingual, find_cross_ws_bilingual,
    find_md, find_pdf, find_split_mds, find_txt, md_dir, processed_stems,
    translated_dir, txt_dir,
)
from services.pipeline_queue import (
    queue_add, queue_clear, queue_list, queue_remove,
)
from services.convert import OCR_REQUIRED_MSG, _do_ocr_only, pdf_to_txt
from services import updater
from services.translate import (
    DERIVED_SUFFIXES as _DERIVED, find_translation, has_translation, out_suffix,
    _needs_translation, _paragraph_already_target, _split_paragraphs_robust,
    _translate_paragraph, _translation_is_valid, book_language, build_translate_system,
    engine_label, find_sequential_footnotes, find_skip_section_paragraphs,
    language_name, needs_translation, set_target_language, should_drop_paragraph,
    source_language, target_language, target_language_name, target_language_options,
    should_skip_translation, translate, translate_engine_options,
    translate_one_chapter,
)
from services.chapters import (
    _is_small_document_for_whole_translation,
    _write_single_chapter_from_text, chapters_dir, list_done_books,
    find_overview_file, list_summary_files,
    load_summary_file, split_book_to_chapters, summarize_book_overview,
    summarize_one_chapter, summary_file_for, LAST_SPLIT_WARNING, SPLIT_MODE_LABELS,
)
from services.papers import (
    download_paper_source, prepare_downloaded_paper_source,
    translate_downloaded_paper,
)
from services.wiki import (
    build_single_chapter_wiki, build_wiki_from_chapter_summaries,
    check_wiki_orphans, ensure_obsidian_vault, list_obsidian_vaults,
    open_in_obsidian, open_wiki_vault, set_wiki_dir, wiki_generator_running,
)
from services.docx_export import build_docx_from_chapter_summaries, set_docx_dir
from services.hwpx_export import build_hwpx_from_chapter_summaries, set_hwpx_dir
from services.epub_export import (
    build_epub_from_chapters, chapters_needing_clean, clean_book_chapters, set_epub_dir,
)
from services.i18n import get_lang, set_lang, t, tf

# ── 설정 ─────────────────────────────────────────────────
# 기계 의존 값(경로·바이너리·분류 폴더)은 전부 config.py가 해석한다.
# 기본값 ~/Documents/My Bookshelf, 덮어쓰기 ~/.config/mybookshelf/config.json.
WORKSPACES = cfg.WORKSPACES   # 보관 폴더 이름 목록. 첫 항목이 기본값.

UPLOAD_TMP    = cfg.UPLOAD_TMP
RAW_DIR       = cfg.RAW_DIR
WIKI_DIR      = cfg.WIKI_DIR
PROCESSED_DIR = cfg.PROCESSED_DIR
DONE_DIR      = cfg.DONE_DIR
OLD_DONE_DIR  = cfg.OLD_DONE_DIR            # 옛 fallback (사용 안 함, 호환용)
FAILED_DIR    = cfg.FAILED_DIR
# translated/는 done/<ws>/_translated/로 통합 (2026-05-18).
# OLD_TRANSLATED_DIR은 데이터 이동 이전 옛 위치 — fallback 용도로만 유지.
OLD_TRANSLATED_DIR = cfg.OLD_TRANSLATED_DIR
LOG_FILE      = cfg.LOG_FILE
RESULTS_FILE  = cfg.RESULTS_FILE

from services import migrate as _migrate
_migrate.ensure_layout()   # v0.9.0 폴더 재구성 — 옛 데이터 자동 이동 (1회)
for _d in [cfg.UPLOAD_TMP, cfg.PDF_DIR, cfg.TXT_DIR, cfg.CHAPTERS_DIR,
           FAILED_DIR, WIKI_DIR, LOG_FILE.parent, RESULTS_FILE.parent]:
    _d.mkdir(parents=True, exist_ok=True)

CATEGORY_ICONS: dict[str, str] = {}  # 워크스페이스 이름 → 이모지. 빈 경우 기본 📚 사용

import re as _re

# ── UI 래퍼: 세션에서 고른 보관함(Vault)을 위키 서비스에 전달 ──────
def trigger_gemini_wiki(txt_path: Path) -> bool:
    return wiki_svc.trigger_gemini_wiki(txt_path, st.session_state.get("wiki_target_dir"))


def trigger_wiki_generation() -> int:
    return wiki_svc.trigger_wiki_generation(st.session_state.get("wiki_target_dir"))



# ── UI ────────────────────────────────────────────────────

def _find_app_icon(name: str) -> Path | None:
    """MyBookshelf.iconset/<name>을 여러 후보 위치에서 찾는다.
    - 개발 트리: core/ 의 부모(레포 루트)
    - .app 번들: Resources/ (pipeline_app.py와 같은 폴더)
    - SSD 실행본: pipeline_app.py와 같은 폴더"""
    here = Path(__file__).resolve().parent
    for base in (here.parent, here, here.parent / "platform" / "windows"):
        p = base / "MyBookshelf.iconset" / name
        if p.exists():
            return p
    return None

_icon_path = _find_app_icon("icon_32x32.png")
_page_icon = str(_icon_path) if _icon_path else "📚"
st.set_page_config(page_title="My Bookshelf", page_icon=_page_icon, layout="wide")

# Cmd/Ctrl+C(복사) 시 뜨던 'Clear caches' 개발자 대화상자는 client.toolbarMode="minimal"
# (.streamlit/config.toml + 실행 플래그)로 개발자 툴바·단축키를 끄면서 제거된다. (2026-07-10)

if "ui_font_scale" not in st.session_state:
    st.session_state["ui_font_scale"] = 1.0

def _font_scale_controls():
    cur = float(st.session_state.get("ui_font_scale", 1.0))
    c1, c2, c3 = st.columns([0.75, 1, 0.75])
    if c1.button("", icon=":material/text_decrease:", key="font_size_minus", use_container_width=True, help="글자 크기 줄이기"):
        st.session_state["ui_font_scale"] = max(0.85, round(cur - 0.05, 2))
        st.rerun()
    c2.markdown(
        f"<div style='text-align:center;color:#6b7280;font-size:0.82rem;line-height:2.35'>"
        f"{int(cur * 100)}%</div>",
        unsafe_allow_html=True,
    )
    if c3.button("", icon=":material/text_increase:", key="font_size_plus", use_container_width=True, help="글자 크기 키우기"):
        st.session_state["ui_font_scale"] = min(1.35, round(cur + 0.05, 2))
        st.rerun()

# 로딩 오버레이 — 세션 최초 진입 시에만 표시 (LLM 작업 중 재렌더링 때는 건너뜀)
_loading_ph = st.empty()

def _loading_step(msg: str, sub: str = "잠시만 기다려 주세요") -> None:
    """로딩 오버레이 메시지 갱신. 첫 진입 시에만 동작."""
    if st.session_state.get("_app_loaded"):
        return
    _loading_ph.markdown(
        "<div style='position:fixed;top:0;left:0;width:100%;height:100%;"
        "background:rgba(255,255,255,0.96);z-index:9999;"
        "display:flex;justify-content:center;align-items:center;"
        "flex-direction:column;gap:14px'>"
        "<div style='font-size:2.4rem'>📚</div>"
        f"<div style='font-size:1.15rem;color:#374151;font-weight:600'>{msg}</div>"
        f"<div style='color:#9ca3af;font-size:0.88rem'>{sub}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

_loading_step("My Bookshelf 실행 중…")

# ── 글로벌 스타일 (2026-05-18 v2 — Linear·Vercel 톤) ────────────
# 잔잔한 segmented control + 모노톤 칩. 선택된 것만 도드라지는 미감.
_ui_font_scale = float(st.session_state.get("ui_font_scale", 1.0))
st.markdown("""
<style>
:root {
    --mb-font-scale: __MB_FONT_SCALE__;
}
/* 앱 상단 기본 여백 축소 */
[data-testid="stHeader"],
header[data-testid="stHeader"] {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    background: transparent !important;
}
[data-testid="stToolbar"],
[data-testid="stDecoration"],
#MainMenu {
    display: none !important;
}
.block-container,
[data-testid="stAppViewContainer"] .block-container,
[data-testid="stAppViewContainer"] section.main .block-container {
    padding-top: 1.25rem !important;
    padding-bottom: 2.25rem !important;
    margin-top: 0 !important;
}

/* === 탭 — Segmented Control (macOS/iOS 영감) === */
.stTabs [data-baseweb="tab-list"] {
    gap: 2px;
    background-color: rgba(0, 0, 0, 0.04);
    padding: 4px;
    border-radius: 10px;
    border: 1px solid rgba(0, 0, 0, 0.05);
    display: inline-flex;
    margin-bottom: 16px;
}
.stTabs [data-baseweb="tab-list"] [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-list"] [data-baseweb="tab-border"] {
    display: none !important;
}
.stTabs [data-baseweb="tab"] {
    height: 38px;
    padding: 0 18px;
    background-color: transparent;
    border: none !important;
    border-radius: 7px;
    color: #6b7280;
    transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
}
.stTabs [data-baseweb="tab"] p {
    font-size: 14.5px !important;
    font-weight: 500 !important;
    margin: 0 !important;
    letter-spacing: -0.008em;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #1f2937;
    background-color: rgba(255, 255, 255, 0.55);
}
.stTabs [aria-selected="true"] {
    background-color: white !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06),
                0 1px 2px rgba(0, 0, 0, 0.04);
}
.stTabs [aria-selected="true"] p {
    color: #111827 !important;
    font-weight: 600 !important;
}

/* === 라디오 — 모노톤 칩 (Vercel/Linear 영감) === */
div[data-testid="stRadio"] > label > div > p {
    font-size: 14px !important;
    font-weight: 500 !important;
    color: #6b7280 !important;
    margin-bottom: 10px !important;
    letter-spacing: -0.005em;
    text-transform: uppercase;
    font-size: 12px !important;
    letter-spacing: 0.05em;
}
div[data-testid="stRadio"] div[role="radiogroup"] {
    gap: 6px;
    flex-wrap: wrap;
}
div[data-testid="stRadio"] label[data-baseweb="radio"] {
    padding: 7px 13px;
    background-color: white;
    border: 1px solid rgba(0, 0, 0, 0.1);
    border-radius: 7px;
    transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
    cursor: pointer;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
}
div[data-testid="stRadio"] label[data-baseweb="radio"]:hover {
    background-color: #fafafa;
    border-color: rgba(0, 0, 0, 0.22);
    transform: translateY(-1px);
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.04);
}
div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {
    display: none;
}
div[data-testid="stRadio"] label[data-baseweb="radio"] > div:last-child p {
    font-size: 13.5px !important;
    font-weight: 500 !important;
    color: #4b5563 !important;
    margin: 0 !important;
    letter-spacing: -0.005em;
}
div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
    background-color: #111827;
    border-color: #111827;
    box-shadow: 0 1px 3px rgba(17, 24, 39, 0.18),
                0 1px 2px rgba(17, 24, 39, 0.12);
}
div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) > div:last-child p {
    color: white !important;
    font-weight: 600 !important;
}

/* === dataframe·container 유동 높이 (viewport 기반, 2026-05-18) === */
[data-testid="stDataFrame"] {
    height: calc(100vh - 280px) !important;
    min-height: 400px !important;
}
[data-testid="stDataFrame"] > div {
    height: 100% !important;
}

/* === 다크모드 자동 대응 === */
@media (prefers-color-scheme: dark) {
    .stTabs [data-baseweb="tab-list"] {
        background-color: rgba(255, 255, 255, 0.04);
        border-color: rgba(255, 255, 255, 0.07);
    }
    .stTabs [data-baseweb="tab"] {
        color: #9ca3af;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #e5e7eb;
        background-color: rgba(255, 255, 255, 0.04);
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(255, 255, 255, 0.08) !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4) !important;
    }
    .stTabs [aria-selected="true"] p {
        color: #f3f4f6 !important;
    }

    div[data-testid="stRadio"] label[data-baseweb="radio"] {
        background-color: rgba(255, 255, 255, 0.03);
        border-color: rgba(255, 255, 255, 0.08);
    }
    div[data-testid="stRadio"] label[data-baseweb="radio"]:hover {
        background-color: rgba(255, 255, 255, 0.06);
        border-color: rgba(255, 255, 255, 0.16);
    }
    div[data-testid="stRadio"] label[data-baseweb="radio"] > div:last-child p {
        color: #9ca3af !important;
    }
    div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
        background-color: #f3f4f6;
        border-color: #f3f4f6;
    }
    div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) > div:last-child p {
        color: #111827 !important;
    }
}

/* === 우상단 툴바 (2026-06-11) === */
/* Deploy 버튼 숨김 — 로컬 앱에는 의미 없음 */
[data-testid="stAppDeployButton"] { display: none !important; }
/* 실행 중 Stop 버튼 — 한글 라벨 + 눈에 띄는 빨강 */
[data-testid="stStatusWidget"] button {
    font-size: 0 !important;
    background: #e5484d !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 4px 12px !important;
    min-height: 28px;
}
[data-testid="stStatusWidget"] button::after {
    content: "⏹ 중지";
    font-size: 0.85rem;
    font-weight: 600;
    color: #ffffff;
}
[data-testid="stStatusWidget"] button:hover {
    background: #d93036 !important;
}

/* 사용자 글자 크기 조절 */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] div,
[data-testid="stText"],
[data-testid="stCaptionContainer"],
label,
input,
textarea,
.stButton button,
[data-testid="stSelectbox"] *,
[data-testid="stRadio"] *,
[data-testid="stCheckbox"] *,
[data-testid="stMetric"] * {
    font-size: calc(1em * var(--mb-font-scale)) !important;
}
[data-testid="stMarkdownContainer"] h1 {
    font-size: calc(2.0rem * var(--mb-font-scale)) !important;
}
[data-testid="stMarkdownContainer"] h2 {
    font-size: calc(1.55rem * var(--mb-font-scale)) !important;
}
[data-testid="stMarkdownContainer"] h3 {
    font-size: calc(1.28rem * var(--mb-font-scale)) !important;
}
[data-testid="stMarkdownContainer"] h4 {
    font-size: calc(1.08rem * var(--mb-font-scale)) !important;
}

.stage-nav-link {
    display: block;
    width: 100%;
    text-align: center;
    padding: 10px 12px;
    border-radius: 9px;
    border: 1px solid rgba(0, 0, 0, 0.12);
    background: #ffffff;
    color: #4b5563 !important;
    text-decoration: none !important;
    font-weight: 600;
    line-height: 1.15;
    transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}
.stage-nav-link:hover {
    border-color: rgba(0, 0, 0, 0.28);
    color: #111827 !important;
}
.stage-nav-link.active {
    background: #111827;
    border-color: #111827;
    color: #ffffff !important;
}
/* 버튼 아이콘·라벨 통일 (Material 아이콘 도입, 2026-07-09) */
.stButton button p, .stFormSubmitButton button p { font-weight: 600; }
.stButton button [data-testid="stIconMaterial"],
.stFormSubmitButton button [data-testid="stIconMaterial"] {
    font-size: 1.15em;
    margin-right: 0.15em;
    vertical-align: middle;
}
/* 파일 업로드 영역 강조 — 실제 투입 지점이 눈에 띄도록 (2026-07-10) */
[data-testid="stFileUploaderDropzone"] {
    border: 2px dashed #111827 !important;
    background: #f4f5f7 !important;
    border-radius: 12px !important;
    padding: 1.1rem !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
    background: #eceef1 !important;
    border-color: #000 !important;
}
[data-testid="stFileUploaderDropzone"] [data-testid="stFileUploaderDropzoneInstructions"] svg {
    color: #111827 !important; fill: #111827 !important;
}
@media (prefers-color-scheme: dark) {
  [data-testid="stFileUploaderDropzone"] {
      border-color: #e5e7eb !important; background: rgba(255,255,255,0.04) !important;
  }
}
/* 체크박스/토글 검은색 강조는 theme.primaryColor(#111827)가 네이티브로 처리한다.
   과거 커스텀 배경 CSS는 토글 라벨까지 검게 칠해 글씨가 안 보이던 버그가 있어 제거함 (2026-07-10). */
/* 버튼 아이콘 무채색 고정 */
.stButton button [data-testid="stIconMaterial"],
.stFormSubmitButton button [data-testid="stIconMaterial"] { color: inherit !important; }
/* 커스텀 HTML(내비·메뉴)용 Material Symbols 아이콘 — 이모지 대신 무채색 통일 (2026-07-10) */
.msr {
    font-family: 'Material Symbols Rounded';
    font-weight: normal; font-style: normal;
    font-size: 1.05em; line-height: 1;
    letter-spacing: normal; text-transform: none; white-space: nowrap;
    vertical-align: -0.15em; margin-right: 0.35em;
    font-feature-settings: 'liga'; -webkit-font-feature-settings: 'liga';
    -webkit-font-smoothing: antialiased;
}
</style>
""".replace("__MB_FONT_SCALE__", str(_ui_font_scale)), unsafe_allow_html=True)

_logo_path = _find_app_icon("icon_128x128.png")
if _logo_path:
    import base64 as _b64
    _logo_b64 = _b64.b64encode(_logo_path.read_bytes()).decode()
    _logo_html = f'<img src="data:image/png;base64,{_logo_b64}" width="52" style="vertical-align:middle;margin-right:10px">'
else:
    _logo_html = "📚 "
_brand_col, _font_col = st.columns([6, 1.6])
_brand_col.markdown(
    f"# {_logo_html}My Bookshelf <span style='font-size:0.42em;color:#9aa0a6;"
    f"font-weight:400;vertical-align:middle'>{APP_VERSION}</span>",
    unsafe_allow_html=True,
)
with _font_col:
    _font_scale_controls()
# ★번역 단계는 화면 언어와 상관없이 늘 켜 둔다 (2026-08-26).
# 2026-07-10에는 "영어 UI면 영→한 번역이 무의미하다"며 숨겼는데, 그때는 도착언어가
# 한국어 하나뿐이었다. 지금은 설정에서 11개 언어 중 고르므로 — 영어 화면으로 쓰면서
# 스페인어로 번역할 수 있다 — 화면 언어로 번역 단계를 막는 것은 근거가 없다.

# 5단계(출력) 선택: 옵시디언 위키 / Word DOCX / 한글 HWPX / EPUB (독립 토글,
# 2026-07-24, HWPX 2026-08-09, EPUB 2026-08-11 — EPUB만 요약이 아니라 챕터 원문·번역본
# 전체를 담는다는 점에서 나머지 셋과 소스가 다름).
_use_ob = bool(llm.get_pref("use_obsidian", True))
_use_dx = bool(llm.get_pref("use_docx", False))
_use_hx = bool(llm.get_pref("use_hwpx", False))
_use_ep = bool(llm.get_pref("use_epub", False))
def _out_short() -> str:
    parts = [nm for on, nm in [(_use_dx, "DOCX"), (_use_hx, "HWPX"), (_use_ep, "EPUB"), (_use_ob, "위키")] if on]
    if not parts:
        return "출력 선택"
    if parts == ["위키"]:
        return "위키반영"
    return "+".join(parts) + ("" if "위키" in parts else " 생성")
def _out_flow() -> str:
    parts = [nm for on, nm in [(_use_dx, "Word(.docx)"), (_use_hx, "한글(.hwpx)"),
                                (_use_ep, "EPUB"), (_use_ob, "Obsidian Wiki")] if on]
    return " + ".join(parts) if parts else "출력 미선택"
st.caption(tf("PDF → TXT변환 → 장별 분할 → 번역 → 요약생성 → %s", _out_flow()))


def _book_chapters(stem: str) -> list[Path]:
    """책의 본문 챕터 파일들 — 파생물(_ko/_wiki/_bilingual/_clean) 제외."""
    _cdir = chapters_dir(DEFAULT_WS, stem)
    if not _cdir.exists():
        return []
    return sorted(f for f in _cdir.glob("??_*.txt")
                  if not f.stem.endswith(_DERIVED))


@st.cache_data(show_spinner=False, ttl=300)
def _book_language(stem: str, _sig: tuple) -> tuple[str, float]:
    """책 원문 언어 (코드, 확신도). _sig(파일 수·수정시각)가 바뀌면 다시 감지한다."""
    return book_language(_book_chapters(stem))


def _book_language_cached(stem: str) -> tuple[str, float]:
    chs = _book_chapters(stem)
    if not chs:
        return "", 0.0
    sig = (len(chs), round(max(f.stat().st_mtime for f in chs), 3))
    return _book_language(stem, sig)


def _route_translate(stem: str) -> bool:
    """이 책을 번역 대기로 보낼지 — **도착언어와 다른 언어의 책**이면 보낸다.

    실제 본문 언어로 판단한다. 파일명(저자명)만 보고 판단하면 "The Artifice of
    Intelligence_노린 헤르츠펠트"처럼 원서 제목에 저자명만 한글 음역인 경우 번역이
    필요 없다고 오판해 번역을 건너뛴다(2026-08-11 실측).

    첫 챕터 하나가 아니라 여러 챕터를 섞어 본다(2026-08-15): 『서양철학사』(한국어
    번역서)는 1장이 독일어 참고문헌으로 뒤덮여 있어 그 장만 보면 '독일어'로 잡혀
    한국어 책이 통째로 번역 대기에 들어갔다.
    챕터 파일을 아직 못 찾을 때만 옛 파일명 휴리스틱으로 폴백한다."""
    if not _book_chapters(stem):
        return _needs_translation(stem)
    _code, _ = _book_language_cached(stem)
    # ★기준은 화면 언어가 아니라 **설정의 도착언어**다 (2026-08-26). 예전에는
    # "ko"가 박혀 있어서, 도착언어를 스페인어로 바꿔도 한국어 책은 번역 대기로
    # 가지 않았다.
    return bool(_code) and _code != target_language()

_loading_step("파일 목록 확인 중…", "처리된 파일과 API 설정을 읽고 있습니다")

# ── 상태 배너 ────────────────────────────────────────────
_avail_api_providers = [llm.PROVIDERS[p]["label"] for p in llm.API_PROVIDERS if llm.has_key(p)]
_avail_cli_providers = [llm.PROVIDERS[p]["label"] for p in llm.CLI_PROVIDERS if llm.has_key(p)]
_avail_ai_providers = _avail_api_providers + _avail_cli_providers
_wiki_key_ok = bool(_avail_ai_providers)
wg_ok = wiki_generator_running()
# CLI 구독은 설치·활성된 도구명을 짧게 표시(Claude/Codex), API 키는 개수 (2026-07-10)
_CLI_SHORT = {"claude_cli": "Claude", "codex_cli": "Codex"}
# 어느 도구를 쓰는지만이 아니라 **어떤 모델로 도는지**도 보이게 한다 (2026-08-17).
# 지금 위키 생성에 걸린 공급자면 그 모델을, 아니면 그 도구의 기본 모델을 적는다.
_wp_now, _wm_now = llm.wiki_provider_model()


def _short_model(model: str, tool: str = "") -> str:
    """`claude-sonnet-4-6` → `Sonnet 4.6`. 앞에 붙는 도구 이름(Claude)과 겹치는
    접두만 뗀다 — Codex의 `gpt-5.5`는 겹치지 않으므로 `GPT-5.5`로 살려 둔다."""
    if model in ("", "default"):
        return "기본"
    m = model
    if tool and m.lower().startswith(tool.lower() + "-"):
        m = m[len(tool) + 1:]
    m = _re.sub(r"-\d{8}$", "", m)                    # 날짜 꼬리표
    m = _re.sub(r"-(\d+)-(\d+)$", r" \1.\2", m)       # -4-6 → 4.6
    m = _re.sub(r"^gpt", "GPT", m)
    return m[:1].upper() + m[1:]


def _cli_model_label(prov: str) -> str:
    """이 CLI 도구가 실제로 쓸 모델. 앱에서 고른 값이 'default'면(=지정 불가) 도구
    자신의 설정을 읽어 온다 — Codex는 ~/.codex/config.toml에 적힌 모델로 돈다."""
    model = _wm_now if prov == _wp_now else (llm.PROVIDERS[prov]["models"] or [""])[0]
    if model in ("", "default"):
        model = llm.cli_configured_model(prov) or model
    return _short_model(model, _CLI_SHORT.get(prov, ""))


_avail_cli_short = [f"{_CLI_SHORT.get(p, llm.PROVIDERS[p]['label'])} {_cli_model_label(p)}"
                    for p in llm.CLI_PROVIDERS if llm.has_key(p)]
# CLI 칸은 모델명까지 들어가 길다 — 왼쪽 여백을 줄여 폭을 준다. 값 글자 크기는 네 칸을
# 한꺼번에 줄여 라벨·값 간격과 줄 높이가 서로 어긋나지 않게 한다 (2026-08-17).
st.markdown("""<style>
.st-key-statusrow [data-testid="stMetricValue"] { font-size: 1.15rem; }
</style>""", unsafe_allow_html=True)
_status_row = st.container(key="statusrow")
_status_spacer, col_s1, col_s2, col_s3, col_s4 = _status_row.columns([1.2, 2.6, 1.05, 1.05, 1.05])
# CLI 구독을 우선(왼쪽)에, API 키를 다음에 배치
col_s1.metric(t("AI 구독(CLI)"),
              ", ".join(_avail_cli_short) if _avail_cli_short else t("✕ 없음"))
col_s2.metric(t("AI API 키"), tf("%d개", len(_avail_api_providers)) if _avail_api_providers else t("✕ 없음"))
col_s3.metric(t("위키 생성기"), t("생성 중") if wg_ok else t("대기"))
col_s4.metric(t("Wiki 완성"), sum(1 for _ in WIKI_DIR.rglob("*.md")))
if not _avail_ai_providers:
    st.error(t("사용 가능한 AI가 없습니다 — :material/settings: 설정 탭에서 API 키를 입력하거나 CLI 구독 도구를 활성화하세요."),
             icon=":material/warning:")

# ── 초기 메뉴 ─────────────────────────────────────────────
# 탭 → Material Symbols 아이콘 이름 (내비·메뉴·제목 공통, 무채색 통일, 2026-07-10)
_STAGE_ICONS = {
    "menu": "grid_view", "1_txt": "description", "2_split": "content_cut",
    "3_translate": "translate", "4_summary": "summarize", "5_wiki": "menu_book",
    "settings": "settings", "all_run": "rocket_launch",
}
TASKS = [
    ("1_txt", "텍스트 변환", "PDF·DOCX·HWP·HWPX·TXT를 텍스트로 변환 · 업로드 대기 → 변환 TXT"),
    ("2_split", "챕터 분할", "책 TXT를 챕터 단위로 분리 · 변환 TXT → chapters"),
    ("3_translate", "번역", "챕터를 도착언어로 번역 · chapters → 번역본"),
    ("4_summary", "문서요약", "챕터별 요약 노트 생성 · chapters → 요약(_wiki.md)"),
    ("5_wiki", "위키반영", "요약을 Obsidian 노트로 저장 · 요약(_wiki.md) → 보관함(Vault)"),
    ("settings", "설정", "API 키와 위키 생성 모델 설정"),
]

# 5단계(출력) 라벨·아이콘·설명: 옵시디언·DOCX 토글 조합에 따라 동적
def _stage_label(tid: str, label: str) -> str:
    return _out_short() if tid == "5_wiki" else label
def _stage_icon(tid: str) -> str:
    return ("description" if (_use_dx and not _use_ob) else "menu_book") if tid == "5_wiki" \
        else _STAGE_ICONS.get(tid, "")
def _stage_desc(tid: str, desc: str) -> str:
    if tid != "5_wiki":
        return desc
    _parts = [nm for on, nm in [(_use_ob, "Obsidian 위키"), (_use_dx, "Word(.docx) 문서"), (_use_hx, "한글(.hwpx) 문서")] if on]
    if not _parts:
        return "출력 방식(위키/DOCX/HWPX)을 하나 이상 선택하세요"
    if len(_parts) == 1:
        return f"요약을 {_parts[0]}로 저장" if _parts[0] != "Obsidian 위키" \
            else "요약을 Obsidian 노트로 저장 · 요약(_wiki.md) → 보관함(Vault)"
    return f"요약을 {' · '.join(_parts)} 여러 곳에 저장"

_active_view = st.session_state.get("active_view")
if not _active_view:
    st.markdown("""
<style>
.menu-card {
    display: block;
    width: 100%;
    padding: 13px 17px;
    margin: 0 0 10px 0;
    border: 1px solid rgba(0, 0, 0, 0.12);
    border-radius: 10px;
    background: #ffffff;
    color: inherit !important;
    text-decoration: none !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
    transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}
.menu-card:hover {
    border-color: rgba(0, 0, 0, 0.28);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
    transform: translateY(-1px);
}
.menu-title {
    display: block;
    font-size: 1.28rem;
    font-weight: 800;
    line-height: 1.25;
}
.menu-desc {
    display: block;
    margin-top: 3px;
    color: #6b7280;
    font-size: 0.96rem;
    line-height: 1.25;
}
</style>
""", unsafe_allow_html=True)
    st.markdown(t("#### 작업 메뉴"))
    st.info(t(
        "처음 사용 전 확인: 이 앱은 사용자가 제공한 PDF·DOCX·HWP·HWPX·TXT를 정리, 번역, 요약, 위키 노트로 재구성하는 개인 작업 도구입니다. "
        "원문 저작권과 이용허락은 사용자 책임으로 확인해야 하며, 외부 AI/CLI로 전송되는 텍스트에는 민감정보나 배포 권한이 불분명한 내용을 넣지 마세요."
    ))
    for _tid, _title, _desc in TASKS:
        _clicked = st.query_params.get("view") == _tid
        _mico = f'<span class="msr" style="font-size:1.2rem">{_stage_icon(_tid)}</span>'
        st.markdown(
            f'<a class="menu-card" href="?view={_tid}" target="_self">'
            f'<span class="menu-title">{_mico}{t(_stage_label(_tid, _title))}</span>'
            f'<span class="menu-desc">{t(_stage_desc(_tid, _desc))}</span>'
            f'</a>',
            unsafe_allow_html=True,
        )
        if _clicked:
            st.session_state["active_view"] = _tid
            st.query_params.clear()
            st.rerun()
    _loading_ph.empty()
    st.session_state["_app_loaded"] = True
    st.stop()

_STAGE_TASKS = [
    ("menu", "메뉴"),
    ("1_txt", "텍스트 변환"),
    ("2_split", "챕터 분할"),
    ("3_translate", "번역"),
    ("4_summary", "문서요약"),
    ("5_wiki", "위키반영"),
    ("settings", "설정"),
]
# 처리 중(잠금)에는 탭 이동 링크를 비활성 텍스트로 렌더 — 작업 이탈 방지 (2026-07-09)
# 영어 UI면 번역 탭(3_translate)을 내비에서 제외 (2026-07-10)
_run_lock = st.session_state.get("_run_lock")
_nav_tasks = list(_STAGE_TASKS)
_nav_cols = st.columns(len(_nav_tasks))
for _col, (_tid, _label) in zip(_nav_cols, _nav_tasks):
    _active_cls = " active" if _active_view == _tid else ""
    _label = _stage_label(_tid, _label)
    _ico = f'<span class="msr">{_stage_icon(_tid)}</span>'
    with _col:
        if _run_lock:
            st.markdown(
                f'<span class="stage-nav-link{_active_cls}" '
                f'style="opacity:0.4;pointer-events:none;cursor:not-allowed">{_ico}{t(_label)}</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<a class="stage-nav-link{_active_cls}" href="?view={_tid}" target="_self">{_ico}{t(_label)}</a>',
                unsafe_allow_html=True,
            )
if st.query_params.get("view") in {tid for tid, _ in _STAGE_TASKS}:
    _view = st.query_params.get("view")
    if _view != _active_view:
        if _view == "menu":
            st.session_state.pop("active_view", None)
        else:
            st.session_state["active_view"] = _view
    # 탭을 누를 때마다(같은 탭 재클릭 포함) 쿼리를 비우고 rerun → 매번 큐·파일 상태를 새로 읽음
    st.query_params.clear()
    st.rerun()

with st.expander(t("📁 저장 위치"), expanded=False):
    _loc_rows = [
        ("0_업로드대기", cfg.UPLOAD_TMP),
        ("1_원본PDF", cfg.PDF_DIR),
        ("2_변환TXT", cfg.TXT_DIR),
        ("3_챕터", cfg.CHAPTERS_DIR),
        ("위키(Vault)", WIKI_DIR),
        ("실패", FAILED_DIR),
        ("로그", cfg.LOG_DIR),
        ("구버전보관", cfg.LEGACY_KEEP),
    ]
    for _lname, _lpath in _loc_rows:
        _lc1, _lc2 = st.columns([0.85, 2.2])
        _lc1.markdown(f"**{_lname}**")
        _lc2.caption(str(_lpath))
        if _lc1.button(t("열기"), icon=":material/folder_open:", key=f"open_loc_{_lname}", use_container_width=True, disabled=not _lpath.exists()):
            open_path(_lpath)



# ─── 공용 헬퍼 ───────────────────────────────────────────


def _view_target_from_item(it: dict) -> Path | None:
    obj = it.get("obj")
    if isinstance(obj, Path):
        return obj
    if isinstance(obj, tuple) and obj and isinstance(obj[0], Path):
        return find_translation(obj[0]) or obj[0]
    if hasattr(obj, "_p"):
        return Path(obj._p)
    if isinstance(obj, dict):
        if isinstance(obj.get("txt"), Path):
            return obj["txt"]
        stem = obj.get("stem")
        ws = obj.get("ws") or DEFAULT_WS
        if stem:
            txt_path = cfg.TXT_DIR / f"{stem}.txt"
            ch_path = chapters_dir(ws, stem)
            if txt_path.exists():
                return txt_path
            if ch_path.exists():
                return ch_path
    if isinstance(obj, str):
        rel_path = cfg.BASE_DIR / obj
        if rel_path.exists():
            return rel_path
    return None


def _goto_view(view_id: str) -> None:
    # ★탭을 옮기면 완료 알림은 닫는다 (2026-08-26). 알림이 세션에 남아 있어서
    # «확정하고 번역(으)로»로 넘어가도 「챕터 분할 완료」가 번역 화면 아래에 계속
    # 따라다녔다 — 이미 지나온 단계의 안내가 다음 화면을 가린다.
    _clear_stage_completion()
    st.session_state["active_view"] = view_id
    st.query_params.clear()
    st.rerun()


def _set_stage_completion(title: str, message: str, next_stage: str | None = None,
                          open_target: Path | None = None, kind: str = "success",
                          question: str | None = None,
                          next_items: list | None = None,   # 안 쓴다 — 아래 주석 참고
                          open_label: str | None = None, open_action=None,
                          choices: list | None = None) -> None:
    st.session_state["_stage_completion"] = {
        "title": title,
        "message": message,
        "next_stage": next_stage,
        "question": question,
        "open_target": str(open_target) if open_target else "",
        "kind": kind,  # "success"|"warning" — 일부 실패 시 완료로 오인되지 않도록 (2026-07-23)
        # 특정 파일 열기 등 결과 폴더 열기를 대신할 동작 — 있으면 open_target보다 우선
        # (예: 방금 만든 DOCX 파일 바로 열기, Obsidian 노트 바로 열기, 2026-07-25)
        "open_label": open_label,
        "open_action": open_action,
        # 다음 단계로 넘기는 것 말고 다른 선택지를 물어야 할 때 쓴다 —
        # [{"label":…, "icon":…, "action": 콜러블, "primary": bool}, …] (2026-08-24)
        "choices": choices,
    }


def _track_flow_book(stem: str) -> None:
    """현재 처리 중인 책을 기록 — on_done이 다음 단계 대상(next_items)으로 넘긴다."""
    lst = st.session_state.setdefault("_flow_books", [])
    _s = _nfc(stem)
    if _s not in lst:
        lst.append(_s)


def _clear_stage_completion() -> None:
    st.session_state.pop("_stage_completion", None)


def _set_ocr_notice(names: list[str]) -> None:
    st.session_state["_ocr_notice"] = list(names)


def _render_ocr_notice() -> None:
    """이미지 전용(스캔) 문서 안내 팝업 — TXT 분리 전 OCR 선행 필요."""
    names = st.session_state.get("_ocr_notice")
    if not names:
        return

    def _render_body():
        st.warning(t("OCR 사전 처리가 필요합니다"))
        st.write(t("다음 문서는 이미지로만 되어 있어, TXT 분리를 위해서는 OCR 사전 처리 작업이 필요합니다:"))
        for _n in names:
            st.write(f"• {_n}")
        if st.button(t("닫기"), icon=":material/close:", key="ocr_notice_close",
                     use_container_width=True, type="primary"):
            st.session_state.pop("_ocr_notice", None)
            st.rerun()

    if hasattr(st, "dialog"):
        @st.dialog(t("OCR 필요"))
        def _ocr_notice_dialog():
            _render_body()
        _ocr_notice_dialog()
    else:
        with st.container(border=True):
            _render_body()


def _do_update(info: dict) -> None:
    """다운로드(진행바) → 검증 → 헬퍼 실행/앱 종료.
    팝업(다이얼로그) 밖의 본문에서 호출된다 — 성공하면 앱이 종료·재시작되고,
    실패하면 팝업을 다시 띄운다 (2026-07-25)."""
    st.markdown(f"### {t('업데이트 설치 중')}")
    st.info(t("설치 파일을 내려받는 중입니다…"))
    _bar = st.progress(0.0)
    _path, _err = updater.download_installer(
        info.get("asset_url", ""), progress_cb=lambda f: _bar.progress(f))
    if not _path:
        st.session_state["_updating"] = False
        st.session_state["_update_error"] = f"{t('자동 업데이트 실패')}: {_err}"
        st.rerun()
    _bar.progress(1.0)
    st.success(t("다운로드 완료 — 앱을 닫고 업데이트를 설치합니다. 잠시 후 자동으로 다시 열립니다."))
    if updater.launch_helper_and_exit(_path):
        st.stop()
    else:
        st.session_state["_updating"] = False
        st.session_state["_update_error"] = t("업데이트 실행에 실패했습니다.")
        st.rerun()


def _render_update_notice() -> None:
    """새 버전 감지 시 반자동 업데이트 팝업 (Windows·macOS). 실패는 모두 안내형으로 폴백."""
    if sys.platform not in ("win32", "darwin"):
        return
    if "_update_info" not in st.session_state:
        st.session_state["_update_info"] = updater.check_for_update() or {}
    info = st.session_state.get("_update_info") or {}
    if not info.get("available") or st.session_state.get("_update_dismissed"):
        return
    # 이 버전을 이미 '나중에'로 미뤘다면 다시 묻지 않는다 — 세션이 아니라
    # 설정 파일에 저장해 앱을 재시작해도 유지되고, 더 새 버전이 나오면
    # (latest 값이 달라지므로) 다시 안내한다 (2026-07-25).
    if info.get("latest") and info["latest"] == llm.get_pref("update_dismissed_version", ""):
        return

    # '지금 업데이트' 클릭 시 팝업을 닫고 본문에 진행 상황을 그대로 보여준다.
    # 실패하면 _do_update가 이 플래그를 다시 꺼서 팝업이 재등장한다 (2026-07-25).
    if st.session_state.get("_updating"):
        _do_update(info)
        return

    def _render_body():
        _err = st.session_state.pop("_update_error", None)
        if _err:
            st.error(_err)
            st.warning(t("아래 '브라우저로 받기'로 직접 내려받아 설치해 주세요."))
        st.write(tf("새 버전 **%s** 이(가) 나왔습니다. (현재 %s)", info["latest"], info["current"]))
        if info.get("notes"):
            with st.expander(t("변경 내용 보기")):
                st.markdown(info["notes"][:1500])
        st.caption(t("업데이트하면 앱이 닫혔다가 자동으로 다시 열립니다."))
        _c1, _c2, _c3 = st.columns(3)
        if _c1.button(t("지금 업데이트"), type="primary", use_container_width=True, key="upd_now"):
            st.session_state["_updating"] = True
            st.rerun()
        if _c2.button(t("브라우저로 받기"), use_container_width=True, key="upd_browser"):
            updater.open_release_page(info.get("page_url", ""))
            llm.set_pref("update_dismissed_version", info.get("latest", ""))
            st.session_state["_update_dismissed"] = True
            st.rerun()
        if _c3.button(t("나중에"), use_container_width=True, key="upd_later"):
            llm.set_pref("update_dismissed_version", info.get("latest", ""))
            st.session_state["_update_dismissed"] = True
            st.rerun()

    if hasattr(st, "dialog"):
        @st.dialog(t("업데이트 사용 가능"))
        def _update_dialog():
            _render_body()
        _update_dialog()
    else:
        with st.container(border=True):
            _render_body()


def _render_stage_completion_notice() -> None:
    # 처리 중(자동 실행 포함)에는 완료 팝업을 띄우지 않는다 — 진행바·중단 버튼을 가리지
    # 않도록. 실행 시작 시 닫히고, 처리가 끝나면(_run_lock 해제 + on_done이 payload 설정)
    # 다음 렌더에서 다시 뜬다. (2026-07-24)
    if st.session_state.get("_run_lock"):
        return
    payload = st.session_state.get("_stage_completion")
    if not payload:
        return

    def _render_body():
        (st.warning if payload.get("kind") == "warning" else st.success)(payload["title"])
        st.write(payload["message"])
        _q = payload.get("question")
        _choices = payload.get("choices")
        if _q and _choices:
            # 다음 단계가 아니라 '지금 해야 할 다른 일'을 묻는 경우 (예: 불량 본문 재OCR)
            st.markdown(f"### {_q}")
            _cols = st.columns(len(_choices))
            for _col, _ch in zip(_cols, _choices):
                if _col.button(_ch["label"], icon=_ch.get("icon"),
                               key=f"stage_choice_{_ch['label'][:12]}",
                               use_container_width=True,
                               type="primary" if _ch.get("primary") else "secondary"):
                    _clear_stage_completion()
                    _ch["action"]()
            if st.button(t("닫기"), icon=":material/close:", key="stage_close3",
                         use_container_width=True):
                _clear_stage_completion()
                st.rerun()
            return
        if _q:
            # 선택지 없이 온 문구는 **다음 화면에서 할 일**을 알려 주는 안내다.
            # 예전에는 이것이 "…할까요?"라는 물음이었고 [예]가 다음 단계를 대신
            # 실행했다. 이제는 알리기만 한다.
            st.info(_q)
        # ★다음 단계를 **자동으로 대신 실행하지 않는다** (2026-08-25 연구자 요청).
        # 예전에는 [예, 바로 진행]이 다음 탭의 처리를 곧바로 시작했는데, 그러면 어떤
        # 책이 어떤 설정으로 도는지 모르는 채 일이 벌어진다. 완료 상황만 요약해 주고
        # **다음 탭으로 데려다 놓는 것까지**가 이 알림의 몫이다 — 실행은 그 화면에서
        # 사람이 고른다. 아래 표준 블록([다음 단계]·[결과 폴더 열기]·[닫기])이 그 일을 한다.
        c1, c2, c3 = st.columns(3)
        if payload.get("next_stage"):
            if c1.button(t("다음 단계"), icon=":material/arrow_forward:", key="stage_done_next", use_container_width=True, type="primary"):
                next_stage = payload["next_stage"]
                _clear_stage_completion()
                _goto_view(next_stage)
        _open_action = payload.get("open_action")
        if _open_action or payload.get("open_target"):
            _open_label = payload.get("open_label") or t("결과 폴더 열기")
            if c2.button(_open_label, icon=":material/folder_open:", key="stage_done_open", use_container_width=True):
                if _open_action:
                    _open_action()
                else:
                    _target = Path(payload["open_target"])
                    open_path(_target, reveal=_target.is_file())
        if c3.button(t("닫기"), icon=":material/close:", key="stage_done_close", use_container_width=True):
            _clear_stage_completion()
            st.rerun()

    # 모달(st.dialog)이 아니라 페이지 안 패널로 렌더링한다. "예, 바로 진행"을
    # 누르면 닫힘→다음 화면 이동→자동실행까지 리런이 연속으로 이어지는데,
    # 이 경우 st.dialog 모달이 화면에 그대로 눌어붙어 처리 화면을 가리는
    # 현상이 있었다(2026-07-25, 실제 재현 스크린샷으로 확인). 일반 패널은
    # 그런 클라이언트 쪽 열림 상태가 없어 리런될 때마다 있으면 보이고
    # 없으면 그냥 안 보이므로 이 문제가 근본적으로 발생하지 않는다.
    with st.container(border=True):
        _render_body()


def _stage_folder(stage_id: str) -> Path:
    if stage_id == "1_txt":
        return cfg.TXT_DIR
    if stage_id in {"2_split", "3_translate", "4_summary"}:
        return cfg.CHAPTERS_DIR
    if stage_id == "5_wiki":
        return WIKI_DIR
    return cfg.BASE_DIR


def _chapter_rel_paths(ws_name: str, stem: str) -> list[str]:
    ch_dir = chapters_dir(ws_name, stem)
    if not ch_dir.exists():
        return []
    return [
        str(f.relative_to(cfg.BASE_DIR))
        for f in sorted(ch_dir.glob("??_*.txt"))
        if not f.stem.endswith(_DERIVED)
    ]


def _dismiss_split_nosplit(stem: str) -> None:
    pending = st.session_state.get("split2_nosplit", [])
    if isinstance(pending, list) and stem in pending:
        st.session_state["split2_nosplit"] = [item for item in pending if item != stem]


def _book_source_text(book: str) -> str:
    """이 책의 변환 TXT. **활성 사본을 먼저** 본다(보관본은 옛것일 수 있다)."""
    for c in (cfg.TXT_DIR / f"{book}.txt", cfg.TXT_ARCHIVE_DIR / f"{book}.txt"):
        if c.exists():
            return c.read_text(encoding="utf-8", errors="ignore")
    return ""


# 이보다 짧으면 차례 쪽을 짚어낼 것도 없이 통째로 연다. 논문·발췌본이 여기 든다.
_SHORT_DOC_PAGES = 30


def _render_toc_side_by_side(key: str, book: str) -> None:
    """원본 PDF의 **차례 쪽을 미리보기 창으로 띄운다** (2026-08-25 연구자 요청).

    ★장 구분이 맞는지는 **차례와 견주어야만** 알 수 있다. 그래서 버튼을 눌러야 열리게
    두지 않고 **확인 화면에 들어오면 저절로 연다** — 눌러야 하는 것은 안 누르게 된다.

    ★앱 창 안 미리보기는 없앴다. 작고 확대가 안 돼 한 줄씩 견주기에 쓸모가 없었고,
    두 가지 보기 방식을 나란히 두면 고르는 일만 늘어난다.

    ★**같은 쪽을 두 번 열지 않는다.** Streamlit은 조작할 때마다 화면을 다시 그리므로,
    그대로 두면 클릭 한 번에 창이 하나씩 늘어난다. 책과 고른 쪽이 바뀔 때만 연다.

    ★**모르면 추측하지 않는다** (2026-08-26). 예전에는 차례를 못 찾으면 `[3, 4]`쪽을
    기본값으로 박아 두고 그대로 창을 띄웠다. 그런데 논문·발췌본은 차례가 없는 것이
    정상이라, 연구자가 볼 때마다 엉뚱한 본문 쪽이 열렸다(실측: 인쇄 455·456쪽).
    짧은 문서는 통째로 열고, 긴 책에서 차례를 못 찾으면 **창을 열지 않고** 말한다."""
    _pdf = cfg.PDF_DIR / f"{book}.pdf"
    if not _pdf.exists():
        return
    _seen = f"{key}_tocopened_{book}"
    _total = toc_svc.page_count(_pdf)

    # ── 짧은 문서: 차례를 찾을 것 없이 전체를 연다 ──────────────────────
    if 0 < _total <= _SHORT_DOC_PAGES:
        if st.session_state.get(_seen) != ("whole", _total):
            # ★원본이 아니라 사본을 연다 — 뷰어가 원본을 붙들면 같은 책을 다시
            # 변환할 때 옮기지 못해 앱이 멎는다 (2026-08-26 WinError 32).
            open_pdf_view(toc_svc.whole_pdf_copy(_pdf))
            st.session_state[_seen] = ("whole", _total)
        st.info("📖 " + tf("**원본 %s쪽 전체를 미리보기 창으로 열었습니다.** "
                           "짧은 글이라 차례 쪽을 따로 짚지 않았습니다 — 그 창을 이 앱 창 옆에 "
                           "나란히 놓고 아래 장 목록과 견주어 보세요.", str(_total)))
        if st.button(t("원본 창 다시 열기"), icon=":material/refresh:",
                     key=f"{key}_tocre_{book}"):
            st.session_state.pop(_seen, None)
            st.rerun()
        return

    # ── 긴 책: 차례 쪽을 짚는다 ────────────────────────────────────────
    _sugg = toc_svc.toc_page_candidates(_book_source_text(book)) or []
    _skey = f"{key}_tocpg_{book}"
    _default = [i + 1 for i in _sugg[:2] if i + 1 <= 40]      # 못 찾으면 비워 둔다
    with st.expander("📖 " + t("차례 쪽 고르기") + (
            tf(" — 차례로 보이는 쪽: %s", ", ".join(str(i + 1) for i in _sugg)) if _sugg else ""),
            expanded=not _sugg):
        st.caption(t("자동으로 짚은 쪽이 차례가 아니면 여기서 고쳐 주세요 — 고치면 창이 다시 열립니다."))
        _pages = st.multiselect(t("차례가 있는 쪽 (1-기반)"), list(range(1, 41)),
                                default=_default, key=_skey)
        # 창을 닫았을 때 되살릴 길 — 접힌 칸 안에 둔다(본 화면에는 버튼을 두지 않는다).
        if st.button(t("차례 창 다시 열기"), icon=":material/refresh:",
                     key=f"{key}_tocre_{book}"):
            st.session_state.pop(_seen, None)
            st.rerun()
    if not _pages:
        if _sugg:
            st.info(t("📖 차례 쪽을 고르면 미리보기 창으로 띄워 드립니다 — 위 «차례 쪽 고르기»를 펴 보세요."))
        else:
            st.info(t("📖 이 책에서는 차례를 찾지 못했습니다. 차례가 있는 쪽을 위에서 짚어 "
                      "주시면 열어 드리겠습니다. 차례가 없는 글이면 그냥 지나가셔도 됩니다."))
        return

    _want = tuple(_pages)
    if st.session_state.get(_seen) != _want:
        _out = toc_svc.pages_pdf(_pdf, [p - 1 for p in _pages])
        if _out:
            open_pdf_view(_out)          # 기기마다 다른 앱이 뜨지 않게 미리보기로 고정
            st.session_state[_seen] = _want
        else:
            st.warning(t("차례 PDF를 만들지 못했습니다 — 쪽 번호를 확인해 주세요."))
            return
    st.info("📖 " + tf("**차례 %s을 미리보기 창으로 열었습니다.** "
                       "그 창을 이 앱 창 옆에 나란히 놓고, 아래 장 목록과 **한 줄씩 견주어 보세요** — "
                       "빠진 장이나 잘못 붙은 장이 보이면 맨 아래 채팅창에 그대로 말씀하시면 됩니다.",
                       toc_svc.printed_label(_pdf, _pages)))


def _chapter_review_panel(key: str, full: bool = True, only_book: str | None = None) -> None:
    """장 목록을 보여주고 고치는 화면 (2026-08-17).

    분할 탭에서는 full=True로 전체 기능을, 요약·번역 탭에서는 full=False로 제목 고치기만
    쓴다 — 잘못된 제목은 대개 요약을 돌리려다 눈에 띄기 때문에, 그 자리에서 바로 고칠
    수 있어야 한다.
    """
    if not cfg.CHAPTERS_DIR.exists():
        return
    books = [d.name for d in sorted(cfg.CHAPTERS_DIR.iterdir())
             if d.is_dir() and cmap.chapter_files(DEFAULT_WS, d.name)]
    if only_book:
        books = [b for b in books if b == only_book]
    else:
        # 기본은 **이번 실행에서 나눈 책만.** 대기 큐 전체를 훑으면 예전에 넣어 둔 책까지
        # 수십 권이 딸려 오고, 다 지나간 책의 "수상한 분할"을 붙잡게 된다(2026-08-18).
        _live = {_nfc(b) for b in st.session_state.get("_review_books", [])}
        _fresh = [b for b in books if _nfc(b) in _live]
        # ★'확인하지 않은 책' 목록은 뺐다 (2026-08-26 연구자 요청 — 자주 안 쓴다).
        # 필요해지면 여기서 확정 안 된 책을 다시 꺼내면 된다.
        books = _fresh
    if not books:
        return
    if full:
        st.markdown("### 📑 " + t("장 구분 확인"))
        st.caption(t("방금 나눈 책의 장 목록입니다. 요약·번역으로 넘기기 전에 "
                     "제목을 고치거나 장을 합치고 나눌 수 있습니다."))
    if len(books) == 1:
        book = books[0]
        if full:
            st.markdown(f"**📚 {book}**")
    else:
        label = {b: ("✅ " if cmap.is_confirmed(DEFAULT_WS, b) else "🔎 ") + b for b in books}
        book = st.selectbox(t("책 고르기"), books, key=f"{key}_book",
                            format_func=lambda b: label.get(b, b))
    if not book:
        return
    files = cmap.chapter_files(DEFAULT_WS, book)
    if full:
        for finding in cmap.review_findings(DEFAULT_WS, book):
            st.warning("⚠️ " + finding)
        _render_toc_side_by_side(key, book)
    ranges = cmap.part_ranges(DEFAULT_WS, book)
    rows, prev_part = [], ""
    for cf in files:
        body = cf.read_text(encoding="utf-8", errors="ignore")
        try:
            n = int(cf.stem[:2])
        except ValueError:
            n = 0
        part = cmap.part_of(ranges, n) if n > 0 else ""
        rows.append({
            "순번": cf.stem[:2],
            "부": part if part != prev_part else "",   # 같은 부는 첫 장에만 적는다
            "제목": cmap.chapter_title(cf),
            "분량": f"{len(body):,}자",
            "시작 부분": _re.sub(r"\s+", " ", body[:80]).strip(),
            "앞 장에 합치기": False,
        })
        prev_part = part
    cols = ["순번", "부", "제목", "분량", "시작 부분"] + (["앞 장에 합치기"] if full else [])
    edited = st.data_editor(
        pd.DataFrame(rows)[cols], key=f"{key}_editor_{book}",
        use_container_width=True, hide_index=True, num_rows="fixed",
        column_config={
            "순번": st.column_config.TextColumn(disabled=True, width="small"),
            "부": st.column_config.TextColumn(
                t("부(部)"), width="small",
                help=t("이 장부터 시작하는 부의 이름. 같은 부가 이어지면 비워 두세요")),
            "제목": st.column_config.TextColumn(t("제목 (고칠 수 있음)"), width="large"),
            "분량": st.column_config.TextColumn(disabled=True, width="small"),
            "시작 부분": st.column_config.TextColumn(disabled=True, width="large"),
            "앞 장에 합치기": st.column_config.CheckboxColumn(
                t("앞 장에 합치기"), help=t("이 장을 지우고 본문을 바로 앞 장 뒤에 붙입니다")),
        },
    )
    def _apply_edits() -> tuple[int, list[tuple[str, str]]]:
        """표에서 고친 것을 실제 파일에 반영한다. (반영 건수, 이름이 바뀐 것들)"""
        recs = edited.to_dict("records")
        changed = 0
        adjusted: list[tuple[str, str]] = []
        for i, row in enumerate(recs):
            new_title = str(row.get("제목", "")).strip()
            if new_title and new_title != rows[i]["제목"]:
                # 파일 이름에 못 쓰는 글자가 있으면 앱이 바꿔서 저장한다 — 무엇이
                # 어떻게 바뀌었는지 **말해 주지 않으면 사라진 줄 안다** (2026-08-25).
                safe = cmap._safe(new_title)
                if safe != new_title:
                    adjusted.append((new_title, safe))
                cmap.rename_chapter(DEFAULT_WS, book, i, new_title)
                changed += 1
        # 부: 값이 적힌 줄에서 새 부가 시작한다
        new_ranges = []
        for i, row in enumerate(recs):
            part = str(row.get("부", "")).strip()
            if part:
                try:
                    new_ranges.append({"start": int(rows[i]["순번"]), "title": part})
                except ValueError:
                    pass
        if new_ranges != ranges:
            cmap.set_parts(DEFAULT_WS, book, new_ranges)
            changed += 1
        if full:
            for i in sorted([i for i, r in enumerate(recs) if r.get("앞 장에 합치기")], reverse=True):
                if cmap.merge_up(DEFAULT_WS, book, i):
                    changed += 1
        return changed, adjusted

    def _report(changed: int, adjusted: list[tuple[str, str]]) -> None:
        if adjusted:
            st.info("ℹ️ " + t("파일 이름에 쓸 수 없는 글자(`: / \\ * ? \" < > |`)를 «-»로 바꿔 저장했습니다:")
                    + "\n\n" + "\n\n".join(f"- 「{a}」 → **「{b}」**" for a, b in adjusted))
        st.success(tf("%d건 반영했습니다.", changed) if changed else t("바뀐 내용이 없습니다."))

    # ★버튼을 둘로 줄이고, 확정하면 **다음 단계로 바로 넘어간다** (2026-08-26).
    # 예전에는 «변경 적용» → «이대로 확정» 두 번을 눌러야 끝났고, 끝나도 같은
    # 화면에 남아 있어 다음에 무엇을 할지가 보이지 않았다.
    _next_view = "3_translate" if _route_translate(book) else "4_summary"
    _next_name = t("번역") if _next_view == "3_translate" else t("문서요약")
    b1, b2, b3 = st.columns([2, 1, 1])
    if b1.button(tf("확정하고 %s(으)로", _next_name), icon=":material/check_circle:",
                 key=f"{key}_confirm", use_container_width=True, type="primary",
                 help=t("표에서 고친 것을 저장하고 장 구분을 확정한 뒤 다음 단계로 넘어갑니다.")):
        _changed, _adjusted = _apply_edits()
        cmap.confirm(DEFAULT_WS, book)
        if _adjusted:
            # 바뀐 이름을 알려야 하므로 이번에는 넘어가지 않는다 — 넘어가면 안내가 사라진다.
            _report(_changed, _adjusted)
            st.caption(t("확정했습니다. 위 안내를 확인하고 한 번 더 누르면 다음 단계로 넘어갑니다."))
        else:
            _goto_view(_next_view)
    if b2.button(t("저장만"), icon=":material/save:", key=f"{key}_apply",
                 use_container_width=True,
                 help=t("고친 것만 저장하고 이 화면에 남습니다 — 계속 다듬을 때.")):
        _changed, _adjusted = _apply_edits()
        _report(_changed, _adjusted)
        if not _adjusted:
            st.rerun()
    if b3.button(t("폴더 열기"), icon=":material/folder_open:", key=f"{key}_open",
                 use_container_width=True):
        open_path(chapters_dir(DEFAULT_WS, book))

    if not full:
        return

    # ★«✂️ 장 나누기»는 뺐다 (2026-08-27 연구자 요청 — "복잡해서 어려울 것 같다").
    # 나누기가 필요하면 목차를 붙여넣어 다시 나누는 아래 방법이 더 쉽다.
    st.divider()

    # ★«📖 PDF 차례에서 가져오기»·«📋 목차 붙여넣기»는 뺐다 (2026-08-27 연구자 요청).
    # 장을 다시 나눌 일이 있으면 분할 탭에서 그 책을 다시 처리하는 편이 단순하다.

def _queue_book_chapters_for_next_stage(ws_name: str, stem: str) -> list[str]:
    chapter_rels = _chapter_rel_paths(ws_name, stem)
    if not chapter_rels:
        return []
    if _route_translate(stem):
        queue_add("tab3_ready", chapter_rels)
    else:
        queue_add("tab4_ready", chapter_rels)
    return chapter_rels


def _save_book_as_single_chapter(ws_name: str, stem: str) -> tuple[bool, str, list[str]]:
    existing_rels = _chapter_rel_paths(ws_name, stem)
    if existing_rels:
        queue_remove("tab2_ready", [stem])
        _dismiss_split_nosplit(stem)
        _queue_book_chapters_for_next_stage(ws_name, stem)
        return True, t("기존 장 파일을 다시 사용했습니다."), existing_rels

    txt_path = find_txt(DONE_DIR, ws_name, stem)
    md_path = find_md(DONE_DIR, ws_name, stem)
    source_path = txt_path or md_path
    if source_path is None:
        return False, t("TXT/MD 파일이 없습니다."), []

    source_text = source_path.read_text(encoding="utf-8", errors="ignore")
    if not source_text.strip():
        return False, t("TXT/MD 내용이 비어 있습니다."), []

    ch_path, _ = _write_single_chapter_from_text(ws_name, stem, source_text)
    queue_remove("tab2_ready", [stem])
    _dismiss_split_nosplit(stem)
    chapter_rels = _queue_book_chapters_for_next_stage(ws_name, stem)
    if not chapter_rels:
        return False, t("단일장 파일 생성에 실패했습니다."), []
    return True, ch_path.name, chapter_rels


def _upload_token(upload_name: str, upload_bytes: bytes) -> str:
    digest = hashlib.sha1(upload_bytes).hexdigest()[:12]
    return f"{Path(upload_name).name}:{len(upload_bytes)}:{digest}"


def _copy_direct_upload_to_processing(stage_name: str, upload_name: str, upload_bytes: bytes) -> tuple[Path, str]:
    token = _upload_token(upload_name, upload_bytes)
    digest = token.rsplit(":", 1)[-1]
    staging_dir = UPLOAD_TMP / "_direct_uploads" / stage_name
    staging_dir.mkdir(parents=True, exist_ok=True)
    raw_name = Path(upload_name).name
    staging_path = staging_dir / raw_name
    if staging_path.exists():
        try:
            if staging_path.read_bytes() != upload_bytes:
                staging_path = staging_dir / f"{Path(upload_name).stem}__{digest}{Path(upload_name).suffix or '.txt'}"
        except Exception:
            staging_path = staging_dir / f"{Path(upload_name).stem}__{digest}{Path(upload_name).suffix or '.txt'}"
    staging_path.write_bytes(upload_bytes)
    return staging_path, token


def _prepare_uploaded_single_chapter(ws_name: str, upload_name: str, upload_bytes: bytes, stage_name: str) -> tuple[bool, Path | None, str, str]:
    _copy_direct_upload_to_processing(stage_name, upload_name, upload_bytes)
    stem = _nfc(Path(upload_name).stem)
    suffix = ".txt"
    src_dir = cfg.TXT_DIR
    src_dir.mkdir(parents=True, exist_ok=True)
    src_path = src_dir / f"{stem}{suffix}"
    src_path.write_bytes(upload_bytes)
    source_text = src_path.read_text(encoding="utf-8", errors="ignore")
    if not source_text.strip():
        return False, None, stem, t("TXT 내용이 비어 있습니다.")

    existing_rels = _chapter_rel_paths(ws_name, stem)
    if len(existing_rels) > 1:
        return False, None, stem, t("이미 여러 장으로 분할된 책입니다. 2-장별분할 탭에서 처리하세요.")
    if existing_rels:
        existing_path = cfg.BASE_DIR / existing_rels[0]
        existing_text = existing_path.read_text(encoding="utf-8", errors="ignore")
        if existing_text == source_text:
            return True, existing_path, stem, t("기존 단일장 파일을 이어서 사용합니다.")
    else:
        # 파일명이 달라도 이미 등록된 책과 본문 내용이 같으면 새 책으로 중복 생성하지
        # 않는다 — 같은 책을 다른 이름의 TXT로 드래그앤드롭했을 때 중복 폴더가 생기던
        # 문제(2026-08-11, "1_기술신학..." 중복 사례).
        for _d in (cfg.CHAPTERS_DIR.iterdir() if cfg.CHAPTERS_DIR.exists() else []):
            if not _d.is_dir() or _d.name == stem:
                continue
            _chs = [f for f in _d.glob("??_*.txt")
                    if not f.stem.endswith(_DERIVED)]
            if len(_chs) != 1:
                continue
            try:
                if _chs[0].read_text(encoding="utf-8", errors="ignore") == source_text:
                    return True, _chs[0], _d.name, t("동일한 내용의 책이 이미 있어 기존 파일을 이어서 사용합니다.")
            except Exception:
                continue

    ch_path, _ = _write_single_chapter_from_text(ws_name, stem, source_text)
    return True, ch_path, stem, t("단일장 파일을 저장했습니다.")


def _count_files(path: Path, patterns: list[str], exclude_suffixes: tuple = ()) -> int:
    """폴더에서 패턴에 맞는 파일 수. exclude_suffixes는 stem 끝 필터 (_ko 등)."""
    if not path.exists():
        return 0
    n = 0
    for pat in patterns:
        for f in path.glob(pat):
            if f.is_file() and not (exclude_suffixes and f.stem.endswith(exclude_suffixes)):
                n += 1
    return n


def _chapter_counts() -> tuple[int, int, int]:
    """chapters/ 전체의 (원문 챕터, 번역본 _ko, 요약 _wiki.md/.json) 개수."""
    root = cfg.CHAPTERS_DIR
    src_n = ko_n = 0
    summary_stems: set[str] = set()
    if root.exists():
        for f in root.rglob("??_*.txt"):
            if f.stem.endswith(_DERIVED) and not f.stem.endswith(("_wiki", "_bilingual", "_clean")):
                ko_n += 1                       # 번역본 — 접미사는 도착언어를 따른다
            elif not f.stem.endswith("_wiki"):
                src_n += 1
        for f in root.rglob("*_wiki.md"):
            summary_stems.add(str(f.with_suffix("")))
        for f in root.rglob("*_wiki.json"):
            summary_stems.add(str(f.with_suffix("")))
    return src_n, ko_n, len(summary_stems)


def _stage_flow_panel(app_title: str, app_desc: str,
                      cards: list[tuple[str, Path, str]], key_prefix: str) -> None:
    """앱 헤더 + (작게) 진행 요약·폴더 열기. 실제 작업 공간이 눈에 띄도록
    폴더 열기란은 접이식으로 작게 처리한다 (2026-07-09). cards=[(라벨, 경로, 개수문구)]"""
    st.markdown(f"### {t(app_title)}")
    st.caption(t(app_desc))
    # ★진행 요약 줄("① 처리전 · … · ② 처리후 · …")은 뺐다 (2026-08-26 연구자 요청).
    # 다섯 탭 머리마다 숫자가 늘어서 있어 정작 할 일이 눈에 안 들어왔다.
    # 폴더 열기는 그대로 둔다 — 그건 실제로 쓰는 기능이다.
    with st.expander(t("📁 폴더 열기"), expanded=False):
        _fcols = st.columns(len(cards))
        for i, (label, path, _count_txt) in enumerate(cards):
            if _fcols[i].button(t(label), icon=":material/folder_open:", key=f"{key_prefix}_open_{i}",
                                use_container_width=True, disabled=not path.exists(),
                                help=str(path)):
                open_path(path)
    st.divider()


# ─── 처리 잠금(시작/중단) 런 패널 (2026-07-09) ──────────────────
# 시작 → 처리 화면만 표시(다른 위젯 미렌더 + 상단 탭 이동 잠금).
# 항목 1개 처리 후 st.rerun → 다음 항목. 중단 클릭은 다음 rerun에서 감지돼
# 현재 항목 처리 후 멈춘다(남은 항목은 지속 큐에 남아 재시작 시 이어짐).

def _run_active(tab: str) -> bool:
    return bool(st.session_state.get(f"{tab}_running"))


def _run_start(tab: str, work: list) -> None:
    """선택한 작업 목록으로 처리 시작. work=처리기 인자 목록."""
    if not work:
        return
    st.session_state[f"{tab}_running"] = True
    st.session_state[f"{tab}_queue"] = list(work)
    st.session_state[f"{tab}_total"] = len(work)
    st.session_state[f"{tab}_log"] = []
    st.session_state[f"{tab}_start_ts"] = time.time()
    st.session_state["_run_lock"] = tab
    st.rerun()


def _run_finish(tab: str) -> None:
    st.session_state[f"{tab}_running"] = False
    st.session_state.pop(f"{tab}_status_place", None)
    st.session_state.pop(f"{tab}_start_ts", None)
    if st.session_state.get("_run_lock") == tab:
        st.session_state.pop("_run_lock", None)


def _fmt_elapsed(secs: float) -> str:
    """경과 시간을 사람이 읽기 좋은 문구로 (2026-08-11 — 처리 중 진행이 보이도록)."""
    secs = max(0, int(secs))
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    if h:
        return tf("%d시간 %d분 %d초", h, m, s)
    if m:
        return tf("%d분 %d초", m, s)
    return tf("%d초", s)


def _run_with_elapsed_ticker(fn, elapsed_place, start_ts: float):
    """fn()을 별도 스레드에서 실행하는 동안, 메인 스레드는 1초마다 경과 시간을 독립적으로
    갱신한다. AI 배치 호출 하나가 수십 초씩 걸리면 그 사이엔 진행 콜백이 전혀 안 불려서
    경과 시간도 같이 멈춘 것처럼 보이던 문제 — 콜백과 무관하게 똑딱이는 타이머가 필요해
    스레드로 분리했다(2026-08-11). add_script_run_ctx로 워커 스레드에서도 다른 placeholder
    (진행 텍스트 등)를 안전하게 갱신할 수 있다."""
    result: dict = {}

    def _target():
        try:
            result["value"] = fn()
        except Exception as e:
            result["error"] = e

    thread = threading.Thread(target=_target, daemon=True)
    add_script_run_ctx(thread)
    thread.start()
    while thread.is_alive():
        elapsed_place.caption(tf("⏱ %s 경과", _fmt_elapsed(time.time() - start_ts)))
        thread.join(timeout=1.0)
    elapsed_place.caption(tf("⏱ %s 경과", _fmt_elapsed(time.time() - start_ts)))
    if "error" in result:
        raise result["error"]
    return result["value"]


def _run_panel(tab: str, title: str, process_one, on_done=None,
               item_progress_text=None, detail_progress: bool = False) -> None:
    """처리 화면 렌더 + 항목 1개 처리 + rerun. process_one(item)->(ok, msg 문자열).
    on_done(): 큐 소진 시 1회 실행(전체요약 등 후처리).
    item_progress_text: 번역처럼 고정된 8개 인자 콜백(기존 방식, 그대로 유지).
    detail_progress=True: 자유 문자열 콜백 process_one(item, cb) — cb(text)를 호출하는
    쪽마다 경과 시간과 함께 실시간으로 보여준다(EPUB 등, 2026-08-11). 처리 중엔 회전
    스피너도 같이 떠서 '멈춘 게 아니다'가 한눈에 보이게 했다."""
    queue = list(st.session_state.get(f"{tab}_queue", []))
    total = st.session_state.get(f"{tab}_total", len(queue)) or 1
    done = total - len(queue)
    log = list(st.session_state.get(f"{tab}_log", []))
    _start_ts = st.session_state.get(f"{tab}_start_ts", time.time())

    st.markdown(f"### ⏳ {t(title)}")
    _elapsed_place = st.empty()
    _elapsed_place.caption(tf("⏱ %s 경과", _fmt_elapsed(time.time() - _start_ts)))
    st.progress(min(done / total, 1.0), text=tf("%d/%d 처리 중", done, total))
    _stopped = st.button(t("중단"), icon=":material/stop:", key=f"{tab}_stopbtn", type="primary")
    st.caption(t("처리 중에는 다른 기능이 잠깁니다. '중단'을 누르면 현재 항목까지 마친 뒤 멈추고, 남은 작업은 다시 '시작'으로 이어집니다."))
    # 완료 로그가 없으면 빈 테두리 박스만 남아 혼란스러워 아예 안 그린다(2026-08-11).
    if log:
        with st.container(height=300, border=True):
            for _ln in log[-80:]:
                st.markdown(_ln)

    if _stopped:
        _run_finish(tab)
        st.rerun()
    if not queue:
        _run_finish(tab)
        if on_done:
            try:
                on_done()
            except Exception as _e:
                st.warning(str(_e)[:200])
        st.rerun()

    _item = queue[0]
    try:
        if item_progress_text:
            _item_progress = st.progress(0.0)

            def _progress_cb(done, total, translated, preserved, dropped, failed, resumed, api_calls):
                fraction = min(max(done / total, 0.0), 1.0) if total else 0.0
                _item_progress.progress(
                    fraction,
                    text=item_progress_text(
                        done, total, translated, preserved, dropped, failed, resumed, api_calls
                    ),
                )

            with st.spinner(t("처리 중…")):
                _ok, _msg = _run_with_elapsed_ticker(
                    lambda: process_one(_item, _progress_cb), _elapsed_place, _start_ts)
        elif detail_progress:
            _detail_place = st.empty()

            def _detail_cb(text: str):
                _detail_place.caption(text)

            with st.spinner(t("처리 중…")):
                _ok, _msg = _run_with_elapsed_ticker(
                    lambda: process_one(_item, _detail_cb), _elapsed_place, _start_ts)
        else:
            with st.spinner(t("처리 중…")):
                _ok, _msg = _run_with_elapsed_ticker(
                    lambda: process_one(_item), _elapsed_place, _start_ts)
    except Exception as _e:
        _ok, _msg = False, f"{type(_e).__name__}: {str(_e)[:150]}"
    log.append(f"{'✅' if _ok else '❌'} {_msg}")
    st.session_state[f"{tab}_log"] = log
    st.session_state[f"{tab}_queue"] = queue[1:]
    st.rerun()


_DND_HINT = "📎 파일 선택 또는 이 영역으로 끌어다 놓기(Drag & Drop) 가능"


def _current_wiki_dir() -> Path:
    target = (st.session_state.get("wiki5_active_dir") or "").strip()
    if target:
        return Path(target)
    try:
        data = json.loads(cfg.CONFIG_FILE.read_text(encoding="utf-8")) if cfg.CONFIG_FILE.exists() else {}
        target = str(data.get("dirs", {}).get("wiki", "")).strip()
        if target:
            return Path(target).expanduser()
    except Exception:
        pass
    return WIKI_DIR


def _current_docx_dir() -> Path:
    """DOCX 저장 폴더 — 설정 탭에서 옵시디언 보관함처럼 바꿀 수 있다 (2026-07-25)."""
    target = (st.session_state.get("docx5_active_dir") or "").strip()
    if target:
        return Path(target)
    try:
        data = json.loads(cfg.CONFIG_FILE.read_text(encoding="utf-8")) if cfg.CONFIG_FILE.exists() else {}
        target = str(data.get("dirs", {}).get("docx", "")).strip()
        if target:
            return Path(target).expanduser()
    except Exception:
        pass
    return cfg.DOCX_DIR


def _current_hwpx_dir() -> Path:
    """HWPX 저장 폴더 — DOCX와 동일한 방식 (2026-08-09)."""
    target = (st.session_state.get("hwpx5_active_dir") or "").strip()
    if target:
        return Path(target)
    try:
        data = json.loads(cfg.CONFIG_FILE.read_text(encoding="utf-8")) if cfg.CONFIG_FILE.exists() else {}
        target = str(data.get("dirs", {}).get("hwpx", "")).strip()
        if target:
            return Path(target).expanduser()
    except Exception:
        pass
    return cfg.HWPX_DIR


def _current_epub_dir() -> Path:
    """EPUB 저장 폴더 — DOCX/HWPX와 동일한 방식 (2026-08-11)."""
    target = (st.session_state.get("epub5_active_dir") or "").strip()
    if target:
        return Path(target)
    try:
        data = json.loads(cfg.CONFIG_FILE.read_text(encoding="utf-8")) if cfg.CONFIG_FILE.exists() else {}
        target = str(data.get("dirs", {}).get("epub", "")).strip()
        if target:
            return Path(target).expanduser()
    except Exception:
        pass
    return cfg.EPUB_DIR


# ★완료 알림은 **화면 맨 아래**에서 그린다 (2026-08-26 연구자 요청).
# 위에 두면 처리를 마친 뒤 «다음 단계» 버튼을 보려고 스크롤을 되올려야 했다.
# 방금 처리한 목록 바로 아래에 있어야 눈이 가는 자리에 있다.
_render_ocr_notice()
_render_update_notice()


def _checklist_keys(items: list[dict], prefix: str) -> list[str]:
    """항목별 위젯 키. 같은 key(예: 동일 stem의 .txt/.md 공존)가 있으면
    뒤쪽에 __N을 붙여 StreamlitDuplicateElementKey 크래시를 막는다. (2026-07-06)"""
    keys, seen = [], {}
    for it in items:
        k = f"{prefix}_{it['key']}"
        n = seen.get(k, 0)
        seen[k] = n + 1
        keys.append(k if n == 0 else f"{k}__{n}")
    return keys


def _checklist(items: list[dict], prefix: str, height: int = 320, viewable: bool = False,
               renamable: bool = False) -> list:
    """체크박스 파일 목록. items=[{"key":str,"label":str,"meta":str,"obj":any,"group":str?}]

    renamable=True면 각 줄에 ✏️ 단추가 붙어 **목록 안에서 바로** 장 제목을 고칠 수 있다.
    잘못된 제목은 대개 요약을 돌리려다 눈에 띄므로, 다른 화면으로 옮겨가지 않고 그
    자리에서 고치는 편이 낫다(2026-08-17). 항목에 "rename": (책 stem, 장 번호)를 담아야
    동작한다.
    "group"이 있으면 같은 값이 연속될 때마다 책 이름 소제목을 붙이고, 그 옆에
    책 전체를 한 번에 선택/해제하는 체크박스를 함께 둔다(선택 단위 자체는 항목별
    그대로 — 위키탭처럼 책 단위로 고를 수 있게, 2026-07-25).
    Returns: 선택된 obj 목록."""
    _keys = _checklist_keys(items, prefix)
    _group_indices: dict[str, list[int]] = {}
    for idx, it in enumerate(items):
        _g = it.get("group")
        if _g is not None:
            _group_indices.setdefault(_g, []).append(idx)
    _has_groups = bool(_group_indices)  # 항목을 책 제목 아래 하위 트리처럼 들여쓸지 (2026-07-25)

    def _toggle_group(grp: str, grp_key: str) -> None:
        _val = st.session_state.get(grp_key, False)
        for j in _group_indices.get(grp, []):
            st.session_state[_keys[j]] = _val

    h1, h2, h3 = st.columns([1.3, 1, 4])
    if h1.button(t("전체 선택"), icon=":material/select_all:", key=f"{prefix}_sa", use_container_width=True):
        for _k in _keys:
            st.session_state[_k] = True
        st.rerun()
    if h2.button(t("해제"), icon=":material/deselect:", key=f"{prefix}_da", use_container_width=True):
        for _k in _keys:
            st.session_state[_k] = False
        st.rerun()
    h3.caption(tf("총 %d개", len(items)))
    selected = []
    with st.container(height=height, border=True):
        _prev_group = object()  # 실제 group 값과 절대 같을 수 없는 표식
        for idx, it in enumerate(items):
            _grp = it.get("group")
            if _grp is not None and _grp != _prev_group:
                _grp_key = f"{prefix}_grpchk_{_re.sub(r'[^a-zA-Z0-9가-힣_-]+', '_', str(_grp))[:60]}"
                _agg = all(st.session_state.get(_keys[j], False) for j in _group_indices[_grp])
                if st.session_state.get(_grp_key) != _agg:
                    st.session_state[_grp_key] = _agg
                _ghc1, _ghc2 = st.columns([0.05, 0.95])
                _ghc1.checkbox(" ", key=_grp_key, label_visibility="collapsed",
                               on_change=_toggle_group, args=(_grp, _grp_key),
                               help=t("이 책 전체 선택/해제"))
                _ghc2.markdown(f"**📚 {_grp}**")
                _prev_group = _grp
            k = _keys[idx]
            # 그룹(책)이 있는 목록이면 항목 행을 들여써서 책 제목 아래 하위
            # 트리처럼 보이게 한다 — 그룹 헤더와 나란한 평평한 목록으로 안 보이도록.
            _rn_here = renamable and it.get("rename") is not None
            _rn_w = [0.07] if renamable else []
            if _has_groups:
                _spec = [0.04, 0.05, 0.78 - sum(_rn_w)] + _rn_w + ([0.13] if viewable else [])
                if not viewable:
                    _spec = [0.04, 0.05, 0.91 - sum(_rn_w)] + _rn_w
                cols = st.columns(_spec)
                c1, c2 = cols[1], cols[2]
            else:
                _spec = [0.05, (0.82 if viewable else 0.95) - sum(_rn_w)] + _rn_w + ([0.13] if viewable else [])
                cols = st.columns(_spec)
                c1, c2 = cols[0], cols[1]
            _rn_col = cols[-2] if (renamable and viewable) else (cols[-1] if renamable else None)
            _view_col = cols[-1] if viewable else None
            chk = c1.checkbox(" ", key=k, label_visibility="collapsed")
            _label_prefix = "↳ " if _has_groups else ""
            _editing = _rn_here and st.session_state.get(f"{prefix}_rn_open") == k
            if _editing:
                _rn_book, _rn_idx = it["rename"]
                _rn_val = c2.text_input(t("장 제목"), value=it.get("title", it["label"]),
                                        key=f"{prefix}_rn_val_{idx}", label_visibility="collapsed")
                if _rn_col.button("", icon=":material/check:", key=f"{prefix}_rn_ok_{idx}",
                                  help=t("제목 저장")):
                    if _rn_val.strip():
                        cmap.rename_chapter(DEFAULT_WS, _rn_book, _rn_idx, _rn_val.strip())
                    st.session_state.pop(f"{prefix}_rn_open", None)
                    st.rerun()
            else:
                c2.markdown(
                    f"{_label_prefix}**{it['label']}** &nbsp;<small style='color:#9ca3af'>{it['meta']}</small>",
                    unsafe_allow_html=True,
                )
                if _rn_here and _rn_col.button("", icon=":material/edit:", key=f"{prefix}_rn_{idx}",
                                               help=t("장 제목 고치기")):
                    st.session_state[f"{prefix}_rn_open"] = k
                    st.rerun()
            if viewable:
                target = _view_target_from_item(it)
                safe_key = _re.sub(r"[^a-zA-Z0-9가-힣_-]+", "_", str(it["key"]))[:80]
                if _view_col.button(t("보기"), icon=":material/visibility:", key=f"{prefix}_view_{idx}_{safe_key}", use_container_width=True,
                                     disabled=target is None):
                    open_path(target, reveal=target.is_file())
            if chk:
                selected.append(it["obj"])
    return selected






_TQ_CACHE: dict[tuple, object] = {}


def _quality_of(path, text: str = ""):
    """책 한 권의 진단 — 파일 수정 시각으로 캐시한다(리런마다 전문을 다시 훑지 않게)."""
    p = Path(path)
    try:
        key = (str(p), p.stat().st_mtime_ns)
    except OSError:
        return textquality.Assessment()
    if key not in _TQ_CACHE:
        _TQ_CACHE[key] = (textquality.assess(unicodedata.normalize("NFC", text))
                          if text else textquality.assess_file(p))
    return _TQ_CACHE[key]

def _df_height(rows: int, max_rows: int = 12) -> int:
    """줄 수에 맞춘 st.dataframe 높이. 기본값은 줄이 몇이든 ~400px로 고정돼서
    한두 줄짜리 표 아래가 통째로 빈칸이 된다 (2026-08-24)."""
    return 38 + 36 * max(1, min(rows, max_rows))

_AXIS_ICON = {"bad": "🔴", "suspect": "🟡", "ok": "🟢", "unknown": "⚪"}


def _scan_text_quality(paths=None) -> list[dict]:
    """변환된 본문 TXT를 진단해 표로 쓸 행 목록을 만든다 (2026-08-24).

    paths=None이면 보관된 TXT를 전부 훑고, 목록을 주면 그것만 본다 — 변환 직후에는
    방금 뽑은 책만 보여야 지난 책 수십 권이 딸려 오지 않는다."""
    if paths is None:
        seen, targets = set(), []
        # ★**활성 사본을 먼저** 본다. 같은 이름이 보관 폴더에도 있으면 하나만 남기는데,
        # 보관본을 먼저 잡으면 재OCR이 **보관본만 고치고** 정작 다음 단계(장별 분할)가
        # 읽는 활성 사본은 불량인 채 남는다. 실제로 『기술신학』이 그랬다 — 373쪽을
        # 다시 읽고도 분할 탭에는 계속 🔴가 떴다 (2026-08-25).
        for d in (cfg.TXT_DIR, cfg.TXT_ARCHIVE_DIR):
            if not d.exists():
                continue
            for f in sorted(d.rglob("*.txt")):
                if _nfc(f.stem) in seen:
                    continue
                seen.add(_nfc(f.stem))
                targets.append(f)
    else:
        targets = [Path(x) for x in paths if str(x).lower().endswith(".txt")]

    rows = []
    for f in targets:
        a = textquality.assess_file(f)
        rows.append({
            "stem": _nfc(f.stem), "verdict": a.verdict, "badge": a.badge,
            "pct": a.one_syllable_pct, "garble": a.garble_per_1k,
            "word_loss": a.word_loss, "garble_v": a.garble, "summary": a.summary(),
            "pdf": str(cfg.PDF_DIR / f"{f.stem}.pdf"), "txt": str(f),
        })
    rows.sort(key=lambda r: ({"bad": 0, "suspect": 1, "ok": 2}.get(r["verdict"], 3), r["pct"]))
    return rows

def _parse_page_range(text: str, max_page: int) -> list[int]:
    """"200-210, 250" 같은 입력을 쪽 번호 목록으로. 범위 밖은 조용히 버린다."""
    pages: set[int] = set()
    for chunk in _re.split(r"[,\s]+", (text or "").strip()):
        if not chunk:
            continue
        m = _re.fullmatch(r"(\d+)\s*[-~]\s*(\d+)", chunk)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            pages.update(range(min(a, b), max(a, b) + 1))
        elif chunk.isdigit():
            pages.add(int(chunk))
    return sorted(p for p in pages if 1 <= p <= max_page)

def _translate_engine_radio(label: str, key: str) -> str:
    _avail = [(eid, lbl) for eid, lbl, av, _ in translate_engine_options() if av]
    _ids = [eid for eid, _lbl in _avail]
    _labels = [lbl for _eid, lbl in _avail]
    _wp, _wm = llm.wiki_provider_model()
    _wiki_engine = f"{_wp}:{_wm}" if _wp and _wm else ""
    _pref = llm.get_pref("translate_engine", "")
    _default = _wiki_engine if _wiki_engine in _ids else (_pref if _pref in _ids else (_ids[0] if _ids else ""))
    _idx = _ids.index(_default) if _default in _ids else 0
    _sel = st.radio(t(label), _labels, index=_idx, horizontal=True, key=key)
    _engine = _ids[_labels.index(_sel)]
    if _engine != _pref:
        llm.set_pref("translate_engine", _engine)
    return _engine


def _wiki_model_radio(key: str) -> tuple[str, str]:
    """사용 가능한 AI 모델 radio 선택기. (prov, model) 반환.
    선택이 현재 wiki_provider_model과 다르면 자동으로 set_wiki_model 호출."""
    _avail = [(p, m)
              for p, info in llm.PROVIDERS.items()
              if llm.has_key(p)
              for m in info["models"]]
    if not _avail:
        st.warning(t("사용 가능한 AI 없음 — :material/settings: 설정 탭에서 API 키를 입력하세요."),
                   icon=":material/warning:")
        return llm.wiki_provider_model()
    _wp, _wm = llm.wiki_provider_model()
    _labels = [f"{llm.PROVIDERS[p]['label']} · {m}" for p, m in _avail]
    _cur = f"{llm.PROVIDERS.get(_wp, {}).get('label', _wp)} · {_wm}"
    _idx = _labels.index(_cur) if _cur in _labels else 0
    _sel = st.radio(t("🤖 AI 모델"), _labels, index=_idx, horizontal=True, key=key)
    _p, _m = _avail[_labels.index(_sel)]
    if (_p, _m) != (_wp, _wm):
        llm.set_wiki_model(_p, _m)
    return _p, _m


def _settings_engine_id() -> str:
    """설정에서 선택된 AI의 번역 엔진 id (provider:model)."""
    _wp, _wm = llm.wiki_provider_model()
    return f"{_wp}:{_wm}" if _wp and _wm else ""


_loading_step("화면 구성 중…", "탭과 UI를 초기화하고 있습니다")

# ── 1: TXT변환 / 전체 실행 ───────────────────────────────
if _active_view in {"1_txt", "all_run"}:
    _pdf_dir1 = cfg.PDF_DIR
    _stage_flow_panel(
        ":material/description: 텍스트 변환",
        "PDF·DOCX·HWP·HWPX에서 텍스트를 추출해 TXT로 저장합니다 (스캔 PDF는 OCR 사전 처리 필요).",
        [
            ("① 처리전 · 업로드 대기", UPLOAD_TMP,
             tf("%d개 대기", _count_files(UPLOAD_TMP, ['*.pdf', '*.docx', '*.hwp', '*.hwpx', '*.txt', '*.md']))),
            ("② 처리후 · 변환 TXT", cfg.TXT_DIR,
             tf("%d권 변환됨", _count_files(cfg.TXT_DIR, ['*.txt']))),
            ("📄 원본 문서 보관", _pdf_dir1,
             tf("%d개 보관", _count_files(_pdf_dir1, ['*.pdf', '*.docx', '*.hwp', '*.hwpx']))),
        ],
        "flow1",
    )

    _ws1 = DEFAULT_WS
    _fast1 = True

    # 파일 업로드
    _uploads1 = st.file_uploader(
        t("PDF·DOCX·HWP·HWPX·TXT 업로드 (여러 파일 가능)"),
        type=["pdf", "docx", "hwp", "hwpx", "txt", "md"], accept_multiple_files=True, key="ocr_uploader",
    )
    st.caption(t(_DND_HINT))
    if _uploads1:
        # 파일명이 아니라 내용 해시(토큰)로 "이미 대기열에 올렸는지" 추적한다 — 처리 완료 후
        # 이 추적을 지워버리면(예전 방식), 업로더 위젯은 파일을 계속 들고 있어서 다음
        # rerun에 똑같은 파일이 "새로 업로드된 것"으로 오인돼 UPLOAD_TMP에 다시 쓰이고,
        # 중복확인 응답까지 초기화돼 "이미 처리된 파일" 경고가 다시 뜨는 버그가 있었다
        # (2026-08-12). 토큰은 내용 기반이라 처리 후에도 계속 남겨둬도 안전 — 진짜 다른
        # 내용으로 재업로드되면 토큰 자체가 달라져 정상적으로 새로 인식된다.
        _already_queued1 = set(st.session_state.get("_ocr_queued", []))
        _added1 = []
        for _uf_new in _uploads1:
            _uf_new_bytes = _uf_new.getvalue()
            _uf_new_token = _upload_token(_uf_new.name, _uf_new_bytes)
            if _uf_new_token in _already_queued1:
                continue  # 이미 대기 목록에 추가된 파일 건너뜀
            _dest1 = UPLOAD_TMP / _uf_new.name
            try:
                _dest1.write_bytes(_uf_new_bytes)
                _added1.append(_uf_new.name)
                _already_queued1.add(_uf_new_token)
                # 같은 이름으로 새로 올라온 파일이므로 예전 중복확인 응답은 무효화
                # (내용이 바뀌었을 수 있음 — 다시 물어야 함).
                st.session_state.get("_ocr_dup_confirmed", set()).discard(_uf_new.name)
                st.session_state.get("_ocr_dup_dismissed", set()).discard(_uf_new.name)
            except Exception as _e1:
                st.error(f"❌ 저장 실패: {_uf_new.name} — {_e1}")
        st.session_state["_ocr_queued"] = sorted(_already_queued1)
        if _added1:
            # 이번에 실제로 올린 파일 이름 — "이미 처리된 파일" 확인은 이것들만 대상으로
            # 한다. 대기 폴더에 남은 옛 잔재까지 물으면 예전 책이 계속 쌓여 보인다
            # (2026-08-18 사용자 지적).
            st.session_state["_ocr_uploaded"] = sorted(
                set(st.session_state.get("_ocr_uploaded", [])) | set(_added1))
            st.success(tf("📥 처리 대기 목록에 추가됨: %s", ", ".join(_added1)))
            st.rerun()  # 대기 목록 갱신 (세션스테이트로 중복 저장 방지됨)

    with st.expander(t("🔎 논문 출처로 가져오기"), expanded=False):
        _paper_src1 = st.text_input(
            t("논문 출처"),
            key="ocr1_paper_source",
            placeholder=t("URL, DOI(10.xxxx/...), doi:..., arXiv 번호 또는 arxiv.org 링크"),
        )
        st.caption(t(
            "💡 URL이 잘 안 될 때: ① 로그인·구독이 필요한 페이지(대학도서관·유료 저널)나 "
            "본문이 아닌 소개 페이지 링크는 받아올 수 없습니다 — PDF를 내려받아 위에서 직접 업로드하세요. "
            "② DOI(10.xxxx/…)나 arXiv 번호(예: 2412.12107)가 있으면 그 값을 넣는 편이 가장 안정적입니다. "
            "③ 링크 끝이 `.pdf`인 직접 주소를 쓰세요. ④ 그래도 안 되면 브라우저에서 PDF를 저장한 뒤 업로드하는 방법이 가장 확실합니다."
        ))
        if st.button(t("다운로드 확인 후 TXT 저장"), icon=":material/download:", key="ocr1_source_prepare",
                     use_container_width=True, type="primary",
                     disabled=not _paper_src1.strip()):
            _ok_prep1 = False
            with st.status(t("논문 출처 확인 중…"), expanded=True):
                _ok_dl1, _src_file1, _reason1 = download_paper_source(_paper_src1)
                if not _ok_dl1 or not _src_file1:
                    st.error(tf("(%s) 때문에 가져올 수 없습니다.", _reason1))
                else:
                    st.write(tf("✅ 다운로드 가능: `%s`", _src_file1.name))
                    _ok_prep1, _final_txt1, _final_pdf1, _msg_prep1 = prepare_downloaded_paper_source(_src_file1, _paper_src1)
                    if _ok_prep1:
                        st.success(tf("✅ TXT 저장 완료: %s", _msg_prep1))
                        if _final_pdf1:
                            st.write(tf("📄 원본 PDF 보관: `%s`", _final_pdf1))
                    else:
                        st.error(tf("(%s) 때문에 TXT로 저장할 수 없습니다.", _msg_prep1))
            if _ok_dl1 and _src_file1 and _ok_prep1:
                # rerun 후에도 TXT/PDF 위치를 열어볼 수 있게 세션에 보존
                st.session_state["paper1_result"] = {
                    "name": _src_file1.name,
                    "txt": str(_final_txt1) if _final_txt1 else "",
                    "pdf": str(_final_pdf1) if _final_pdf1 else "",
                }
                _src_file1.unlink(missing_ok=True)   # Temp에 받은 원본 정리 (보관본은 pdf/에 복사됨)
                st.rerun()

    _pr1 = st.session_state.get("paper1_result")
    if _pr1:
        with st.container(border=True):
            _prh1, _prh2 = st.columns([5, 1])
            _prh1.markdown(tf("**🔎 최근 가져온 논문:** %s", _pr1["name"]))
            if _prh2.button(t("닫기"), icon=":material/close:", key="paper1_result_close", use_container_width=True):
                st.session_state.pop("paper1_result", None)
                st.rerun()
            _txt_p1 = Path(_pr1["txt"]) if _pr1.get("txt") else None
            _pdf_p1 = Path(_pr1["pdf"]) if _pr1.get("pdf") else None
            _pra1, _prb1 = st.columns([4.2, 1])
            _pra1.caption(tf("📝 변환 TXT: %s", _txt_p1 if _txt_p1 else "—"))
            if _prb1.button(t("위치 열기"), icon=":material/folder_open:", key="paper1_open_txt", use_container_width=True,
                            disabled=not (_txt_p1 and _txt_p1.exists())):
                open_path(_txt_p1, reveal=True)
            _pra2, _prb2 = st.columns([4.2, 1])
            _pra2.caption(tf("📄 원본 PDF: %s", _pdf_p1 if _pdf_p1 else t("— (TXT 출처라 PDF 없음)")))
            if _prb2.button(t("위치 열기"), icon=":material/folder_open:", key="paper1_open_pdf", use_container_width=True,
                            disabled=not (_pdf_p1 and _pdf_p1.exists())):
                open_path(_pdf_p1, reveal=True)

    st.divider()

    # 처리 대기 목록 (UPLOAD_TMP) — 이미 변환된(TXT 존재) 원본은 기본 제외해 잔재가
    # 대기에 계속 뜨는 문제 방지(변환 실패로 TXT 없는 것은 그대로 남아 재시도 가능).
    # 다만 같은 파일명이라도 내용이 바뀌었을 수 있으므로, 제외하기 전에 사용자에게
    # 다시 처리할지 먼저 물어본다(2026-08-09).
    _converted_stems1 = {_nfc(p.stem) for p in cfg.TXT_DIR.rglob("*.txt")} if cfg.TXT_DIR.exists() else set()
    _dup_confirmed1 = st.session_state.setdefault("_ocr_dup_confirmed", set())
    _dup_dismissed1 = st.session_state.setdefault("_ocr_dup_dismissed", set())
    _all_uploaded1 = (
        [f for f in UPLOAD_TMP.glob("*")
         if f.is_file() and f.suffix.lower() in {".pdf", ".docx", ".hwp", ".hwpx", ".txt", ".md"}]
        if UPLOAD_TMP.exists() else []
    )
    # 변환이 끝난 뒤 남은 원본은 대기 폴더에 그대로 있다. 그것까지 "다시 처리할까요?"로
    # 물으면 예전에 처리한 책이 계속 쌓여 보인다(2026-08-17 사용자 지적). **새로 넣은
    # 파일일 때만** 묻는다 — 이미 만들어진 TXT보다 원본이 나중 것이면 원고가 바뀐 것이다.
    _txt_mtime1 = {}
    if cfg.TXT_DIR.exists():
        for _p1 in cfg.TXT_DIR.rglob("*.txt"):
            _k1 = _nfc(_p1.stem)
            _txt_mtime1[_k1] = max(_txt_mtime1.get(_k1, 0), _p1.stat().st_mtime)

    def _is_newer_upload1(f: Path) -> bool:
        prev = _txt_mtime1.get(_nfc(f.stem))
        return prev is None or f.stat().st_mtime > prev + 60

    _uploaded_now1 = set(st.session_state.get("_ocr_uploaded", []))
    _dup_unconfirmed1 = sorted(
        [f for f in _all_uploaded1
         if f.name in _uploaded_now1                      # 이번에 올린 파일만 묻는다
         and _nfc(f.stem) in _converted_stems1 and _is_newer_upload1(f)
         and f.name not in _dup_confirmed1 and f.name not in _dup_dismissed1],
        key=lambda f: f.stat().st_mtime, reverse=True,
    )
    if _dup_unconfirmed1:
        st.warning(t("⚠️ 이미 처리된 적 있는 파일명이 있습니다 — 원고 내용이 바뀌었을 수 있습니다. 다시 처리할까요?"))
        for _dupf1 in _dup_unconfirmed1:
            _dc1, _dc2, _dc3 = st.columns([4, 1.3, 1.3])
            _dc1.markdown(f"`{_dupf1.name}`")
            if _dc2.button(t("다시 처리"), icon=":material/refresh:", key=f"dup_redo_{_dupf1.name}",
                            use_container_width=True, type="primary"):
                _dup_confirmed1.add(_dupf1.name)
                st.rerun()
            if _dc3.button(t("건너뛰기"), icon=":material/close:", key=f"dup_skip_{_dupf1.name}",
                            use_container_width=True):
                _dup_dismissed1.add(_dupf1.name)
                _dupf1.unlink(missing_ok=True)
                st.rerun()
        st.divider()
    _pending_all1 = sorted(
        [f for f in _all_uploaded1
         if _nfc(f.stem) not in _converted_stems1 or f.name in _dup_confirmed1],
        key=lambda f: f.stat().st_mtime, reverse=True,
    )
    st.markdown(tf("#### 처리 대기 (%d개)", len(_pending_all1)))
    if _pending_all1:
        _items1 = [
            {"key": f.name,
             "label": f.name,
             "meta": f"{f.stat().st_size//1024}KB · {datetime.fromtimestamp(f.stat().st_mtime).strftime('%m-%d %H:%M')}",
             "obj": _PathAsUpload(f)}
            for f in _pending_all1
        ]
        _sel1 = _checklist(_items1, "ocr1", height=250, viewable=True)
        _b1c1, _b1c2 = st.columns(2)
        _run_sel1 = _b1c1.button(tf("텍스트 변환 처리 (%d개)", len(_sel1)), icon=":material/play_arrow:", key="ocr1_run_sel",
                                   use_container_width=True, type="primary", disabled=len(_sel1)==0)
        _del1 = _b1c2.button(tf("삭제 (%d개)", len(_sel1)), icon=":material/delete:", key="ocr1_del_sel",
                             use_container_width=True, disabled=len(_sel1)==0)
        if _del1 and _sel1:
            for _dobj1 in _sel1:
                try:
                    Path(_dobj1._p).unlink(missing_ok=True)
                except Exception:
                    pass
            st.rerun()
        _to_run1 = _sel1 if _run_sel1 else []
        if _to_run1:
            _prog1 = st.progress(0.0)
            _done_txt_paths1: list[Path] = []
            _ocr_needed1: list[str] = []
            _notes1: list[str] = []
            for _i1, _uf1 in enumerate(_to_run1, 1):
                with st.status(f"텍스트 변환 [{_i1}/{len(_to_run1)}]: {_uf1.name}", expanded=False):
                    _r1 = _do_ocr_only(_uf1, _ws1, fast=_fast1)
                if _r1["ok"] and _r1.get("txt_path"):
                    _done_txt_paths1.append(Path(_r1["txt_path"]))
                    _note1 = _r1.get("note") or ""
                    st.success(f"✅ {_uf1.name} → `{Path(_r1['txt_path']).name}`"
                               + (f" — ⚠️ {_note1}" if _note1 else ""))
                    if _note1:
                        _notes1.append(f"{_uf1.name}: {_note1}")
                elif _r1.get("needs_ocr"):
                    _ocr_needed1.append(_uf1.name)
                    st.warning(f"🖼️ {_uf1.name}: {_r1['error']}")
                else:
                    st.error(f"❌ {_uf1.name}: {_r1['error']}")
                _prog1.progress(_i1 / len(_to_run1))
            if _done_txt_paths1:
                # 방금 뽑은 본문을 곧바로 진단한다 — 불량 텍스트 레이어를 그대로 퍼 온 것이
                # 요약·EPUB·위키를 다 태운 뒤에야 드러나던 사고를 여기서 끊는다 (2026-08-24).
                st.session_state["tq_rows"] = _scan_text_quality(_done_txt_paths1)
                st.session_state.pop("tq_dismissed", None)
                _bad_now1 = [r for r in st.session_state["tq_rows"] if r["verdict"] == "bad"]
                _msg1 = tf("%d개 파일 처리를 마쳤습니다. 다음 단계에서 장별 분할을 진행하세요.", len(_done_txt_paths1))
                if _bad_now1:
                    _msg1 = tf("%d개 파일 처리를 마쳤습니다.", len(_done_txt_paths1)) + "\n\n" + tf(
                        "🔴 그중 **%d권**은 본문 품질이 불량합니다(한 글자 낱말 누락). "
                        "장별 분할로 넘어가기 전에 아래 «본문 품질 검사»를 확인하세요: %s",
                        len(_bad_now1), ", ".join(r["stem"] for r in _bad_now1))
                if _notes1:
                    _msg1 += "\n\n" + t("⚠️ 일부 문서는 처리 중 특이사항이 있었습니다 (자동 보정됨):") \
                             + "\n\n" + "\n".join(f"- {x}" for x in _notes1)
                if _ocr_needed1:
                    _msg1 += "\n\n" + tf("⚠️ 다음 %d개 문서는 이미지로만 되어 있어 OCR 사전 처리가 필요합니다: %s",
                                         len(_ocr_needed1), ", ".join(_ocr_needed1))
                # 🔴 불량본이 있으면 다음 단계가 아니라 **재OCR**을 묻는다 —
                # 분할·번역·요약·EPUB·위키가 전부 이 TXT에서 파생되므로, 불량인 채로
                # 넘기면 나중에 되돌릴 때 파생물을 전부 다시 만들어야 한다 (2026-08-24).
                if _bad_now1:
                    def _yes_reocr1(_items=[_nfc(p.stem) for p in _done_txt_paths1]):
                        st.session_state.pop("tq_dismissed", None)
                        st.rerun()

                    def _no_split1(_items=[_nfc(p.stem) for p in _done_txt_paths1]):
                        # 데려다만 놓는다 — 분할 실행은 그 화면에서 사람이 고른다.
                        st.session_state["tq_dismissed"] = True
                        _goto_view("2_split")

                    _q1 = tf("🔴 %d권은 본문이 불량합니다. AI로 다시 읽을까요?", len(_bad_now1))
                    _choices1 = [
                        {"label": t("예, AI로 다시 읽기"), "icon": ":material/auto_fix_high:",
                         "action": _yes_reocr1, "primary": True},
                        {"label": t("아니요, 이대로 분할"), "icon": ":material/arrow_forward:",
                         "action": _no_split1},
                    ]
                else:
                    _q1, _choices1 = t("다음은 **장별 분할**입니다."), None
                _set_stage_completion(
                    t("1-TXT변환 완료"),
                    _msg1,
                    next_stage="2_split",
                    open_target=_stage_folder("1_txt"),
                    question=_q1,
                    choices=_choices1,
                    kind="warning" if _bad_now1 else "success",
                    next_items=[_nfc(p.stem) for p in _done_txt_paths1],
                )
            elif _ocr_needed1:
                _set_ocr_notice(_ocr_needed1)
            st.rerun()
    else:
        st.info(t("대기 중인 파일 없음 — 위에서 PDF를 업로드하세요."))

    st.divider()

    # ── 🔬 본문 품질 검사 + AI 재OCR (2026-08-24) ─────────────────
    # 접어 둔 채로 아래에 두면 아무도 안 본다. 변환이 끝나면 자동으로 진단해서
    # 여기에 결과를 펼치고, 불량이면 "다시 읽을까요?" 하고 물어본 뒤에 실행한다.
    _rows_tq = st.session_state.get("tq_rows")
    if _rows_tq is None:
        # ★평소에는 버튼 하나만 둔다. 제목·설명 캡션을 늘 펼쳐 두니 화면이 무거웠다
        # (2026-08-26 연구자 요청). 설명은 «?» 도움말로 접는다.
        if st.button("🔬 " + t("본문 품질 검사"), icon=":material/science:", key="tq_scan",
                     help=t("변환된 본문이 쓸 만한지 봅니다. 두 가지를 따로 재요 — "
                            "낱말 유실(수·것·될 같은 한 글자 낱말이 통째로 빠짐, 정상 7~25%)과 "
                            "문자 깨짐(기合·디지!i처럼 글자가 뭉개짐). 실측상 둘은 서로 무관해서 "
                            "각자 기준으로 재고 나쁜 쪽을 따릅니다. 불량으로 나온 책은 여기서 "
                            "AI로 다시 읽을 수 있습니다. 다시 읽기는 쪽수에 따라 몇 분에서 수십 분까지 "
                            "걸릴 수 있습니다.")):
            st.session_state["tq_rows"] = _scan_text_quality(None)
            st.session_state.pop("tq_dismissed", None)
            st.rerun()
    else:
        # ★결과 요약 줄과 표를 뺐다 (2026-08-26 연구자 요청). 「🔴 0권 · 🟡 0권 ·
        # 🟢 0권」과 진단표가 늘 자리를 차지했는데, 정작 필요한 것은 **형편없는 책을
        # 다시 읽는 것** 하나였다. 좋으면 한 줄로 말하고 끝낸다.
        _bad_tq = [r for r in _rows_tq if r["verdict"] == "bad"]
        _sus_tq = [r for r in _rows_tq if r["verdict"] == "suspect"]
        if not _bad_tq:
            st.caption("🟢 " + (tf("본문 품질 확인함 — 다시 읽어야 할 책은 없습니다. (확인 권장 %d권)",
                                   len(_sus_tq)) if _sus_tq
                                else t("본문 품질 확인함 — 다시 읽어야 할 책은 없습니다.")))
        if st.button(t("다시 검사"), icon=":material/refresh:", key="tq_rescan"):
            st.session_state["tq_rows"] = _scan_text_quality(None)
            st.session_state.pop("tq_dismissed", None)
            st.rerun()

        # ── 불량본이 있으면 물어본다 ──
        if _bad_tq and not st.session_state.get("tq_dismissed"):
            st.warning(t("이 책들은 원본 PDF에 구워져 있던 불량 OCR 레이어를 그대로 가져온 상태라 "
                         "손볼 방법이 없습니다. 원본 이미지에서 **AI로 다시 읽어야** 합니다."))
            _sel_tq = st.selectbox(
                t("다시 읽을 책"), _bad_tq, key="tq_book",
                format_func=lambda r: f'{r["badge"]} {r["stem"]}')
            _pdf_tq = Path(_sel_tq["pdf"])
            if not _pdf_tq.exists():
                st.error(t("원본 PDF를 찾지 못했습니다 — 이미지에서 다시 읽을 수 없습니다.")
                         + f"  ({_pdf_tq})")
            else:
                _npages_tq = ai_ocr.page_count(_pdf_tq)
                _prov_opts = list(llm.CLI_PROVIDERS) + list(llm.API_PROVIDERS)
                _prov_lbl = {"codex_cli": t("Codex CLI (구독 · 추가 과금 없음)"),
                             "claude_cli": t("Claude CLI (구독 · 추가 과금 없음)")}
                _prov_tq = st.radio(
                    t("판독 공급자"), _prov_opts, horizontal=True, key="tq_prov",
                    format_func=lambda p: _prov_lbl.get(p, f"{p} API"))
                # 안내는 '실제로 판독할 쪽 수'로 계산해야 한다 — 시험 3쪽인데
                # 책 전체 기준으로 겁을 주면 안 된다. _pages_tq는 아래에서 정해지므로
                # 안내도 그 뒤로 미룬다.

                _c1_tq, _c2_tq = st.columns(2)
                _mode_tq = _c1_tq.radio(
                    t("범위"), ["sample", "all", "range"], key="tq_mode",
                    format_func=lambda m: {"sample": t("시험 3쪽"), "all": t("전체"),
                                           "range": t("쪽 지정")}[m])
                if _mode_tq == "range":
                    _rng_tq = _c2_tq.text_input(t("쪽 번호 (예: 200-210, 250)"), key="tq_range")
                    _pages_tq = _parse_page_range(_rng_tq, _npages_tq)
                elif _mode_tq == "sample":
                    _mid_tq = max(1, _npages_tq // 2)
                    _pages_tq = [_mid_tq, _mid_tq + 1, _mid_tq + 2]
                else:
                    _pages_tq = None
                _cnt_tq = len(_pages_tq) if _pages_tq else _npages_tq
                _c2_tq.metric(t("판독할 쪽"), f"{_cnt_tq:,} / {_npages_tq:,}")
                st.caption(tf(
                    "한 번에 %d쪽씩 · 동시 %d갈래 · **같은 쪽을 %d번 읽어 견줍니다** "
                    "— %d쪽이면 대략 %d분.",
                    ai_ocr.DEFAULT_PAGES_PER_CALL, ai_ocr.DEFAULT_WORKERS,
                    ai_ocr.DEFAULT_PASSES, _cnt_tq,
                    max(1, _cnt_tq * 13 * ai_ocr.DEFAULT_PASSES
                        // ai_ocr.DEFAULT_WORKERS // 60)))
                # 두 번 읽으면 한도도 두 배 쓴다 — 안내에 반영한다
                _cost_tq = ai_ocr.cost_notice(_prov_tq, _cnt_tq * ai_ocr.DEFAULT_PASSES)
                if _cost_tq.startswith("⚠️"):
                    st.warning(_cost_tq)
                    _ok_cost = st.checkbox(
                        t("비용·한도 소모를 이해했고 그대로 진행합니다"), key="tq_cost_ok")
                else:
                    st.info(_cost_tq)
                    _ok_cost = True

                # 상태는 작업 폴더의 파일로 본다 — 앱이 리로드·재시작돼도 이어진다
                # (프로세스 메모리에 뒀더니 «중단»이 먹통이 됐다, 2026-08-24)
                # ★재OCR 결과는 **그 책의 TXT가 실제로 있는 자리**에 써야 한다.
                # 보관 폴더로 못박아 두었더니, 『기술신학』 373쪽을 다시 읽어 1음절
                # 비율을 0.01%→8.7%로 되살리고도 **다음 단계(장별 분할)가 읽는 활성
                # 사본은 불량인 채 남아** 화면에 계속 🔴가 떴다 (2026-08-25).
                # 우선순위는 services/files.find_txt와 같다 — 활성 → 보관.
                _out_tq = next(
                    (c for c in (cfg.TXT_DIR / f"{_pdf_tq.stem}.txt",
                                 cfg.TXT_ARCHIVE_DIR / f"{_pdf_tq.stem}.txt") if c.exists()),
                    cfg.TXT_ARCHIVE_DIR / f"{_pdf_tq.stem}.txt")
                _running_tq = ai_ocr.is_running(_out_tq)
                _b1_tq, _b2_tq, _b3_tq = st.columns(3)
                if _b1_tq.button(t("예, 다시 읽겠습니다"), icon=":material/play_arrow:",
                                 key="tq_go", disabled=_running_tq or not _ok_cost,
                                 type="primary"):
                    _bak_tq = _out_tq.with_suffix(".txt.before_reocr")
                    if _out_tq.exists() and not _bak_tq.exists():
                        shutil.copy2(_out_tq, _bak_tq)      # 옛 본문은 반드시 남긴다
                    ai_ocr.start_background(_pdf_tq, _out_tq, _prov_tq, "", _pages_tq)
                    st.rerun()
                if _b2_tq.button(t("중단"), icon=":material/stop:", key="tq_stop",
                                 disabled=not _running_tq):
                    ai_ocr.request_stop(_out_tq)
                    _n_killed = ai_ocr.kill_orphans(_out_tq)
                    st.info(t("판독 중이던 쪽을 끊고 멈춥니다. 다시 시작하면 이어서 합니다.")
                            + (tf(" (진행 중이던 %d개 프로세스 종료)", _n_killed)
                               if _n_killed else ""))
                if _b3_tq.button(t("아니요, 이대로 진행"), key="tq_skip", disabled=_running_tq):
                    st.session_state["tq_dismissed"] = True
                    st.rerun()

                _st_tq = ai_ocr.status(_out_tq)
                if _running_tq:
                    _done_tq, _tot_tq = _st_tq.get("done", 0), max(1, _st_tq.get("total", 1))
                    # 한 쪽이 3~5분 걸리는 일이 있어 경과 초를 같이 보여준다 —
                    # 없으면 멈춘 것처럼 보인다 (2026-08-24 사용자 지적)
                    _el_tq = int(time.time() - _st_tq.get("page_started", time.time()))
                    st.progress(_done_tq / _tot_tq,
                                text=tf("%d / %d쪽 완료 · 지금 %d쪽 판독 중 (%d초째)",
                                        _done_tq, _tot_tq, _st_tq.get("page", 0), _el_tq))
                    time.sleep(3)
                    st.rerun()
                elif _st_tq.get("error"):
                    st.error(_st_tq["error"])

                # ── 검증 보고 ──
                _rep_tq = ai_ocr.load_report(_out_tq)
                if _rep_tq:
                    _warn_tq = [r for r in _rep_tq if r.status == "warn"]
                    _fail_tq = [r for r in _rep_tq if r.status == "failed"]
                    _unv_tq = [r for r in _rep_tq if r.status == "unverified"]
                    _chk_tq = [r for r in _rep_tq if r.status == "check"]
                    st.markdown(tf(
                        "**판독 결과** — 정상 %d쪽 · 🔎 두 판독 불일치 %d쪽 · 대조 불가 %d쪽 "
                        "· ⚠️ 확인 필요 %d쪽 · 실패 %d쪽",
                        sum(1 for r in _rep_tq if r.status == "ok"), len(_chk_tq),
                        len(_unv_tq), len(_warn_tq), len(_fail_tq)))
                    if _chk_tq:
                        st.info(t("🔎 같은 쪽을 두 번 읽어 견준 결과입니다. 아래 자리에서 "
                                  "판독이 갈렸으니 원문과 대조하세요 — 낱말 하나가 바뀌는 "
                                  "오독은 쪽 전체 유사도로는 걸리지 않습니다."))
                        _rows_chk = [{t("쪽"): r.page, t("앞말"): d["before"],
                                      t("1차 판독"): d["a"], t("2차 판독"): d["b"]}
                                     for r in _chk_tq for d in r.disagreements]
                        st.dataframe(pd.DataFrame(_rows_chk), use_container_width=True,
                                     hide_index=True, height=_df_height(len(_rows_chk)))
                    # 두 판독이 같이 틀린 경우까지 보려면 — 시끄러우므로 접어 둔다
                    _jn_tq = [(r.page, d) for r in _rep_tq for d in (r.judge_notes or [])]
                    if _jn_tq:
                        with st.expander(tf("🔬 로컬 판독과 다른 자리 %d곳 — 정밀 대조용",
                                            len(_jn_tq))):
                            st.caption(t("두 번 다 같게 잘못 읽으면 대조로는 안 걸립니다. "
                                         "로컬 OCR(Apple Vision)이 다르게 읽은 자리를 모았습니다 "
                                         "— 로컬 쪽이 틀린 경우가 더 많으니 참고로만 보세요."))
                            st.dataframe(
                                pd.DataFrame([{t("쪽"): p, t("앞말"): d["before"],
                                               t("채택본"): d["a"], t("로컬 판독"): d["b"]}
                                              for p, d in _jn_tq[:400]]),
                                use_container_width=True, hide_index=True,
                                height=_df_height(min(len(_jn_tq), 12)))
                    if _unv_tq:
                        st.caption(tf("대조 불가 %d쪽은 원본 레이어가 너무 깨져 견줄 수가 없던 "
                                      "쪽입니다(차례·판권 등). AI 판독을 그대로 채택했습니다.",
                                      len(_unv_tq)))
                    if _warn_tq or _fail_tq:
                        st.warning(t("아래 쪽은 원본과 어긋나 환각이 섞였을 수 있습니다. "
                                     "본문은 그대로 두었으니 직접 확인하세요."))
                        st.dataframe(
                            pd.DataFrame([{t("쪽"): r.page, t("상태"): r.status,
                                           t("유사도"): r.similarity,
                                           t("글자수"): f"{r.chars} / {r.base_chars}",
                                           t("사유"): r.note}
                                          for r in (_warn_tq + _fail_tq)]),
                            use_container_width=True, hide_index=True)
                    _new_tq = textquality.assess_file(_out_tq)
                    st.info(f"{_new_tq.badge} " + t("재OCR 후 진단: ") + _new_tq.summary())
                    st.caption(t("옛 본문은 `.before_reocr` 로 남겨 두었습니다. "
                                 "결과가 좋으면 챕터 분할부터 다시 진행하세요."))
        elif _bad_tq:
            st.caption(t("불량본을 그대로 두고 진행하기로 했습니다. 「다시 검사」를 누르면 다시 물어봅니다."))

    st.divider()

    # 실패 기록
    _fail1 = sorted([p for p in FAILED_DIR.rglob("*") if p.is_file()],
                    key=lambda p: p.stat().st_mtime, reverse=True) if FAILED_DIR.exists() else []
    if _fail1:
        with st.expander(tf("⚠️ 실패 %d건", len(_fail1))):
            for _ff1 in _fail1[:30]:
                _fc1, _fc2, _fc3 = st.columns([5, 1, 1])
                _fc1.caption(_ff1.name)
                if _fc2.button("", icon=":material/undo:", key=f"retry_f1_{_ff1}", help="재시도"):
                    shutil.move(str(_ff1), str(UPLOAD_TMP / _ff1.name)); st.rerun()
                if _fc3.button("", icon=":material/delete:", key=f"del_f1_{_ff1}", help="삭제"):
                    try: _ff1.unlink()
                    except Exception: pass
                    st.rerun()




# ── 2: 장별 분할 ────────────────────────────────────────
if _active_view == "2_split":
    _split_arch_dir2 = cfg.TXT_ARCHIVE_DIR

    def _archive_split_source(stem: str) -> bool:
        """분할이 끝난 원본 TXT/MD를 1_txt/완료/로 이동 (2026-07-07)."""
        moved = False
        _split_arch_dir2.mkdir(parents=True, exist_ok=True)
        for _ext in (".txt", ".md"):
            _srcf = cfg.TXT_DIR / (stem + _ext)
            if _srcf.exists():
                try:
                    shutil.move(str(_srcf), str(_split_arch_dir2 / _srcf.name))
                    moved = True
                except Exception:
                    pass
        return moved

    def _proc_split2(obj):
        _ws, _stem = obj["ws"], obj["stem"]
        # 재분할 확인을 받은 책이면, 옛 챕터·번역·요약이 새 챕터와 뒤섞이지 않도록
        # 먼저 폴더를 비운다(2026-08-09) — split_book_to_chapters는 같은 이름의
        # 챕터 파일만 덮어쓰고, 새 분할의 챕터 수가 줄면 옛 파일이 그대로 남는다.
        if _stem in st.session_state.get("_split_dup_confirmed", set()):
            _old_ch_dir = chapters_dir(_ws, _stem)
            if _old_ch_dir.exists():
                shutil.rmtree(_old_ch_dir, ignore_errors=True)
            # 재확인 없이 계속 통과되지 않도록, 처리 성공 여부와 무관하게 1회용으로 소진한다.
            st.session_state.get("_split_dup_confirmed", set()).discard(_stem)
            st.session_state.get("_split_dup_dismissed", set()).discard(_stem)
        _sn, _serr, _smode = split_book_to_chapters(_ws, _stem)
        if _serr:
            if _smode == "single":  # 장 구조 감지 실패 — 아래 '장 구조 미감지'에서 선택하게 함
                _pend_ns2 = st.session_state.get("split2_nosplit", [])
                if _stem not in _pend_ns2:
                    st.session_state["split2_nosplit"] = _pend_ns2 + [_stem]
            return False, f"{_stem}: {_serr}"
        _cdir = chapters_dir(_ws, _stem)
        _new = [str(f.relative_to(cfg.BASE_DIR)) for f in sorted(_cdir.glob("??_*.txt"))
                if not f.stem.endswith(_DERIVED)]
        if not _new:
            return False, f"{_stem}: 챕터 생성 안 됨"
        queue_remove("tab2_ready", [_stem])
        if _route_translate(_stem):
            st.session_state["split2_any_en"] = True
            queue_add("tab3_ready", _new)
        else:
            queue_add("tab4_ready", _new)
        _archive_split_source(_stem)
        _track_flow_book(_stem)
        # 방금 나눈 책은 «장 구분 확인» 목록에 바로 뜨게 한다
        st.session_state["_review_books"] = sorted(
            set(st.session_state.get("_review_books", [])) | {_nfc(_stem)})
        # 커버리지 미달 경고는 로그가 아니라 화면에 붙인다 — 본문 일부가 빠진 채로
        # 번역·요약·EPUB까지 진행되던 사고 방지 (2026-08-17)
        _cov_warn = LAST_SPLIT_WARNING.pop(_stem, "")
        _res_msg = f"{_stem} → {len(_new)}챕터 ({t(SPLIT_MODE_LABELS.get(_smode, _smode))})"
        return True, (f"{_res_msg} ⚠️ {_cov_warn}" if _cov_warn else _res_msg)

    def _split2_on_done():
        _any_en = st.session_state.pop("split2_any_en", False)
        _items2 = st.session_state.pop("_flow_books", [])
        _log2 = st.session_state.get("split2_log", [])
        _fails2 = [ln[2:].strip() for ln in _log2 if ln.startswith("❌")]
        _oks2 = [ln[2:].strip() for ln in _log2 if ln.startswith("✅")]
        if _fails2:
            # 일부/전부 실패 — 무조건 성공으로 뜨던 배너가 실제 결과와 어긋나던 문제 수정 (2026-07-23)
            _msg2 = (tf("%d권 분할 완료.", len(_oks2)) if _oks2 else t("분할된 책이 없습니다.")) + "\n\n" \
                    + tf("⚠️ %d권 분할 실패 — 대기 목록에 그대로 남아있습니다:", len(_fails2)) + "\n" \
                    + "\n".join(f"- {m}" for m in _fails2)
            _set_stage_completion(
                t("2-챕터 분할 결과") if _oks2 else t("2-챕터 분할 실패"),
                _msg2,
                next_stage=("3_translate" if _any_en else "4_summary") if _oks2 else None,
                open_target=_stage_folder("2_split"),
                kind="warning",
            )
            return
        _set_stage_completion(
            t("2-챕터 분할 완료"),
            t("분할을 마쳤습니다.")
            + (" " + t("외국어 책 → 번역") if _any_en else " " + t("한글 책 → 문서요약")),
            next_stage="3_translate" if _any_en else "4_summary",
            open_target=_stage_folder("2_split"),
            question=t("다음은 **번역**입니다.") if _any_en else t("다음은 **장별 요약**입니다."),
            next_items=_items2,
        )

    _ch_root2f = cfg.CHAPTERS_DIR
    _n_books2f = len([d for d in _ch_root2f.iterdir() if d.is_dir()]) if _ch_root2f.exists() else 0
    # 처리 중이면 최상단에서 진행 화면만 렌더(다른 위젯 건너뜀) — 대화형/수동 공통
    if _run_active("split2"):
        _run_panel("split2", "챕터 분할 처리 중", _proc_split2, on_done=_split2_on_done)
        st.stop()
    _stage_flow_panel(
        ":material/content_cut: 챕터 분할",
        "책 TXT를 챕터(Chapter) 단위 파일로 분리해 책별 폴더에 저장합니다.",
        [
            ("① 처리전 · 변환 TXT", cfg.TXT_DIR,
             tf("%d권", _count_files(cfg.TXT_DIR, ['*.txt', '*.md']))),
            ("② 처리후 · 챕터 폴더", _ch_root2f, tf("%d권 분할됨", _n_books2f)),
            ("✅ 완료 보관 (원본 TXT)", cfg.TXT_ARCHIVE_DIR,
             tf("%d권 보관", _count_files(cfg.TXT_ARCHIVE_DIR, ['*.txt', '*.md']))),
        ],
        "flow2",
    )
    _sp_prov2, _sp_model2 = llm.wiki_provider_model()

    # TXT 직접 업로드
    _up2 = st.file_uploader(t("TXT 직접 업로드"),
                              type=["txt", "md"], accept_multiple_files=True, key="split_uploader")
    st.caption(t(_DND_HINT))
    if _up2:
        # 내용 해시(토큰)로 "이미 이 업로드를 반영했는지" 추적한다 — 업로더 위젯은 파일을
        # 계속 들고 있으므로, 추적 없이 매 rerun마다 다시 저장 + 재분할 확인 상태를
        # 초기화하면 사용자가 '다시 분할'을 눌러도 바로 다음 rerun에 그 확인이 다시
        # 지워져 영원히 분할 대기에 안 뜨는 교착 상태가 됐다(2026-08-12).
        _split_up_seen2 = set(st.session_state.get("_split_up_tokens", []))
        _added_split_stems2: list[str] = []
        for _u2 in _up2:
            _u2_bytes = _u2.getvalue()
            _u2_token = _upload_token(_u2.name, _u2_bytes)
            if _u2_token in _split_up_seen2:
                continue
            _split_up_seen2.add(_u2_token)
            cfg.TXT_DIR.mkdir(parents=True, exist_ok=True)
            _dst2 = cfg.TXT_DIR / _u2.name
            _dst2.write_bytes(_u2_bytes)
            _stem_u2 = _nfc(Path(_u2.name).stem)
            _added_split_stems2.append(_stem_u2)
            # 같은 이름으로 새로 올라온 TXT이므로 예전 재분할 확인 응답은 무효화
            st.session_state.get("_split_dup_confirmed", set()).discard(_stem_u2)
            st.session_state.get("_split_dup_dismissed", set()).discard(_stem_u2)
        st.session_state["_split_up_tokens"] = sorted(_split_up_seen2)
        if _added_split_stems2:
            queue_add("tab2_ready", _added_split_stems2)
            st.success(tf("%d개 TXT 저장 완료", len(_added_split_stems2))); st.rerun()

    # ── 분할 대기 (큐 기반 + 1_txt/ 전체 폴백) ──────────────
    _q2_stems = queue_list("tab2_ready")
    _split_pend2: list[dict] = []
    _split_short2: list[dict] = []
    _split_bad_quality2: list[str] = []
    _txt_root2 = cfg.TXT_DIR

    # 큐에 없어도 1_txt/에 있는 TXT 모두 포함
    _all_txt2_stems = ({f.stem for f in _txt_root2.glob("*.txt")} | {f.stem for f in _txt_root2.glob("*.md")}) if _txt_root2.exists() else set()
    _q2_stems_set = set(_q2_stems)
    _extra2 = sorted(_all_txt2_stems - _q2_stems_set)  # 큐에 없는 TXT
    _all2_stems = list(_q2_stems) + _extra2

    # 이미 챕터가 있는 책은 기본 제외(과분할·중복 방지)하되, TXT가 다시 들어왔다면
    # 원고 내용이 바뀌었을 수 있으므로 조용히 건너뛰지 않고 먼저 물어본다(2026-08-09,
    # 텍스트변환 탭의 같은 문제 수정과 동일한 이유).
    _split_dup_confirmed2 = st.session_state.setdefault("_split_dup_confirmed", set())
    _split_dup_dismissed2 = st.session_state.setdefault("_split_dup_dismissed", set())
    _split_dup_unconfirmed2: list[dict] = []
    for _stem2 in _all2_stems:
        _txt2 = _txt_root2 / (_stem2 + ".txt")
        if not _txt2.exists():
            _txt2 = _txt_root2 / (_stem2 + ".md")
        if not _txt2.exists():
            continue
        _ch2 = chapters_dir(DEFAULT_WS, _stem2)
        _ch_txts2 = [f for f in (_ch2.glob("??_*.txt") if _ch2.exists() else [])
                     if not f.stem.endswith(_DERIVED)]
        _meta2 = f"{_txt2.stat().st_size//1024}KB" + ("" if _stem2 in _q2_stems_set else " ·미등록")
        _already2 = bool(_ch_txts2) and _stem2 not in _split_dup_confirmed2
        # 분할이 끝난 뒤에도 TXT가 1_txt/에 남아 있으면 계속 "다시 분할할까요?"가 뜬다.
        # **TXT가 챕터보다 새 것일 때만** 묻는다 — 그때가 원고가 다시 들어온 경우다
        # (2026-08-17 사용자 지적).
        _txt_newer2 = _txt2.stat().st_mtime > max(f.stat().st_mtime for f in _ch_txts2) + 60 \
                      if _ch_txts2 else True
        if _already2 and not _txt_newer2:
            continue                      # 분할 뒤 남은 잔재 — 조용히 제외
        if _already2 and _stem2 not in _split_dup_dismissed2:
            _split_dup_unconfirmed2.append({"stem": _stem2, "meta": _meta2})
            continue
        if _already2:  # 건너뛰기로 이미 응답함 — 조용히 제외
            continue
        _src2 = _txt2.read_text(encoding="utf-8", errors="ignore")
        # 불량 본문을 그대로 분할하면 아래 파생물(번역·요약·EPUB·위키)을 전부 다시
        # 만들어야 한다 — 목록에서 바로 보이게 배지를 단다 (2026-08-24)
        _q2 = _quality_of(_txt2, _src2)
        _label2 = _stem2 if _q2.verdict in ("ok", "unknown") else f"{_q2.badge} {_stem2}"
        _meta2q = _meta2 + (f" · {_q2.badge} " + t("본문 품질 확인 필요")
                            if _q2.verdict == "bad" else "")
        _item2 = {"key": _stem2, "label": _label2, "meta": _meta2q,
                  "obj": {"ws": DEFAULT_WS, "stem": _stem2}}
        if _q2.verdict == "bad":
            _split_bad_quality2.append(_stem2)
        if _is_small_document_for_whole_translation(_src2):
            _item2["text"] = _src2
            _split_short2.append(_item2)
        else:
            _split_pend2.append(_item2)

    if _split_bad_quality2:
        st.warning("🔴 " + tf(
            "다음 %d권은 본문 품질이 불량합니다(한 글자 낱말 누락·글자 깨짐). 이대로 분할하면 "
            "번역·요약·EPUB·위키까지 불량 본문으로 만들어집니다 — **1-텍스트 변환** 탭의 "
            "«🔬 본문 품질 검사»에서 AI로 다시 읽는 편이 낫습니다: %s",
            len(_split_bad_quality2), ", ".join(_split_bad_quality2)))
        if st.button(t("1-텍스트 변환으로 이동"), icon=":material/auto_fix_high:",
                     key="split2_goto_tq"):
            st.session_state.pop("tq_dismissed", None)
            _goto_view("1_txt")

    if _split_dup_unconfirmed2:
        st.warning(t(
            "⚠️ 이미 챕터 분할된 책과 같은 이름의 TXT가 있습니다 — 원고 내용이 바뀌었을 수 있습니다. "
            "다시 분할할까요? (다시 분할하면 이 책의 기존 챕터·번역·요약이 모두 삭제되고 새로 만들어집니다)"
        ))
        for _dupb2 in _split_dup_unconfirmed2:
            _bc1, _bc2, _bc3 = st.columns([4, 1.3, 1.3])
            _bc1.markdown(f"`{_dupb2['stem']}` ({_dupb2['meta']})")
            if _bc2.button(t("다시 분할"), icon=":material/refresh:", key=f"splitdup_redo_{_dupb2['stem']}",
                            use_container_width=True, type="primary"):
                _split_dup_confirmed2.add(_dupb2["stem"])
                st.rerun()
            if _bc3.button(t("건너뛰기"), icon=":material/close:", key=f"splitdup_skip_{_dupb2['stem']}",
                            use_container_width=True):
                _split_dup_dismissed2.add(_dupb2["stem"])
                st.rerun()
        st.divider()

    st.markdown(tf("#### 분할 대기 (%d권)", len(_split_pend2)))
    if _split_pend2:
        _sel2 = _checklist(_split_pend2, "split2", height=280, viewable=True)
        _b2c1, _b2c2, _b2c3 = st.columns(3)
        _rs2 = _b2c1.button(tf("분할 처리 (%d권)", len(_sel2)), icon=":material/play_arrow:", key="split2_run_sel",
                              use_container_width=True, type="primary", disabled=len(_sel2)==0)
        _next2 = _b2c2.button(tf("다음단계로 이동 (%d권)", len(_sel2)), icon=":material/arrow_forward:", key="split2_next",
                              use_container_width=True, disabled=len(_sel2)==0,
                              help=t("분할 없이 단일장으로 저장하고 한국어가 아니면 번역, 한국어면 문서요약으로 이동"))
        _del2 = _b2c3.button(tf("삭제 (%d권)", len(_sel2)), icon=":material/delete:", key="split2_del",
                             use_container_width=True, disabled=len(_sel2)==0)
        if _del2 and _sel2:
            for _dobj2 in _sel2:
                _dstem2 = _dobj2["stem"]
                for _dext2 in (".txt", ".md"):
                    try:
                        (_txt_root2 / (_dstem2 + _dext2)).unlink(missing_ok=True)
                    except Exception:
                        pass
                queue_remove("tab2_ready", [_dstem2])
            st.rerun()
        if _next2 and _sel2:
            # 다음단계로 이동: 분할 없이 단일장 저장 후 라우팅 (빠른 처리라 즉시)
            _completed2 = 0
            _queued_translate2 = 0
            _queued_summary2 = 0
            _done_stems2 = []
            for _s2 in _sel2:
                _ok2, _detail2, _new_chs2 = _save_book_as_single_chapter(_s2["ws"], _s2["stem"])
                if _ok2 and _new_chs2:
                    _completed2 += 1
                    _done_stems2.append(_s2["stem"])
                    if _route_translate(_s2["stem"]):
                        _queued_translate2 += 1
                    else:
                        _queued_summary2 += 1
                else:
                    st.warning(f"⚠️ {_s2['stem']}: {_detail2}")
            if _completed2:
                _next_stage2 = "3_translate" if _queued_translate2 else "4_summary"
                _set_stage_completion(
                    t("2-단일장 저장 완료"),
                    tf("%d건을 다음 단계로 보냈습니다.", _completed2)
                    + (" " + t("외국어 → 번역") if _queued_translate2 else " " + t("한글 → 문서요약")),
                    next_stage=_next_stage2,
                    open_target=_stage_folder("2_split"),
                    question=t("다음은 **번역**입니다.") if _queued_translate2 else t("다음은 **장별 요약**입니다."),
                    next_items=_done_stems2,
                )
                st.rerun()
        if _rs2 and _sel2:
            _run_start("split2", _sel2)
    else:
        if _split_short2:
            st.warning(t("⚠️ 짧은 문서가 감지되었습니다. 아래 '짧은 문서 확인'에서 분할 처리 또는 다음단계로 이동을 선택하세요."))
        else:
            st.info(t("분할 대기 없음 — 📄 텍스트 변환에서 TXT를 먼저 생성하거나 아래에서 수동 추가하세요"))

    if _split_short2:
        st.divider()
        st.markdown(tf("### ⚠️ 짧은 문서 확인 (%d권)", len(_split_short2)))
        st.caption(t("짧은 문서는 챕터로 나누기 애매합니다. 각 문서를 '보기'로 확인한 뒤, 아래에서 분할 처리·다음 단계 이동·삭제를 선택하세요."))
        _sel_short2 = _checklist(_split_short2, "shortsplit2", height=240, viewable=True)
        _shc1, _shc2, _shc3 = st.columns(3)
        _sh_split2 = _shc1.button(tf("분할 처리 (%d권)", len(_sel_short2)), icon=":material/play_arrow:",
                                  key="shortsplit2_split", use_container_width=True, disabled=len(_sel_short2) == 0)
        _sh_next2 = _shc2.button(tf("다음단계로 이동 (%d권)", len(_sel_short2)), icon=":material/arrow_forward:",
                                 key="shortsplit2_next", type="primary", use_container_width=True, disabled=len(_sel_short2) == 0,
                                 help=t("분할 없이 단일장으로 저장하고 한국어가 아니면 번역, 한국어면 문서요약으로 이동"))
        _sh_del2 = _shc3.button(tf("삭제 (%d권)", len(_sel_short2)), icon=":material/delete:",
                                key="shortsplit2_del", use_container_width=True, disabled=len(_sel_short2) == 0)

        if _sh_split2 and _sel_short2:
            _short_done2 = 0
            for _o2 in _sel_short2:
                _sn2, _serr2, _ = split_book_to_chapters(_o2["ws"], _o2["stem"], allow_short=True)
                if _serr2:
                    st.warning(f"⚠️ {_o2['stem']}: {_serr2}")
                    continue
                queue_remove("tab2_ready", [_o2["stem"]])
                _ch_dir2 = chapters_dir(_o2["ws"], _o2["stem"])
                _new_chs2 = [str(f.relative_to(cfg.BASE_DIR))
                             for f in sorted(_ch_dir2.glob("??_*.txt"))
                             if not f.stem.endswith(_DERIVED)]
                if _new_chs2:
                    queue_add("tab3_ready" if _route_translate(_o2["stem"]) else "tab4_ready", _new_chs2)
                    _archive_split_source(_o2["stem"])
                    _short_done2 += 1
                    st.session_state["_review_books"] = sorted(
                        set(st.session_state.get("_review_books", [])) | {_nfc(_o2["stem"])})

            if _short_done2:
                st.success(tf("%d권을 챕터로 분할했습니다.", _short_done2))
            st.rerun()

        if _sh_next2 and _sel_short2:
            _short_moved2 = 0
            _short_last_stage2 = "4_summary"
            for _o2 in _sel_short2:
                _txp2 = cfg.TXT_DIR / (_o2["stem"] + ".txt")
                if not _txp2.exists():
                    _txp2 = cfg.TXT_DIR / (_o2["stem"] + ".md")
                _src2 = _txp2.read_text(encoding="utf-8", errors="ignore") if _txp2.exists() else ""
                if not _src2.strip():
                    continue
                _one_path2, _ = _write_single_chapter_from_text(_o2["ws"], _o2["stem"], _src2)
                queue_remove("tab2_ready", [_o2["stem"]])
                _new_chs2 = [str(f.relative_to(cfg.BASE_DIR))
                             for f in sorted(_one_path2.parent.glob("??_*.txt"))
                             if not f.stem.endswith(_DERIVED)]
                _stage2 = "3_translate" if _route_translate(_o2["stem"]) else "4_summary"
                if _new_chs2:
                    queue_add("tab3_ready" if _stage2 == "3_translate" else "tab4_ready", _new_chs2)
                    _archive_split_source(_o2["stem"])
                    _short_moved2 += 1
                    _short_last_stage2 = _stage2
            if _short_moved2:
                _set_stage_completion(
                    t("2-단일장 저장 완료"),
                    tf("%d건을 단일장으로 저장해 다음 단계로 보냈습니다.", _short_moved2),
                    next_stage=_short_last_stage2,
                    open_target=_stage_folder("2_split"),
                )
            st.rerun()

        if _sh_del2 and _sel_short2:
            _short_del2 = 0
            for _o2 in _sel_short2:
                _removed_any = False
                for _ext2 in (".txt", ".md"):
                    _f2 = cfg.TXT_DIR / (_o2["stem"] + _ext2)
                    try:
                        if _f2.exists():
                            _f2.unlink()
                            _removed_any = True
                    except Exception:
                        pass
                queue_remove("tab2_ready", [_o2["stem"]])
                if _removed_any:
                    _short_del2 += 1
            st.success(tf("%d개 문서를 삭제했습니다.", _short_del2))
            st.rerun()

    # 장 구조 미감지 — 단일장 저장 선택지 (2026-07-03)
    _nosplit2 = st.session_state.get("split2_nosplit", [])
    if _nosplit2:
        st.divider()
        st.markdown(tf("#### 장 구조 미감지 (%d권)", len(_nosplit2)))
        st.caption(t("장 헤딩을 찾지 못해 분할에 실패한 문서입니다. 통째로 번역·요약하려면 단일장(단권요약)으로 저장하거나, 진행하지 않으려면 삭제하세요."))
        for _ns2 in list(_nosplit2):
            _nc1, _nc2, _nc3 = st.columns([4, 1.6, 0.7])
            _nc1.markdown(f"**{_ns2}**")
            if _nc2.button(t("단일장으로 저장"), icon=":material/article:", key=f"nosplit_save_{_ns2}", use_container_width=True):
                _sn2b, _smsg2b, _ = split_book_to_chapters(DEFAULT_WS, _ns2, allow_short=True)
                if _sn2b > 0:
                    queue_remove("tab2_ready", [_ns2])
                    _ch_dir2b = chapters_dir(DEFAULT_WS, _ns2)
                    _new_chs2b = [str(f.relative_to(cfg.BASE_DIR))
                                  for f in sorted(_ch_dir2b.glob("??_*.txt"))
                                  if not f.stem.endswith(_DERIVED)]
                    if _new_chs2b:
                        if _route_translate(_ns2):
                            queue_add("tab3_ready", _new_chs2b)
                        else:
                            queue_add("tab4_ready", _new_chs2b)
                        _archive_split_source(_ns2)
                    st.session_state["_review_books"] = sorted(
                        set(st.session_state.get("_review_books", [])) | {_nfc(_ns2)})

                    st.session_state["split2_nosplit"] = [x for x in _nosplit2 if x != _ns2]
                    st.rerun()
                else:
                    st.error(f"❌ {_ns2}: {_smsg2b}")
            if _nc3.button("", icon=":material/delete:", key=f"nosplit_del_{_ns2}", help="진행하지 않고 삭제"):
                for _ext2 in (".txt", ".md"):
                    try:
                        (cfg.TXT_DIR / (_ns2 + _ext2)).unlink(missing_ok=True)
                    except Exception:
                        pass
                queue_remove("tab2_ready", [_ns2])
                st.session_state["split2_nosplit"] = [x for x in _nosplit2 if x != _ns2]
                st.success(tf("%s 삭제 완료", _ns2))
                st.rerun()

    # ── 장 구분 확인 (2026-08-17) ────────────────────────────────
    # 분할이 조용히 틀린 채로 요약·번역·EPUB까지 진행되던 사고를 막는 자리다.
    _chapter_review_panel("rv2", full=True)



# ── 3: 번역 ─────────────────────────────────────────────
if _active_view == "3_translate":
    _tr_eng3 = _settings_engine_id()
    # 번역 출력 방식(독립 토글, 여러 개 가능) — 그냥 번역이 기본, 영한대역은 선택 (2026-08-11)
    _want_plain3 = bool(llm.get_pref("translate_want_plain", True))
    _want_bil3 = bool(llm.get_pref("translate_want_bilingual", False))

    def _proc_translate3(rel, progress_cb=None):
        _cf = cfg.BASE_DIR / rel
        if not _cf.exists():
            return False, f"{Path(rel).name}: 파일 없음"
        if not (_want_plain3 or _want_bil3):
            return False, f"{Path(rel).name}: {t('출력 방식을 하나 이상 선택하세요')}"
        _ok, _msg = translate_one_chapter(_cf, _tr_eng3, progress_cb=progress_cb,
                                           want_plain=_want_plain3, want_bilingual=_want_bil3)
        if _ok:
            queue_remove("tab3_ready", [rel])
            queue_add("tab4_ready", [rel])
            _track_flow_book(_nfc(_cf.parent.name))
        return _ok, f"{_cf.name}: {str(_msg)[:80]}"

    def _tr3_on_done():
        _items3 = st.session_state.pop("_flow_books", [])
        _log3 = st.session_state.get("tr3_log", [])
        _fails3 = [ln[2:].strip() for ln in _log3 if ln.startswith("❌")]
        _oks3 = [ln[2:].strip() for ln in _log3 if ln.startswith("✅")]
        if _fails3:
            _msg3 = (tf("%d개 번역 완료.", len(_oks3)) if _oks3 else t("번역된 챕터가 없습니다.")) + "\n\n" \
                    + tf("⚠️ %d개 번역 실패 — 대기 목록에 그대로 남아있습니다:", len(_fails3)) + "\n" \
                    + "\n".join(f"- {m}" for m in _fails3)
            _set_stage_completion(
                t("3-번역 결과") if _oks3 else t("3-번역 실패"),
                _msg3,
                next_stage="4_summary" if _oks3 else None,
                open_target=_stage_folder("3_translate"),
                kind="warning",
            )
            return
        _set_stage_completion(
            t("3-번역 완료"),
            t("번역을 마쳤습니다."),
            next_stage="4_summary",
            open_target=_stage_folder("3_translate"),
            question=t("다음은 **장별 요약**입니다."),
            next_items=_items3,
        )

    _src_n3f, _ko_n3f, _ = _chapter_counts()
    _ch_root3f = cfg.CHAPTERS_DIR
    if _run_active("tr3"):
        _run_panel(
            "tr3", "번역 처리 중", _proc_translate3, on_done=_tr3_on_done,
            item_progress_text=lambda done, total, translated, preserved, dropped, failed, resumed, api_calls: tf(
                "단락 %d/%d · 재사용 %d · API 호출 %d · 번역 %d · 보존 %d · 제외 %d · 실패 %d",
                done, total, resumed, api_calls, translated, preserved, dropped, failed,
            ),
        )
        st.stop()
    _stage_flow_panel(
        ":material/translate: 번역",
        tf("챕터 TXT를 %s로 번역해 같은 폴더에 저장합니다. "
            "원문 언어(영어·독일어·네덜란드어·프랑스어·라틴어·일본어·중국어 등)는 자동으로 감지하며, "
            "도착언어는 설정에서 바꿉니다.", target_language_name()),
        [
            ("① 처리전 · 원문 챕터", _ch_root3f, tf("%d개", _src_n3f)),
            ("② 처리후 · 번역본", _ch_root3f, tf("%d개 번역됨", _ko_n3f)),
        ],
        "flow3",
    )

    if not _tr_eng3:
        st.warning(t("사용 가능한 AI 없음 — :material/settings: 설정 탭에서 API 키를 입력하세요."),
                   icon=":material/warning:")
    else:

        # 번역 출력 방식 — 독립 토글(둘 다 켜도 됨), 최소 하나는 있어야 함 (2026-08-11)
        _wp_new3 = st.toggle(t("번역문만"), value=_want_plain3, key="tr3_want_plain",
                              help=t("원문 없이 번역문만 저장합니다."))
        _wb_new3 = st.toggle(t("원문·번역 나란히"), value=_want_bil3, key="tr3_want_bilingual",
                              help=t("원문과 번역을 문단별로 나란히 저장합니다."))
        if bool(_wp_new3) != _want_plain3 or bool(_wb_new3) != _want_bil3:
            llm.set_pref("translate_want_plain", bool(_wp_new3))
            llm.set_pref("translate_want_bilingual", bool(_wb_new3))
            st.rerun()
        if not (_wp_new3 or _wb_new3):
            st.warning(t("번역문만 · 원문·번역 나란히 중 하나 이상 선택하세요."))

        # TXT 직접 업로드 — 즉시 번역하지 않고 번역 대기 큐에 등록 (2026-07-09)
        _up3 = st.file_uploader(t("TXT 직접 업로드"),
                                  type=["txt"], accept_multiple_files=True, key="tr3_uploader")
        st.caption(t(_DND_HINT))
        st.caption(t("업로드한 TXT는 아래 '번역 대기'에 등록됩니다. [▶ 시작]을 눌러야 번역이 시작됩니다."))
        if not _up3:
            st.session_state.pop("_tr3_uploaded_tokens", None)
        if _up3:
            _seen3 = set(st.session_state.get("_tr3_uploaded_tokens", []))
            _staged3 = 0
            for _u3 in _up3:
                _u3_bytes = _u3.getvalue()
                _token3 = _upload_token(_u3.name, _u3_bytes)
                if _token3 in _seen3:
                    continue
                _seen3.add(_token3)
                _ok3p, _ch3_path, _book3u, _prep3_msg = _prepare_uploaded_single_chapter(
                    DEFAULT_WS, _u3.name, _u3_bytes, "translate"
                )
                if not _ok3p or _ch3_path is None:
                    st.error(f"❌ {_u3.name}: {_prep3_msg}")
                    continue
                queue_add("tab3_ready", [str(_ch3_path.relative_to(cfg.BASE_DIR))])
                _staged3 += 1
            st.session_state["_tr3_uploaded_tokens"] = sorted(_seen3)
            if _staged3:
                st.success(tf("번역 대기에 %d개 등록됨 — 아래에서 [▶ 시작]", _staged3))
            st.rerun()

        # ── 번역 대기 (큐 기반) ──────────────────────────────
        _q3_rels = queue_list("tab3_ready")
        _tr_pend3: list[dict] = []
        _tr_done3 = 0
        for _rel3 in _q3_rels:
            _cf3 = cfg.BASE_DIR / _rel3
            if not _cf3.exists():
                continue
            _ko3 = find_translation(_cf3) or _cf3.with_name(_cf3.stem + out_suffix() + ".txt")
            if _ko3.exists():
                _tr_done3 += 1
            else:
                _meta3 = f"{_cf3.stat().st_size//1024}KB"
                # 감지된 원문 언어를 항목마다 보여준다 — 영어만 다루던 때와 달리
                # 독일어·일본어 원서가 섞이면 무엇이 무슨 언어인지 눈으로 봐야 한다
                # (2026-08-15).
                _lang3, _ = source_language(_cf3)
                if _lang3:
                    _meta3 += f" · {language_name(_lang3)}"
                if _cf3.with_name(_cf3.stem + out_suffix() + ".progress.json").exists():
                    _meta3 += t(" · ♻️ 중단됨 — 이어하기 가능")
                _tr_pend3.append({
                    "key": _rel3,
                    "label": _cf3.name,
                    "meta": _meta3,
                    "obj": _rel3,
                    "group": _cf3.parent.name,
                })
        _tr_pend3.sort(key=lambda it: (it["group"], it["key"]))

        st.divider()
        st.markdown(tf("#### 번역 대기 (%d개) / 완료 %d개", len(_tr_pend3), _tr_done3))
        if _tr_pend3:
            _sel3 = _checklist(_tr_pend3, "tr3", height=280, viewable=True)
            _b3c1, _b3c2 = st.columns(2)
            _rs3 = _b3c1.button(tf("시작 (%d개)", len(_sel3)), icon=":material/play_arrow:", key="tr3_start",
                                  use_container_width=True, type="primary", disabled=len(_sel3)==0)
            _del3 = _b3c2.button(tf("삭제 (%d개)", len(_sel3)), icon=":material/delete:", key="tr3_del",
                                 use_container_width=True, disabled=len(_sel3)==0)
            if _del3 and _sel3:
                queue_remove("tab3_ready", _sel3)
                st.rerun()
            if _rs3 and _sel3:
                _run_start("tr3", _sel3)
        else:
            st.info(t("번역 대기 없음 — 📂 챕터 분할에서 챕터를 먼저 분리하세요"))



# ── 4: 요약생성 ─────────────────────────────────────────
def _wiki_len_cb(widget_key: str):
    """슬라이더 조작 즉시 pref에 커밋 (설정·문서요약 두 슬라이더 동기화의 핵심)."""
    try:
        llm.set_pref("wiki_length_pct", int(st.session_state[widget_key]))
    except Exception:
        pass


def _render_wiki_length_slider(widget_key: str):
    """요약 분량 % 슬라이더 — 설정 탭·문서요약 탭 공용. pref_wiki_length_pct 공유.
    on_change가 먼저 커밋되므로 매 렌더에서 pref로 재동기화해도 사용자 조작을 되돌리지 않는다."""
    import chapter_wiki as _cw
    st.session_state[widget_key] = _cw.wiki_pct()
    st.slider(
        t("요약 분량 (원문 대비 %)"),
        min_value=_cw.WIKI_PCT_MIN, max_value=_cw.WIKI_PCT_MAX,
        step=1, format="%d%%", key=widget_key,
        on_change=_wiki_len_cb, args=(widget_key,),
        # ★설명은 캡션 두 줄로 늘어놓지 않고 ? 도움말로 접는다 (2026-08-26).
        # 늘 보일 필요 없는 글이 바보다 길면 정작 바를 못 본다.
        help=t("장별 요약 본문을 원문 글자수 대비 몇 %로 만들지 정합니다 (권장 15%). "
               "짧은 장은 최소 분량을 보장합니다. 다음 요약부터 적용됩니다. "
               "분량이 커질수록 요약이 길어져 출력 토큰 소비·API 비용이 늘어납니다 "
               "(원문을 보내는 입력 토큰은 분량과 무관하게 동일합니다). "
               "설정 탭과 문서요약 탭이 같은 값을 공유합니다."))


if _active_view == "4_summary":
    def _proc_summary4(rel):
        _cf = cfg.BASE_DIR / rel
        if not _cf.exists():
            return False, f"{Path(rel).name}: 파일 없음"
        _book = _nfc(_cf.parent.name)
        _ok, _msg = summarize_one_chapter(_cf, _book)
        if _ok:
            queue_remove("tab4_ready", [rel])
            queue_remove("tab4_failed", [rel])
            _touched = set(st.session_state.get("summ4_touched", []))
            _touched.add(_book)
            st.session_state["summ4_touched"] = sorted(_touched)
            queue_add("tab5_ready", [_book])
            _track_flow_book(_book)
        else:
            queue_remove("tab4_ready", [rel])
            queue_add("tab4_failed", [rel])
        return _ok, f"{_cf.name}: {str(_msg)[:70]}"

    def _summ4_on_done():
        _touched4 = list(st.session_state.get("summ4_touched", []))
        for _stem in _touched4:
            try:
                summarize_book_overview(DEFAULT_WS, _stem)
            except Exception:
                pass
        st.session_state.pop("summ4_touched", None)
        st.session_state.pop("_flow_books", None)
        _log4 = st.session_state.get("summ4_log", [])
        _fails4 = [ln[2:].strip() for ln in _log4 if ln.startswith("❌")]
        _oks4 = [ln[2:].strip() for ln in _log4 if ln.startswith("✅")]
        if _fails4:
            _msg4 = (tf("%d개 요약 완료.", len(_oks4)) if _oks4 else t("요약된 챕터가 없습니다.")) + "\n\n" \
                    + tf("⚠️ %d개 요약 실패 — 아래 '요약 실패' 목록에서 재시도하세요:", len(_fails4)) + "\n" \
                    + "\n".join(f"- {m}" for m in _fails4)
            _set_stage_completion(
                t("4-문서요약 결과") if _oks4 else t("4-문서요약 실패"),
                _msg4,
                next_stage="5_wiki" if _oks4 else None,
                open_target=_stage_folder("4_summary"),
                kind="warning",
            )
            return
        # 위키 반영 질문 — C: 옵시디언 미사용(DOC) / A: 이미 반영됨(교체) / B: 미반영(반영)
        _out_name4 = _out_flow()   # "Obsidian Wiki" / "Word(.docx)" / 둘 다
        _vault4 = _current_wiki_dir()
        _vstems4 = {_nfc(p.stem) for p in _vault4.rglob("*.md")} if _vault4.exists() else set()
        _already4 = [s for s in _touched4 if _nfc(s) in _vstems4]
        if _use_ob and _already4 and _touched4:
            _q4 = (tf("「%s」은(는) 이미 위키에 있습니다 — 다음 화면에서 방금 요약으로 갱신해 %s(으)로 저장합니다.", _touched4[0], _out_name4)
                   if len(_touched4) == 1 else
                   tf("다음 화면에서 요약한 %d권을 %s(으)로 저장합니다 (일부는 기존 위키 갱신).", len(_touched4), _out_name4))
        elif _touched4:
            _q4 = (tf("다음 화면에서 「%s」을(를) %s(으)로 저장합니다.", _touched4[0], _out_name4)
                   if len(_touched4) == 1 else
                   tf("다음 화면에서 요약된 %d권을 %s(으)로 저장합니다.", len(_touched4), _out_name4))
        else:
            _q4 = tf("다음 화면에서 요약된 문서를 %s(으)로 저장합니다.", _out_name4)
        _set_stage_completion(
            t("4-문서요약 완료"),
            t("요약을 마쳤습니다."),
            next_stage="5_wiki",
            open_target=_stage_folder("4_summary"),
            question=_q4,
            next_items=_touched4,
        )

    _src_n4f, _ko_n4f, _json_n4f = _chapter_counts()
    _ch_root4f = cfg.CHAPTERS_DIR
    if _run_active("summ4"):
        _run_panel("summ4", "문서요약 처리 중", _proc_summary4, on_done=_summ4_on_done)
        st.stop()
    _stage_flow_panel(
        ":material/summarize: 문서요약",
        "챕터 TXT(번역본 우선)로 요약을 생성해 같은 폴더에 `_wiki.md`로 저장합니다.",
        [
            ("① 처리전 · 챕터 (번역본 우선)", _ch_root4f,
             tf("원문 %d · 번역 %d", _src_n4f, _ko_n4f)),
            ("② 처리후 · 요약 (_wiki.md)", _ch_root4f, tf("%d개 요약됨", _json_n4f)),
        ],
        "flow4",
    )

    # 요약 분량 조절 — 여기서도 바로 조절(설정 탭의 기본값과 동기화, 2026-07-23)
    # 펼쳐 둔다 — 접어 두면 있는 줄도 모른다 (2026-08-26)
    _render_wiki_length_slider("wiki_length_pct_sl4")

    _prov_ok4 = any(llm.has_key(p) for p in llm.PROVIDERS)
    if not _prov_ok4:
        st.warning(t("요약 API 없음 — :material/settings: 설정 탭에서 키를 입력하세요."),
                   icon=":material/warning:")
    else:

        # TXT 직접 업로드 — 즉시 요약하지 않고 요약 대기 큐에 등록 (2026-07-09)
        _up4 = st.file_uploader(t("TXT 직접 업로드"),
                                  type=["txt"], accept_multiple_files=True, key="summ4_uploader")
        st.caption(t(_DND_HINT))
        st.caption(t("업로드한 TXT는 아래 '요약 대기'에 등록됩니다. [▶ 시작]을 눌러야 요약이 시작됩니다."))
        if not _up4:
            st.session_state.pop("_summ4_uploaded_tokens", None)
        if _up4:
            _seen4 = set(st.session_state.get("_summ4_uploaded_tokens", []))
            _staged4n = 0
            for _u4 in _up4:
                _u4_bytes = _u4.getvalue()
                _token4 = _upload_token(_u4.name, _u4_bytes)
                if _token4 in _seen4:
                    continue
                _seen4.add(_token4)
                _ok4p, _ch4_path, _book4u, _prep4_msg = _prepare_uploaded_single_chapter(
                    DEFAULT_WS, _u4.name, _u4_bytes, "summary"
                )
                if not _ok4p or _ch4_path is None:
                    st.error(f"❌ {_u4.name}: {_prep4_msg}")
                    continue
                queue_add("tab4_ready", [str(_ch4_path.relative_to(cfg.BASE_DIR))])
                queue_remove("tab4_failed", [str(_ch4_path.relative_to(cfg.BASE_DIR))])
                _staged4n += 1
            st.session_state["_summ4_uploaded_tokens"] = sorted(_seen4)
            if _staged4n:
                st.success(tf("요약 대기에 %d개 등록됨 — 아래에서 [▶ 시작]", _staged4n))
            st.rerun()

        # ── 요약 대기 (큐 기반) ──────────────────────────────
        _q4_rels = queue_list("tab4_ready")
        _q4_failed_rels = queue_list("tab4_failed")
        _sum_pend4: list[dict] = []
        _sum_failed4: list[dict] = []
        _sum_done4 = 0
        _q4_remove_missing: list[str] = []
        _q4_remove_done: list[str] = []
        for _rel4 in _q4_rels:
            _cf4 = cfg.BASE_DIR / _rel4
            if not _cf4.exists():
                _q4_remove_missing.append(_rel4)
                continue
            _bstem4 = _nfc(_cf4.parent.name)
            if summary_file_for(_cf4) is not None:
                _sum_done4 += 1
                _q4_remove_done.append(_rel4)
            else:
                _ko4 = find_translation(_cf4) or _cf4.with_name(_cf4.stem + out_suffix() + ".txt")
                _tag4 = "🌐ko" if _ko4.exists() else "📄원문"
                # 목록 안에서 바로 제목을 고칠 수 있게 (책, 그 책에서 몇 번째 장) 을 얹는다
                _bfiles4 = cmap.chapter_files(DEFAULT_WS, _bstem4)
                _bidx4 = next((i for i, f in enumerate(_bfiles4) if f == _cf4), None)
                _sum_pend4.append({
                    "key": _rel4,
                    "label": _cf4.name,
                    "title": cmap.chapter_title(_cf4),
                    "meta": f"{_tag4} · {_cf4.stat().st_size//1024}KB",
                    "obj": (_cf4, _bstem4),
                    "group": _bstem4,
                    "rename": (_bstem4, _bidx4) if _bidx4 is not None else None,
                })
        for _rel4f in _q4_failed_rels:
            _cf4f = cfg.BASE_DIR / _rel4f
            if not _cf4f.exists():
                _q4_remove_missing.append(_rel4f)
                continue
            if summary_file_for(_cf4f) is not None:
                _sum_done4 += 1
                _q4_remove_done.append(_rel4f)
                continue
            _sum_failed4.append({
                "key": _rel4f,
                "label": _cf4f.name,
                "meta": f"{_cf4f.stat().st_size//1024}KB · 실패",
                "obj": _rel4f,
                "group": _nfc(_cf4f.parent.name),
            })
        _sum_pend4.sort(key=lambda it: (it["group"], it["key"]))
        _sum_failed4.sort(key=lambda it: (it["group"], it["key"]))
        if _q4_remove_missing:
            queue_remove("tab4_ready", _q4_remove_missing)
            queue_remove("tab4_failed", _q4_remove_missing)
        if _q4_remove_done:
            queue_remove("tab4_ready", _q4_remove_done)
            queue_remove("tab4_failed", _q4_remove_done)

        st.divider()
        st.markdown(tf("#### 요약 대기 (%d개) / 완료 %d개", len(_sum_pend4), _sum_done4))
        if _sum_pend4:
            _sel4 = _checklist(_sum_pend4, "summ4", height=280, viewable=True, renamable=True)
            _b4c1, _b4c2 = st.columns(2)
            _rs4 = _b4c1.button(tf("시작 (%d개)", len(_sel4)), icon=":material/play_arrow:", key="summ4_start",
                                  use_container_width=True, type="primary", disabled=len(_sel4)==0)
            _del4 = _b4c2.button(tf("삭제 (%d개)", len(_sel4)), icon=":material/delete:", key="summ4_del",
                                 use_container_width=True, disabled=len(_sel4)==0)
            _sel4_rels = [str(_cfx.relative_to(cfg.BASE_DIR)) for _cfx, _bx in _sel4]
            if _del4 and _sel4:
                queue_remove("tab4_ready", _sel4_rels)
                queue_remove("tab4_failed", _sel4_rels)
                st.rerun()
            if _rs4 and _sel4_rels:
                _run_start("summ4", _sel4_rels)
        else:
            st.info(t("요약 대기 없음 — 🌐 번역 처리 후 자동 등록되거나 위에서 TXT를 직접 업로드하세요"))

        if _sum_failed4:
            st.markdown(tf("#### 요약 실패 (%d개)", len(_sum_failed4)))
            _fail_sel4 = _checklist(_sum_failed4, "summ4_failed", height=180)
            _f4c1, _f4c2 = st.columns([2, 1])
            if _f4c1.button(tf("선택 재시도 대기 (%d개)", len(_fail_sel4)), icon=":material/refresh:", key="summ4_retry_failed",
                              use_container_width=True, disabled=len(_fail_sel4)==0):
                queue_remove("tab4_failed", _fail_sel4)
                queue_add("tab4_ready", _fail_sel4)
                st.rerun()
            if _f4c2.button(t("실패 목록 비우기"), icon=":material/delete_sweep:", key="summ4_clear_failed", use_container_width=True):
                queue_clear("tab4_failed")
                st.rerun()



# ── 5: Wiki반영 ─────────────────────────────────────────
if _active_view == "5_wiki":
    _cur_wiki5_path = _current_wiki_dir()
    _docx_dir5 = _current_docx_dir()
    _hwpx_dir5 = _current_hwpx_dir()
    _epub_dir5 = _current_epub_dir()
    _epub_engine5 = _settings_engine_id()

    def _proc_wiki5(stem, progress_cb=None):
        # 옵시디언·DOCX·HWPX·EPUB 토글 조합대로 출력을 생성한다 (여러 개 켜면 전부).
        _res = []
        _produced = {"wiki": None, "docx": None, "hwpx": None, "epub": None}
        if _use_ob:
            if progress_cb:
                progress_cb(tf("%s — Wiki 노트 생성 중", stem))
            _cdir = chapters_dir(DEFAULT_WS, stem)
            for _cjf in list_summary_files(_cdir):
                build_single_chapter_wiki(DEFAULT_WS, stem, _cjf, wiki_dir=_cur_wiki5_path)
            _wok, _wmsg = build_wiki_from_chapter_summaries(DEFAULT_WS, stem, wiki_dir=_cur_wiki5_path)
            _res.append(("Wiki", _wok, Path(_wmsg).name if _wok else str(_wmsg)[:45]))
            if _wok:
                _produced["wiki"] = Path(_wmsg)
        if _use_dx:
            if progress_cb:
                progress_cb(tf("%s — DOCX 문서 생성 중", stem))
            _dok, _dmsg = build_docx_from_chapter_summaries(DEFAULT_WS, stem, _docx_dir5)
            _res.append(("DOCX", _dok, Path(_dmsg).name if _dok else str(_dmsg)[:45]))
            if _dok:
                _produced["docx"] = Path(_dmsg)
        if _use_hx:
            if progress_cb:
                progress_cb(tf("%s — HWPX 문서 생성 중", stem))
            _hok, _hmsg = build_hwpx_from_chapter_summaries(DEFAULT_WS, stem, _hwpx_dir5)
            _res.append(("HWPX", _hok, Path(_hmsg).name if _hok else str(_hmsg)[:45]))
            if _hok:
                _produced["hwpx"] = Path(_hmsg)
        if _use_ep:
            # clean=False — 자간정리는 아래 '자간정리 먼저 실행' 버튼이 맡는 별도
            # 단계다. 그래야 EPUB 생성이 한글책이든 영어책이든 즉시 끝난다(2026-08-14).
            _eok, _emsg = build_epub_from_chapters(DEFAULT_WS, stem, _epub_dir5,
                                                    engine=_epub_engine5, clean=False,
                                                    progress_cb=progress_cb)
            _res.append(("EPUB", _eok, Path(_emsg).name if _eok else str(_emsg)[:45]))
            if _eok:
                _produced["epub"] = Path(_emsg)
        if not _res:
            return False, f"{stem}: {t('출력 방식(위키/DOCX/HWPX/EPUB)을 하나 이상 선택하세요')}"
        _allok = all(r[1] for r in _res)
        if _allok:
            queue_remove("tab5_ready", [stem])
            _touched5 = dict(st.session_state.get("wiki5_touched", {}))
            _touched5[stem] = _produced
            st.session_state["wiki5_touched"] = _touched5
        return _allok, f"{stem}: " + " · ".join(f"{nm} {'✓' if ok else '✗ ' + m}" for nm, ok, m in _res)

    def _proc_clean5(stem, progress_cb=None):
        """자간정리 전용 처리기 — 한 권의 한글 원문 챕터를 _clean.txt로 만들어 둔다.
        EPUB 큐(tab5_ready)는 건드리지 않는다: 정리는 EPUB의 준비 작업일 뿐이라
        끝난 뒤에도 그 책은 EPUB 대기 목록에 그대로 남아야 한다."""
        _cok, _cmsg = clean_book_chapters(DEFAULT_WS, stem, _epub_engine5,
                                           progress_cb=progress_cb)
        return _cok, f"{stem}: {str(_cmsg)[:90]}"

    def _clean5_on_done():
        _log5c = st.session_state.get("clean5_log", [])
        _fails5c = [ln[2:].strip() for ln in _log5c if ln.startswith("❌")]
        _oks5c = [ln[2:].strip() for ln in _log5c if ln.startswith("✅")]
        _set_stage_completion(
            t("자간정리 완료") if not _fails5c else t("자간정리 결과"),
            (tf("%d권 자간정리 완료 — 이제 EPUB 생성은 바로 끝납니다.", len(_oks5c))
             if _oks5c else t("자간정리된 책이 없습니다."))
            + ("" if not _fails5c else "\n\n" + tf("⚠️ %d권 실패:", len(_fails5c)) + "\n"
               + "\n".join(f"- {m}" for m in _fails5c)),
            next_stage=None,
            open_target=None,
            kind="warning" if _fails5c else "success",
        )

    def _wiki5_on_done():
        # 방금 처리에서 책이 정확히 한 권이면, 폴더 대신 그 결과물을 바로 연다
        # (DOCX·HWPX만 켠 단독 출력 → 파일 바로 열기, 위키 켜짐 → Obsidian에서 그 노트 바로 열기).
        _touched5 = dict(st.session_state.pop("wiki5_touched", {}))
        _open_label5, _open_action5 = None, None
        if len(_touched5) == 1:
            _produced5 = next(iter(_touched5.values()))
            if _use_ob and _produced5.get("wiki"):
                _note_path5 = _produced5["wiki"]
                _open_label5 = t("Obsidian에서 열기")
                _open_action5 = lambda p=_note_path5: open_in_obsidian(p)
            elif _use_dx and not _use_hx and not _use_ep and _produced5.get("docx"):
                _docx_path5 = _produced5["docx"]
                _open_label5 = t("DOCX 파일 열기")
                _open_action5 = lambda p=_docx_path5: open_path(p)
            elif _use_hx and not _use_dx and not _use_ep and _produced5.get("hwpx"):
                _hwpx_path5 = _produced5["hwpx"]
                _open_label5 = t("HWPX 파일 열기")
                _open_action5 = lambda p=_hwpx_path5: open_path(p)
            elif _use_ep and not _use_dx and not _use_hx and _produced5.get("epub"):
                _epub_path5 = _produced5["epub"]
                _open_label5 = t("EPUB 파일 열기")
                _open_action5 = lambda p=_epub_path5: open_path(p)
        _log5 = st.session_state.get("wiki5_log", [])
        _fails5 = [ln[2:].strip() for ln in _log5 if ln.startswith("❌")]
        _oks5 = [ln[2:].strip() for ln in _log5 if ln.startswith("✅")]
        if _fails5:
            _msg5 = (tf("%d권 Wiki 반영 완료.", len(_oks5)) if _oks5 else t("Wiki 반영된 책이 없습니다.")) + "\n\n" \
                    + tf("⚠️ %d권 Wiki 반영 실패 — 대기 목록에 그대로 남아있습니다:", len(_fails5)) + "\n" \
                    + "\n".join(f"- {m}" for m in _fails5)
            _set_stage_completion(
                t("5-Wiki 반영 결과") if _oks5 else t("5-Wiki 반영 실패"),
                _msg5,
                next_stage=None,
                open_target=_stage_folder("5_wiki"),
                kind="warning",
            )
            return
        _set_stage_completion(
            t("5-출력 완료"),
            tf("완료: %s", _out_flow()),
            next_stage=None,
            open_target=(_stage_folder("5_wiki") if _use_ob
                         else (_docx_dir5 if _use_dx else (_hwpx_dir5 if _use_hx else _epub_dir5))),
            open_label=_open_label5,
            open_action=_open_action5,
        )

    _, _, _json_n5f = _chapter_counts()
    _ch_root5f = cfg.CHAPTERS_DIR
    _vault5f = _current_wiki_dir()
    _n_notes5f = sum(1 for _ in _vault5f.rglob("*.md")) if _vault5f.exists() else 0
    _n_docx5 = len(list(_docx_dir5.glob("*.docx"))) if _docx_dir5.exists() else 0
    _n_hwpx5 = len(list(_hwpx_dir5.glob("*.hwpx"))) if _hwpx_dir5.exists() else 0
    _n_epub5 = len(list(_epub_dir5.glob("*.epub"))) if _epub_dir5.exists() else 0
    if _run_active("clean5"):
        _run_panel("clean5", "자간정리 처리 중", _proc_clean5, on_done=_clean5_on_done,
                   detail_progress=True)
        st.stop()
    if _run_active("wiki5"):
        _run_panel("wiki5", "출력 생성 중", _proc_wiki5, on_done=_wiki5_on_done, detail_progress=True)
        st.stop()
    # 켠 출력만 카드로 — 여러 개 켜면 폴더가 서로 달라 카드도 그만큼 늘어난다
    # (2026-07-25, HWPX 2026-08-09, EPUB 2026-08-11)
    _out_cards5 = []
    if _use_dx:
        _out_cards5.append(("Word 문서(DOCX)", _docx_dir5, tf("%d개", _n_docx5)))
    if _use_hx:
        _out_cards5.append(("한글 문서(HWPX)", _hwpx_dir5, tf("%d개", _n_hwpx5)))
    if _use_ep:
        _out_cards5.append(("전자책(EPUB)", _epub_dir5, tf("%d개", _n_epub5)))
    if _use_ob:
        _out_cards5.append(("Obsidian 보관함", _vault5f, tf("%d노트", _n_notes5f)))
    _circled5 = ["②", "③", "④", "⑤"]
    _after_cards5 = [(f"{_circled5[_i5]} 처리후 · {_nm5}", _p5, _c5) for _i5, (_nm5, _p5, _c5) in enumerate(_out_cards5)]
    _stage_flow_panel(
        f":material/{_stage_icon('5_wiki')}: {_out_short()}",
        _stage_desc("5_wiki", ""),
        [
            ("① 처리전 · 요약 (_wiki.md)", _ch_root5f, tf("%d개", _json_n5f)),
            *_after_cards5,
        ],
        "flow5",
    )

    # ── 출력 방식 선택 — 전문 그대로(EPUB)를 요약 기반(DOCX·HWPX·옵시디언) 위에
    #    구분해서 보여준다. 옵시디언은 맨 아래에 두어 그 토글 바로 밑에 보관함
    #    설정이 이어지도록 한다 (2026-07-25, HWPX 2026-08-09, EPUB 2026-08-11,
    #    EPUB을 요약 그룹 위로·상시 자간정리 2026-08-11).
    _ep_new5 = st.toggle(
        t("EPUB 전자책 생성"), value=_use_ep, key="wiki5_use_epub",
        help=t(
            "챕터 원문·번역본 전체를 전자책(.epub) 한 권으로 묶어 저장합니다(요약이 아닌 본문 그대로). "
            "번역본이나 자간정리본이 있으면 그걸 쓰고, 없으면 원문 그대로 담습니다 — "
            "AI를 부르지 않으므로 항상 즉시 끝납니다. 한글 원문 책의 OCR 줄바꿈을 다듬으려면 "
            "아래 «자간정리»를 한 번 돌려두세요. "
            "⚠️ 저작권이 있는 책 전체가 그대로 담기므로 개인적인 사용 목적으로만 쓰세요 — 배포·공유는 저작권법 위반이 될 수 있습니다."
        ),
    )
    if _use_ep:
        # 저장 위치와 저작권 주의는 위 토글 «?» 도움말에 그대로 있다 — 화면에는
        # 만들어진 것을 바로 열어 볼 길만 둔다 (2026-08-26).
        if st.button(t("전자책 폴더 열어보기"), icon=":material/folder_open:",
                     key="epub5_open_dir", help=str(_epub_dir5)):
            open_path(_epub_dir5)

        # ── 자간정리(선택) — EPUB 생성에서 떼어낸 별도 단계 (2026-08-14) ──────
        # 스캔 PDF에서 뽑은 한글 본문은 인쇄된 줄마다 어절이 쪼개져 있다. 그 자리를
        # 붙일지 띄울지는 AI만 가릴 수 있어 시간이 걸리는데, 예전에는 그 작업이 EPUB
        # 버튼 안에 숨어 있어서 "한글책은 EPUB이 몇십 분씩 걸린다"로 보였다. 이제
        # 여기서 미리 끝내두면 EPUB은 항상 즉시 끝난다.
        _clean_targets5 = {}
        for _cs5 in queue_list("tab5_ready"):
            _need5 = chapters_needing_clean(DEFAULT_WS, _cs5)
            if _need5:
                _clean_targets5[_cs5] = len(_need5)
        # ★설명 캡션과 "대상 N권 · M챕터" 요약은 뺐다 (2026-08-26 연구자 요청).
        # 대신 **어떤 책을 돌리려는지 이름을 보여 준다** — 권수만 적어 두면 무엇에
        # AI를 부르는지 모른 채 누르게 된다.
        # 동시 실행 칸도 뺐다. 저장해 둔 값(clean_workers)을 그대로 쓴다.
        if _clean_targets5:
            # ★버튼 하나만 두고, 설명과 **대상 책 목록**을 «?» 도움말에 함께 넣는다
            # (2026-08-26). 무엇에 AI를 부르는지는 알아야 하지만, 화면에 늘 펼쳐
            # 둘 만큼 자주 쓰는 것은 아니다.
            _tgt_lines5 = "\n".join(f"· {_b5} ({_n5}" + t("챕터") + ")"
                                    for _b5, _n5 in _clean_targets5.items())
            if st.button(tf("자간정리 (%d권)", len(_clean_targets5)),
                         icon=":material/format_align_left:", key="clean5_start",
                         disabled=not _epub_engine5,
                         help=t("스캔 PDF에서 뽑은 한글 원문은 인쇄된 줄마다 어절이 쪼개져 있습니다. "
                                "AI에 줄바꿈마다 '붙임/공백'만 물어 이어 붙입니다. 한 번 해두면 결과가 "
                                "남아 다시 걸리지 않습니다. 선택 사항입니다 — 하지 않아도 EPUB은 "
                                "만들어지며, 원문이 쪼개진 그대로 담깁니다.")
                              + "\n\n" + t("대상") + "\n" + _tgt_lines5):
                _run_start("clean5", list(_clean_targets5))
            if not _epub_engine5:
                st.caption(t("사용 가능한 AI가 없어 자간정리를 실행할 수 없습니다 — 설정 탭을 확인하세요."))
        # EPUB 전용 수동 추가 — 요약(_wiki.md) 없이 챕터만 있어도 대상이 된다.
        # 아래 '요약 완료된 책' 추가와 달리, 요약·번역을 안 거친 책도 여기서 바로
        # 큐(tab5_ready)에 넣을 수 있다 (2026-08-11).
        with st.expander(t("➕ EPUB 대상 수동으로 추가 (챕터가 있는 책 — 번역·요약 여부 무관)")):
            # TXT·PDF 직접 업로드(드래그앤드롭) — 챕터 분할 없이 단일장으로 즉시 등록.
            # PDF는 텍스트 레이어를 바로 추출해 TXT와 동일하게 처리한다(스캔 이미지
            # PDF처럼 텍스트 레이어가 없으면 별도 OCR이 필요해 안내만 하고 건너뛴다,
            # 2026-08-11).
            _epup5 = st.file_uploader(t("TXT 또는 PDF 직접 업로드"), type=["txt", "pdf"],
                                       accept_multiple_files=True, key="epub5_uploader")
            st.caption(t(_DND_HINT))
            st.caption(t("업로드한 파일은 챕터 분할 없이 단일장으로 등록되어 바로 EPUB 대상이 됩니다. "
                          "PDF는 텍스트를 자동 추출합니다(스캔 이미지 PDF는 1-업로드 탭에서 OCR을 먼저 거쳐야 합니다)."))
            if not _epup5:
                st.session_state.pop("_epub5_uploaded_tokens", None)
            if _epup5:
                _epseen5 = set(st.session_state.get("_epub5_uploaded_tokens", []))
                _epstaged5 = 0
                for _epu5 in _epup5:
                    _epu5_bytes = _epu5.getvalue()
                    _eptoken5 = _upload_token(_epu5.name, _epu5_bytes)
                    if _eptoken5 in _epseen5:
                        continue
                    _epseen5.add(_eptoken5)
                    _epu5_name = _epu5.name
                    if _epu5_name.lower().endswith(".pdf"):
                        UPLOAD_TMP.mkdir(parents=True, exist_ok=True)
                        _eppdf_tmp5 = UPLOAD_TMP / _epu5_name
                        _eppdf_tmp5.write_bytes(_epu5_bytes)
                        _eptxt_path5, _, _eperr5, _epnote5 = pdf_to_txt(_eppdf_tmp5)
                        if not _eptxt_path5:
                            _eppdf_tmp5.unlink(missing_ok=True)
                            st.error(f"❌ {_epu5_name}: "
                                     + (t("스캔 이미지 PDF로 보입니다 — 1-업로드 탭에서 OCR 처리 후 다시 시도하세요.")
                                        if _eperr5 == OCR_REQUIRED_MSG else (_eperr5 or t("PDF에서 텍스트를 추출하지 못했습니다."))))
                            continue
                        _epu5_bytes = _eptxt_path5.read_text(encoding="utf-8", errors="ignore").encode("utf-8")
                        _eptxt_path5.unlink(missing_ok=True)
                        cfg.PDF_DIR.mkdir(parents=True, exist_ok=True)
                        _eppdf_tmp5.replace(cfg.PDF_DIR / _epu5_name)  # 원본 PDF 보관(다른 업로드 경로와 동일한 위치)
                        _epu5_name = Path(_epu5_name).stem + ".txt"
                        if _epnote5:
                            st.caption(f"ℹ️ {_epu5.name}: {_epnote5}")
                    _epok5, _epch5_path, _epbook5, _epmsg5 = _prepare_uploaded_single_chapter(
                        DEFAULT_WS, _epu5_name, _epu5_bytes, "epub"
                    )
                    if not _epok5 or _epch5_path is None:
                        st.error(f"❌ {_epu5.name}: {_epmsg5}")
                        continue
                    queue_add("tab5_ready", [_epbook5])
                    _epstaged5 += 1
                st.session_state["_epub5_uploaded_tokens"] = sorted(_epseen5)
                if _epstaged5:
                    st.success(tf("EPUB 대기에 %d개 등록됨", _epstaged5)); st.rerun()
            st.divider()

            _epch_root5 = cfg.CHAPTERS_DIR
            _epall5 = list(_epch_root5.iterdir()) if _epch_root5.exists() else []
            _epsearch5 = st.text_input(t("책 이름 검색"), key="epub5_search", placeholder=t("검색어 입력…"))
            _epbooks5 = []
            for _epd in _epall5:
                if not _epd.is_dir():
                    continue
                _epchs5 = [f for f in _epd.glob("??_*.txt")
                           if not f.stem.endswith(_DERIVED)]
                if not _epchs5:
                    continue
                _epbooks5.append((_epd, len(_epchs5)))
            _epbooks5.sort(key=lambda b: b[0].stat().st_mtime, reverse=True)
            _epfilt5 = ([b for b in _epbooks5 if _epsearch5.lower() in b[0].name.lower()]
                        if _epsearch5 else _epbooks5)
            # 요약 개수는 EPUB과 무관해 오해를 살 수 있어 표시하지 않는다(2026-08-11) —
            # EPUB은 항상 챕터 원문·번역본만 쓰고 _wiki.md는 절대 읽지 않는다.
            _epitems5 = [
                {"key": d.name, "label": d.name, "meta": tf("%d챕터", n), "obj": d.name}
                for d, n in _epfilt5
            ]
            _epsel5 = _checklist(_epitems5, "epub5m", height=200)
            _epc5a, _epc5b = st.columns(2)
            if _epc5a.button(tf("선택 항목 큐에 추가 (%d권)", len(_epsel5)), icon=":material/add:", key="epub5m_add",
                             use_container_width=True, disabled=len(_epsel5) == 0):
                queue_add("tab5_ready", _epsel5); st.rerun()
            if _epc5b.button(tf("삭제 (%d권)", len(_epsel5)), icon=":material/delete:", key="epub5m_del",
                             use_container_width=True, disabled=len(_epsel5) == 0):
                queue_remove("tab5_ready", _epsel5); st.rerun()
    st.divider()

    st.caption(t("요약 문서 포맷"))
    _dx_new5 = st.toggle(t("DOCX 문서 생성"), value=_use_dx, key="wiki5_use_docx",
                          help=t("편집 가능한 Word(.docx) 문서로 저장합니다."))
    if _use_dx:
        st.caption(tf("Word 문서는 여기에 저장됩니다: `%s`", str(_docx_dir5)))
    _hx_new5 = st.toggle(t("HWPX 문서 생성"), value=_use_hx, key="wiki5_use_hwpx",
                          help=t("편집 가능한 한글(.hwpx) 문서로 저장합니다."))
    if _use_hx:
        st.caption(tf("한글 문서는 여기에 저장됩니다: `%s`", str(_hwpx_dir5)))
    _ob_new5 = st.toggle(t("옵시디언 위키 사용"), value=_use_ob, key="wiki5_use_obsidian",
                          help=t("Obsidian 보관함에 위키 노트로 저장합니다."))
    if (bool(_ob_new5) != _use_ob or bool(_dx_new5) != _use_dx
            or bool(_hx_new5) != _use_hx or bool(_ep_new5) != _use_ep):
        llm.set_pref("use_obsidian", bool(_ob_new5))
        llm.set_pref("use_docx", bool(_dx_new5))
        llm.set_pref("use_hwpx", bool(_hx_new5))
        llm.set_pref("use_epub", bool(_ep_new5))
        st.rerun()
    if not (_use_ob or _use_dx or _use_hx or _use_ep):
        st.warning(t("출력 방식을 하나 이상 선택하세요 (위키·DOCX·HWPX·EPUB 중)."))

    # ── 위키 저장 보관함(Vault) 선택 (옵시디언 사용 시 의미) ──────────────
    _vaults5 = list_obsidian_vaults()
    # 세션에 저장된 보관함(Vault) 경로가 있으면 우선 사용, 없으면 기본값
    _cur_wiki5_path = _current_wiki_dir()
    _cur_wiki5 = str(_cur_wiki5_path)
    with st.expander(tf("📁 위키 저장 보관함(Vault): `%s`  (`%s`)", _cur_wiki5_path.name, _cur_wiki5), expanded=False):
        if _vaults5:
            _vault_opts5 = _vaults5 + ([] if _cur_wiki5 in _vaults5 else [_cur_wiki5])
            _vault_idx5 = _vault_opts5.index(_cur_wiki5) if _cur_wiki5 in _vault_opts5 else 0
            _vault_sel5 = st.selectbox(t("Obsidian 보관함(Vault) 선택"), _vault_opts5, index=_vault_idx5,
                                       key="wiki5_vault_sel",
                                       format_func=lambda p: f"{Path(p).name}  ({p})")
            if _vault_sel5 != _cur_wiki5:
                if st.button(t("이 보관함(Vault)로 변경 (즉시 적용)"), icon=":material/check:", key="wiki5_vault_save"):
                    set_wiki_dir(_vault_sel5)
                    st.session_state["wiki5_active_dir"] = _vault_sel5
                    st.success(f"✅ 보관함(Vault) 변경됨: {_vault_sel5}")
                    st.rerun()
        else:
            st.info(t("Obsidian 보관함(Vault) 목록을 가져올 수 없습니다. Obsidian이 설치·실행됐는지 확인하세요."))
        _custom5 = st.text_input(t("또는 직접 경로 입력"), key="wiki5_vault_custom", placeholder="/path/to/vault")
        if _custom5 and st.button(t("직접 입력 경로로 변경 (즉시 적용)"), icon=":material/check:", key="wiki5_vault_custom_save"):
            set_wiki_dir(_custom5)
            st.session_state["wiki5_active_dir"] = _custom5
            st.success(f"✅ 보관함(Vault) 변경됨: {_custom5}")
            st.rerun()

    _wiki_prov_ok5 = any(llm.has_key(p) for p in llm.PROVIDERS)
    if not _wiki_prov_ok5:
        st.warning(t("Wiki 생성 API 없음 — :material/settings: 설정 탭에서 키를 입력하세요."),
                   icon=":material/warning:")

    _fws5 = DEFAULT_WS
    _wiki_stems5 = {_nfc(p.stem) for p in _cur_wiki5_path.rglob("*.md")} if _cur_wiki5_path.exists() else set()

    # ── 챕터 요약 → Wiki (큐 기반) ───────────────────────────
    _q5_stems = queue_list("tab5_ready")   # Tab4가 등록한 책 stem
    _wiki_pend5: list[dict] = []
    _wiki_refresh5: list[dict] = []
    for _stem5 in _q5_stems:
        _ch5 = chapters_dir(DEFAULT_WS, _stem5)
        # 유령 항목 자동 정리: 챕터 폴더가 없으면(삭제·프래그먼트 잔재) 큐에서 제거하고 건너뜀
        if not _ch5.exists():
            queue_remove("tab5_ready", [_stem5])
            continue
        _jsons5 = list_summary_files(_ch5)
        _total5 = len([f for f in _ch5.glob("??_*.txt")
                       if not f.stem.endswith(_DERIVED)]) if _ch5.exists() else 0
        # 요약 기반(위키/DOCX/HWPX) 정보는 그 출력 중 하나라도 켜져 있을 때만 의미가
        # 있다 — EPUB만 켰을 때는 요약·전체요약 여부와 무관하므로 챕터 수만 보여준다
        # (2026-08-11).
        if _use_ob or _use_dx or _use_hx:
            _ratio5 = tf("%d/%d챕터 요약됨", len(_jsons5), _total5)
            _has_ov5 = find_overview_file(DEFAULT_WS, _stem5) is not None
            _meta5 = _ratio5 + " · " + (t("전체요약 ✓") if _has_ov5 else t("전체요약 — (반영 시 자동 생성)"))
        else:
            _meta5 = tf("%d챕터", _total5)
        # 챕터 이름 목록 (NN_제목.txt → 제목)
        _ch_names5 = [_re.sub(r'^\d+_', '', f.stem) for f in sorted(_ch5.glob("??_*.txt"))
                      if not f.stem.endswith(_DERIVED)] if _ch5.exists() else []
        _wiki_item5 = {
            "key": _stem5,
            "label": _stem5,
            "meta": _meta5,
            "obj": {"ws": DEFAULT_WS, "stem": _stem5},
            "ch_names": _ch_names5,
        }
        # '이미 위키 노트가 있음' 갱신 확인은 위키 출력을 실제로 켰을 때만 의미가
        # 있다 — EPUB(또는 DOCX/HWPX)만 켠 경우 위키 보관함 상태와 무관하게 항상
        # 대기 목록에 그대로 뜨게 한다(2026-08-11 — 이미 위키 반영된 책은 EPUB만
        # 원해도 위키 전용 "갱신 확인" 화면으로 빠져 헷갈리던 문제).
        if _use_ob and _stem5 in _wiki_stems5:
            _wiki_refresh5.append(_wiki_item5)
        else:
            _wiki_pend5.append(_wiki_item5)

    if _wiki_pend5:
        # 전체 선택 / 해제 (분할 탭 체크리스트와 동일한 조작)
        _wk5_keys = [f"wiki5_{_it5['key']}" for _it5 in _wiki_pend5]
        _wsel5c1, _wsel5c2, _wsel5c3 = st.columns([1.3, 1, 4])
        if _wsel5c1.button(t("전체 선택"), icon=":material/select_all:", key="wiki5_select_all", use_container_width=True):
            for _wk in _wk5_keys:
                st.session_state[_wk] = True
            st.rerun()
        if _wsel5c2.button(t("해제"), icon=":material/deselect:", key="wiki5_deselect_all", use_container_width=True):
            for _wk in _wk5_keys:
                st.session_state[_wk] = False
            st.rerun()
        _wsel5c3.caption(tf("총 %d권", len(_wiki_pend5)))
        # 책 단위 체크리스트 + 챕터 이름 펼치기
        _sel5: list = []
        with st.container(height=320, border=True):
            _w5h1, _w5h2, _w5h3, _w5h4 = st.columns([0.05, 0.5, 0.32, 0.13])
            _w5h2.markdown(t("**책 제목**"), unsafe_allow_html=True)
            _w5h3.markdown(f"<small style='color:#9ca3af'>{t('챕터')}</small>", unsafe_allow_html=True)
            for _it5 in _wiki_pend5:
                _k5 = f"wiki5_{_it5['key']}"
                _c5a, _c5b, _c5c, _c5d = st.columns([0.05, 0.5, 0.32, 0.13])
                _chk5 = _c5a.checkbox(" ", key=_k5, label_visibility="collapsed")
                if _chk5:
                    _sel5.append(_it5["obj"])
                _c5b.markdown(f"**{_it5['label']}**", unsafe_allow_html=True)
                _ch_preview5 = " · ".join(_it5["ch_names"][:4])
                if len(_it5["ch_names"]) > 4:
                    _ch_preview5 += f" … +{len(_it5['ch_names'])-4}개"
                _c5c.caption(_it5["meta"])
                _view_dir5 = chapters_dir(DEFAULT_WS, _it5["obj"]["stem"])
                if _c5d.button(t("보기"), icon=":material/visibility:", key=f"wiki5_view_{_it5['key']}", use_container_width=True,
                                disabled=not _view_dir5.exists()):
                    open_path(_view_dir5)
                if _it5["ch_names"]:
                    with st.expander(f"  ↳ {_ch_preview5}", expanded=False):
                        _ch5_dir = chapters_dir(DEFAULT_WS, _it5["obj"]["stem"])
                        for _cn5 in _it5["ch_names"]:
                            # NN_제목.txt → NN_제목_wiki.md(구형 json 폴백) 탐색
                            _cn5_txt = next((_ch5_dir.glob(f"??_{_cn5}.txt")), None) if _ch5_dir.exists() else None
                            _cn5_json = summary_file_for(_cn5_txt) if _cn5_txt else None
                            _has_json5 = _cn5_json is not None
                            _cj1, _cj2 = st.columns([4, 1])
                            if _has_json5:
                                _cj1.markdown(f"✅ **{_cn5}**")
                                _safe_key5 = _re.sub(r"[^a-zA-Z0-9가-힣]", "_", _cn5)[:30]
                                if _cj2.button("Wiki", icon=":material/menu_book:", key=f"ch5w_{_it5['key'][:20]}_{_safe_key5}", use_container_width=True):
                                    _bok5, _bmsg5 = build_single_chapter_wiki(DEFAULT_WS, _it5["obj"]["stem"], _cn5_json, wiki_dir=_cur_wiki5_path)
                                    (st.success if _bok5 else st.error)(
                                        f"{'✅ ' + Path(_bmsg5).name if _bok5 else '❌ ' + _bmsg5}")
                                _pv5 = load_summary_file(_cn5_json)
                                if _pv5:
                                    with st.expander(f"  📖 {_cn5[:35]}", expanded=False):
                                        if _pv5.get("summary"):
                                            st.info(_pv5["summary"])
                                        if _pv5.get("body"):
                                            st.markdown(_pv5["body"])
                            else:
                                _cj1.caption(f"⏳ {_cn5}")
        _b5c1, _b5c2 = st.columns(2)
        _rs5 = _b5c1.button(tf("시작 (%d권)", len(_sel5)), icon=":material/play_arrow:", key="wiki5_run_sel",
                              use_container_width=True, type="primary", disabled=len(_sel5)==0)
        _del5 = _b5c2.button(tf("삭제 (%d권)", len(_sel5)), icon=":material/delete:", key="wiki5_del",
                             use_container_width=True, disabled=len(_sel5)==0)
        if _del5 and _sel5:
            queue_remove("tab5_ready", [_o5["stem"] for _o5 in _sel5])
            st.rerun()
        if _rs5 and _sel5:
            st.session_state["wiki5_status_place"] = "pending"
            _run_start("wiki5", [_o5["stem"] for _o5 in _sel5])
    elif not _wiki_refresh5:
        st.info(t("Wiki 대기 없음 — 📝 문서요약에서 요약 완료 후 자동 등록되거나 아래에서 수동 추가하세요"))

    if _wiki_refresh5:
        st.divider()
        st.markdown(tf("#### 새 요약 있음 · 기존 Wiki 갱신 확인 (%d권)", len(_wiki_refresh5)))
        st.warning(
            t("기존 Wiki가 있습니다. 명시적으로 선택한 책만 새 요약으로 다시 반영합니다. 선택하지 않은 책은 기존 노트를 유지합니다."),
            icon=":material/warning:",
        )
        _refresh_sel5 = _checklist(_wiki_refresh5, "wiki5_refresh", height=240, viewable=True)
        _refresh_stems5 = [_o5["stem"] for _o5 in _refresh_sel5]
        _wr5c1, _wr5c2 = st.columns(2)
        _refresh_run5 = _wr5c1.button(
            tf("다시 반영 (%d권)", len(_refresh_stems5)),
            icon=":material/refresh:", key="wiki5_refresh_run", use_container_width=True,
            type="primary", disabled=len(_refresh_stems5) == 0,
        )
        _refresh_skip5 = _wr5c2.button(
            tf("이번 갱신 건너뛰기 (%d권)", len(_refresh_stems5)),
            icon=":material/skip_next:", key="wiki5_refresh_skip", use_container_width=True,
            disabled=len(_refresh_stems5) == 0,
        )
        if _refresh_skip5 and _refresh_stems5:
            queue_remove("tab5_ready", _refresh_stems5)
            st.rerun()
        if _refresh_run5 and _refresh_stems5:
            st.session_state["wiki5_status_place"] = "refresh"
            _run_start("wiki5", _refresh_stems5)

    # 수동 추가 expander (책 단위)
    with st.expander(t("➕ 수동으로 추가 (요약 완료된 책에서 선택)")):
        _mc5a, _mc5b = st.columns([3, 2])
        _search5 = _mc5a.text_input(t("책 이름 검색"), key="wiki5_search", placeholder=t("검색어 입력…"))
        _sort5 = _mc5b.radio(t("정렬"), [t("최근 추가순"), t("이름순")], horizontal=True, key="wiki5_sort")
        _ch_root5m = cfg.CHAPTERS_DIR
        _all_books5 = list(_ch_root5m.iterdir()) if _ch_root5m.exists() else []
        _books_with_json5 = [d for d in _all_books5 if d.is_dir() and list_summary_files(d)]
        _books_with_json5 = sorted(_books_with_json5, key=lambda d: d.stat().st_mtime, reverse=True) \
                            if _sort5 == t("최근 추가순") else sorted(_books_with_json5, key=lambda d: d.name)
        _filt5 = [d for d in _books_with_json5 if _search5.lower() in d.name.lower()] if _search5 else _books_with_json5
        _mitems5 = [{"key": d.name, "label": d.name,
                     "meta": tf("%d챕터 요약", len(list_summary_files(d))), "obj": d.name}
                    for d in _filt5]
        _msel5 = _checklist(_mitems5, "wiki5m", height=200)
        _madd5c1, _madd5c2 = st.columns(2)
        if _madd5c1.button(tf("선택 항목 큐에 추가 (%d권)", len(_msel5)), icon=":material/add:", key="wiki5m_add",
                           use_container_width=True, disabled=len(_msel5)==0):
            queue_add("tab5_ready", _msel5); st.rerun()
        if _madd5c2.button(tf("삭제 (%d권)", len(_msel5)), icon=":material/delete:", key="wiki5m_del",
                           use_container_width=True, disabled=len(_msel5)==0):
            queue_remove("tab5_ready", _msel5); st.rerun()

    # 단일 TXT 기반 (챕터 분할 없는 책 — 큐 외 별도 경로)
    _single_pend5: list[dict] = []
    _t5s = cfg.TXT_DIR
    if _t5s.exists():
        for _txt5s in sorted(_t5s.glob("*.txt")):
            _stem5s = _nfc(_txt5s.stem)
            _ch5s = chapters_dir(DEFAULT_WS, _stem5s)
            if _ch5s.exists() and any(f for f in _ch5s.glob("??_*.txt")
                                       if not f.stem.endswith(_DERIVED)):
                continue
            if _stem5s in _wiki_stems5:
                continue
            _single_pend5.append({
                "key": f"s_{_stem5s}",
                "label": _stem5s,
                "meta": f"단일TXT · {_txt5s.stat().st_size//1024}KB",
                "obj": {"ws": DEFAULT_WS, "stem": _stem5s, "txt": _txt5s},
            })

    # 단일 TXT → Wiki (설정된 AI로 직접 생성)
    if _single_pend5:
        st.divider()
        st.markdown(tf("#### 단일 TXT → Wiki (%d권 · 챕터 분할 없음)", len(_single_pend5)))
        st.caption(t("아직 위키로 만들지 않은 단일 TXT입니다. 위키로 만들거나, 필요 없으면 원본 TXT를 삭제할 수 있습니다."))
        _sel5s = _checklist(_single_pend5, "wiki5s", height=200)
        _s5c1, _s5c2 = st.columns(2)
        _run5s = _s5c1.button(tf("Wiki 생성 (%d권)", len(_sel5s)), icon=":material/play_arrow:", key="wiki5s_run",
                     use_container_width=True, type="primary", disabled=len(_sel5s)==0)
        _del5s = _s5c2.button(tf("삭제 (%d권)", len(_sel5s)), icon=":material/delete:", key="wiki5s_del",
                     use_container_width=True, disabled=len(_sel5s)==0)
        if _run5s and _sel5s:
            for _wo5s in _sel5s:
                _ok5s = trigger_gemini_wiki(_wo5s["txt"])
                (st.success if _ok5s else st.error)(
                    f"{'✅ 백그라운드 시작' if _ok5s else '❌ 실패'}: {_wo5s['stem']}")
            st.rerun()
        if _del5s and _sel5s:
            for _wo5s in _sel5s:
                try:
                    Path(_wo5s["txt"]).unlink(missing_ok=True)
                except Exception:
                    pass
            st.rerun()

    # Wiki 완료
    st.divider()
    _wiki_files5 = sorted(_cur_wiki5_path.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True) \
                   if _cur_wiki5_path.exists() else []
    st.markdown(t("#### Wiki 완료"))
    if _wiki_files5:
        _wv_col1, _wv_col2 = st.columns(2)
        if _wv_col1.button(t("Obsidian 보관함(Vault) 열기"), icon=":material/menu_book:", key="w5_vault", use_container_width=True):
            open_wiki_vault()
        if _wv_col2.button(t("폴더 열기"), icon=":material/folder_open:", key="w5_folder", use_container_width=True):
            open_path(_cur_wiki5_path)
    else:
        st.caption("생성된 Wiki 없음")


# ── 설정 (API 키) ─────────────────────────────────────
if _active_view == "settings":
    _lang_cur = get_lang()
    _lang_sel = st.radio("🌐 언어 / Language", ["한국어", "English"],
                         index=0 if _lang_cur == "ko" else 1,
                         horizontal=True, key="ui_lang_radio")
    _lang_new = "ko" if _lang_sel == "한국어" else "en"
    if _lang_new != _lang_cur:
        set_lang(_lang_new)
        st.rerun()
    st.caption(t("화면에 쓰는 언어입니다 — 번역 결과물의 언어는 바로 아래에서 따로 고릅니다."))

    # ── 도착언어 — 번역본·요약·위키가 모두 이 언어로 나온다 (2026-08-15) ──────
    # 화면 언어(위)와 별개다: 한국어 화면을 쓰면서 결과물만 영어로 뽑을 수 있다.
    _tgt_opts = target_language_options()
    _tgt_cur = target_language()
    _tgt_codes = [c for c, _ in _tgt_opts]
    _tgt_new = st.selectbox(
        t("🎯 번역 도착언어"), _tgt_codes,
        index=_tgt_codes.index(_tgt_cur) if _tgt_cur in _tgt_codes else 0,
        format_func=lambda c: dict(_tgt_opts).get(c, c), key="target_lang_select",
        help=t("번역본·챕터 요약·위키 노트가 모두 이 언어로 만들어집니다. "
                "원문 언어는 자동으로 감지하므로 따로 고르지 않아도 됩니다."),
    )
    if _tgt_new != _tgt_cur:
        set_target_language(_tgt_new)
        st.rerun()
    if _tgt_cur != "ko":
        st.caption(t("⚠️ 이미 만들어 둔 번역본·요약은 예전 도착언어 그대로 남아 있습니다 — "
                      "새 언어로 바꾸려면 해당 파일을 지우고 다시 처리하세요."))
    st.divider()

    # ── 업데이트 ──────────────────────────────────────────
    st.markdown("#### " + t("업데이트"))
    _upc1, _upc2 = st.columns([2, 1])
    _upc1.caption(tf("현재 버전: %s", APP_VERSION))
    if _upc2.button(t("업데이트 확인"), icon=":material/system_update:", key="settings_check_update",
                    use_container_width=True):
        _upd_info = updater.check_for_update()
        if _upd_info:
            st.session_state["_update_info"] = _upd_info
            st.session_state.pop("_update_dismissed", None)
            # 수동으로 확인한 거라, 예전에 이 버전을 '나중에'로 미뤄뒀어도
            # 항상 팝업을 보여준다 (2026-07-25).
            llm.set_pref("update_dismissed_version", "")
            st.rerun()
        elif sys.platform not in ("win32", "darwin"):
            st.info(t("앱 내 업데이트는 Windows·macOS에서만 지원됩니다."))
        else:
            st.success(t("최신 버전을 사용 중입니다."))
    st.divider()

    st.caption(t(
        "API 키는 이 화면에서 직접 저장한 값만 사용합니다. "
        "저장 키는 `~/.config/mybookshelf/keys.json`에만 보관되며 저장소에 올라가지 않습니다."
    ))

    # 위키 생성 모델 (공급자/모델) — 모노톤 AI 아이콘
    _wp, _wm = llm.wiki_provider_model()
    _wp_label = llm.PROVIDERS.get(_wp, {}).get("label", _wp)
    st.markdown(f":material/smart_toy: **{t('위키 생성 모델')}** — {t('현재')}: `{_wp_label} · {_wm}`")
    _avail = [(p, m) for p, info in llm.PROVIDERS.items() if llm.has_key(p) for m in info["models"]]
    if _avail:
        _labels = [f"{llm.PROVIDERS[p]['label']} · {m}" for p, m in _avail]
        _curlbl = f"{llm.PROVIDERS.get(_wp, {}).get('label', _wp)} · {_wm}"
        _idx = _labels.index(_curlbl) if _curlbl in _labels else 0
        _sel = st.selectbox(t("위키 노트를 생성할 모델"), _labels, index=_idx, key="wiki_model_sel")
        _p, _m = _avail[_labels.index(_sel)]
        if (_p, _m) != (_wp, _wm) and st.button(t("이 모델로 위키 생성"), icon=":material/check:", use_container_width=True):
            llm.set_wiki_model(_p, _m); st.success(f"위키 모델 = {_p} · {_m}"); st.rerun()
    else:
        st.info(t("사용 가능한 API 키나 활성화된 CLI가 없습니다. 아래에서 API 키를 입력하거나 CLI 사용을 켜세요."))
    st.caption(t("번역과 별개로, 위키 노트 생성에 쓸 모델입니다. 구조화 출력은 공급자별로 자동 처리됩니다."))
    st.divider()

    # 요약 분량 — 원문 대비 % 슬라이더 (기본 설정 홈. 문서요약 탭과 pref 공유, 2026-07-23)
    st.markdown(f":material/tune: **{t('요약 분량')}**")
    _render_wiki_length_slider("wiki_length_pct_sl")
    st.divider()

    # 🖥 CLI 구독 도구 — API 등록보다 앞(우선) · Claude/Codex 컴팩트 토글 (2026-07-10)
    st.markdown(t("### :material/hub: AI 구독 (CLI)"))
    st.caption(t("API 키 없이 구독으로 사용 — 설치·로그인 후 켜세요. AI 키 등록보다 우선합니다."))
    _cc1, _cc2 = st.columns(2)
    with _cc1:
        _claude_installed = llm.claude_cli_installed()
        _claude_enabled = bool(llm.get_pref("use_claude_cli", False))
        if _claude_installed:
            _new_enabled = st.toggle("Claude", value=_claude_enabled, key="set_use_claude_cli",
                                     help=f"설치됨: {llm.claude_cli_path()} · Claude 구독 로그인 시 켜세요")
            st.caption(f"모델: `{_cli_model_label('claude_cli')}`")
            if _new_enabled != _claude_enabled:
                llm.set_claude_cli_enabled(_new_enabled)
                st.rerun()
        else:
            st.toggle("Claude", value=False, disabled=True, key="set_use_claude_cli", help="미설치")
            st.caption("미설치 · `npm i -g @anthropic-ai/claude-code`")
    with _cc2:
        _codex_installed = llm.codex_cli_installed()
        _codex_enabled = bool(llm.get_pref("use_codex_cli", False))
        if _codex_installed:
            _new_codex_enabled = st.toggle("Codex", value=_codex_enabled, key="set_use_codex_cli",
                                           help=f"설치됨: {llm.codex_cli_path()} · ChatGPT 로그인 시 켜세요")
            st.caption(f"모델: `{_cli_model_label('codex_cli')}`"
                       + ("  · " + t("Codex 설정(~/.codex/config.toml)을 따릅니다")
                          if llm.codex_cli_model() else
                          "  · " + t("ChatGPT 구독은 모델 지정이 안 됩니다")))
            if _new_codex_enabled != _codex_enabled:
                llm.set_codex_cli_enabled(_new_codex_enabled)
                st.rerun()
        else:
            st.toggle("Codex", value=False, disabled=True, key="set_use_codex_cli", help="미설치")
            st.caption("미설치 · `npm i -g @openai/codex`")
    st.divider()

    # 🔑 API 등록 (CLI 공급자 제외)
    st.markdown(t("### :material/key: API 키 등록"))
    _cli_provs = {"claude_cli", "codex_cli"}
    for _prov, _info in llm.PROVIDERS.items():
        if _prov in _cli_provs:
            continue
        _cur = llm.masked(_prov)
        _api_label = ("✅ " + t("저장됨") + " " + _cur) if _cur else t("미설정")
        with st.expander(f"{_info['label']}  —  {_api_label}",
                         expanded=False):
            with st.form(f"keyform_{_prov}", clear_on_submit=True):
                _newk = st.text_input(f"{_info['label']} API 키", type="password",
                                      placeholder=_info["hint"], key=f"keyin_{_prov}")
                _c1, _c2 = st.columns(2)
                _save = _c1.form_submit_button(t("저장"), icon=":material/save:", use_container_width=True)
                _del = _c2.form_submit_button(t("삭제"), icon=":material/delete:", use_container_width=True)
                if _save:
                    if _newk.strip():
                        llm.save_key(_prov, _newk.strip())
                        st.success(t("저장됨"))
                        st.rerun()
                    else:
                        st.warning(t("키를 입력하세요."))
                if _del:
                    llm.save_key(_prov, "")
                    st.info("저장 키 삭제됨")
                    st.rerun()
            if _cur:
                st.caption("현재 앱 설정에 저장된 키를 사용합니다.")
            st.caption(f"모델: {', '.join(_info['models'])}")

    st.divider()
    st.markdown(t("### :material/description: DOCX 보관함 설정"))
    st.caption(
        f"현재: `{_current_docx_dir()}` — 'DOCX 문서 생성'으로 만든 Word 문서가 여기 저장됩니다."
    )
    _dd_custom = st.text_input("폴더 경로 직접 입력", value="", key="docx_dir_custom",
                               placeholder=str(_current_docx_dir()))
    if st.button(t("DOCX 보관함 저장 (즉시 적용)"), icon=":material/save:", use_container_width=True, key="docx_dir_save"):
        _dd_target = _dd_custom.strip()
        if not _dd_target:
            st.warning(t("경로를 입력하세요."))
        elif _dd_target == str(_current_docx_dir()):
            st.info("이미 이 폴더를 쓰고 있습니다.")
        else:
            set_docx_dir(_dd_target)
            st.session_state["docx5_active_dir"] = _dd_target
            st.success(f"✅ 저장됨: `{_dd_target}` — Tab 5에 즉시 반영됩니다")
    st.caption("ℹ️ 기존에 만든 문서는 자동으로 옮겨지지 않습니다. 옮기려면 폴더에서 직접 이동하세요.")

    st.divider()
    st.markdown(t("### :material/description: HWPX 보관함 설정"))
    st.caption(
        f"현재: `{_current_hwpx_dir()}` — 'HWPX 문서 생성'으로 만든 한글 문서가 여기 저장됩니다."
    )
    _hd_custom = st.text_input("폴더 경로 직접 입력", value="", key="hwpx_dir_custom",
                               placeholder=str(_current_hwpx_dir()))
    if st.button(t("HWPX 보관함 저장 (즉시 적용)"), icon=":material/save:", use_container_width=True, key="hwpx_dir_save"):
        _hd_target = _hd_custom.strip()
        if not _hd_target:
            st.warning(t("경로를 입력하세요."))
        elif _hd_target == str(_current_hwpx_dir()):
            st.info("이미 이 폴더를 쓰고 있습니다.")
        else:
            set_hwpx_dir(_hd_target)
            st.session_state["hwpx5_active_dir"] = _hd_target
            st.success(f"✅ 저장됨: `{_hd_target}` — Tab 5에 즉시 반영됩니다")
    st.caption("ℹ️ 기존에 만든 문서는 자동으로 옮겨지지 않습니다. 옮기려면 폴더에서 직접 이동하세요.")

    st.divider()
    st.markdown(t("### :material/menu_book: EPUB 전자책 설정"))
    st.caption(
        f"현재: `{_current_epub_dir()}` — 'EPUB 전자책 생성'으로 만든 전자책이 여기 저장됩니다."
    )
    _ed_custom = st.text_input("폴더 경로 직접 입력", value="", key="epub_dir_custom",
                               placeholder=str(_current_epub_dir()))
    if st.button(t("EPUB 보관함 저장 (즉시 적용)"), icon=":material/save:", use_container_width=True, key="epub_dir_save"):
        _ed_target = _ed_custom.strip()
        if not _ed_target:
            st.warning(t("경로를 입력하세요."))
        elif _ed_target == str(_current_epub_dir()):
            st.info("이미 이 폴더를 쓰고 있습니다.")
        else:
            set_epub_dir(_ed_target)
            st.session_state["epub5_active_dir"] = _ed_target
            st.success(f"✅ 저장됨: `{_ed_target}` — Tab 5에 즉시 반영됩니다")
    st.caption("ℹ️ 기존에 만든 전자책은 자동으로 옮겨지지 않습니다. 옮기려면 폴더에서 직접 이동하세요.")

    st.divider()
    st.markdown(t("### :material/book_2: 옵시디언(Obsidian) 보관함 설정"))
    st.caption(
        f"현재: `{_current_wiki_dir()}` — 생성된 위키 노트가 여기 저장되고, "
        "Wiki 목록 탭의 [옵시디언에서 위키 보관함(Vault) 열기]도 이 폴더를 엽니다."
    )
    _default_wiki = str(cfg.BASE_DIR / "wiki")
    _wiki_cands: list[str] = []
    for _c in [_default_wiki] + list_obsidian_vaults():
        if _c and _c not in _wiki_cands:
            _wiki_cands.append(_c)
    _cur_wiki = str(_current_wiki_dir())
    _wd_sel = st.selectbox(
        "폴더 선택 — 기본값 + 옵시디언에 등록된 보관함(Vault)들",
        _wiki_cands,
        index=_wiki_cands.index(_cur_wiki) if _cur_wiki in _wiki_cands else 0,
        key="wiki_dir_sel",
    )
    _wd_custom = st.text_input("또는 폴더 경로 직접 입력 (비우면 위 선택 사용)", value="", key="wiki_dir_custom")
    _wd_target = (_wd_custom.strip() or _wd_sel).strip()
    if st.button(t("위키 보관함(Vault) 저장 (즉시 적용)"), icon=":material/save:", use_container_width=True, key="wiki_dir_save"):
        if _wd_target == _cur_wiki:
            st.info("이미 이 폴더를 쓰고 있습니다.")
        else:
            set_wiki_dir(_wd_target)
            st.session_state["wiki5_active_dir"] = _wd_target
            st.success(f"✅ 저장됨: `{_wd_target}` — Tab 5에 즉시 반영됩니다")
    st.caption("ℹ️ 기존에 만든 노트는 자동으로 옮겨지지 않습니다. 옮기려면 폴더에서 직접 이동하세요.")

    st.divider()
    with st.expander(t("저작권 및 사용 주의"), expanded=False):
        st.markdown(t(
            "**My Bookshelf** · © 2026 저작자 — 개인·비상업 연구 보조 용도. "
            "이 프로그램의 저작권은 저작자에게 있으며, 개인적·학술적 용도로 사용할 수 있으나 "
            "서면 동의 없는 재판매·상업적 배포는 허용되지 않습니다. 프로그램은 '있는 그대로' 제공되며 "
            "정확성·무결성을 보증하지 않습니다."
        ))
        st.write(t(
            "원문 문서의 저작권·번역권·요약·재배포 가능 여부는 이용자 본인이 확인해야 합니다. "
            "이 앱은 법률·출판·학술 제출 요건을 자동 판정하지 않습니다."
        ))
        st.write(t(
            "AI API 또는 CLI 구독 도구를 활성화하면 문서 일부 또는 전체가 외부 AI 서비스로 전송됩니다. "
            "개인정보, 비공개 원고, 배포 권한이 불명확한 자료는 넣지 마세요."
        ))
        st.write(t(
            "생성된 번역·요약·위키 노트의 정확성·완전성은 보장되지 않습니다. "
            "출판·제출·인용·대외 배포 전에는 반드시 원문과 결과물을 직접 대조해 검토하세요."
        ))

_render_stage_completion_notice()

# 로딩 오버레이 제거 + 이후 재렌더링에서는 오버레이 건너뜀
_loading_ph.empty()
st.session_state["_app_loaded"] = True
