"""번역 탭의 «문제 도우미» 화면 (2026-10-13). 일은 services/helper 가 하고 여기선 보여 주기만 한다."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

import config as cfg
from services import helper
from services.i18n import t, tf


def _chat_key(rel: str) -> str:
    return f"_helper_chat::{rel}"


def _apply(ch: Path, action: dict, rel: str, run_start) -> None:
    n = helper.apply_action(ch, action)
    if n:
        st.toast(tf("%d단락에 적용했습니다 — 장을 다시 완성합니다", n), icon=":material/check:")
        run_start("tr3", [rel])
    else:
        st.warning(t("적용할 단락이 없습니다 — 이미 처리됐거나 목록이 바뀌었습니다."))


def _action_label(action: dict) -> str:
    if action["type"] == "keep":
        return tf("단락 %s 원문 유지", ", ".join(str(i) for i in action["idx"]))
    return tf("단락 %d에 이 번역 넣기", action["idx"])


def render(rels: list[str], run_start) -> None:
    """rels = 부분완료·실패 상태인 챕터(BASE_DIR 기준 상대경로). run_start(stage, rels)로 다시 실행."""
    with st.expander(tf("문제 도우미 — 왜 실패했는지 보고 바로 풀기 (%d개)", len(rels)),
                     icon=":material/medical_services:"):
        labels = {r: f"{Path(r).parent.name} / {Path(r).name}" for r in rels}
        rel = st.selectbox(t("살펴볼 장"), rels, format_func=labels.get, key="helper_pick")
        if not rel:
            return
        ch = cfg.BASE_DIR / rel
        ev = helper.collect(ch)

        # ① 자동 진단
        st.markdown(t("##### 1. 원인"))
        hints = helper.diagnose(ev)
        if not hints:
            st.info(t("알려진 원인에 해당하지 않습니다. 아래 AI 상담에 물어보세요."))
        for i, h in enumerate(hints):
            st.markdown(f"- **{h['cause']}**  \n  {h['advice']}")
            if h.get("action") and st.button(t("짧은 줄 모두 원문 유지하고 완성"), key=f"helper_hint_{rel}_{i}",
                                             icon=":material/done_all:"):
                _apply(ch, h["action"], rel, run_start)

        # ② 단락별로 직접 정하기
        if ev["failed"]:
            st.markdown(tf("##### 2. 실패한 단락 (%d개) — 하나씩 정하기", len(ev["failed"])))
            for f in ev["failed"][:30]:
                with st.container(border=True):
                    st.caption(tf("단락 %d · %s · %d자", f["idx"], f.get("kind") or "text", len(f["src"])))
                    st.text(f["src"][:600])
                    c1, c2 = st.columns([3, 1])
                    typed = c1.text_input(t("번역 직접 넣기"), key=f"helper_manual_{rel}_{f['idx']}",
                                          label_visibility="collapsed", placeholder=t("번역 직접 넣기"))
                    if typed.strip() and c2.button(t("넣기"), key=f"helper_put_{rel}_{f['idx']}"):
                        _apply(ch, {"type": "manual", "idx": f["idx"], "text": typed}, rel, run_start)
                    if not typed.strip() and c2.button(t("원문 유지"), key=f"helper_keep_{rel}_{f['idx']}"):
                        _apply(ch, {"type": "keep", "idx": [f["idx"]]}, rel, run_start)

        # ③ AI 상담
        st.markdown(t("##### 3. AI 상담"))
        st.caption(t("설정한 AI 에게 이 장의 상태와 실패한 단락을 보여 주고 묻습니다. "
                     "AI 는 설명과 제안만 하고, 적용은 [적용]을 눌러야 됩니다. 파일을 직접 고치지는 못합니다."))
        chat = st.session_state.setdefault(_chat_key(rel), [])
        for n, msg in enumerate(chat):
            with st.chat_message("user" if msg["role"] == "user" else "assistant"):
                st.markdown(msg["text"])
                for k, a in enumerate(msg.get("actions") or []):
                    if st.button(t("적용: ") + _action_label(a), key=f"helper_ai_{rel}_{n}_{k}"):
                        _apply(ch, a, rel, run_start)
        q = st.text_area(t("물어볼 말"), key=f"helper_q_{rel}", height=80,
                         placeholder=t("예: 왜 이 단락들은 계속 실패하나요? 어떻게 하면 되나요?"))
        if st.button(t("AI 에게 묻기"), key=f"helper_ask_{rel}", icon=":material/forum:",
                     disabled=not q.strip()):
            with st.spinner(t("AI 가 살펴보는 중…")):
                try:
                    res = helper.ask(ev, chat, q.strip())
                except Exception as exc:  # 연결 문제는 화면에 그대로 알린다
                    st.error(tf("AI 에게 묻지 못했습니다: %s", str(exc)[:200]))
                    res = None
            if res:
                chat.append({"role": "user", "text": q.strip()})
                chat.append({"role": "assistant", "text": res["answer"], "actions": res["actions"],
                             "program_bug": res["program_bug"], "bug_summary": res["bug_summary"]})
                st.session_state.pop(f"helper_q_{rel}", None)
                st.rerun()

        # ④ 개발자에게 알리기
        last_ai = next((m for m in reversed(chat) if m["role"] == "assistant"), None)
        st.markdown(t("##### 4. 개발자에게 알리기"))
        if last_ai and last_ai.get("program_bug"):
            st.warning(t("AI 판단: 프로그램 결함으로 보입니다. 보고해 주시면 다음 판에서 고칩니다."),
                       icon=":material/bug_report:")
        note = st.text_area(t("무슨 일이 있었나요 (선택)"), key=f"helper_note_{rel}", height=70)
        with_text = st.checkbox(t("책 원문 조각 포함 (단락마다 80자까지)"), value=False,
                                key=f"helper_text_{rel}",
                                help=t("기본은 빼 둡니다 — 책 내용은 저작권이 있고, 보고서는 공개 게시판에 올라갑니다. "
                                       "원인을 찾는 데 꼭 필요할 때만 켜세요."))
        body = helper.report(ev, note, with_text, last_ai)
        st.caption(t("보내기 전에 아래 내용을 확인하세요. 컴퓨터 사용자 이름·메일·전화번호는 가렸습니다."))
        st.code(body, language="markdown")
        b1, b2, b3 = st.columns(3)
        b1.link_button(t("GitHub 이슈로 보내기"), helper.issue_url(helper.issue_title(ev), body),
                       icon=":material/open_in_new:", width="stretch",
                       help=t("브라우저에서 GitHub 새 이슈 화면이 열립니다(GitHub 계정 필요). [Submit]을 눌러야 보내집니다."))
        b2.link_button(t("메일로 보내기"), helper.mailto_url(helper.issue_title(ev), body),
                       icon=":material/mail:", width="stretch",
                       help=tf("메일 프로그램에서 %s 앞으로 새 메일이 열립니다. [보내기]를 눌러야 보내집니다. "
                               "보고서가 길면 앞부분만 들어가니, 저장한 보고서 파일을 붙여 주세요.",
                               helper.FEEDBACK_EMAIL))
        b3.download_button(t("보고서 파일로 저장"), body.encode("utf-8"),
                           file_name=f"mybookshelf_report_{Path(rel).stem[:40]}.md",
                           mime="text/markdown", icon=":material/download:", width="stretch",
                           help=t("메일에 붙이거나 메신저로 보낼 보고서 파일입니다. "
                                  "위 상자 오른쪽 위 복사 단추로 내용만 복사해도 됩니다."))
