"""문제 도우미 — 번역이 «부분완료·실패»로 멈춘 장을 사용자가 스스로 풀게 돕는다 (2026-10-13).

세 가지 일을 한다.
  1. 증거 모으기: 상태 기록·실패한 단락·로그·앱 버전을 한 꾸러미로.
  2. 풀기: 미리 정해 둔 행동만 한다 — 단락을 «원문 유지»로 두기, 번역을 직접 넣기.
     AI 상담은 설명과 제안만 하고, 실제 적용은 사용자가 [적용]을 눌러야 한다.
     AI 에게는 파일·명령 권한을 주지 않는다(CLI 도 도구 없이 부른다).
  3. 개발자에게 알리기: 프로그램 결함이면 보고서를 만든다. 책 본문은 기본으로 빼고,
     컴퓨터 사용자 이름·메일 주소 같은 것은 가린다. 보내는 일은 사용자가 직접 한다
     (GitHub 이슈 링크·파일 저장·복사).

앱 코드를 그 자리에서 고치지는 않는다 — 설치본은 업데이트 때 덮어써지고,
다른 컴퓨터에는 전해지지 않기 때문이다. 코드 결함은 보고를 거쳐 고친다.
"""
from __future__ import annotations

import json
import os
import platform
import re
import urllib.parse
from pathlib import Path

import config as cfg
import llm_providers as llm
from services import translate as tr
from services.i18n import t, tf
from version import APP_VERSION

REPO_URL = "https://github.com/Brightinyou/my-bookshelf"
# GitHub 계정이 없는 사용자를 위한 보고 메일 (2026-10-13 개발자 결정 — 커밋 기록에 이미 공개된 주소).
FEEDBACK_EMAIL = "neofront@naver.com"
# 메일 프로그램은 긴 mailto 주소를 자르거나 아예 열지 못한다 — 본문을 이만큼으로 줄이고
# 나머지는 저장한 보고서 파일을 붙이라고 안내한다.
_MAILTO_LIMIT = 1800
# GitHub 이슈 주소는 너무 길면 열리지 않는다(약 8천 자). 넘치면 본문을 줄이고
# 전체 보고서는 파일로 붙이라고 안내한다.
_ISSUE_URL_LIMIT = 7000
SHORT_PARAGRAPH = 40          # 이보다 짧은 실패 단락은 «원문 유지»를 먼저 권한다
_SNIPPET = 80                 # 보고서에 원문을 넣을 때 단락마다 이만큼만


# ─── 1. 증거 ────────────────────────────────────────────────────────────────
def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def failed_paragraphs(ch_path: Path) -> list[dict]:
    """지난 실행에서 실패한 단락 — 이미 사용자가 정한 단락은 뺀다."""
    suf = tr.out_suffix()
    rows = _read_json(ch_path.with_name(ch_path.stem + suf + ".progress.json"))
    if not isinstance(rows, list):
        audit = _read_json(ch_path.with_name(ch_path.stem + suf + ".audit.json")) or {}
        rows = audit.get("results") if isinstance(audit, dict) else None
    if not isinstance(rows, list):
        return []
    decided = tr.load_overrides(ch_path)
    out = []
    for row in rows:
        if not isinstance(row, dict) or row.get("status") != "failed":
            continue
        src = row.get("src") or ""
        if tr.override_key(src) in decided:
            continue
        out.append({"idx": row.get("idx"), "kind": row.get("kind", ""), "src": src})
    return out


def _log_lines(name: str, limit: int = 15) -> list[str]:
    try:
        lines = cfg.LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [ln for ln in lines if name in ln][-limit:]


