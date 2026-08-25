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


# 줄 한복판에 '번호 + 서지사항'이 이어지는 자리 — 각주가 본문에 녹아든 모양.
# ★**번호 앞에 공백이 있어야 한다.** 본문 속 각주 참조는 문장부호·글자 바로 뒤에
# **공백 없이** 붙고(`주장하였다.11`·`예속되었고12`), 쪽 아래 각주 항목은 공백으로
# 떨어져 시작한다(`… 11 이기상,`). 이 구별을 안 넣었다가 실측 17쪽에서 **본문 참조를
# 각주로 잘못 보고 본문을 찢었다**(2026-08-25).
_INLINE_NOTE = re.compile(r'(?<=\s)(\d{1,3})\s+(?=[가-힣A-Za-z(『「][^\n]{5,})')
# 각주다운 끝맺음 — 서지사항은 쪽수나 마침표로 끝난다
_NOTE_TAIL = re.compile(r'[.。]\s*$|\d\s*[.。]?\s*$')
# 덩어리 안에서 다음 각주를 찾을 때 — 앞 공백을 요구하지 않는다
_NOTE_ANY = re.compile(r'(\d{1,3})\s+(?=[가-힣A-Za-z(『「][^\n]{5,})')


def split_inline_notes(page: str) -> str:
    """본문 줄에 녹아든 각주를 제 줄로 되돌린다 (2026-08-25).

    ★판독 프롬프트가 "한 문단은 한 줄로"를 강조한 탓에 모델이 **각주까지 본문 문단에
    이어 붙였다.** 실측 『기술신학』 373쪽 중 105쪽이 이 모양이었다:

        …도취되지 않고 8 현대를 흔히… 9 그 대표적인… 10 기술철학이란… 11 이기상, …454.

    프롬프트는 고쳤지만 **이미 판독한 글도 되돌려야** 한다. 다시 읽으면 다른 오독이
    새로 생기므로, 확실한 자리만 규칙으로 가른다.

    ★★**두 단계로 나눈다. 이것이 핵심이다.**

    ① **각주 덩어리가 어디서 시작하는지** 먼저 찾는다 — 번호 **앞에 공백이 있고**
       오름차순으로 둘 이상 이어지는 자리. 본문 속 각주 참조는 문장부호·글자 바로
       뒤에 **공백 없이** 붙으므로(`주장하였다.11`) 이 조건이 둘을 가른다.
       ★이걸 안 넣었다가 실측 17쪽에서 **본문 참조를 각주로 보고 본문을 찢었다.**
    ② 시작을 찾은 **뒤로는** 공백을 요구하지 않는다 — 이미 각주 영역 안이므로
       `…알려져 있다.11 이기상,`처럼 붙어 있어도 다음 각주다.
       ★①의 규칙만 쓰면 이런 자리를 놓쳐 각주 10이 11·12·13을 삼킨다.
    """
    out: list[str] = []
    for line in page.split("\n"):
        marks = _note_marks(line)
        if not marks:
            out.append(line)
            continue
        head = line[:marks[0][0]].rstrip()
        if head:
            out.append(head)
            out.append("")                      # 본문과 각주 사이 빈 줄
        for k, (pos, _n) in enumerate(marks):
            end = marks[k + 1][0] if k + 1 < len(marks) else len(line)
            out.append(line[pos:end].strip())
    return "\n".join(out)


