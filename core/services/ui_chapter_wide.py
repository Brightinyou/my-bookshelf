"""장 구분 편집 작업창 — 넓은 별창에서 장 목록 전체를 펴 놓고 고친다 (2026-09-21).

연구자 지적: 확인 화면은 접혀 있어 장 제목 하나만 보이고, 제목 말고는 고칠 수 없고,
쪽 번호가 없어 맞는지 견줄 수 없고, 1장과 3장 사이에 2장을 **끼워 넣을 길이 없고**,
「들어가며」처럼 잘못 잡힌 장을 지울 길이 없다.

그래서 이 창은
  · 장을 **전부 펼쳐** 한 줄에 하나씩 놓고 (순번 · 쪽 · 제목 · 시작 부분),
  · 제목은 그 자리에서 고치면 바로 파일 이름에 반영되고,
  · ＋ 는 그 장 안에서 새 장이 시작할 줄을 **쪽 번호와 함께** 골라 끼워 넣고,
  · − 는 그 장을 앞 장에 합쳐 없앤다.

파일이 곧 진실이다(services/chapter_map 머리 주석). 여기서 누른 것은 곧장 챕터
파일에 반영되고, 본창은 다시 그릴 때 파일을 새로 읽으므로 따로 맞출 것이 없다.
확정(«확정하고 다음으로»)은 본창에서 한다 — 이 창은 고치는 곳이다."""
from __future__ import annotations

import re

import streamlit as st

from services import chapter_map as cmap
from services.i18n import t, tf

_WS = re.compile(r"\s+")
_PREVIEW_CHARS = 60
# 제목답게 생긴 줄 — 「I. 들어가는 말」·「제3장 …」·「2. 연구 방법」·「Ⅳ. 결론」. 후보가
# 수백 줄일 때(OCR 본문은 줄마다 문단이라 짧은 줄이 널렸다 — 『기술윤리』 3장 477개)
# 이런 줄을 앞에 세운다. 실측: 기본 후보가 «래를 예상하였고, 90% 이상의 …» 같은
# 문장 조각이었다 (2026-09-21).
_HEADING_LIKE = re.compile(
    r"^(?:제\s?\d{1,2}\s?[장절부편강과화]|\d{1,2}\s?[.장절)]|[IVXivx]{1,5}\s?[.)]|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\s?[.)]?|"
    r"chapter\s?\d+|part\s?\d+)\s*\S", re.I)
# 번호 없는 짧은 표제 — 「해설」·「관계문헌」·「옮긴이의 말」. 숫자·문장부호 없이 8자 이하.
_BARE_HEAD = re.compile(r"[가-힣A-Za-z][가-힣A-Za-z ]{1,7}")
_MAX_CANDS = 60


def _candidates(ws: str, book: str, idx: int, query: str) -> tuple[list[tuple[int, str]], int, bool]:
    """([(위치, 줄)], 전체 후보 수, 제목다운 줄만 추렸는지). 찾기가 있으면 그대로 다 보인다."""
    cands, total = cmap.split_candidates(ws, book, idx, limit=10 ** 6, query=query)
    if query or len(cands) <= _MAX_CANDS:
        return cands[:_MAX_CANDS], total, False
    heads = [(p, s) for p, s in cands
             if len(s) <= 40 and (_HEADING_LIKE.match(s) or cmap.boundary_word(s)
                                  or cmap.is_backmatter_title(s) or _BARE_HEAD.fullmatch(s))]
    if heads:
        return heads[:_MAX_CANDS], total, True
    step = len(cands) / _MAX_CANDS
    return [cands[int(i * step)] for i in range(_MAX_CANDS)], total, False


# ── 자료 ────────────────────────────────────────────────────

def page_label(rng: tuple[int, int] | None, offset: int | None) -> str:
    """'12–34쪽', 인쇄 번호를 알면 '12–34쪽 (인쇄 10–32)'. 모르면 '—'."""
    if not rng:
        return "—"
    a, b = rng
    body = tf("%s쪽", str(a) if a == b else f"{a}–{b}")
    if offset:
        pa, pb = a + offset, b + offset
        body += f" ({t('인쇄')} {pa if pa == pb else f'{pa}–{pb}'})"
    return body


def chapter_rows(ws: str, book: str, pm: cmap.PageMap | None = None,
                 offset: int | None = None) -> list[dict]:
    """본창의 요약 목록과 이 작업창이 함께 쓰는 장 목록."""
    files = cmap.chapter_files(ws, book)
    pm = pm or cmap.PageMap(ws, book)
    sect = set(cmap.section_title_chapters(ws, book))
    rows = []
    for i, f in enumerate(files):
        body = f.read_text(encoding="utf-8", errors="ignore")
        rows.append({
            "idx": i,
            "stem": f.stem,
            "순번": f.stem[:2],
            "쪽": page_label(pm.chapter_range(i), offset),
            "제목": cmap.chapter_title(f),
            "글자": len(body),
            "시작 부분": _WS.sub(" ", body[:_PREVIEW_CHARS * 2]).strip()[:_PREVIEW_CHARS],
            "절제목": i in sect,
            "뒷부속": cmap.is_backmatter_title(cmap.chapter_title(f)),
            "껍데기": i > 0 and len(body) < 300,
        })
    return rows


