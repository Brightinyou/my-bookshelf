# -*- coding: utf-8 -*-
"""원문 언어 감지 — 외부 의존성 없이 문자 종류 + 기능어 빈도로 판별 (2026-08-15).

이 앱은 어떤 언어든 **한국어로** 옮기는 것이 목적이라, 파이프라인의 분기 판단은
예전부터 "한글이냐 아니냐" 하나면 충분했다(needs_translation). 하지만 그러면
화면에 "영문번역"이라고만 뜨고 독일어·일본어 책도 영어책 취급을 받는다. 여기서는
**무슨 언어인지 이름을 알아내** 화면 표시와 번역 프롬프트에 쓴다.

새 패키지를 붙이지 않는 이유는 이 프로젝트가 지금까지 지켜온 방침 그대로다
(PyMuPDF 대신 pypdfium2, EPUB도 표준 zipfile) — langdetect/fasttext 같은 의존성을
늘리는 대신, 책 한 권 분량이면 충분히 정확한 고전적 방법을 쓴다:
  1) 문자 종류로 먼저 가른다. 한글·가나·한자·키릴·그리스·히브리·아랍 문자는
     그 자체로 언어를 거의 확정한다.
  2) 라틴 문자는 그것만으로 못 가르므로 기능어(the/der/de/le …) 빈도로 고른다.
     기능어는 어느 언어에서나 최빈 단어라 한 문단만 있어도 신호가 뚜렷하다.
"""
import re
import unicodedata

# 코드 → (한국어 이름, 영어 이름)
LANGUAGES: dict[str, tuple[str, str]] = {
    "ko": ("한국어", "Korean"),
    "en": ("영어", "English"),
    "de": ("독일어", "German"),
    "nl": ("네덜란드어", "Dutch"),
    "fr": ("프랑스어", "French"),
    "es": ("스페인어", "Spanish"),
    "it": ("이탈리아어", "Italian"),
    "pt": ("포르투갈어", "Portuguese"),
    "la": ("라틴어", "라틴어"),
    "ja": ("일본어", "Japanese"),
    "zh": ("중국어", "Chinese"),
    "ru": ("러시아어", "Russian"),
    "el": ("그리스어", "Greek"),
    "he": ("히브리어", "Hebrew"),
    "ar": ("아랍어", "Arabic"),
}
LANGUAGES["la"] = ("라틴어", "Latin")

SAMPLE_CHARS = 4000     # 앞부분 이 정도만 봐도 충분하다(표지·목차가 섞여도 무방)
KO_THRESHOLD = 0.30     # 기존 needs_translation과 같은 기준 — 분기 동작을 바꾸지 않는다

_HANGUL = re.compile(r"[가-힣]")
_KANA = re.compile(r"[ぁ-んァ-ヶー]")
_HAN = re.compile(r"[一-鿿㐀-䶿]")
_CYRILLIC = re.compile(r"[Ѐ-ӿ]")
_GREEK = re.compile(r"[Ͱ-Ͽἀ-῿]")
_HEBREW = re.compile(r"[֐-׿]")
_ARABIC = re.compile(r"[؀-ۿ]")
_LATIN = re.compile(r"[A-Za-zÀ-ÿĀ-ž]")

