"""각주 복원 — 판독한 본문에서 각주를 찾아 Markdown 각주로 바꾼다 (2026-08-24).

**왜.** 학위논문에서 각주는 본문만큼 중요한데, TXT로 뽑으면 각주 번호가 본문
한복판에 맨숫자로 박히고(`비판하였다.58 시몽동은`) 각주 본문은 쪽 아래에 따로
떨어져 아무 표시 없이 놓인다. 나중에 인용할 때 어느 숫자가 각주인지, 그 각주가
무슨 내용인지 사람이 매번 되짚어야 한다. Markdown은 각주 문법이 있으므로 담을 수
있다.

**단서(사용자 관찰, 실측으로 확인).**
  · 본문의 각주 번호는 대개 **마침표·따옴표·닫는괄호 바로 뒤**에 붙는다.
  · 각주 본문은 쪽 아래에서 **줄 첫머리에 그 번호로 시작**하고, 번호가 **오름차순**
    으로 이어진다 (`16 …` 줄바꿈 `17 …` 줄바꿈 `18 …`).
  · 그 둘은 **같은 쪽이나 바로 다음 쪽 안에서** 짝을 이룬다.

**확신도로 가른다.** 줄 첫머리 숫자를 찾았다고 다 각주는 아니다 — 쪽번호와
러닝헤더도 그 모양이다(실측 레비나스 110쪽 `110 대화의 철학과 세인 철학`).
그래서 두 신호 중 **하나라도 있어야** 각주로 본다:

    ① 본문에 그 번호가 참조로 박혀 있다              ← 가장 강한 신호
    ② 번호가 이어지고(39·40·41) **마침표로 끝난다**  ← 둘을 함께 봐야 한다

②에서 마침표를 함께 요구하는 이유: 러닝헤더도 쪽마다 번호가 2씩 늘어 연번처럼
보인다(110·112·114). 그런데 **각주는 문장이거나 서지사항이라 마침표로 끝나고**
러닝헤더는 그렇지 않다. 연번은 쪽 안에서만이 아니라 **책 전체를 쪽 순서로 훑어**
잇는다 — 쪽마다 각주가 하나씩이면 쪽 안에서는 늘 '단독'이라 놓치기 때문이다.

둘 다 없으면 떼어냈던 것을 **본문으로 되돌린다.** 잘못 떼면 되돌릴 수 없다.
services/layout이 "이 쪽엔 각주가 없다"고 알려 주면 아예 찾지도 않는다.
"""

import re
from dataclasses import dataclass, field

PAGE_SEP = "\f"

# 각주 본문 줄: 줄 첫머리 숫자 + 공백 + 내용. 번호는 1~3자리.
_NOTE_LINE = re.compile(r"^(\d{1,3})\s+(\S.*)$")
# 본문 속 각주 번호: 문장부호나 한글/닫는따옴표 **바로 뒤**에 공백 없이 붙은 숫자.
# 공백 뒤 숫자(`제 3 장`, `1 부`)는 각주가 아니므로 일부러 뺀다.
_REF_IN_TEXT = re.compile(r"(?<=[.,!?)\]”’\"'가-힣])(\d{1,3})(?=[\s.,)\]”’]|$)")

# 각주 블록으로 인정할 최소 조건 — 한 줄짜리 우연을 걸러낸다
MIN_NOTE_CHARS = 12
# ★각주는 문장이거나 서지사항이라 **마침표로 끝난다**(사용자 관찰).
# 러닝헤더는 안 그렇다 — `110 대화의 철학과 세인 철학`엔 마침표가 없다.
# 닫는 따옴표·괄호·쪽수 뒤에 마침표가 오는 서지 형식도 함께 받는다.
_ENDS_LIKE_NOTE = re.compile(r"[.。!?][\s”’\"')\]』」]*$")
# 짝을 찾을 범위(쪽) — 각주가 다음 쪽으로 넘어가는 일이 흔하다
PAIR_WINDOW = 1


@dataclass
class Note:
    num: int
    text: str
    page: int                       # 0-기준 쪽 인덱스


@dataclass
class Result:
    markdown: str
    notes: list[Note] = field(default_factory=list)
    linked: int = 0                 # 본문에서 참조를 찾아 이어붙인 각주 수
    orphan: list[int] = field(default_factory=list)   # 본문 참조를 못 찾은 각주


def _split_notes(page: str) -> tuple[str, list[tuple[int, str]]]:
    """한 쪽을 (본문, [(번호, 각주본문)])으로 가른다.

    쪽 **끝에서부터** 거슬러 올라가며 각주 블록을 찾는다 — 각주는 항상 쪽 아래에
    있고, 위에서부터 훑으면 본문 속 숫자에 걸려 넘어진다."""
    lines = page.split("\n")
    starts: list[int] = []
    for i, ln in enumerate(lines):
        m = _NOTE_LINE.match(ln.strip())
        if m:
            starts.append(i)
    if not starts:
        return page, []

    # 뒤에서부터 '번호가 오름차순으로 이어지는' 가장 긴 꼬리를 고른다
    best: list[int] = []
    for begin in starts:
        chain, last = [], 0
        for i in starts:
            if i < begin:
                continue
            n = int(_NOTE_LINE.match(lines[i].strip()).group(1))
            if n > last:
                chain.append(i)
                last = n
        # 그 블록 아래로 본문이 다시 나오면 각주 블록이 아니다
        if chain and len(chain) >= len(best):
            best = chain
    if not best:
        return page, []

    head = "\n".join(lines[:best[0]]).rstrip()
    notes: list[tuple[int, str]] = []
    for k, i in enumerate(best):
        end = best[k + 1] if k + 1 < len(best) else len(lines)
        m = _NOTE_LINE.match(lines[i].strip())
        body = " ".join(x.strip() for x in [m.group(2)] + lines[i + 1:end] if x.strip())
        if len(body) >= MIN_NOTE_CHARS:
            notes.append((int(m.group(1)), body))
    if not notes:
        return page, []
    return head, notes