def _note_marks(line: str) -> list[tuple[int, int]]:
    """줄 안에서 각주가 시작하는 [(위치, 번호)]. 확실하지 않으면 빈 목록."""
    if not _NOTE_TAIL.search(line):
        return []                               # 서지사항답게 끝나지 않는다
    # ① 공백 뒤 번호로 시작하는 오름차순 사슬 — 가장 긴 것, 같으면 뒤쪽
    starts = [(m.start(1), int(m.group(1))) for m in _INLINE_NOTE.finditer(line)]
    best: list[tuple[int, int]] = []
    for i in range(len(starts)):
        chain = [starts[i]]
        for pos, n in starts[i + 1:]:
            if 0 < n - chain[-1][1] <= 2:
                chain.append((pos, n))
        if len(chain) >= 2 and len(chain) >= len(best):
            best = chain
    if not best:
        return []
    # ② 덩어리 안에서는 공백 없이 붙은 번호도 각주다
    marks = list(best)
    while True:
        pos, num = marks[-1]
        m = _NOTE_ANY.search(line, pos + 1)
        while m and not (0 < int(m.group(1)) - num <= 2):
            m = _NOTE_ANY.search(line, m.start(1) + 1)
        if not m:
            break
        marks.append((m.start(1), int(m.group(1))))
    return marks


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

    head_lines = lines[:best[0]]
    notes: list[tuple[int, str]] = []
    for k, i in enumerate(best):
        end = best[k + 1] if k + 1 < len(best) else len(lines)
        m = _NOTE_LINE.match(lines[i].strip())
        body = " ".join(x.strip() for x in [m.group(2)] + lines[i + 1:end] if x.strip())
        # ★길이만으로 자르면 **`위의 책, 12.`가 통째로 사라진다.** 한국 학술서에서
        # 가장 흔한 각주 형식인데 11자라 임계(12자)에 걸렸다 — 실측 『기술신학』에서
        # 68건이 Markdown에서 유실되고 있었다(2026-08-25). 짧아도 **연번 안에 있고
        # 마침표로 끝나면** 각주다.
        short_ok = len(best) >= 2 and bool(_ENDS_LIKE_NOTE.search(body))
        if body and (len(body) >= MIN_NOTE_CHARS or short_ok):
            notes.append((int(m.group(1)), body))
        else:
            # ★각주로 못 본 줄은 **본문으로 되돌린다.** 어느 쪽도 아니면 글이 사라진다.
            head_lines += lines[i:end]
    head = "\n".join(head_lines).rstrip()
    if not notes:
        return page, []
    return head, notes


# 문장이 끝난 모양 — 마침표·물음표·닫는 따옴표 따위로 맺혔는가.
_SENTENCE_END = re.compile(r"""[.!?。…][\s"'”’)\]』」]*$|[”’"')\]』」]$""")
# 붙일지 띄울지 가를 때 보는 한글 덩어리
_HANGUL_TAIL = re.compile(r"[가-힣]+$")
_HANGUL_HEAD = re.compile(r"^[가-힣]+")


def ends_midsentence(text: str) -> bool:
    """이 쪽이 **문장 도중에** 끝났는가."""
    t = text.rstrip()
    return bool(t) and not _SENTENCE_END.search(t)


def join_across_break(left: str, right: str, lexicon: str = "") -> str:
    """쪽 경계에서 끊긴 문장을 잇는다 — **붙일지 띄울지는 책 어휘로 가른다.**

    ★한국어 책은 **어절 한복판에서도 줄이 바뀐다**(`…제본스의 역` / `설’인데`).
    그래서 쪽 경계를 무조건 공백으로 이으면 낱말이 쪼개지고(`역 설`), 무조건 붙이면
    어절이 뭉친다(`소위‘제본스의`). 둘 다 틀린다.

    가르는 법: 왼쪽 끝 한글 덩어리와 오른쪽 첫 한글 덩어리를 **붙여 본 말이 이 책
    어디에 실제로 나오면** 붙이고, 아니면 띄운다. 실측(『기술신학』 58/59쪽):
        `역` + `설` → `역설`  책에 있음 → 붙인다 → `제본스의 역설’인데`  ✔
    ★**판독이 틀렸을 때는 일부러 띄운다** — `역` + `철`(오독) → `역철`은 책에 없으니
    `역 철’인데`가 되어 **눈에 띈다.** 확인을 도우려고 잇는 것이므로 이편이 낫다.

    사전이 없으면 공백으로 잇는다(reflowlib.reflow와 같은 보수적 선택)."""
    l, r = left.rstrip(), right.lstrip()
    if not l or not r:
        return l or r
    mt, mh = _HANGUL_TAIL.search(l), _HANGUL_HEAD.search(r)
    if lexicon and mt and mh:
        merged = mt.group(0)[-4:] + mh.group(0)[:4]
        if merged and merged in lexicon:
            return l + r                      # 어절이 쪽에 걸쳐 쪼개졌다 — 붙인다
    if l.endswith("-"):                       # 영문 하이픈 분철
        return l[:-1] + r if r[:1].islower() else l + r
    return l + " " + r


def _first_para(page: str) -> tuple[str, str]:
    """쪽을 (첫 문단, 나머지)로 가른다."""
    parts = re.split(r"\n[ \t]*\n", page.lstrip(), maxsplit=1)
    return (parts[0], parts[1] if len(parts) > 1 else "")