def _printed_offset(book: str) -> int | None:
    """원본 PDF에 찍힌 쪽 번호와 물리 쪽의 차이. 책마다 한 번만 센다."""
    key = f"_wb_offset_{book}"
    if key not in st.session_state:
        off = None
        try:
            import config as cfg
            from services import toc as toc_svc
            pdf = cfg.PDF_DIR / f"{book}.pdf"
            if pdf.exists():
                off = toc_svc.printed_offset(pdf)
        except Exception:
            off = None
        st.session_state[key] = off
    return st.session_state[key]


# ── 동작 ────────────────────────────────────────────────────

def _rename(ws: str, book: str, idx: int, widget_key: str) -> None:
    new = str(st.session_state.get(widget_key, "")).strip()
    files = cmap.chapter_files(ws, book)
    if not new or not (0 <= idx < len(files)) or new == cmap.chapter_title(files[idx]):
        return
    safe = cmap._safe(new)
    if cmap.rename_chapter(ws, book, idx, new):
        if safe != new:
            st.session_state["_wb_notice"] = tf(
                "파일 이름에 쓸 수 없는 글자를 «-»로 바꿔 「%s」로 저장했습니다.", safe)
        else:
            st.session_state["_wb_notice"] = tf("제목을 「%s」로 바꿨습니다.", new)


def _merge_many(ws: str, book: str, idxs: list[int]) -> int:
    done = 0
    for i in sorted(idxs, reverse=True):          # 뒤에서부터 — 앞 순번이 안 밀린다
        if cmap.merge_up(ws, book, i):
            done += 1
    return done


# ── 화면 ────────────────────────────────────────────────────

def _split_panel(ws: str, book: str, idx: int, row: dict, pm: cmap.PageMap,
                 offset: int | None, key: str) -> None:
    """＋ 를 누른 장 아래 펼쳐지는 '새 장 끼워 넣기' 칸."""
    files = cmap.chapter_files(ws, book)
    text = files[idx].read_text(encoding="utf-8", errors="ignore")
    with st.container(border=True):
        st.markdown("**➕ " + tf("「%s」 안에서 새 장이 시작하는 줄을 고르세요", row["제목"]) + "**")
        st.caption(t("제목처럼 생긴 줄만 후보로 보입니다. 원하는 줄이 안 보이면 그 제목의 낱말로 찾으세요. "
                     "고른 줄부터 끝까지가 새 장이 되고, 그 앞은 이 장에 남습니다."))
        q = st.text_input(t("찾기 — 새 장 제목에 든 낱말"), key=f"{key}_q_{row['stem']}",
                          placeholder=t("예: 서론, Introduction, 3장"))
        cands, total, heads_only = _candidates(ws, book, idx, q)
        if not cands:
            st.info(t("후보가 없습니다. 다른 낱말로 찾아보세요."))
        else:
            if heads_only:
                st.caption(tf("후보 %d개 중 제목답게 생긴 %d개만 보입니다 — 다른 줄은 찾기로 찾으세요.",
                              total, len(cands)))
            elif total > len(cands):
                st.caption(tf("후보 %d개 중 %d개만 고르게 보입니다 — 찾기로 좁히면 다 보입니다.",
                              total, len(cands)))
            labels = []
            for pos, line in cands:
                pg = pm.page_at(idx, text[:pos])
                labels.append((tf("%s쪽", pg) + " · " if pg else "") + line)
            pick = st.selectbox(t("새 장이 시작하는 줄"), list(range(len(cands))),
                                key=f"{key}_pick_{row['stem']}", format_func=lambda k: labels[k])
            pos, line = cands[pick]
            st.caption("📄 " + _WS.sub(" ", text[pos:pos + 220]).strip() + " …")
            title = st.text_input(t("새 장 제목"), value=line, key=f"{key}_nt_{row['stem']}")
            b1, b2 = st.columns([1, 1])
            if b1.button(t("여기서 나누기"), icon=":material/content_cut:", type="primary",
                         key=f"{key}_do_{row['stem']}", width="stretch"):
                if cmap.split_chapter(ws, book, idx, pos, title):
                    st.session_state["_wb_notice"] = tf("「%s」 장을 끼워 넣었습니다.", title.strip() or line)
                    st.session_state.pop(f"{key}_split_open", None)
                    st.rerun()
                st.error(t("그 자리에서는 나눌 수 없습니다 — 앞뒤 본문이 모두 있어야 합니다."))
            if b2.button(t("닫기"), key=f"{key}_x_{row['stem']}", width="stretch"):
                st.session_state.pop(f"{key}_split_open", None)
                st.rerun()


