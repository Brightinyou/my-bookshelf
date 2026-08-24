"""chapter_chat.py — 장 구분을 말로 고치기 (2026-08-25)

『기술신학』을 겪고 나서 연구자가 정리한 진단: **텍스트 변환 다음으로 문제가 가장
많이 생기는 곳이 장별 분할**이다. 그런데 지금 화면은 무엇이 잘못됐는지 사람이
표에서 찾아내야 한다. "마지막 챕터가 분할이 안 된 것 같아"라고 말하면 되게 한다.

## ★설계 원칙 — 모델은 알아듣기만 하고, 판단과 실행은 앱이 한다

    사람의 말 ──(LLM)──▶ 의도 + 값 ──(앱)──▶ 사실 확인 ──▶ 제안 ──(사람)──▶ 실행

세 가지를 지킨다.

1. **모델이 실행하지 않는다.** 의도는 정해진 목록에서만 고르고, 값은 숫자와 짧은
   문자열뿐이다. 임의의 코드도 경로도 오가지 않는다.
2. **모델의 주장을 믿지 않는다.** "마지막 장이 안 나뉜 것 같다"가 맞는지는 모델이
   알 수 없다 — 그러나 **앱은 안다**(장 분량·후보 줄·커버리지). 그래서 말은 접수만
   하고 **사실 확인은 기존 진단 코드가** 한다.
3. **언제나 사람이 마지막에 누른다.** 자동 실행은 2026-08-25에 앱 전체에서 걷어냈다
   (`_render_stage_completion_notice` 주석 참고). 여기서 되살리지 않는다.

## LLM이 없어도 돌아간다

공급자가 없거나 호출이 실패하면 규칙 기반 해석으로 내려간다. 한국어로 장 번호와
동사만 잡으면 대부분의 요청은 처리된다 — 이 기능이 구독 유무에 매이면 안 된다.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import llm_providers as llm
from services import chapter_map as cmap

# 모델이 고를 수 있는 의도는 이것뿐이다. 늘릴 때는 반드시 plan()에 확인 절차를 같이 만든다.
INTENTS = ("split", "merge", "rename", "status", "resplit", "unknown")

SYSTEM = (
    "너는 한국어 책의 '장 구분 고치기' 요청을 분류한다. "
    "설명하지 말고 JSON 객체 하나만 출력한다."
)

PROMPT = """사용자의 말을 아래 의도 중 하나로 분류하라.

- split   : 한 장이 둘 이상으로 나뉘어야 한다 (예: "마지막 장이 안 나뉜 것 같아", "3장 중간에 새 장이 있어")
- merge   : 한 장을 바로 앞 장에 붙여야 한다 (예: "5장은 4장에 붙어야 해")
- rename  : 장 제목을 바꾼다 (예: "2장 제목을 서론으로")
- status  : 지금 어떻게 나뉘었는지 알려 달라
- resplit : 처음부터 다시 나눈다
- unknown : 위 어디에도 해당하지 않는다

값:
- chapter : 대상 장의 순번(1부터). 모르면 null. "마지막"이면 {last}, "첫"이면 1.
- query   : split일 때, 새 장이 시작될 줄에 들어 있을 법한 말. 사용자가 따옴표로
            준 말이 있으면 그것. 없으면 null.
- title   : rename일 때 새 제목. 없으면 null.

이 책의 장 목록:
{chapters}

사용자의 말: {message}