def reflow_pages(text: str, has_notes: list[bool] | None = None,
                 lexicon: str = "") -> str:
    """쪽을 합칠 때 **각주가 문장을 끊지 않게** 다시 짠다 (2026-08-25 연구자 요청).

    책은 쪽 아래에 각주를 두므로, 문장이 쪽을 넘어가면 판독 결과가 이렇게 된다:

        …생명체인 것처럼 착각하고 있다고 비판하였다.58 시     ← 낱말 한복판에서 끊긴다
        58 시몽동, 『기술적 대상들의 존재양식에 대하여』, 71-73.
        (다음 쪽) 몽동은 생명체와 기술 개체의 차이를…

    ★**문장이 완성되지 않으면 사람도 AI도 검증하지 못한다.** 그래서 각주 위에서
    끊긴 본문을 다음 쪽 **본문**과 잇고, 각주 덩어리는 **쪽 차례 그대로** 뒤에 놓는다.

    ★★**다음 쪽에서 끌어올 것은 그 쪽의 '본문'이지 '첫 문단'이 아니다.** 빈 줄로
    각주가 갈려 있지 않은 쪽에서는 첫 문단이 **각주까지 통째로**라, 그대로 끌어올리면
    그 쪽 각주가 앞 쪽 각주보다 먼저 나온다 — 실측에서 58이 55·56·57 앞에 놓였다
    (2026-08-25 연구자 지적). 그래서 `_split_notes`로 본문만 떼어 끌어온다.

    ★한 번 이어도 여전히 문장 중간이면(위 예의 `시` → `몽동은`) **다음 쪽까지 이어
    간다.** 그때 지나친 쪽들의 각주는 **쪽 차례대로** 뒤에 붙인다."""
    pages = text.split(PAGE_SEP)
    out: list[str] = []
    carry: dict[int, str] = {}          # 앞 쪽이 본문을 가져가고 남긴 것

    def _block(notes: list[tuple[int, str]]) -> str:
        return "\n".join(f"{n} {b}" for n, b in notes)

    def _skip(i: int) -> bool:
        return has_notes is not None and i < len(has_notes) and not has_notes[i]

    i = 0
    while i < len(pages):
        page = carry.pop(i) if i in carry else pages[i]
        if _skip(i) or not page.strip():
            # ★본문을 앞 쪽이 다 가져가 빈 쪽이어도 **조각은 남긴다.** 조각 수가
            # 원래 쪽 수와 같아야 뒤따르는 단계(services/layout이 잰 has_notes,
            # 각주 짝짓기)의 쪽 번호가 어긋나지 않는다.
            out.append(page.strip())
            i += 1
            continue
        head, notes = _split_notes(page)
        if not notes:
            out.append(page.strip())
            i += 1
            continue
        blocks = [_block(notes)]
        j = i
        while ends_midsentence(head) and j + 1 < len(pages) and (j + 1) not in carry:
            nh, nn = _split_notes(pages[j + 1])
            if not nh.strip():
                break
            first, rest = _first_para(nh)
            if not first.strip() or _NOTE_LINE.match(first.strip().split("\n")[0]):
                break
            head = join_across_break(head, first, lexicon)
            if rest.strip():
                # 그 쪽에 본문이 남았다 — 남은 본문과 그 쪽 각주로 다시 세운다
                carry[j + 1] = (rest.strip() + ("\n\n" + _block(nn) if nn else "")).strip()
                break
            carry[j + 1] = ""           # 본문을 다 가져왔다
            if nn:
                blocks.append(_block(nn))   # ★각주는 쪽 차례대로 뒤에 붙인다
            j += 1
        out.append("\n\n".join([head.strip()] + blocks).strip())
        i += 1
    # ★쪽 구분자 앞뒤에 줄바꿈을 둔다. `\f`만 넣으면 화면에서 보이지 않아
    # 앞 쪽의 마지막 각주와 다음 쪽 첫 본문이 한 줄처럼 붙는다.
    return ("\n" + PAGE_SEP + "\n").join(out)


