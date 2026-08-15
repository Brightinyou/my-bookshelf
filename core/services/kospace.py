# -*- coding: utf-8 -*-
"""한글 OCR 줄바꿈 복원 — 본문을 되받지 않고 '판정표'만 받는 방식 (2026-08-14).

PDF에서 뽑은 한글 본문은 인쇄된 줄이 끝나는 자리마다 어절이 쪼개진다. 그 자리가
단어 중간이었는지(붙여야 함) 어절 경계였는지(공백을 넣어야 함)는 좌표로도 알 수
없다 — 실측(『외로워지는 사람들』 2개 장, 줄바꿈 690곳)에서 붙임 357 : 공백 333
으로 거의 반반이라 규칙으로는 가를 수 없었다.

그래서 AI는 쓰되 본문 전체를 다시 쓰게 하지는 않는다. 줄바꿈마다 J(붙임)/S(공백)
만 답하게 하고 공백을 실제로 넣는 일은 이 모듈이 한다:
  - 한 장당 출력이 3만 토큰대에서 3천 토큰대로 줄어 호출이 훨씬 빠르다
    (한글은 토큰 밀도가 높아 LLM 지연을 출력 생성이 지배한다).
  - 본문 글자가 애초에 AI를 거치지 않으므로 내용 변조가 구조적으로 불가능하다.
    예전 방식의 사후 검증(_clean_is_valid)이 하던 일을 설계로 대신한다.

문단 경계는 AI에게 묻지 않는다. 조판된 책에서 오른쪽 여백까지 꽉 찬 줄은 정의상
문단의 마지막 줄일 수 없으므로, 줄 길이가 그 장의 중앙값에 못 미치면 문단 끝으로
본다(실측: 한 장 701줄 중 꽉 찬 줄 636 · 짧은 줄 65). 덤으로 EPUB의 <p>가 인쇄된
줄이 아니라 진짜 문단 단위가 된다.
"""
import re

_WORDISH = re.compile(r"[0-9A-Za-z가-힣]")

_SHORT_LINE_RATIO = 0.9   # 중앙 길이의 90%에 못 미치는 줄 = 문단의 마지막 줄
_CONTEXT = 14             # 판정용으로 보여줄 줄바꿈 앞뒤 글자 수

# 한 번의 AI 호출로 판정할 줄바꿈 수. 판정 하나가 입력 ~35자 · 출력 ~5토큰이라
# 크게 잡아도 부담이 없다 — codex CLI처럼 호출당 고정 오버헤드가 큰 엔진에서는
# 묶음을 키우는 쪽이 훨씬 빠르다.
BREAKS_PER_CALL = 200

JOIN, SPACE, PARA = "J", "S", "P"


def split_lines(text: str) -> list[str]:
    """인쇄된 물리적 줄 목록 — 빈 줄은 버린다(문단 경계는 줄 길이로 따로 판단)."""
    return [ln.strip() for ln in (text or "").split("\n") if ln.strip()]


def plan(text: str) -> tuple[list[str], list]:
    """(lines, kinds) 반환. kinds[i]는 lines[i]와 lines[i+1] 사이 줄바꿈의 처리 방식:
    PARA=문단 경계, SPACE=공백으로 이음(물어볼 필요 없음), None=AI 판정 필요."""
    lines = split_lines(text)
    if len(lines) < 2:
        return lines, []
    widths = sorted(len(ln) for ln in lines)
    median = widths[len(widths) // 2] or 1
    kinds: list = []
    for i in range(len(lines) - 1):
        cur, nxt = lines[i], lines[i + 1]
        if len(cur) < median * _SHORT_LINE_RATIO:
            kinds.append(PARA)          # 여백을 남기고 끝난 줄 = 문단 끝
        elif _WORDISH.search(cur[-1]) and _WORDISH.search(nxt[0]):
            kinds.append(None)          # 글자와 글자 사이에서 잘림 → 물어봐야 한다
        else:
            kinds.append(SPACE)         # 문장부호·기호가 끼면 공백이 안전
    return lines, kinds


def pending_indexes(kinds: list) -> list[int]:
    return [i for i, k in enumerate(kinds) if k is None]


def build_system() -> str:
    return (
        "You are a Korean typesetting assistant. The text comes from a scanned book. "
        "Each numbered item below is a place where a printed line ended and the text was "
        "split; whether a space belonged there is no longer recorded.\n\n"
        "Each item shows the text just before the break, then ⏎, then the text just after. "
        "Decide whether the two sides are one word that the line break split apart, or two "
        "separate words.\n\n"
        "Answer one item per line, exactly in the form 'N:J' or 'N:S':\n"
        "  J = join them directly with no space (the break fell inside a word)\n"
        "  S = put a single space between them (the break fell at a word boundary)\n\n"
        "Answer EVERY item, in order. Output nothing else — no explanation, no other text."
    )


def format_questions(lines: list[str], idxs: list[int]) -> str:
    """묶음 하나를 '번호. 앞맥락 ⏎ 뒷맥락' 목록으로."""
    return "\n".join(
        f"{n}. {lines[i][-_CONTEXT:]} ⏎ {lines[i + 1][:_CONTEXT]}"
        for n, i in enumerate(idxs, 1)
    )


_ANSWER_RE = re.compile(r"(\d+)\s*[:.\)]?\s*([JS])\b", re.I)


def parse_answers(out: str, count: int) -> dict[int, str]:
    """'12:J' 꼴 응답에서 {문항번호: 'J'|'S'}. 못 읽은 문항은 그냥 빠진다."""
    got: dict[int, str] = {}
    for m in _ANSWER_RE.finditer(out or ""):
        n = int(m.group(1))
        if 1 <= n <= count:
            got[n] = m.group(2).upper()
    return got


def render(lines: list[str], kinds: list) -> str:
    """판정이 끝난 kinds로 본문 재조립 — 문단 하나가 빈 줄로 구분된 한 줄로 흐른다.
    판정을 못 받은 자리(None)는 공백으로 둔다: 손대기 전 원문과 같은 상태라 안전하다."""
    if not lines:
        return ""
    parts = [lines[0]]
    for i, k in enumerate(kinds):
        parts.append("\n\n" if k == PARA else ("" if k == JOIN else " "))
        parts.append(lines[i + 1])
    return "".join(parts)