# 라틴 문자 언어의 기능어. 내용어가 아니라 문법 뼈대라 주제·시대와 무관하게 나온다.
_STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset("""the of and to in is that it for was as with on be at by this not are from
        or an but which we they have has been their would there his he she who what when all
        can more one about into than them these""".split()),
    "de": frozenset("""der die das und ist nicht sich den dem ein eine zu von mit auf für als auch
        es an werden aus er hat dass sie nach wird bei einer um über wenn noch durch ich im
        dieser sind war oder nur wie so kann aber vor zum zur""".split()),
    "nl": frozenset("""de het een en van is in dat op te met voor niet zijn aan er maar om ook als
        dan of naar door over ze uit bij nog kan worden hij wij deze dit was heeft werd zich
        men zo veel wat waar hun""".split()),
    "fr": frozenset("""le la les de des du et est en un une que qui dans pour sur pas plus ce il
        elle nous vous au aux par avec ne se son sa ses mais comme ou dont cette leur nest
        sont été être fait tout""".split()),
    "es": frozenset("""el la los las de del y es en un una que se por con para no su al lo como más
        pero sus le ya o este sí porque esta entre cuando muy sin sobre también me hasta hay
        donde han quien""".split()),
    "it": frozenset("""il la di che e un una in per non con si da del al le dei come più sono ma gli
        nel alla lo delle questo anche se ha quando molto dove chi loro essere sua suo tutto
        della degli""".split()),
    "pt": frozenset("""de que e o a do da em para com não uma os no se na por mais as dos como mas
        ao ele das à seu sua ou quando muito nos já está eu também só pelo pela até isso""".split()),
    "la": frozenset("""et in est non ad quod cum ut si qui quae autem enim sed ex per de esse sunt
        hoc eius ipse atque nec quam tamen etiam ita quia omnia deus dei quo eo a ab""".split()),
}

# 그 언어에서만(또는 압도적으로) 쓰이는 글자 — 기능어가 팽팽할 때 가른다.
_DIACRITIC_HINTS: dict[str, str] = {
    "de": "ßäöüÄÖÜ",
    "es": "ñÑ¿¡",
    "pt": "ãõÃÕ",
    "fr": "çœèùêâÇŒ",
    "it": "àòùìÀÒ",
    "nl": "ĳĲ",
}

_WORD_RE = re.compile(r"[a-zà-ÿā-ž]+")


def _script_counts(text: str) -> dict[str, int]:
    return {
        "hangul": len(_HANGUL.findall(text)),
        "kana": len(_KANA.findall(text)),
        "han": len(_HAN.findall(text)),
        "cyrillic": len(_CYRILLIC.findall(text)),
        "greek": len(_GREEK.findall(text)),
        "hebrew": len(_HEBREW.findall(text)),
        "arabic": len(_ARABIC.findall(text)),
        "latin": len(_LATIN.findall(text)),
    }


def _score_latin(text: str) -> tuple[str, float]:
    """라틴 문자 본문의 (언어코드, 확신도 0~1). 기능어 적중률이 가장 높은 언어."""
    low = unicodedata.normalize("NFC", text.lower())
    words = _WORD_RE.findall(low)
    if len(words) < 12:
        return "en", 0.0            # 표본이 너무 짧으면 영어로 두되 확신도 0
    scores: dict[str, float] = {}
    for code, stops in _STOPWORDS.items():
        hits = sum(1 for w in words if w in stops)
        bonus = sum(low.count(c) for c in _DIACRITIC_HINTS.get(code, "")) / len(words)
        scores[code] = hits / len(words) + min(bonus, 0.05)
    best = max(scores, key=scores.get)
    ranked = sorted(scores.values(), reverse=True)
    if ranked[0] <= 0:
        return "en", 0.0
    # 1등이 2등보다 얼마나 앞서는지를 확신도로 — 비슷하면 낮게 나온다.
    margin = (ranked[0] - ranked[1]) / ranked[0] if len(ranked) > 1 else 1.0
    return best, round(min(1.0, margin + min(ranked[0] * 2, 0.5)), 3)


def detect(text: str) -> tuple[str, float]:
    """(언어코드, 확신도). 판단할 근거가 없으면 ("", 0.0)."""
    sample = (text or "")[:SAMPLE_CHARS]
    if not sample.strip():
        return "", 0.0
    c = _script_counts(sample)
    letters = sum(c.values())
    if not letters:
        return "", 0.0

    # 한글은 한국어에만 쓰이므로 비율만으로 확정 — 기존 분기 기준(0.30)을 그대로 쓴다.
    if c["hangul"] / letters >= KO_THRESHOLD:
        return "ko", round(c["hangul"] / letters, 3)
    # 가나가 섞이면 일본어(한자만 있으면 중국어). 일본어는 한자·가나가 함께 나온다.
    cjk = c["kana"] + c["han"]
    if cjk / letters >= 0.30:
        if c["kana"] >= max(8, cjk * 0.05):
            return "ja", round(cjk / letters, 3)
        return "zh", round(cjk / letters, 3)
    for script, code in (("cyrillic", "ru"), ("greek", "el"),
                         ("hebrew", "he"), ("arabic", "ar")):
        if c[script] / letters >= 0.50:
            return code, round(c[script] / letters, 3)
    if c["latin"] / letters >= 0.50:
        return _score_latin(sample)
    return "", 0.0


