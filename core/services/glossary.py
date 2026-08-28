#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""용어집 — 보관함에서 (한글, 원어) 짝을 모아 표기를 통일한다 (2026-08-29).

배경: 요약의 «용어 한글(원어) 병기»는 프롬프트 지시뿐이라 노트마다 표기가
흩어진다. 실측(노트 571개) 결과 한글어 1104개 중 100개에서 원어가 갈렸다.

다만 갈린 것 대부분은 **오류가 아니라 원서 언어 차이**다 —
  책임: responsibility(영서) / responsabilité(레비나스) / Verantwortung(본회퍼)
셋 다 맞다. 전역 통일은 맞는 정보를 파괴한다. 그래서 이 모듈은

  ① 대소문자·공백만 다른 것  → 자동 통일 (안전)
  ② 원어 자체가 다른 것      → 손대지 않고 «검토 목록»으로만 넘긴다

두 갈래로만 나눈다. ②의 판정은 사람이 한다.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

# ── 노트에서 키워드 줄을 읽는다 ──
# '## 핵심 키워드' 아래의 '#키워드 — 해설(원어 포함)' 형식
KW_LINE = re.compile(r'^#(\S+)\s+—\s*(.+)$')
# 해설 안 괄호의 라틴/그리스 문자열 = 원어 후보
ORIG_IN_PAREN = re.compile(r'\(([A-Za-zÀ-ÿĀ-ſΑ-Ωα-ωἀ-ῼ][^)]{0,40})\)')
# 괄호 **바로 앞**의 한글 덩어리. 이것이 키워드와 맞아야 그 키워드의 원어다.
KO_BEFORE_PAREN = re.compile(
    r'([가-힣A-Za-z0-9][가-힣A-Za-z0-9\s]{0,24})\s*\(([A-Za-zÀ-ÿĀ-ſΑ-Ωα-ωἀ-ῼ][^)]{0,40})\)')

KW_HEADING = "## 핵심 키워드"


def norm_key(s: str) -> str:
    """대소문자·공백·붙임표만 지운 비교용 키. 이것이 같으면 '같은 원어'로 본다."""
    return re.sub(r'[\s\-]', '', unicodedata.normalize("NFC", s)).casefold()


def guess_lang(s: str) -> str:
    """원어의 언어를 대강 짚는다. 충돌이 '원서 차이'인지 가르는 데만 쓴다."""
    if re.search(r'[Α-Ωα-ωἀ-ῼ]', s):
        return "el"
    if re.search(r'[äöüÄÖÜß]', s) or re.search(r'(ung|heit|keit|schaft|Dasein)\b', s):
        return "de"
    if re.search(r'[éèêëàâçôîïûù]', s):
        return "fr"
    if re.search(r'\b(Dei|Deus|homo|Homo|imago|Imago|Missio|sui|ex)\b', s):
        return "la"
    return "en"


def iter_keyword_lines(text: str):
    """'## 핵심 키워드' 구획 안의 (한글, 해설) 을 훑는다."""
    inside = False
    for line in text.splitlines():
        if line.startswith(KW_HEADING):
            inside = True
            continue
        if inside and line.startswith("## "):
            inside = False
        if not inside:
            continue
        m = KW_LINE.match(line.strip())
        if m:
            yield m.group(1), m.group(2)


def orig_for(ko: str, desc: str) -> str:
    """해설에서 **그 키워드의** 원어만 집는다.

    첫 괄호를 무조건 집으면 남의 원어를 가져온다. 실제로 그렇게 재다가 틀렸다:
      #AI윤리 — 인공지능(AI)의 개발과…        → (AI)는 '인공지능'의 원어
      #교회론 — 교회는 그리스도의 몸(Leib Christi)… → '그리스도의 몸'의 원어
    괄호 바로 앞의 한글이 키워드와 맞을 때만 인정한다. 키워드는 공백이 없으므로
    (‘도덕적행위자’) 앞말의 공백을 지워 비교한다."""
    target = re.sub(r'\s', '', ko)
    for m in KO_BEFORE_PAREN.finditer(desc):
        before, orig = m.group(1), m.group(2).strip()
        head = re.sub(r'\s', '', before)
        # 앞말이 키워드로 끝날 때만 인정한다(‘사회 계층(stratification)’ ← ‘계층’).
        # 반대 방향(키워드가 앞말로 끝남)은 남의 원어를 물어 온다 —
        # ‘인공지능 전환(AX)’의 ‘전환’이 ‘디지털전환’에 걸렸었다.
        if head.endswith(target):
            return orig
    return ""