def collect(ch_path: Path) -> dict:
    """한 장의 문제 꾸러미."""
    status = tr.translation_status(ch_path)
    return {
        "book": ch_path.parent.name,
        "chapter": ch_path.name,
        "state": status.get("state", ""),
        "engine": status.get("engine", ""),
        "total": status.get("total"),
        "translated": status.get("translated"),
        "error": status.get("error", ""),
        "blocked": bool(status.get("blocked")),
        "stopped": bool(status.get("stopped")),
        "target": status.get("target") or tr.target_language(),
        "failed": failed_paragraphs(ch_path),
        "log": _log_lines(ch_path.name),
        "app_version": APP_VERSION,
        "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
    }


# ─── 2. 자동 진단 (AI 없이, 알려진 경우) ─────────────────────────────────────
def diagnose(ev: dict) -> list[dict]:
    """알려진 원인 목록. 각 항목: {"cause", "advice", "action"(있으면), "bug"(프로그램 탓인가)}."""
    hints: list[dict] = []
    err = (ev.get("error") or "").lower()
    if ev.get("blocked") or any(w in err for w in ("auth", "login", "credit", "quota", "usage", "404", "model")):
        hints.append({"cause": t("AI 연결 문제 — 로그인·사용량·모델 설정 때문에 AI 가 답하지 못했습니다."),
                      "advice": t("설정 탭에서 AI 연결과 모델을 확인한 뒤 다시 시도하세요. 단락 탓이 아닙니다."),
                      "bug": False})
    if ev.get("stopped"):
        hints.append({"cause": t("도중에 멈춘 장입니다."),
                      "advice": t("다시 시작하면 번역한 단락은 그대로 쓰고 남은 곳부터 이어 합니다."),
                      "bug": False})
    failed = ev.get("failed") or []
    short = [f for f in failed if len((f.get("src") or "").strip()) <= SHORT_PARAGRAPH]
    if short:
        hints.append({"cause": tf("짧은 줄 %d개(소제목·숫자·이름 등)가 번역 검사에 걸렸습니다. "
                                 "다시 해도 같은 결과가 나오기 쉽습니다.", len(short)),
                      "advice": t("이런 줄은 원문 그대로 두어도 읽는 데 지장이 없습니다. "
                                  "[짧은 줄 모두 원문 유지]를 누르면 나머지는 그대로 두고 장을 완성합니다."),
                      "action": {"type": "keep", "idx": [f["idx"] for f in short]},
                      "bug": True})
    long_ = [f for f in failed if f not in short]
    if long_ and not ev.get("blocked"):
        hints.append({"cause": tf("본문 단락 %d개가 번역되지 않았습니다.", len(long_)),
                      "advice": t("한 번 더 시도해 보고, 같은 단락이 또 실패하면 AI 상담에 물어보거나 "
                                  "번역을 직접 넣으세요."),
                      "bug": False})
    return hints


# ─── 3. 행동 (정해 둔 것만) ──────────────────────────────────────────────────
def _by_idx(ch_path: Path) -> dict[int, str]:
    return {f["idx"]: f["src"] for f in failed_paragraphs(ch_path)}


def apply_action(ch_path: Path, action: dict) -> int:
    """{"type": "keep", "idx": [..]} 또는 {"type": "manual", "idx": n, "text": "..."}.
    지금 실패 목록에 있는 단락만 건드린다(AI 가 엉뚱한 번호를 내도 막힌다). 바꾼 수."""
    srcs = _by_idx(ch_path)
    kind = action.get("type")
    if kind == "keep":
        idxs = action.get("idx")
        idxs = idxs if isinstance(idxs, list) else [idxs]
        n = 0
        for i in idxs:
            if i in srcs:
                tr.set_override(ch_path, srcs[i], "keep")
                n += 1
        return n
    if kind == "manual":
        i, text = action.get("idx"), (action.get("text") or "").strip()
        if i in srcs and text:
            tr.set_override(ch_path, srcs[i], "manual", text)
            return 1
        return 0
    return 0