# 언어별 고유 문자 — 라틴 문자를 쓰는 언어들은 여기 없다(문자만으로는 못 가르므로).
_OWN_SCRIPT: dict[str, tuple[str, ...]] = {
    "ko": ("hangul",),
    "ja": ("kana", "han"),
    "zh": ("han",),
    "ru": ("cyrillic",),
    "el": ("greek",),
    "he": ("hebrew",),
    "ar": ("arabic",),
}


def has_own_script(code: str) -> bool:
    """그 언어가 라틴 문자와 구별되는 고유 문자를 쓰는가 — 판정 방법이 갈린다."""
    return code in _OWN_SCRIPT


def script_ratio(text: str, code: str) -> float:
    """text에서 code 언어가 쓰는 문자가 차지하는 비율(0~1). 글자가 없으면 0."""
    c = _script_counts(text or "")
    letters = sum(c.values())
    if not letters:
        return 0.0
    keys = _OWN_SCRIPT.get(code) or ("latin",)
    return sum(c[k] for k in keys) / letters


def looks_like(text: str, code: str) -> bool:
    """text가 code 언어로 보이는가 — '이미 도착언어인 단락'을 가려낼 때 쓴다.

    고유 문자를 쓰는 언어는 문자 비율만으로 확실하게 가른다. 라틴 문자권끼리는
    (영어/독일어/프랑스어…) 문자가 같아 그 방법이 통하지 않으므로 기능어 감지로
    확인하고, 표본이 짧아 확신이 없으면 False를 준다 — 여기서 틀리면 번역해야 할
    단락을 건너뛰어 원문이 그대로 남으므로, 애매할 땐 번역하는 쪽이 안전하다."""
    if not code:
        return False
    if has_own_script(code):
        return script_ratio(text, code) >= 0.60
    got, conf = detect(text)
    return got == code and conf > 0.0


def name(code: str, lang: str = "ko") -> str:
    """언어 이름 — lang='ko'면 '독일어', 'en'이면 'German'. 모르는 코드는 그대로."""
    pair = LANGUAGES.get(code or "")
    if not pair:
        return code or ""
    return pair[0] if lang == "ko" else pair[1]


def detect_file(path, default: str = "") -> tuple[str, float]:
    """파일 앞부분을 읽어 감지. 읽기 실패는 조용히 default."""
    try:
        return detect(path.read_text(encoding="utf-8", errors="ignore")[:SAMPLE_CHARS])
    except Exception:
        return default, 0.0


def detect_book(paths, max_chapters: int = 6) -> tuple[str, float]:
    """책 전체의 언어 — 여러 챕터에서 고르게 표본을 떠 합친 뒤 한 번에 감지한다.

    첫 챕터 하나만 보면 안 된다(실측 2026-08-15): 『서양철학사』(한국어 번역서)는
    1장이 독일어 참고문헌으로 뒤덮여 있어 그 장만 보면 '독일어'로 잡히고, 한국어
    책이 통째로 번역 대기에 들어간다. 본문 여러 곳을 섞으면 책의 실제 언어가 이긴다."""
    files = [p for p in (paths or []) if p is not None]
    if not files:
        return "", 0.0
    # 앞·중간·뒤가 고루 섞이도록 균등 간격으로 고른다(앞머리는 표제지·참고문헌이 많다).
    if len(files) > max_chapters:
        step = len(files) / max_chapters
        files = [files[int(i * step)] for i in range(max_chapters)]
    per = max(SAMPLE_CHARS // len(files), 400)
    chunks = []
    for p in files:
        try:
            chunks.append(p.read_text(encoding="utf-8", errors="ignore")[:per])
        except Exception:
            continue
    return detect("\n".join(chunks)) if chunks else ("", 0.0)