def audit_sequence(text: str, has_notes: list[bool] | None = None) -> list[dict]:
    """각주 번호가 **빠짐없이 이어지는지** 훑는다 (2026-08-25 연구자 지적).

    ★연구자의 판단을 그대로 규칙으로 옮긴 것이다 — "각주로는 4 다음 6이 잡히는데,
    그러면 5가 어디선가 사라진 것이다." 각주 번호는 글 안에서 **연속**이므로 빠진
    번호는 곧 **놓친 각주**다. 사람은 눈으로 알아채지만 훑어야 알 수 있고, 373쪽을
    사람이 다 훑을 수는 없다.

    돌려주는 것: [{"page": 쪽(0기반), "after": 앞 번호, "missing": [빠진 번호들]}]

    ★**고치지 않고 알리기만 한다.** 빠진 자리를 자동으로 메우려면 각주가 어디서
    끝나고 본문이 어디서 다시 시작하는지 알아야 하는데, 그건 확신할 수 없는 판단이다
    (`recover_hint` 참고). 잘못 메우면 본문이 각주로 떨어져 나가고 되돌릴 수 없다."""
    pages = text.split(PAGE_SEP)
    found: list[tuple[int, int]] = []          # (쪽, 번호)
    for pi, page in enumerate(pages):
        if has_notes is not None and pi < len(has_notes) and not has_notes[pi]:
            continue
        _h, notes = _split_notes(page)
        for n, _b in notes:
            found.append((pi, n))
    out: list[dict] = []
    for (p1, n1), (p2, n2) in zip(found, found[1:]):
        if n2 <= n1:
            continue                            # 장이 바뀌며 1로 돌아가는 자리
        if n2 - n1 > 1 and n2 - n1 <= 15:      # 너무 크게 벌어지면 장이 바뀐 것이다
            out.append({"page": p2, "after": n1, "from_page": p1,
                        "missing": list(range(n1 + 1, n2))})
    return out


# 되찾기를 시도할 만한 크기 — 이보다 크면 사람에게 넘긴다.
RECOVER_MAX_MISSING = 3
RECOVER_MAX_SPAN = 2


def recoverable_gaps(gaps: list[dict]) -> tuple[list[dict], list[dict]]:
    """끊긴 자리를 (되찾아 볼 만한 것, 사람이 봐야 할 것)으로 가른다.

    ★실측에서 배운 것(2026-08-25): 이 책은 쪽마다의 각주만 쓰지 않는다. 글 끝에
    **미주를 모아 놓은 쪽**이 있어(60쪽에 39~64번 26개) 번호가 크게 뛴다. 그런
    자리를 "빠졌다"고 보고 그 쪽만 다시 읽으면 당연히 못 찾는다 — 실측 15쪽을
    시도해 1쪽만 성공했다.

    그래서 **작은 끊김만** 되찾는다: 빠진 번호가 {maxm}개 이하이고 쪽 간격이
    {maxs}쪽 이하일 때. 그 조건에서는 정말 그 언저리에서 놓친 각주다.
    나머지는 고치려 들지 않고 **알리기만 한다.**""".format(
        maxm=RECOVER_MAX_MISSING, maxs=RECOVER_MAX_SPAN)
    small, large = [], []
    for g in gaps:
        span = g.get("page", 0) - g.get("from_page", g.get("page", 0))
        (small if len(g["missing"]) <= RECOVER_MAX_MISSING and span <= RECOVER_MAX_SPAN
         else large).append(g)
    return small, large


def recover_hint(page: str, missing: int, lexicon: str = "") -> dict | None:
    """빠진 각주 하나를 **어디서 떼어내면 되는지** 짚어 본다. 고치지는 않는다.

    ★연구자의 검증법을 그대로 옮겼다 — "각주 5 앞에 있는 `신` 다음에 `앙인`이 있으니
    `신앙인`으로 이어진다. 그러면 그 사이가 각주다." 즉 **각주를 들어내고 남은 본문이
    책에 있는 낱말로 이어붙으면** 그 경계가 맞다.

    돌려주는 것: {"start": 시작위치, "end": 끝위치, "join": 이어붙은 낱말} 또는 None.
    확신이 서지 않으면 None이다 — **찍지 않는다.**"""
    if not lexicon:
        return None
    # 번호가 여러 번 나오면 **뒤엣것**이 각주다(앞엣것은 본문 속 참조).
    starts = [m.start() for m in re.finditer(rf"(?<=\s){missing}\s+(?=\S)", page)]
    if not starts:
        return None
    s = starts[-1]
    before = page[:s].rstrip()
    mt = _HANGUL_TAIL.search(before)
    if not mt:
        return None
    tail = mt.group(0)[-3:]
    # 각주가 끝나고 본문이 다시 시작하는 자리를 찾는다 — 이어붙인 말이 책에 있어야 한다
    for m in re.finditer(r"(?<=[.。])\s*(?=[가-힣])", page[s:]):
        e = s + m.end()
        mh = _HANGUL_HEAD.search(page[e:])
        if not mh:
            continue
        joined = tail + mh.group(0)[:3]
        for k in range(len(joined), 1, -1):
            if joined[:k] in lexicon and len(joined[:k]) >= 2:
                return {"start": s, "end": e, "join": joined[:k]}
    return None


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