def collect(wiki_dir: Path) -> list[tuple[str, str, Path]]:
    """보관함 전체에서 (한글, 원어, 노트경로) 을 모은다."""
    out = []
    for f in sorted(wiki_dir.rglob("*.md")):
        if f.name.startswith("_"):        # _retrofit.log 등 부속 파일
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for ko, desc in iter_keyword_lines(text):
            orig = orig_for(ko, desc)
            if orig:
                out.append((ko, orig, f))
    return out


def build(pairs) -> dict:
    """한글어별로 원어를 묶는다.

    반환: {한글: {"groups": [{"key","canonical","forms":{형태:횟수},"lang"}], ...}}
    같은 norm_key 끼리가 한 group — 그 안에서만 표기를 통일한다.
    """
    by_ko: dict[str, Counter] = defaultdict(Counter)
    for ko, orig, _ in pairs:
        by_ko[ko][orig] += 1

    gloss = {}
    for ko, forms in by_ko.items():
        groups: dict[str, Counter] = defaultdict(Counter)
        for form, n in forms.items():
            groups[norm_key(form)][form] += n
        gl = []
        for key, variants in groups.items():
            # 최빈 형태를 정본으로. 동수면 소문자 쪽을 택한다.
            top = max(variants.items(), key=lambda kv: (kv[1], kv[0] == kv[0].lower()))
            gl.append({
                "key": key,
                "canonical": top[0],
                "forms": dict(variants),
                "lang": guess_lang(top[0]),
            })
        gl.sort(key=lambda g: -sum(g["forms"].values()))
        gloss[ko] = {"groups": gl, "total": sum(forms.values())}
    return gloss


def unify_targets(gloss: dict) -> list[tuple[str, str, str, int]]:
    """자동 통일 대상: (한글, 바꿀 형태, 정본, 횟수). 대소문자·공백 차이뿐이다."""
    out = []
    for ko, entry in gloss.items():
        for g in entry["groups"]:
            for form, n in g["forms"].items():
                if form != g["canonical"]:
                    out.append((ko, form, g["canonical"], n))
    return sorted(out, key=lambda r: -r[3])


def _parts(form: str) -> list[str]:
    """'Artificial Intelligence, AI' → ['Artificial Intelligence', 'AI'].

    머리글자를 뽑으려면 낱말 경계가 살아 있어야 하므로 정규화 전 형태를 준다."""
    return [p.strip() for p in form.split(",") if p.strip()]


def _acronym(s: str) -> str:
    """'artificial intelligence' → 'ai'. 머리글자만 뽑는다."""
    words = re.findall(r'[A-Za-zÀ-ÿ]+', s)
    return "".join(w[0] for w in words).casefold() if len(words) > 1 else ""


def related(a: str, b: str) -> bool:
    """약어·확장·부분 관계면 True. 'AI'와 'artificial intelligence'는 같은 것이다."""
    pa, pb = _parts(a), _parts(b)
    if {norm_key(x) for x in pa} & {norm_key(y) for y in pb}:
        return True
    for x in pa:
        for y in pb:
            if norm_key(x) == _acronym(y) or norm_key(y) == _acronym(x):
                return True
    return False


def review_targets(gloss: dict) -> list[tuple[str, list, bool]]:
    """검토 목록: 원어 자체가 갈린 한글어.

    셋째 값 benign=True 는 약어·확장 관계라 손댈 것이 없다는 뜻이다
    (AI ↔ artificial intelligence). 나머지가 사람이 볼 몫이다.
    언어 판정은 힌트로만 붙인다 — visage·Resonanz 처럼 표시가 없는 프랑스어·
    독일어 낱말은 자동으로 가려내지 못한다."""
    out = []
    for ko, entry in gloss.items():
        if len(entry["groups"]) < 2:
            continue
        forms = [g["canonical"] for g in entry["groups"]]
        benign = all(related(forms[0], f) for f in forms[1:])
        out.append((ko,
                    [(g["canonical"], sum(g["forms"].values()), g["lang"]) for g in entry["groups"]],
                    benign))
    return sorted(out, key=lambda r: (r[2], -sum(n for _, n, _ in r[1])))


def apply_to_text(text: str, gloss: dict) -> tuple[str, int]:
    """'## 핵심 키워드' 구획 안의 '(원어)' 표기만 정본으로 바꾼다.

    본문 산문까지 손대면 한 문장 안에서 표기가 어긋난다. 실제로 그렇게 했다가
    «현상학(phenomenology), 민속 방법론(Ethnomethodology)» 처럼 나란한 항목의
    한쪽만 소문자가 되었다. 전역 일관성을 얻자고 지역 일관성을 깬 셈이라
    범위를 키워드 구획으로 좁혔다 — 그쪽이 용어집의 정본 자리다."""
    lines = text.split("\n")
    out, inside, n = [], False, 0
    for line in lines:
        if line.startswith(KW_HEADING):
            inside = True
            out.append(line)
            continue
        if inside and line.startswith("## "):
            inside = False
        if inside and line.lstrip().startswith("#"):
            for entry in gloss.values():
                for g in entry["groups"]:
                    canon = g["canonical"]
                    for form in g["forms"]:
                        if form == canon:
                            continue
                        pat = "(" + form + ")"
                        if pat in line:
                            n += line.count(pat)
                            line = line.replace(pat, "(" + canon + ")")
        out.append(line)
    return "\n".join(out), n