# ─── 4. AI 상담 ─────────────────────────────────────────────────────────────
_ASK_SYSTEM = """You are the built-in troubleshooting helper of "My Bookshelf", a desktop app that
translates book chapters paragraph by paragraph with an AI. A chapter is stuck as "partial":
some paragraphs failed the app's automatic check and were left in the source language.

How the app's check works (so you can explain causes):
- A translation is rejected if it is empty, looks like a refusal, contains almost no
  target-language script, or is more than 82% similar to the source text.
- Very short lines (headings with only a name, number/symbol fragments from tables) often
  fail repeatedly for these reasons; retrying usually gives the same result.
- Login, usage-limit or model-setting problems make every paragraph fail.

You can only PROPOSE these actions; the user must press Apply:
- {"type": "keep", "idx": [paragraph numbers]}  -> leave those paragraphs in the source language
- {"type": "manual", "idx": n, "text": "translation"}  -> use your translation for paragraph n
Only use paragraph numbers from the failed list. You cannot edit files or run commands.

Answer in the user's language (the language of their question; Korean if unsure), plainly,
for a non-programmer. Say whether this looks like a program defect the developer should fix.
Output ONLY one JSON object:
{"answer": "...", "actions": [...], "program_bug": true|false, "bug_summary": "one line for the developer or empty"}"""


def _evidence_text(ev: dict) -> str:
    lines = [f"Book: {ev['book']}", f"Chapter: {ev['chapter']}", f"State: {ev['state']}",
             f"Engine: {ev['engine']}", f"Target language: {ev['target']}",
             f"Translated: {ev.get('translated')}/{ev.get('total')}"]
    if ev.get("error"):
        lines.append(f"Last error: {ev['error'][:400]}")
    lines.append("Failed paragraphs:")
    for f in (ev.get("failed") or [])[:30]:
        lines.append(f"  [{f['idx']}] ({f.get('kind') or 'text'}) {f['src'][:600]}")
    if ev.get("log"):
        lines.append("Recent log lines:")
        lines += ["  " + ln[:300] for ln in ev["log"][-8:]]
    return "\n".join(lines)


def ask(ev: dict, history: list[dict], question: str) -> dict:
    """AI 에게 묻는다. history = [{"role": "user"|"assistant", "text": ...}]."""
    provider, model = llm.task_provider_model("translate")
    convo = "\n".join(f"{'User' if h['role'] == 'user' else 'Helper'}: {h['text']}" for h in history[-8:])
    prompt = (_evidence_text(ev) + ("\n\nConversation so far:\n" + convo if convo else "")
              + f"\n\nUser: {question}")
    data = llm.complete_json(provider, model, _ASK_SYSTEM, prompt, max_tokens=4096, retries=1)
    if not isinstance(data, dict):
        data = {}
    valid = {f["idx"] for f in ev.get("failed") or []}
    actions = []
    for a in data.get("actions") or []:
        if not isinstance(a, dict):
            continue
        if a.get("type") == "keep":
            idx = [i for i in (a.get("idx") if isinstance(a.get("idx"), list) else [a.get("idx")]) if i in valid]
            if idx:
                actions.append({"type": "keep", "idx": idx})
        elif a.get("type") == "manual" and a.get("idx") in valid and str(a.get("text") or "").strip():
            actions.append({"type": "manual", "idx": a["idx"], "text": str(a["text"]).strip()})
    return {"answer": str(data.get("answer") or "").strip() or t("답을 받지 못했습니다."),
            "actions": actions, "program_bug": bool(data.get("program_bug")),
            "bug_summary": str(data.get("bug_summary") or "").strip()}


# ─── 5. 개발자에게 알리기 ─────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\b0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}\b")


def redact(text: str) -> str:
    """보고서에서 개인 정보를 가린다 — 사용자 폴더 이름·메일·전화번호."""
    text = text or ""
    home = str(Path.home())
    for h in {home, home.replace("\\", "/")}:
        text = text.replace(h, "~")
    user = os.environ.get("USER") or os.environ.get("USERNAME") or ""
    if len(user) >= 3:
        text = re.sub(rf"(?<![\w]){re.escape(user)}(?![\w])", "[user]", text)
    text = _EMAIL_RE.sub("[email]", text)
    return _PHONE_RE.sub("[phone]", text)