JSON: {{"intent": "...", "chapter": 3, "query": null, "title": null}}"""


@dataclass
class Intent:
    intent: str = "unknown"
    chapter: int | None = None      # 1-기반 순번
    query: str = ""
    title: str = ""
    source: str = "rule"            # "llm" | "rule" — 어떻게 알아들었는지 밝힌다


@dataclass
class Proposal:
    """앱이 **사실을 확인한 뒤** 내놓는 제안. 사람이 누르기 전까지 아무 일도 없다."""
    action: str = "none"            # split | merge | rename | resplit | none
    message: str = ""               # 확인 문장 — 이대로 화면에 뜬다
    evidence: list[str] = field(default_factory=list)   # 앱이 실제로 확인한 근거
    params: dict = field(default_factory=dict)
    ok: bool = False                # 실행할 수 있는가


# ── ① 알아듣기 ──────────────────────────────────────────────

_LAST = re.compile(r"마지막|끝|맨\s*뒤|last")
_FIRST = re.compile(r"첫|처음|맨\s*앞|first")
_NUM = re.compile(r"(\d+)\s*장")
_SPLIT = re.compile(r"나[누눠]|분할|쪼개|갈라|안\s*나뉘|따로|새\s*장")
_MERGE = re.compile(r"합치|붙[여이]|한\s*장으로|이어\s*붙")
_RENAME = re.compile(r"제목|이름.*바꾸|바꿔")
_RESPLIT = re.compile(r"다시\s*(나|분할)|처음부터")
_STATUS = re.compile(r"어떻게|상태|알려|보여|몇\s*장")
_QUOTED = re.compile(r"[\"'“”‘’「『]([^\"'“”‘’」』]{2,40})[\"'“”‘’」』]")


def interpret_rule(message: str, n_chapters: int) -> Intent:
    """규칙만으로 알아듣기 — LLM이 없을 때의 바닥. 못 알아들으면 unknown을 낸다.

    ★**어림짐작으로 의도를 지어내지 않는다.** 틀린 의도로 장을 자르면 되돌리기
    어렵다(파생물이 함께 지워진다). 모르면 모른다고 하고 사람에게 되묻는 편이 낫다."""
    msg = message.strip()
    it = Intent()
    m = _NUM.search(msg)
    if m:
        it.chapter = int(m.group(1))
    elif _LAST.search(msg):
        it.chapter = n_chapters
    elif _FIRST.search(msg):
        it.chapter = 1
    q = _QUOTED.search(msg)
    if q:
        it.query = q.group(1).strip()
    if _RESPLIT.search(msg):
        it.intent = "resplit"
    elif _RENAME.search(msg):
        it.intent = "rename"
        if q:
            it.title, it.query = it.query, ""
    elif _MERGE.search(msg):
        it.intent = "merge"
    elif _SPLIT.search(msg):
        it.intent = "split"
    elif _STATUS.search(msg):
        it.intent = "status"
    return it


def interpret(message: str, titles: list[str],
              provider: str = "", model: str = "") -> Intent:
    """말을 의도로 바꾼다. LLM이 되면 LLM으로, 안 되면 규칙으로."""
    n = len(titles)
    rule = interpret_rule(message, n)
    if not provider:
        return rule
    try:
        listing = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles))
        raw = llm.complete_json(
            provider, model, SYSTEM,
            PROMPT.format(last=n or 1, chapters=listing or "(없음)", message=message),
            max_tokens=300, retries=1)
        got = str(raw.get("intent", "")).strip()
        if got not in INTENTS:
            return rule
        ch = raw.get("chapter")
        it = Intent(intent=got,
                    chapter=int(ch) if isinstance(ch, (int, float)) and 1 <= int(ch) <= max(n, 1) else None,
                    query=str(raw.get("query") or "").strip(),
                    title=str(raw.get("title") or "").strip(),
                    source="llm")
        # 모델이 장을 못 짚었으면 규칙이 짚은 것을 쓴다 — 둘 다 보는 편이 낫다
        if it.chapter is None:
            it.chapter = rule.chapter
        if not it.query:
            it.query = rule.query
        return it
    except Exception:
        return rule


# ── ② 사실 확인하고 제안 만들기 ─────────────────────────────

def _sizes(ws: str, stem: str) -> list[int]:
    return [len(f.read_text(encoding="utf-8", errors="ignore"))
            for f in cmap.chapter_files(ws, stem)]


def plan(ws: str, stem: str, it: Intent) -> Proposal:
    """의도를 **앱이 확인한 제안**으로 바꾼다. 확인에 실패하면 ok=False로 돌려준다."""
    files = cmap.chapter_files(ws, stem)
    titles = [cmap.chapter_title(f) for f in files]
    n = len(files)
    if n == 0:
        return Proposal(message="아직 나뉜 장이 없습니다.")

    if it.intent == "status":
        sizes = _sizes(ws, stem)
        lines = [f"{i + 1}. {titles[i]} — {sizes[i]:,}자" for i in range(n)]
        return Proposal(action="none", ok=False,
                        message=f"지금 {n}개 장으로 나뉘어 있습니다.",
                        evidence=lines + cmap.review_findings(ws, stem))

    if it.intent == "resplit":
        return Proposal(action="resplit", ok=True,
                        message=f"「{stem}」을(를) 처음부터 다시 나눕니다.",
                        evidence=["★지금의 장·번역·요약이 모두 지워지고 새로 만들어집니다."],
                        params={})

    if it.chapter is None:
        return Proposal(message="어느 장인지 알려 주세요 (예: “3장”, “마지막 장”).")
    idx = it.chapter - 1
    if not (0 <= idx < n):
        return Proposal(message=f"{it.chapter}장은 없습니다 — 지금 {n}개 장이 있습니다.")

    if it.intent == "rename":
        if not it.title:
            return Proposal(message="새 제목을 알려 주세요 (예: “2장 제목을 ‘서론’으로”).")
        return Proposal(action="rename", ok=True,
                        message=f"{it.chapter}장 제목을 「{titles[idx]}」에서 「{it.title}」(으)로 바꿉니다.",
                        params={"idx": idx, "title": it.title})

    if it.intent == "merge":
        if idx == 0:
            return Proposal(message="첫 장은 앞에 붙일 장이 없습니다.")
        return Proposal(action="merge", ok=True,
                        message=f"{it.chapter}장 「{titles[idx]}」을(를) "
                                f"{it.chapter - 1}장 「{titles[idx - 1]}」 뒤에 붙입니다.",
                        evidence=[f"{it.chapter}장 본문 {_sizes(ws, stem)[idx]:,}자가 앞 장으로 옮겨집니다."],
                        params={"idx": idx})

    if it.intent == "split":
        return _plan_split(ws, stem, idx, it, titles)

    return Proposal(message="무슨 말씀인지 알아듣지 못했습니다. "
                            "“마지막 장이 안 나뉜 것 같아”, “5장을 4장에 붙여줘”처럼 말씀해 주세요.")


# 이 배수를 넘게 크면 '덜 나뉜 장'으로 본다. 중앙값 대비.
BIG_CHAPTER_RATIO = 1.8


def _plan_split(ws: str, stem: str, idx: int, it: Intent, titles: list[str]) -> Proposal:
    """★사용자의 주장을 그대로 믿지 않고 **앱이 근거를 모아** 자를 자리를 제안한다."""
    sizes = _sizes(ws, stem)
    body = sorted(s for s in sizes if s > 0)
    med = body[len(body) // 2] if body else 0
    ev: list[str] = [f"{idx + 1}장 「{titles[idx]}」은(는) {sizes[idx]:,}자입니다."]
    if med:
        ratio = sizes[idx] / med
        ev.append(f"장 분량 중앙값은 {med:,}자로, 이 장은 **{ratio:.1f}배**입니다."
                  + ("  ← 덜 나뉜 장일 가능성이 큽니다" if ratio >= BIG_CHAPTER_RATIO else ""))

    cands, total = cmap.split_candidates(ws, stem, idx, limit=40, query=it.query)
    if not cands:
        if it.query:
            return Proposal(ok=False, evidence=ev,
                            message=f"{idx + 1}장 안에서 「{it.query}」가 들어간 줄을 찾지 못했습니다. "
                                    "다른 말로 알려 주시겠어요?")
        return Proposal(ok=False, evidence=ev,
                        message=f"{idx + 1}장 안에서 새 장이 시작될 만한 줄을 찾지 못했습니다.")
    ev.append(f"새 장이 시작될 만한 줄 후보가 {total:,}개 있습니다"
              + (f" (「{it.query}」로 찾음)." if it.query else "."))
    at, line = cands[0]
    return Proposal(
        action="split", ok=True,
        message=f"{idx + 1}장을 「{line}」 앞에서 둘로 나눕니다.",
        evidence=ev,
        params={"idx": idx, "at": at, "title": line[:50], "candidates": cands})


# ── ③ 실행 (사람이 누른 뒤에만) ─────────────────────────────

def apply(ws: str, stem: str, p: Proposal) -> tuple[bool, str]:
    """제안을 실제로 반영한다. **화면에서 사람이 누른 뒤에만 불린다.**"""
    if not p.ok:
        return False, "실행할 수 있는 제안이 아닙니다."
    try:
        if p.action == "rename":
            ok = cmap.rename_chapter(ws, stem, p.params["idx"], p.params["title"])
            return ok, "제목을 바꿨습니다." if ok else "제목을 바꾸지 못했습니다."
        if p.action == "merge":
            ok = cmap.merge_up(ws, stem, p.params["idx"])
            return ok, "앞 장에 붙였습니다." if ok else "합치지 못했습니다."
        if p.action == "split":
            ok = cmap.split_chapter(ws, stem, p.params["idx"], p.params["at"],
                                    p.params.get("title", ""))
            return ok, "장을 나눴습니다." if ok else "나누지 못했습니다."
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    return False, "이 제안은 화면에서 처리합니다."