def chapter_workbench(ws: str, book: str, key: str = "wb") -> None:
    files = cmap.chapter_files(ws, book)
    st.markdown(f"## 📑 {t('장 구분 편집')} — {book}")
    if not files:
        st.info(t("이 책에는 챕터가 없습니다."))
        return
    st.caption(t("고친 것은 바로 파일에 반영됩니다. 다 고쳤으면 이 창을 닫고 본창에서 «확정»을 누르세요. "
                 "제목은 칸에서 고치고 Enter · ＋ 는 그 장 안에 새 장 끼워 넣기 · − 는 그 장을 앞 장에 합치기"))
    notice = st.session_state.pop("_wb_notice", None)
    if notice:
        st.success(notice)

    pm = cmap.PageMap(ws, book)
    offset = _printed_offset(book) if pm.ok else None
    rows = chapter_rows(ws, book, pm, offset)
    for w in cmap.review_findings(ws, book):
        st.warning("⚠️ " + w)
    if not pm.ok:
        st.caption(t("쪽 번호를 셀 수 없는 책입니다 (보관된 원본 TXT가 없거나 챕터와 글자 수가 어긋남)."))

    sect = [r["idx"] for r in rows if r["절제목"]]
    c1, c2, c3 = st.columns([2.2, 1.2, 1.2])
    if sect and c1.button(tf("절 제목 장 %d개를 모두 앞 장에 합치기", len(sect)),
                          icon=":material/merge:", type="primary", key=f"{key}_merge_sect",
                          width="stretch",
                          help=t("「들어가는 말」·「나가는 말」처럼 논문 안의 절 제목이 장으로 잡힌 것을 한 번에 정리합니다.")):
        n = _merge_many(ws, book, sect)
        st.session_state["_wb_notice"] = tf("%d개 장을 앞 장에 합쳤습니다.", n)
        st.rerun()
    try:
        import config as cfg
        from services.common import open_pdf_view, open_path
        from services.chapters import chapters_dir
        pdf = cfg.PDF_DIR / f"{book}.pdf"
        if pdf.exists() and c2.button(t("원본 PDF 열기"), icon=":material/picture_as_pdf:",
                                      key=f"{key}_pdf", width="stretch"):
            from services import toc as toc_svc
            open_pdf_view(toc_svc.whole_pdf_copy(pdf))
        if c3.button(t("챕터 폴더 열기"), icon=":material/folder_open:", key=f"{key}_dir", width="stretch"):
            open_path(chapters_dir(ws, book))
    except Exception:
        pass

    # ── 장 목록 — 전부 펼쳐서 ──────────────────────────────────
    widths = [0.55, 1.4, 4.2, 3.0, 0.45, 0.45]
    h = st.columns(widths)
    for col, name in zip(h, ("순번", "쪽", "제목", "시작 부분", "", "")):
        col.caption(t(name) if name else "")
    open_idx = st.session_state.get(f"{key}_split_open")
    for r in rows:
        i = r["idx"]
        c = st.columns(widths, vertical_alignment="center")
        c[0].markdown(f"**{r['순번']}**")
        c[1].markdown(r["쪽"])
        wk = f"{key}_t_{r['stem']}"
        c[2].text_input(t("장 제목"), value=r["제목"], key=wk, label_visibility="collapsed",
                        on_change=_rename, args=(ws, book, i, wk))
        flags = []
        if r["절제목"]:
            flags.append("🔸 " + t("절 제목 — 앞 장에 합치는 것이 맞을 수 있습니다"))
        if r["껍데기"]:
            flags.append("⚠️ " + t("본문이 거의 없음"))
        if r["뒷부속"]:
            flags.append(t("참고문헌·찾아보기 — 번역·요약에서 뺍니다"))
        c[3].caption(f"{r['글자']:,}{t('자')} · {r['시작 부분']} …" + ("  \n" + " · ".join(flags) if flags else ""))
        if c[4].button("＋", key=f"{key}_plus_{r['stem']}", help=t("이 장 안에서 새 장이 시작하는 자리를 골라 끼워 넣습니다")):
            st.session_state[f"{key}_split_open"] = None if open_idx == i else i
            st.rerun()
        if c[5].button("−", key=f"{key}_minus_{r['stem']}", disabled=(i == 0),
                       help=t("이 장을 없애고 본문을 앞 장 뒤에 붙입니다") if i else t("첫 장은 합칠 앞 장이 없습니다")):
            if cmap.merge_up(ws, book, i):
                st.session_state["_wb_notice"] = tf("「%s」을(를) 앞 장에 합쳤습니다.", r["제목"])
                st.session_state.pop(f"{key}_split_open", None)
                st.rerun()
        if open_idx == i:
            _split_panel(ws, book, i, r, pm, offset, key)