def report(ev: dict, note: str = "", include_text: bool = False, ai: dict | None = None) -> str:
    """개발자용 보고서(Markdown). include_text=False 면 책 본문은 길이·종류만 남긴다."""
    lines = ["## 무슨 일이 있었나요", (note.strip() or "(사용자 설명 없음)"), "",
             "## 환경", f"- 앱: {ev['app_version']}", f"- 운영체제: {ev['os']}",
             f"- AI 엔진: {ev['engine']}", f"- 도착언어: {ev['target']}", "",
             "## 상태", f"- 상태: {ev['state']} · 번역 {ev.get('translated')}/{ev.get('total')}"
             + f" · 실패 {len(ev.get('failed') or [])}단락"]
    if ev.get("error"):
        lines.append(f"- 마지막 오류: `{ev['error'][:400]}`")
    lines += ["", "## 실패한 단락"]
    for f in (ev.get("failed") or [])[:30]:
        src = f.get("src") or ""
        shown = (f"`{src[:_SNIPPET]}`" + ("…" if len(src) > _SNIPPET else "")) if include_text \
            else "(본문 생략)"
        lines.append(f"- [{f['idx']}] {f.get('kind') or 'text'} · {len(src)}자 · {shown}")
    hints = diagnose(ev)
    if hints:
        lines += ["", "## 앱의 자동 진단"] + [f"- {h['cause']}" for h in hints]
    if ai and ai.get("bug_summary"):
        lines += ["", "## AI 상담 요약", f"- {ai['bug_summary']}"]
    if ev.get("log"):
        lines += ["", "## 로그", "```"] + [ln[:300] for ln in ev["log"][-10:]] + ["```"]
    if include_text:
        lines += ["", f"(책: {ev['book']} / 장: {ev['chapter']})"]
    return redact("\n".join(lines))


def issue_title(ev: dict) -> str:
    return redact(f"[문제 도우미] 번역 {ev['state']} — 실패 {len(ev.get('failed') or [])}단락 ({ev['app_version']})")


def issue_url(title: str, body: str) -> str:
    """GitHub 새 이슈 주소 — 제목·본문을 미리 채운다. 너무 길면 본문을 줄인다."""
    base = f"{REPO_URL}/issues/new?"
    tail = "\n\n…(길어서 줄였습니다 — 전체 보고서는 파일로 저장해 붙여 주세요)"
    while True:
        url = base + urllib.parse.urlencode({"title": title, "body": body})
        if len(url) <= _ISSUE_URL_LIMIT or len(body) < 200:
            return url
        body = body[: int(len(body) * 0.8)].rstrip() + tail
        tail = ""


def mailto_url(title: str, body: str) -> str:
    """개발자 메일 주소로 제목·본문을 채운 mailto 링크. 길면 본문을 줄인다."""
    def build(b: str) -> str:
        return f"mailto:{FEEDBACK_EMAIL}?" + urllib.parse.urlencode(
            {"subject": title, "body": b}, quote_via=urllib.parse.quote)
    url = build(body)
    if len(url) <= _MAILTO_LIMIT:
        return url
    tail = "\n\n…(길어서 줄였습니다 — 앱에서 저장한 보고서 파일을 이 메일에 붙여 주세요)"
    lo, hi = 0, len(body)
    while lo < hi:                      # 들어가는 가장 긴 앞부분을 찾는다
        mid = (lo + hi + 1) // 2
        if len(build(body[:mid].rstrip() + tail)) <= _MAILTO_LIMIT:
            lo = mid
        else:
            hi = mid - 1
    return build(body[:lo].rstrip() + tail)
