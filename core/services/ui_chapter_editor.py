"""Chapter drafts shared by a narrow-friendly form and the full table editor."""
import hashlib

import pandas as pd
import streamlit as st

from services.i18n import t


def chapter_editor(rows, key, full=True):
    # A source change (rename/merge/external edit) invalidates old widget state.
    revision = hashlib.sha256(repr(rows).encode()).hexdigest()[:16]
    draft_key = f"{key}_draft"
    if st.session_state.get(f"{key}_revision") != revision:
        st.session_state[draft_key] = [dict(row) for row in rows]
        st.session_state[f"{key}_revision"] = revision
        st.session_state.pop(f"{key}_last_mode", None)
    draft = st.session_state[draft_key]
    cols = ["순번", "부", "제목", "분량", "시작 부분"] + (["앞 장에 합치기"] if full else [])
    if not draft:
        return pd.DataFrame(columns=cols)
    mode = st.selectbox(t("편집 방식"), ["single", "table"], key=f"{key}_mode",
                        format_func=lambda value: t("한 장씩 편집") if value == "single" else t("표로 편집"),
                        help=t("좁은 창에서는 한 장씩 편집하세요. 방식이나 장을 바꿔도 수정 내용은 저장 전까지 유지됩니다."))
    if mode == "table" and st.session_state.get(f"{key}_last_mode") != "table":
        st.session_state[f"{key}_table_base"] = [dict(row) for row in draft]
        st.session_state[f"{key}_table_generation"] = st.session_state.get(f"{key}_table_generation", 0) + 1
    st.session_state[f"{key}_last_mode"] = mode
    if mode == "table":
        generation = st.session_state[f"{key}_table_generation"]
        edited = st.data_editor(
            pd.DataFrame(st.session_state[f"{key}_table_base"])[cols], key=f"{key}_table_{revision}_{generation}",
            width="stretch", hide_index=True, num_rows="fixed",
            column_config={
                "순번": st.column_config.TextColumn(t("순번"), disabled=True, width="small"),
                "부": st.column_config.TextColumn(t("부(部)"), width="small",
                    help=t("이 장부터 시작하는 부의 이름. 같은 부가 이어지면 비워 두세요")),
                "제목": st.column_config.TextColumn(t("제목 (고칠 수 있음)"), width="large"),
                "분량": st.column_config.TextColumn(t("분량"), disabled=True, width="small"),
                "시작 부분": st.column_config.TextColumn(t("시작 부분"), disabled=True, width="large"),
                "앞 장에 합치기": st.column_config.CheckboxColumn(t("앞 장에 합치기"),
                    help=t("이 장을 지우고 본문을 바로 앞 장 뒤에 붙입니다")),
            })
        st.session_state[draft_key] = edited.to_dict("records")
        if full and any(r.get("앞 장에 합치기") for r in st.session_state[draft_key]):
            st.warning(t("합치기로 선택한 장은 저장 시 앞 장에 붙고 기존 장 파일은 삭제됩니다."))
        return edited

    idx = st.selectbox(t("편집할 장"), list(range(len(draft))), key=f"{key}_chapter_{revision}",
                       format_func=lambda i: f"{draft[i]['순번']} · {draft[i]['제목']}")
    row = draft[idx]
    st.caption(f"{row['순번']} · {row['분량']}")

    def remember(field, widget_key):
        st.session_state[draft_key][idx][field] = st.session_state[widget_key]

    for field, label in (("제목", "장 제목"), ("부", "부(部)")):
        widget_key = f"{key}_{revision}_{idx}_{field}"
        st.text_input(t(label), value=row.get(field, ""), key=widget_key,
                      on_change=remember, args=(field, widget_key),
                      help=t("이 장부터 시작하는 부의 이름. 같은 부가 이어지면 비워 두세요") if field == "부" else None)
    st.caption(t("시작 부분"))
    st.text(row.get("시작 부분", ""))
    if full:
        widget_key = f"{key}_{revision}_{idx}_merge"
        st.checkbox(t("앞 장에 합치기"), value=bool(row.get("앞 장에 합치기", False)),
                    disabled=idx == 0, key=widget_key, on_change=remember,
                    args=("앞 장에 합치기", widget_key),
                    help=t("이 장을 지우고 본문을 바로 앞 장 뒤에 붙입니다"))
        if any(r.get("앞 장에 합치기") for r in draft):
            st.warning(t("합치기로 선택한 장은 저장 시 앞 장에 붙고 기존 장 파일은 삭제됩니다."))
    return pd.DataFrame(draft)[cols]
