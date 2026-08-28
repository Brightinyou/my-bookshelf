#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""용어 대조 — 원어가 그 분야에 실재하는 표기인지 외부 권위 목록에 물어본다 (2026-08-29).

**할 수 있는 것은 딱 하나다**: 그 원어가 권위 목록에 실린 표제어인지.
뜻풀이가 맞는지는 판정하지 않는다 — 노트 키워드의 상당수가 책 고유의 조어라
(예언자적섬김·재난신학) 어떤 사전에도 없고, 없다고 틀린 것이 아니다.
그래서 못 찾은 것은 **«미확인»일 뿐 «오류»가 아니다.**

쓰는 곳(직접 호출해 확인, 2026-08-29):
  LCSH  id.loc.gov     — 미국 의회도서관 주제명표목. 표본 40개 중 23개 적중
  InPhO inphoproject   — 철학 개념 2625개(SEP 연결 1349). 통째로 받아 로컬 대조
  Getty vocab.getty.edu — 미술·건축 용어(AAT)
빠진 곳: PhilPapers는 403(Cloudflare), SEP은 API가 없다, Wikidata는 429가 잦고
검색 품질이 느슨하다("control problem"이 엉뚱한 논문 제목에 걸린다).
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = "my-bookshelf/1.0 (personal research tool)"
TIMEOUT = 20
PAUSE = 0.3          # 상대 서버 배려. LCSH는 이 정도로 충분했다.


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except Exception:
        return None


# ── LCSH (미 의회도서관 주제명표목) ──
def lcsh(term: str) -> str:
    d = _get("https://id.loc.gov/authorities/subjects/suggest2/?q="
             + urllib.parse.quote(term) + "&count=1")
    try:
        hits = d.get("hits") or []
        return hits[0].get("aLabel", "") if hits else ""
    except Exception:
        return ""


# ── InPhO (철학 개념) — 한 번 받아 캐시 ──
_INPHO: dict[str, str] | None = None


def inpho_index(cache: Path) -> dict[str, str]:
    """{정규화된 개념명: 표시명}. 파일이 있으면 그것을 쓴다."""
    global _INPHO
    if _INPHO is not None:
        return _INPHO
    raw = None
    if cache.exists():
        try:
            raw = json.loads(cache.read_text(encoding="utf-8"))
        except ValueError:
            raw = None
    if raw is None:
        raw = _get("https://www.inphoproject.org/idea.json")
        if raw:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    idx = {}
    try:
        for r in raw["responseData"]["results"]:
            label = (r.get("label") or "").strip()
            if label:
                idx[_norm(label)] = label
    except Exception:
        pass
    _INPHO = idx
    return idx


# ── Getty AAT (미술·건축) ──
def getty(term: str) -> str:
    q = ('SELECT ?l WHERE { ?s skos:prefLabel ?l . '
         'FILTER(LCASE(STR(?l)) = "%s") } LIMIT 1' % term.lower().replace('"', ''))
    d = _get("https://vocab.getty.edu/sparql.json?query=" + urllib.parse.quote(q))
    try:
        b = d["results"]["bindings"]
        return b[0]["l"]["value"] if b else ""
    except Exception:
        return ""


def _norm(s: str) -> str:
    return re.sub(r'[\s\-]', '', s).casefold()


def check(term: str, cache_dir: Path, use_getty: bool = False) -> dict:
    """한 원어를 대조한다. 반환: {"lcsh":…, "inpho":…, "getty":…, "found":bool}"""
    res = {"lcsh": "", "inpho": "", "getty": ""}
    idx = inpho_index(cache_dir / "inpho.json")
    res["inpho"] = idx.get(_norm(term), "")
    res["lcsh"] = lcsh(term)
    time.sleep(PAUSE)
    if use_getty and not (res["lcsh"] or res["inpho"]):
        res["getty"] = getty(term)
        time.sleep(PAUSE)
    res["found"] = bool(res["lcsh"] or res["inpho"] or res["getty"])
    return res


def _cli() -> int:
    import argparse
    import sys
    # Windows 콘솔은 기본이 cp949 라 한글·«»·① 이 UnicodeEncodeError 를 낸다.
    # setup.bat 이 chcp 65001 을 하는 것과 같은 취지. (2026-08-29)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import config as cfg                                   # noqa: E402
    from services import glossary as gl                    # noqa: E402

    ap = argparse.ArgumentParser(description="용어 원어를 권위 목록과 대조")
    ap.add_argument("--min", type=int, default=2, help="이 횟수 이상 쓰인 용어만")
    ap.add_argument("--limit", type=int, default=200, help="최대 조회 수")
    ap.add_argument("--getty", action="store_true", help="Getty AAT까지 본다(느림)")
    a = ap.parse_args()

    g = gl.load_any(cfg.CONFIG_DIR, cfg.WIKI_DIR)
    if not g:
        print("용어집이 없다. 먼저: python3 -m services.glossary --report")
        return 1

    terms = {}
    for ko, entry in g.items():
        for grp in entry["groups"]:
            n = sum(grp["forms"].values())
            if n >= a.min:
                terms.setdefault(grp["canonical"], [n, set()])
                terms[grp["canonical"]][0] = max(terms[grp["canonical"]][0], n)
                terms[grp["canonical"]][1].add(ko)
    ordered = sorted(terms.items(), key=lambda kv: -kv[1][0])[:a.limit]

    cache = cfg.CONFIG_DIR
    ok, miss = [], []
    print(f"{len(ordered)}개 원어를 대조한다 (LCSH · InPhO"
          + (" · Getty" if a.getty else "") + ")\n")
    for term, (n, kos) in ordered:
        r = check(term, cache, a.getty)
        src = "LCSH" if r["lcsh"] else ("InPhO" if r["inpho"] else ("Getty" if r["getty"] else ""))
        (ok if r["found"] else miss).append((term, n, sorted(kos)[0], src))

    print(f"확인됨   {len(ok)}개")
    for t, n, ko, src in ok[:20]:
        print(f"    {src:<6} {t[:36]:<36} ({ko}, {n}회)")
    print(f"\n미확인   {len(miss)}개  ← 틀렸다는 뜻이 아니다. 책 고유 조어면 정상이다.")
    for t, n, ko, _ in miss[:25]:
        print(f"           {t[:36]:<36} ({ko}, {n}회)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