def hint_for(text: str, gloss: dict, limit: int = 25) -> str:
    """요약 프롬프트에 끼울 조각 — 이 원문에 실제로 나오는 용어만 추린다.

    전역 목록을 통째로 넣으면 모델이 무관한 용어를 끌어온다. 본문에 한글어가
    보이는 것만, 정본이 하나로 확정된 것만 넘긴다."""
    # 키워드는 공백이 없고(‘하나님의형상’) 본문은 띄어 쓴다(‘하나님의 형상’).
    # 양쪽 공백을 지우고 맞춘다.
    flat = re.sub(r'\s', '', text)
    rows = []
    for ko, entry in gloss.items():
        if len(entry["groups"]) != 1:       # 원어가 갈린 것은 넘기지 않는다
            continue
        if len(ko) >= 2 and re.sub(r'\s', '', ko) in flat:
            rows.append((entry["total"], ko, entry["groups"][0]["canonical"]))
    rows.sort(reverse=True)
    if not rows:
        return ""
    lines = "\n".join(f"- {ko} — {orig}" for _, ko, orig in rows[:limit])
    return ("\n[이미 쓰이는 용어 표기]\n"
            "아래는 이 보관함에서 이미 확정된 한글-원어 대응이다. 같은 개념이면 "
            "이 표기를 그대로 따른다. 목록에 없는 용어는 평소대로 판단한다.\n"
            f"{lines}\n")


# ── 저장/적재 ──
def path_for(config_dir: Path) -> Path:
    return config_dir / "glossary.json"


def save(gloss: dict, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(gloss, ensure_ascii=False, indent=1), encoding="utf-8")


def load(src: Path) -> dict:
    try:
        return json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# ── 단독 실행 ──
def _cli() -> int:
    import argparse
    import shutil
    import sys
    import time

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import config as cfg                                   # noqa: E402

    ap = argparse.ArgumentParser(description="용어집 만들기·표기 통일")
    ap.add_argument("--wiki", default=str(cfg.WIKI_DIR), help="보관함 경로")
    ap.add_argument("--report", action="store_true", help="현황만 보여 준다")
    ap.add_argument("--apply", action="store_true", help="노트를 실제로 고친다(백업 후)")
    a = ap.parse_args()

    wiki = Path(a.wiki)
    if not wiki.exists():
        print(f"보관함이 없다: {wiki}")
        return 1

    pairs = collect(wiki)
    gloss = build(pairs)
    dest = path_for(cfg.CONFIG_DIR if hasattr(cfg, "CONFIG_DIR") else Path.home() / ".config" / "mybookshelf")
    save(gloss, dest)

    uni = unify_targets(gloss)
    rev = review_targets(gloss)
    benign = [r for r in rev if r[2]]
    susp = [r for r in rev if not r[2]]

    print(f"노트에서 모은 (한글,원어) {len(pairs)}개 · 한글어 {len(gloss)}개")
    print(f"용어집 저장: {dest}")
    print(f"\n① 자동 통일 대상(대소문자·공백만 다름): {len(uni)}건")
    for ko, form, canon, n in uni[:15]:
        print(f"    {ko:<16} {form}  →  {canon}   ({n}회)")
    if len(uni) > 15:
        print(f"    … 외 {len(uni)-15}건")

    print(f"\n② 원어 자체가 다름: {len(rev)}건 — 자동으로 손대지 않는다")
    print(f"   약어·확장 관계라 무해: {len(benign)}건 (AI ↔ artificial intelligence 따위)")
    print(f"   사람이 볼 몫: {len(susp)}건")
    for ko, variants, _ in susp[:25]:
        print(f"    {ko:<16} " + " / ".join(f"{c}×{n}" for c, n, _ in variants))

    if not a.apply:
        print("\n(고치려면 --apply)")
        return 0

    backup = wiki.parent / f"{wiki.name}_backup_{time.strftime('%Y%m%d_%H%M%S')}"
    print(f"\n백업: {backup}")
    shutil.copytree(wiki, backup)

    changed = total = 0
    for f in sorted(wiki.rglob("*.md")):
        if f.name.startswith("_"):
            continue
        try:
            old = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        new, n = apply_to_text(old, gloss)
        if n and new != old:
            f.write_text(new, encoding="utf-8")
            changed += 1
            total += n
    print(f"고친 노트 {changed}개 · 표기 {total}곳")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