def convert(text: str, has_notes: list[bool] | None = None) -> Result:
    """쪽 구분(`\\f`)이 있는 본문을 Markdown으로. 각주는 `[^n]` / `[^n]: …`.

    has_notes를 주면(services/layout이 줄 간격으로 잰 결과) **각주가 없는 쪽에서는
    아예 찾지 않는다.** 줄 첫머리 숫자는 쪽번호·러닝헤더에도 흔해서(`110 대화의
    철학과 세인 철학`) 텍스트만 보고는 헷갈린다."""
    pages = text.split(PAGE_SEP)
    bodies: list[str] = []
    found: list[Note] = []
    for pi, page in enumerate(pages):
        if has_notes is not None and pi < len(has_notes) and not has_notes[pi]:
            bodies.append(page.rstrip())          # 각주 없는 쪽 — 손대지 않는다
            continue
        head, notes = _split_notes(page)
        bodies.append(head)
        found += [Note(n, b, pi) for n, b in notes]

    # 각주 번호는 장마다 1부터 다시 시작하는 일이 흔하다 — 쪽을 붙여 고유하게 만든다
    keys: dict[int, str] = {}
    used: set[str] = set()
    for nt in found:
        key = str(nt.num)
        if key in used:
            key = f"{nt.num}-{nt.page + 1}"
        used.add(key)
        keys[id(nt)] = key

    # ★번호가 이어지면 그것만으로도 각주다운 신호다.
    # 사용자 관찰: "연속되는 숫자들이 맨 앞에 있으면 각주일 가능성이 높고, 본문에
    # 그 숫자가 있으면 더더욱. **앞서 각주로 확인한 번호의 다음 숫자가 각주로
    # 이어져야 한다.**"
    #
    # 그래서 두 가지로 본다:
    #   · 같은 쪽 안에서 이웃(39·40·41)
    #   · ★**쪽을 넘어 이어지는 흐름** — 30쪽 39, 31쪽 40, 32쪽 41처럼 쪽마다
    #     하나씩이면 쪽 안에서는 늘 '단독'이라 놓친다. 책 전체를 쪽 순서로 훑어야
    #     비로소 연번인 줄 안다.
    run_mates: set[tuple[int, int]] = set()      # (쪽, 번호)
    by_page: dict[int, list[Note]] = {}
    for nt in found:
        by_page.setdefault(nt.page, []).append(nt)
    for pi, group in by_page.items():
        nums = sorted(n.num for n in group)
        for i, v in enumerate(nums):
            if ((i > 0 and v - nums[i - 1] <= 2)
                    or (i + 1 < len(nums) and nums[i + 1] - v <= 2)):
                run_mates.add((pi, v))

    ordered = sorted(found, key=lambda n: (n.page, n.num))
    prev: Note | None = None
    for nt in ordered:
        if prev is not None and 0 < nt.num - prev.num <= 2:
            run_mates.add((nt.page, nt.num))
            run_mates.add((prev.page, prev.num))   # 앞 것도 같이 확정된다
        prev = nt

    linked, orphan, rejected = 0, [], []
    kept: list[Note] = []
    for nt in found:
        key = keys[id(nt)]
        # 같은 쪽부터 앞뒤 PAIR_WINDOW쪽까지 훑어 본문 참조를 찾는다
        hit = False
        for pi in range(max(0, nt.page - PAIR_WINDOW), min(len(bodies), nt.page + PAIR_WINDOW + 1)):
            def _sub(m, _k=key, _n=nt.num):
                nonlocal hit
                if hit or int(m.group(1)) != _n:
                    return m.group(0)
                hit = True
                return f"[^{_k}]"
            bodies[pi] = _REF_IN_TEXT.sub(_sub, bodies[pi])
            if hit:
                break
        if hit:
            linked += 1
            kept.append(nt)
        elif (nt.page, nt.num) in run_mates and _ENDS_LIKE_NOTE.search(nt.text):
            # 연번이고 **마침표로 끝난다** — 본문 참조는 못 찾았어도 각주로 본다.
            # 마침표를 함께 요구하는 이유: 러닝헤더도 쪽마다 번호가 2씩 늘어
            # 연번처럼 보인다(110·112·114). 그런데 러닝헤더는 마침표가 없다.
            orphan.append(nt.num)
            kept.append(nt)
        else:
            # 홀로 뜬 숫자에 본문 참조도 없다 — 쪽번호·러닝헤더일 공산이 크다.
            # 각주로 떼어낸 것을 **본문으로 되돌린다.** 잘못 떼면 되돌릴 수 없다.
            rejected.append(nt)

    for nt in rejected:
        bodies[nt.page] = (bodies[nt.page].rstrip() + "\n\n" + f"{nt.num} {nt.text}").strip()

    md = ("\n\n".join(b.strip() for b in bodies if b.strip())
          + ("\n\n" + "\n\n".join(f"[^{keys[id(n)]}]: {n.text}" for n in kept) if kept else ""))
    return Result(md, kept, linked, orphan)
