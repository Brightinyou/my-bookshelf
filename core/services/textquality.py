"""TXT 품질 진단 — 변환된 본문이 실제로 쓸 만한지 검사한다 (2026-08-24).

만든 이유: 『기술신학』에서 **앱이 OCR을 하지 않고 PDF에 이미 구워져 있던 불량
OCR 레이어를 그대로 퍼 왔다**는 것이 드러났다. 그런데 그 사실이 요약·번역·EPUB·
위키를 다 태운 뒤에야 사람 눈에 띄었다. 분할과 마찬가지로 **결과를 아무도 검사하지
않는다**는 같은 결함이다 (services/chapter_map.py 머리말 참고).

핵심 지표 = **1음절 한글 낱말 비율**. 불량 레이어는 수·것·될·할·더·또 같은 한 글자
낱말을 통째로 빠뜨린다. 조사와 의존명사가 사라지므로 문장이 다른 뜻이 되고,
학위논문 인용문으로는 못 쓴다. 눈으로는 "좀 깨졌네" 정도로만 보여 놓치기 쉽지만
숫자로는 확연하다:

    정상 한국어 산문   7 ~ 25%   (『한국윤리문화사』 24.9 · 『공공신학과 한국사회』 22.5)
    불량 레이어        0 ~ 0.1%  (『기술신학』 47,219토큰 중 7개 = 0.01%)

실측 보강 지표: 『기술신학』은 `할/될/을 수 있`이 **0회**인데 `할/될/을 있`이 231회다.

**두 번째 축 = 문자 깨짐.** 낱말은 멀쩡한데 글자가 깨진 책(`기合`·`디지!i`·`옥회`)은
위 지표로 안 잡힌다. 그래서 따로 잰다 — ★**두 축은 합치지 않는다.** 25권 실측에서
깨짐률은 낱말 유실과 **상관이 없었다**(불량 8권 0.00~5.83 / 정상 17권 0.00~5.37로
완전히 겹침). 스캔본은 표지·판권·러닝헤더에서 원래 좀 깨지기 때문이다. 합쳐서
판정하면 새로 잡히는 건 없고 오탐만 는다. 각자 제 기준으로 재고 나쁜 쪽을 따른다.

깨짐률은 본문을 40토막으로 나눠 토막별 깨짐 밀도의 **중앙값**을 쓴다 — 앞뒤의
표지·판권 잡음에 흔들리지 않게.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# 정상 산문의 하한이 7%대라 2%는 넉넉한 안전 마진이다. 5%는 "이상하지만 단정은 못 함".
BAD_ONE_SYLLABLE = 2.0
SUSPECT_ONE_SYLLABLE = 5.0

# 한국어 책으로 볼 최소 조건 — 영문 원서에 1음절 잣대를 들이대면 전부 불량이 된다
MIN_HANGUL_TOKENS = 500
MIN_HANGUL_CHAR_RATIO = 0.20

# 깨짐 임계(1,000자당) — 실측 분포는 0.00~5.83이라 6 이상은 본 적 없는 수준이다
BAD_GARBLE = 6.0
SUSPECT_GARBLE = 3.0
GARBLE_BLOCKS = 40

_HANGUL_TOKEN = re.compile(r"^[가-힣]+$")
# 깨짐 = ①한글에 한자·소문자·기호가 공백 없이 붙음(기合·디지!i) ②OCR이 뱉는 기호
#        ③홀로 떠도는 자모 ④제어문자·대체문자.
# 가운뎃점(·∙)은 정상 한국어 문장부호라 뺀다 — 넣으면 각주 많은 논문이 전부 걸린다.
_GARBLE = re.compile(
    r"[가-힣][一-鿿a-z!@#$%^&*~`|\\/<>\[\]{}=+]"
    r"|[一-鿿a-z!@#$%^&*~`|\\/<>\[\]{}=+][가-힣]"
    r"|[■□▪●◆◇♦※〓＊¤†‡]|[ㄱ-ㆎ]|[\x00-\x08\x0b\x0e-\x1f\ufffd]")
_HANGUL_CHAR = re.compile(r"[가-힣]")
_CJK_CHAR = re.compile(r"[一-鿿]")
# 제어문자와 대체문자(U+FFFD) — 인코딩이 깨진 흔적
_ODD_CHAR = re.compile(r"[\x00-\x08\x0b\x0e-\x1f�]")


@dataclass
class Assessment:
    """한 권의 진단 결과. verdict = ok | suspect | bad | unknown"""
    verdict: str = "unknown"
    one_syllable_pct: float = 0.0
    hangul_tokens: int = 0
    hangul_char_ratio: float = 0.0
    cjk_ratio: float = 0.0
    odd_ratio: float = 0.0
    su_ok: int = 0            # "할 수 있" 정상형
    su_dropped: int = 0       # "할 있"   — 수 누락형
    garble_per_1k: float = 0.0
    word_loss: str = "unknown"   # 축 A — 낱말 유실
    garble: str = "unknown"      # 축 B — 문자 깨짐
    reasons: list[str] = field(default_factory=list)

    @property
    def needs_reocr(self) -> bool:
        return self.verdict == "bad"

    @property
    def badge(self) -> str:
        return {"bad": "🔴", "suspect": "🟡", "ok": "🟢"}.get(self.verdict, "⚪")

    def summary(self) -> str:
        if self.verdict == "unknown":
            return "판정 보류 — " + (self.reasons[0] if self.reasons else "표본 부족")
        head = f"1음절 {self.one_syllable_pct:.2f}% · 깨짐 {self.garble_per_1k:.1f}/천자"
        return head + " · " + " · ".join(self.reasons)


def garble_rate(text: str) -> float:
    """1,000자당 깨짐 건수. 본문을 토막내 **중앙값**을 쓴다 — 표지·판권·색인처럼
    원래 깨지는 앞뒤 구간이 책 전체 점수를 끌어올리지 않게."""
    if len(text) < GARBLE_BLOCKS * 200:                    # 짧으면 통째로
        return len(_GARBLE.findall(text)) / max(1, len(text)) * 1000
    size = len(text) // GARBLE_BLOCKS
    rates = sorted(len(_GARBLE.findall(text[i * size:(i + 1) * size])) / size * 1000
                   for i in range(GARBLE_BLOCKS))
    return rates[GARBLE_BLOCKS // 2]


_RANK = {"ok": 0, "suspect": 1, "bad": 2}


def assess(text: str) -> Assessment:
    """본문 TXT 한 덩어리를 진단한다. 판정 기준은 모듈 머리말 참고."""
    a = Assessment()
    if not text or not text.strip():
        a.reasons.append("본문이 비어 있습니다")
        return a

    total_chars = len(text)
    hangul_chars = len(_HANGUL_CHAR.findall(text))
    a.hangul_char_ratio = hangul_chars / total_chars
    a.cjk_ratio = len(_CJK_CHAR.findall(text)) / total_chars
    a.odd_ratio = len(_ODD_CHAR.findall(text)) / total_chars

    tokens = [w for w in text.split() if _HANGUL_TOKEN.match(w)]
    a.hangul_tokens = len(tokens)

    # 한국어 책이 아니면 이 잣대를 쓰지 않는다 (영문 원서 오탐 방지)
    if a.hangul_tokens < MIN_HANGUL_TOKENS or a.hangul_char_ratio < MIN_HANGUL_CHAR_RATIO:
        a.reasons.append("한국어 본문이 적어 1음절 검사를 적용하지 않았습니다")
        return a

    one = sum(1 for w in tokens if len(w) == 1)
    a.one_syllable_pct = one / a.hangul_tokens * 100

    a.su_ok = len(re.findall(r"[할될을] 수 있", text))
    a.su_dropped = len(re.findall(r"[할될을] (?!수)있", text))

    # ── 축 A: 낱말 유실 ──
    if a.one_syllable_pct < BAD_ONE_SYLLABLE:
        a.word_loss = "bad"
        a.reasons.append(
            f"1음절 한글 낱말이 {a.hangul_tokens:,}개 중 {one}개뿐"
            " — 수·것·될 같은 한 글자 낱말이 통째로 빠졌습니다")
    elif a.one_syllable_pct < SUSPECT_ONE_SYLLABLE:
        a.word_loss = "suspect"
        a.reasons.append("1음절 낱말 비율이 낮습니다(정상 7~25%)")
    else:
        a.word_loss = "ok"

    if a.su_dropped and a.su_ok == 0:
        a.reasons.append(
            f"`할 수 있`이 0회인데 `할 있`이 {a.su_dropped}회 — 의존명사 '수' 전량 누락")
    elif a.su_dropped > max(3, a.su_ok):
        a.reasons.append(f"`할 있`({a.su_dropped}) > `할 수 있`({a.su_ok})")

    # ── 축 B: 문자 깨짐 (축 A와 합치지 않는다 — 머리말 참고) ──
    a.garble_per_1k = garble_rate(text)
    if a.garble_per_1k >= BAD_GARBLE:
        a.garble = "bad"
        a.reasons.append(
            f"깨진 글자가 1,000자당 {a.garble_per_1k:.1f}건 — 기合·디지!i처럼 글자가 뭉개졌습니다")
    elif a.garble_per_1k >= SUSPECT_GARBLE:
        a.garble = "suspect"
        a.reasons.append(f"깨진 글자가 1,000자당 {a.garble_per_1k:.1f}건 — 눈으로 확인해 보세요")
    else:
        a.garble = "ok"

    if a.cjk_ratio > 0.02:
        a.reasons.append(f"한자 혼입 {a.cjk_ratio * 100:.1f}%")
        if a.garble == "ok":
            a.garble = "suspect"

    # 최종 판정 = 두 축 중 나쁜 쪽
    a.verdict = "bad" if _RANK[a.word_loss] == 2 or _RANK[a.garble] == 2 else (
        "suspect" if max(_RANK[a.word_loss], _RANK[a.garble]) == 1 else "ok")
    if a.verdict == "ok":
        a.reasons.append("낱말·글자 모두 정상")
    return a


def assess_file(path) -> Assessment:
    try:
        raw = Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        a = Assessment()
        a.reasons.append(f"읽기 실패: {type(e).__name__}")
        return a
    return assess(unicodedata.normalize("NFC", raw))
