"""번역: 어떤 언어든 → 고른 도착언어 — 언어 감지, 단락 분할, 번역 호출, skip/drop 필터.

출발언어를 영어로 한정하지 않는다(2026-08-15). 독일어·네덜란드어·프랑스어·라틴어
같은 라틴 문자권은 물론 일본어·중국어·러시아어처럼 문자 자체가 다른 원서도
services.langdetect가 무슨 언어인지 알아내고, 그 이름을 번역 프롬프트와 화면에
함께 쓴다.

도착언어도 설정에서 고른다(target_language, 기본 한국어). 도착언어가 한국어면
'번역이 필요한가' 판단이 예전과 똑같이 한글 비율 하나로 떨어지므로 기존 동작이
그대로 보존된다. 검증 방식은 도착언어의 문자 체계에 따라 갈린다 — 고유 문자를
쓰는 언어(한글·가나·키릴 …)는 문자 비율로 확실히 가리지만, 라틴 문자권끼리는
문자가 같아 그 방법이 통하지 않으므로 기능어 감지와 '원문과 거의 같은가' 검사에
맡긴다.

번역본 파일 이름은 **도착언어를 따른다**(2026-08-26 변경) — 스페인어면 `_es.txt`.
예전에는 늘 `_ko.txt`였는데 한국어가 도착언어가 아닐 때 이름이 사실과 어긋났다.
이미 만들어 둔 `_ko.txt`는 그 자리에 그대로 두고 계속 읽는다 — 아래
`find_translation()`이 현재 도착언어 → `_ko` → 그 밖의 언어 순으로 찾는다."""

import hashlib
import json
import re as _re
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path

import llm_providers as llm

from services import kospace, langdetect
from services.common import _save_json_atomic, append_log
from services.files import _save_bilingual_atomic

_KO_SCRIPT = _re.compile(r"[가-힣]")


DEFAULT_TARGET = "ko"

# 도착언어 후보 — 감지 가능한 언어를 그대로 도착언어로도 고를 수 있게 한다.
TARGET_CHOICES = ("ko", "en", "ja", "zh", "de", "fr", "es", "it", "pt", "nl", "ru")


def target_language() -> str:
    """번역·요약 결과를 쓸 언어 코드. 설정에서 바꾸며 기본은 한국어(2026-08-15)."""
    code = str(llm.get_pref("target_lang", DEFAULT_TARGET) or DEFAULT_TARGET)
    return code if code in langdetect.LANGUAGES else DEFAULT_TARGET


def set_target_language(code: str) -> None:
    if code in langdetect.LANGUAGES:
        llm.set_pref("target_lang", code)


def target_language_name() -> str:
    return language_name(target_language())


# ── 번역본 파일 이름 (2026-08-26) ──────────────────────────────────────
# 예전에는 도착언어와 무관하게 늘 `_ko.txt`였다. 한국어→스페인어처럼 한국어가
# 도착언어가 아니면 이름이 사실과 어긋난다(연구자 지적).
#
# ★**이미 만들어 둔 `_ko.txt` 번역본은 그 자리에 그대로 둔다.** 읽을 때는
# 현재 도착언어 → 예전 `_ko` → 그 밖의 알려진 언어 순으로 찾으므로 예전 파일도
# 계속 쓰인다. 새로 만드는 것만 새 이름을 쓴다 — 옮기거나 지우지 않는다.
LANG_SUFFIXES = tuple(f"_{_c}" for _c in TARGET_CHOICES)
# 챕터 목록에서 원문과 구분해 걸러내야 하는 파생물들
DERIVED_SUFFIXES = LANG_SUFFIXES + ("_wiki", "_bilingual", "_clean")


def out_suffix(target: str = "") -> str:
    """지금 도착언어의 파일 이름 접미사. 한국어면 예전과 같은 `_ko`."""
    return "_" + (target or target_language())


def translated_path(ch_path: Path, target: str = "") -> Path:
    """**새로 만들** 번역본 경로."""
    return ch_path.with_name(ch_path.stem + out_suffix(target) + ".txt")


def find_translation(ch_path: Path) -> Path | None:
    """**이미 있는** 번역본을 찾는다 — 현재 도착언어 → `_ko` → 그 밖의 언어 순.

    도착언어를 바꿔도 예전에 만들어 둔 번역본이 사라지지 않게 하는 자리다."""
    cur = translated_path(ch_path)
    if cur.exists():
        return cur
    for suf in ("_ko",) + LANG_SUFFIXES:
        p = ch_path.with_name(ch_path.stem + suf + ".txt")
        if p.exists():
            return p
    return None


def has_translation(ch_path: Path) -> bool:
    return find_translation(ch_path) is not None


def is_derived(stem: str) -> bool:
    """파생물(번역본·요약·대역·자간정리본)인가 — 원문 챕터 목록에서 뺄 것인가."""
    return stem.endswith(DERIVED_SUFFIXES)


def target_language_options() -> list[tuple[str, str]]:
    """[(코드, 화면에 쓸 이름)] — 설정 화면 선택지."""
    return [(c, language_name(c)) for c in TARGET_CHOICES]


def needs_translation(txt_path: Path, threshold: float = 0.3, target: str = "") -> bool:
    """번역이 필요한가 = 원문이 이미 도착언어가 아닌가.

    도착언어가 한국어면 예전과 똑같이 한글 비율 하나로 판단한다(분기 동작 보존).
    다른 언어를 고르면 감지 결과와 비교한다."""
    target = target or target_language()
    sample = txt_path.read_text(encoding="utf-8", errors="ignore")[:3000]
    if target == "ko":
        ko_ratio = len(_KO_SCRIPT.findall(sample)) / max(len(sample), 1)
        return ko_ratio < threshold
    return langdetect.detect(sample)[0] != target


def source_language(txt_path: Path) -> tuple[str, float]:
    """챕터 파일 하나의 원문 언어 (코드, 확신도). 책 단위 판단은 book_language를 쓸 것."""
    return langdetect.detect_file(txt_path)


def book_language(ch_paths) -> tuple[str, float]:
    """책 한 권의 원문 언어 — 여러 챕터를 섞어 판단한다(첫 장만 보면 참고문헌에 속는다)."""
    return langdetect.detect_book(ch_paths)


def language_name(code: str) -> str:
    """언어 코드 → 화면에 쓸 이름. UI 언어 설정을 따른다('독일어' / 'German')."""
    try:
        from services.i18n import get_lang
        return langdetect.name(code, get_lang())
    except Exception:
        return langdetect.name(code)


def _ko_ratio(text: str) -> float:
    return len(_KO_SCRIPT.findall(text or "")) / max(len(text or ""), 1)


_TRANSLATION_REFUSAL_PHRASES = (
    "\ubc88\uc5ed\ud560 \ud559\uc220 \ubb38\ub2e8\uc744 \uc544\uc9c1 \ubc1b\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4",
    "\ubc88\uc5ed\ud558\uc2e4 \ud14d\uc2a4\ud2b8",
    "\ud14d\uc2a4\ud2b8\ub97c \ubd99\uc5ec\ub123\uc5b4",
    "\uc6d0\ubb38\uc744 \uc81c\uacf5",
    "\ubcf8\ubb38\uc744 \ubcf4\ub0b4",
)

_TRANSLATION_REFUSAL_RE = _re.compile(
    r"(?:please\s+provide|send|paste).{0,80}(?:text|paragraph|source)|"
    r"(?:no|not|haven't|have\s+not).{0,80}(?:text|paragraph|source).{0,80}(?:translate|received)",
    _re.I | _re.S,
)


def _looks_like_translation_refusal(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if any(phrase in text for phrase in _TRANSLATION_REFUSAL_PHRASES):
        return True
    return bool(_TRANSLATION_REFUSAL_RE.search(lowered))


def _translation_is_valid(src: str, out: str | None, target: str = "") -> bool:
    """번역 결과가 실제로 도착언어 번역인지 확인한다."""
    if not out:
        return False
    target = target or target_language()
    cleaned_src = _re.sub(r"\s+", " ", src or "").strip()
    cleaned_out = _re.sub(r"\s+", " ", out or "").strip()
    if not cleaned_out:
        return False
    if _looks_like_translation_refusal(cleaned_out):
        return False
    # 도착언어가 고유 문자를 쓰면(한글·가나·키릴 …) 결과에 그 문자가 거의 없다는 건
    # 번역이 안 됐다는 뜻이다. 라틴 문자권이 도착언어면 원문과 문자가 같아 이 검사가
    # 무의미하므로 건너뛰고, 아래 '원문과 거의 같은가' 검사에 맡긴다(2026-08-15).
    if langdetect.has_own_script(target) and langdetect.script_ratio(cleaned_out, target) < 0.08:
        return False
    if cleaned_src and SequenceMatcher(None, cleaned_src[:2000], cleaned_out[:2000]).ratio() > 0.82:
        return False
    return True


_HEADING_LIKE_RE = _re.compile(r"^\s*(?:\d+(?:\.\d+)*|[IVXLC]+)\s+.+", _re.I)


def _translate_retry_prompt(paragraph: str, target: str = "") -> str:
    tgt = langdetect.name(target or target_language(), "en") or "Korean"
    return (
        f"Translate the following academic paragraph into {tgt}, whatever language it is in. "
        "Preserve numbering such as section numbers or chapter numbers. "
        "Do not leave any sentence or title untranslated in the source language. "
        "If this is a section heading, translate only the heading text while keeping the numbering. "
        f"Output ONLY the {tgt} text.\n\n"
        f"{paragraph}"
    )


def _translate_paragraph(paragraph: str, engine: str, glossary: dict | None = None,
                          src_lang: str = "", target: str = "") -> str | None:
    target = target or target_language()
    tgt_name = langdetect.name(target, "en") or "Korean"
    ko = translate(paragraph, engine, glossary=glossary, src_lang=src_lang, target=target)
    if _translation_is_valid(paragraph, ko, target):
        return ko
    if not paragraph.strip():
        return ko
    retry = translate(_translate_retry_prompt(paragraph, target), engine, glossary=glossary,
                      src_lang=src_lang, target=target)
    if _translation_is_valid(paragraph, retry, target):
        return retry
    if _HEADING_LIKE_RE.match(paragraph.strip()):
        heading_retry = translate(
            "This is a section heading from an academic chapter. Translate it into "
            f"{tgt_name} and keep the numbering.\n\n"
            f"{paragraph}",
            engine,
            glossary=glossary,
            src_lang=src_lang,
            target=target,
        )
        if _translation_is_valid(paragraph, heading_retry, target):
            return heading_retry
    return None


def translate_title(title: str, engine: str, src_lang: str = "",
                     target: str = "") -> str | None:
    """장 제목만 짧게 번역 — 실패·불확실하면 None(원제 그대로 유지 신호)."""
    if not title.strip() or not engine or ":" not in engine:
        return None
    target = target or target_language()
    ko = translate(title, engine, src_lang=src_lang, target=target)
    if not _translation_is_valid(title, ko, target):
        return None
    return _re.sub(r"\s+", " ", ko).strip()


# 한국어 도착일 때만 쓰는 문체 규칙 — 학술 평서체 고정, 높임말 금지.
_KO_STYLE_RULES = (
    "Use ONLY plain declarative academic Korean (평서체/하다체): "
    "endings such as -다, -이다, -한다, -였다, -이었다. "
    "DO NOT use any polite/honorific forms — never use -습니다, -입니다, "
    "-해요, -이에요, -지요, -군요, -네요, or any other -요/-니다 endings. "
)


def build_translate_system(src_lang: str = "", target: str = "") -> str:
    """번역 시스템 프롬프트. src_lang을 주면 원문 언어를 명시한다 — 독일어·네덜란드어처럼
    서로 닮은 언어에서 모델이 헷갈리는 것을 줄인다. target은 도착언어 코드(기본 설정값).
    한국어 도착일 때의 문체 규칙(평서체·높임말 금지)은 그 언어에만 해당하므로, 다른
    언어를 고르면 일반적인 학술 문어체 지시로 갈음한다(2026-08-15)."""
    target = target or target_language()
    tgt_name = langdetect.name(target, "en") or "Korean"
    src_name = langdetect.name(src_lang, "en") if src_lang else ""
    src_hint = (f"The source text is written in {src_name}. "
                if src_name and src_lang != target else
                "Detect the source language automatically. ")
    style = _KO_STYLE_RULES if target == "ko" else (
        f"Write in formal academic prose appropriate for scholarly writing in {tgt_name}; "
        "do not use conversational or promotional register. "
    )
    return (
        "You are a professional theological/academic translator. "
        + src_hint +
        f"Translate the user's text into {tgt_name}. "
        f"Proper nouns (personal names, place names): on FIRST mention write the {tgt_name} "
        "rendering followed by the original in parentheses; "
        f"if a name is listed below as already introduced, write the {tgt_name} form ONLY. "
        "Preserve technical terms and scripture references as-is. "
        + style +
        "The text may be an incomplete fragment cut mid-sentence (PDF page breaks): "
        "translate it as-is anyway — NEVER comment on it, NEVER ask for more context, "
        "NEVER say the text is incomplete. "
        f"Output ONLY the {tgt_name} translation, nothing else."
    )

# 번역 엔진 ID (UI 라디오와 1:1)
# 번역 엔진 id = "provider:model". 공급자는 llm_providers.PROVIDERS + Claude CLI(구독).
_translate_error_logged = False


def translate_engine_options() -> list[tuple[str, str, bool, str]]:
    """[(engine_id, label, available, hint)]. 키 있는 공급자만 available=True."""
    opts: list[tuple[str, str, bool, str]] = []
    for prov in llm.API_PROVIDERS:
        info = llm.PROVIDERS[prov]
        avail = llm.has_key(prov)
        for m in info["models"]:
            opts.append((f"{prov}:{m}", f"{m} · {info['label']}", avail, info["hint"]))
    for prov in llm.CLI_PROVIDERS:
        info = llm.PROVIDERS[prov]
        avail = llm.has_key(prov)
        for m in info["models"]:
            opts.append((f"{prov}:{m}", f"{m} · {info['label']}", avail, info["hint"]))
    return opts


def engine_label(engine_id) -> str:
    if not engine_id:
        return "?"
    for eid, lbl, _av, _h in translate_engine_options():
        if eid == engine_id:
            return lbl
    return engine_id


def _merge_dangling(paras: list[str], max_chunk: int = 3000) -> list[str]:
    """PDF 페이지 경계·각주 번호 때문에 문장 중간에서 끊긴 단락을 병합. (2026-06-11)
    이전 단락이 종결부호 없이 끝났거나 현재 단락이 소문자로 시작하면 같은 문장으로 본다."""
    _terminal = _re.compile(r'[.!?:;"”’)\]]\s*$')
    merged: list[str] = []
    # ★쪽을 넘는 문장을 잇기 위한 «미룸 상자» (2026-08-27 연구자 요청 — "다음
    #   페이지로 가기 전에 문장마침이 되지 않으면 다음 페이지의 문장까지 보고
    #   번역한다").
    #
    #   예전에는 각주·쪽표식을 만나면 그 자리에서 그대로 내보냈다. 그런데 실제 논문
    #   흐름은 «본문 … 각주34 각주35 각주36 [[PAGEBREAK]] 다음쪽 본문» 이라,
    #   문장 중간에서 끊긴 본문과 그 뒷부분 사이에 **각주 세 덩이와 쪽표식이 끼어**
    #   있다. 그래서 이어 붙일 기회가 아예 오지 않았고, 한 문장이 두 조각으로 나뉘어
    #   각각 번역돼 «어색한 곳이 곳곳에» 남았다.
    #
    #   이제 사이에 낀 것들은 상자에 담아 두었다가, 본문끼리 이어 붙인 **뒤에**
    #   내보낸다. 각주는 여전히 홀로 서고 쪽표식도 그대로 남으므로(→  보존),
    #   EPUB 각주 변환은 하던 대로 돌아간다. 달라지는 것은 쪽을 걸친 문장의 꼬리가
    #   제 머리 쪽으로 따라붙는다는 것뿐이다 — 각주 번호도 제 쪽에 함께 남는다.
    pending: list[str] = []
    for p in paras:
        if _is_footnote_block(p):
            pending.append(p)          # 각주·쪽표식은 잠시 미룬다
            continue
        prev = merged[-1] if merged else ""
        if (prev
                and not _is_footnote_block(prev)
                and not prev.lstrip().startswith("#")      # 제목은 단독 유지
                and len(prev) + len(p) + 1 <= max_chunk
                and (not _terminal.search(prev) or _re.match(r"^[a-z]", p))):
            merged[-1] = prev.rstrip() + " " + p.lstrip()
        else:
            merged.extend(pending)     # 못 이으면 낀 것들을 먼저 제자리에
            pending = []
            merged.append(p)
            continue
        merged.extend(pending)         # 이었으면 그 뒤에 붙인다
        pending = []
    merged.extend(pending)
    return merged


def _is_footnote_block(b: str) -> bool:
    """이 블록을 **홀로 두어야** 하는가 — 각주 문단, 또는 쪽 구분 표식.

    각주: 번호로 시작하는 짧은 글. 짧다는 이유로 앞뒤 문단에 합쳐지면 안 된다.
    쪽 구분 표식(_PAGE_TOKEN): 13자뿐이라 그냥 두면 합쳐져 사라진다 — 그러면 번역본에
     가 남지 않고, EPUB 각주 변환기가 쪽을 못 나눠 각주를 거의 못 잡는다
    (2026-08-27)."""
    s = b.strip()
    if s == _PAGE_TOKEN:
        return True
    # ★길이 조건은 없앴다 (2026-08-27 연구자: "각주의 길이는 문제가 되지 않아").
    # 500자 제한이던 때 Dorobantu 논문의 5번 각주(544자, 책 네 권을 나열한 서지)가
    # 각주로 인정받지 못하고 앞 본문 문단에 합쳐져 EPUB에서 통째로 사라졌다.
    # 서지 각주는 책을 여러 권 나열하면 얼마든지 길어진다 — 길이는 각주 여부를 가르는
    # 기준이 될 수 없다. **번호로 시작하는가**만 본다.
    #
    # 여기는 **문단 합치기를 막을지**만 정하므로 넉넉해도 손해가 없다. 본문 문단이
    # 우연히 번호로 시작해 걸리더라도, 원래 제 문단이던 것을 그대로 두는 것뿐이다.
    return bool(s and _FOOTNOTE_NUM_START.match(s))


def _merge_short_blocks(blocks: list[str], min_len: int = 50) -> list[str]:
    """min_len 이하인 블록을 뒤 블록과 이어 붙여 min_len을 넘을 때까지 합친다 —
    짧다고 통째로 버리지 않는다(2026-08-11). 사진촬영 OCR은 문단이 아니라 거의
    줄 단위로 \n\n이 남발되는 경우가 많아, 예전처럼 50자 이하 블록을 그냥 버리면
    책 내용의 상당 부분(실측: 어떤 책은 전체 글자 수의 70%)이 조용히 사라진다.

    ★**각주는 짧아도 합치지 않는다** (2026-08-27 연구자 지적). 변환 단계에서 애써
    제 문단으로 떼어 낸 각주가 여기서 도로 본문에 붙었다 — `3 Psalm 8:4.`(12자)가
    앞 본문 문단에 먹히는 식이다. 실측: 원문 문단 162개가 번역을 거치며 57개로,
    각주 문단 15개가 6개로 줄었고, 그래서 EPUB에서 각주가 본문과 섞여 나왔다.
    각주는 어차피 번역하지 않으므로(should_skip_translation) 홀로 두는 편이 맞다."""
    merged: list[str] = []
    buf = ""
    for b in blocks:
        if _is_footnote_block(b):
            if buf:                       # 모아 두던 짧은 것들을 먼저 내보낸다
                merged.append(buf)
                buf = ""
            merged.append(b)              # 각주는 제 문단 그대로
            continue
        buf = (buf + "\n\n" + b).strip() if buf else b
        if len(buf) > min_len:
            merged.append(buf)
            buf = ""
    if buf:
        if merged:
            merged[-1] = merged[-1] + "\n\n" + buf
        else:
            merged.append(buf)
    return merged


def _split_paragraphs_robust(text_raw: str, target_chunk: int = 1500, min_para: int = 5) -> list[str]:
    """단락 분할 보강. \\n\\n 의존이 실패하면 단일 줄바꿈·문장 단위 fallback.
    OCR 출력 형식에 무관하게 작동. (2026-05-16 신설)

    1차: \\n\\n 분리 후 50자 이하 블록은 뒤 블록과 병합(내용 손실 방지). 단락 수 ≥
    min_para 이고 평균 길이 ≤ target_chunk*2 이면 통과.
    2차: \\n 단일 분리 후 target_chunk 자 단위 누적 청크.
    3차: 문장(. ! ?) 단위 분리 후 target_chunk 자 단위 누적 청크.
    """
    _raw_blocks = [p.strip() for p in text_raw.split("\n\n") if p.strip()]
    primary = _merge_short_blocks(_raw_blocks, 50)
    if len(primary) >= min_para:
        avg = sum(len(p) for p in primary) / len(primary)
        if avg <= target_chunk * 2:
            return _merge_dangling(primary)

    # 2차 — 단일 줄바꿈 후 누적 청크
    lines = [ln.strip() for ln in text_raw.split("\n") if ln.strip()]
    chunks: list[str] = []
    buf = ""
    for ln in lines:
        if len(buf) + len(ln) + 1 <= target_chunk:
            buf = (buf + " " + ln).strip() if buf else ln
        else:
            if buf:
                chunks.append(buf)
            buf = ln
    if buf:
        chunks.append(buf)
    if len(chunks) >= min_para:
        return chunks

    # 3차 — 문장 단위 누적 청크
    sentences = _re.split(r"(?<=[.!?])\s+", text_raw.replace("\n", " "))
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    chunks = []
    buf = ""
    for s in sentences:
        if len(buf) + len(s) + 1 <= target_chunk:
            buf = (buf + " " + s).strip() if buf else s
        else:
            if buf:
                chunks.append(buf)
            buf = s
    if buf:
        chunks.append(buf)
    return chunks if chunks else primary  # 정말 아무것도 안 잡히면 1차 반환


def translate(text: str, engine: str, glossary: dict | None = None,
               src_lang: str = "", target: str = "") -> str | None:
    """단락 하나를 'provider:model' 엔진으로 한국어 번역. 실패 시 None(원문 유지).
    glossary: 앞 단락들에서 이미 소개된 고유명사 {원어: 한글} — 한글만 쓰게 지시.
    src_lang: 감지된 원문 언어 코드(있으면 프롬프트에 명시)."""
    global _translate_error_logged
    if not engine or ":" not in engine:
        return None
    provider, model = engine.split(":", 1)
    sys_prompt = build_translate_system(src_lang, target)
    if glossary:
        # 이미 소개된 고유명사 — 목표 언어 표기만 쓰게 지시 (최근 80개 제한)
        _pairs = "; ".join(f"{en} = {ko}" for en, ko in list(glossary.items())[-80:])
        sys_prompt += " Already-introduced proper nouns (target-language form only, no parentheses): " + _pairs
    try:
        out = llm.complete(provider, model, sys_prompt, text, max_tokens=8192)
        return out.strip() or None
    except Exception as e:
        if not _translate_error_logged:
            append_log(f"ERROR: 번역 실패 [{engine}] ({type(e).__name__}): {str(e)[:300]}")
            _translate_error_logged = True
        return None


# ─────────────────────────────────────────────────────────────────────────────
# P6. 각주·미주·인용 번역 skip (2026-05-17 추가)
# 학술 인용은 번역 가치 낮음 (저자명·연도·DOI·URL 형식). 원어 보존이 학술 추적
# 에 유리. 본 PDF 검증: 단락의 ~49% skip → 번역 비용·시간 절반 절감.
# ─────────────────────────────────────────────────────────────────────────────

_FOOTNOTE_DAGGER    = _re.compile(r"^\s*†\s")
_CITATION_NUMBERED  = _re.compile(r"^\s*\[?[0-9]+\*?\]?\s+[A-Z][^.]*,\s+[A-Z]")
_CITATION_BULLET    = _re.compile(r"^\s*-\s+[0-9]+\*?\s+[A-Z]")
_CITATION_URL_HEAVY = _re.compile(r"(https?://|arXiv|doi\.org|dx\.doi)", _re.IGNORECASE)
# 단독 페이지번호·그래프 레이블: 숫자·공백·쉼표·점·하이픈만으로 이루어진 짧은 단락
# "100", "80", "3,000 4,000 5,000", "1-10" 등 → 번역 불필요
_PAGE_NUMBER_ONLY   = _re.compile(r"^[\d\s,.\-–—%]+$")
# OCR 분리 또는 일반 각주 번호로 시작하는 단락 감지
# "1 ", "[1] ", "1.", "1)", "1 0 " (OCR split 10), "1 2 " (OCR split 12) 등
_FOOTNOTE_NUM_START = _re.compile(
    r"^\s*(?:"
    r"\[?\d{1,3}\]?[\s.,):]"    # 일반: [1] · 1. · 1) · 1:
    r"|"
    r"\d\s\d[\s.,):]"           # OCR 분리 두 자리: "1 0 " "2 3." 등
    r")\s*\S"
)
# 소제목·목차 오탐 방지: 인용 마커(숫자·참조 키워드) 없는 짧은 텍스트를 각주로 처리 안 함
_RE_CITE_MARKER = _re.compile(
    r"\d|같은|참조|ibid|op\.|p\.|각주|위의|앞의|출처|see\s|cf\.", _re.IGNORECASE
)
_RE_EDITION_INFO = _re.compile(r"^판\s*\d")   # "판 1 쇄…" 등 출판 판수 정보
# 명시적 인용 마커: 쪽수·연도·저자이니셜·성경책·URL 등 — 소제목과 구별
_RE_EXPLICIT_CITE = _re.compile(
    r"같은\s*책|위의\s*책|앞의\s*책|ibid|op\.\s*cit|"
    r"p\.\s*\d+|pp\.\s*\d+|각주\s*\d|"
    r"\d+\s*쪽|쪽[,. ]|"
    r"[A-Z][a-z]{1,15},\s+[A-Z]|"          # Author, I. 패턴
    r"\b(19|20)\d{2}[),]|"                 # (2020) 또는 2020) 연도
    r"마태|누가복음|요한복음|로마서|고린도|갈라디|에베|"
    r"시편\s*\d|잠언\s*\d|창세기|출애굽|이사야|예레미야|"
    r"https?://|doi:\s*10|www\.",
    _re.IGNORECASE
)


def _is_short_heading(text: str) -> bool:
    """목차·소제목(각주 아님) 판별: 20자 이하이고 인용 마커가 없으면 True."""
    text = text.strip()
    if _RE_EDITION_INFO.match(text):   # "판 N 쇄" 형태 = 출판 정보
        return True
    if len(text) > 20:
        return False
    return not _RE_CITE_MARKER.search(text)


def _parse_footnote_number(p: str) -> int | None:
    """단락 선두 각주 번호를 정수로 반환. OCR 분리 숫자("1 0"→10) 포함. 없으면 None.

    오탐 방지:
    - 줄바꿈 포함 → 섹션 제목+본문 합체, None
    - "1.3.4" 형태 소단원 번호 → None
    - 20자 이하 + 인용 마커 없음 → 목차·소제목, None
    """
    p = p.strip()
    # 줄바꿈 포함 = 섹션 본문(제목+내용) → 각주 아님
    if "\n" in p:
        return None
    # OCR 분리 두 자리 숫자 우선 ("1 0 text" → 10)
    m = _re.match(r"^(\d)\s(\d)[\s.,):]\s*\S", p)
    if m:
        remaining = p[m.end() - 1:].strip()
        if _is_short_heading(remaining):
            return None
        return int(m.group(1) + m.group(2))
    # 일반 숫자 (최대 3자리): 구분자가 "."이고 바로 뒤가 숫자면 소수점 → 제외
    m = _re.match(r"^\[?(\d{1,3})\]?([\s.,):])(.)", p)
    if m:
        sep, nxt = m.group(2), m.group(3)
        if sep == "." and nxt.isdigit():   # "1.3.4" 같은 소단원 번호
            return None
        remaining = p[m.end() - 1:].strip()
        if _is_short_heading(remaining):
            return None
        return int(m.group(1))
    return None


def find_sequential_footnotes(paragraphs: list[str], min_run: int = 3,
                               max_len: int = 300) -> set[int]:
    """연속 번호(1,2,3…)로 이루어진 각주 단락 인덱스를 반환.

    조건:
    - 단락이 각주 번호로 시작하고 max_len 이하
    - 3개 이상 연속 증가 번호 묶음(run)이 존재
    OCR 분리 숫자("1 0" = 10)도 처리.

    오탐 방지 (Q&A 문답/목차 구조):
    - 첫 번째 런 위치가 문서 앞 50% 이내 AND 감지 비율 > 15% → 본문 구조로 판정, 빈 셋 반환
    """
    total = len(paragraphs)
    # (index, number) 후보 수집
    candidates: list[tuple[int, int]] = []
    for i, p in enumerate(paragraphs):
        if len(p.strip()) > max_len:
            continue
        n = _parse_footnote_number(p)
        if n is not None and 1 <= n <= 999:
            candidates.append((i, n))

    if len(candidates) < min_run:
        return set()

    skip: set[int] = set()
    # 연속 run 탐지: n, n+1, n+2 … 가 연달아 나오는 구간 찾기
    run_start = 0
    first_run_idx: int | None = None
    for k in range(1, len(candidates)):
        prev_n = candidates[k - 1][1]
        curr_n = candidates[k][1]
        if curr_n != prev_n + 1:
            run_len = k - run_start
            if run_len >= min_run:
                if first_run_idx is None:
                    first_run_idx = candidates[run_start][0]
                for j in range(run_start, k):
                    skip.add(candidates[j][0])
            run_start = k
    # 마지막 run 처리
    run_len = len(candidates) - run_start
    if run_len >= min_run:
        if first_run_idx is None:
            first_run_idx = candidates[run_start][0]
        for j in range(run_start, len(candidates)):
            skip.add(candidates[j][0])

    if not skip:
        return set()

    # Q&A 문답·목차 오탐 방지: 첫 런이 앞 50%에 있고 감지 비율이 15% 초과면 제외
    if first_run_idx is not None and total > 0:
        position_ratio = first_run_idx / total
        detect_ratio   = len(skip) / total
        if position_ratio < 0.5 and detect_ratio > 0.15:
            return set()

    # 명시적 인용 마커 부재 시 오탐 처리: 소제목·통계표 등 비인용 구조
    # 정상 각주는 반드시 쪽수·저자·성경책명·URL 등 하나 이상 포함
    has_any_cite = any(
        _RE_EXPLICIT_CITE.search(paragraphs[i])
        for i in skip
        if i < total
    )
    if not has_any_cite:
        return set()

    return skip

_SKIP_SECTION_NAMES = {
    "references", "bibliography", "works cited", "참고문헌",
    "literaturverzeichnis", "bibliographie", "références",
    "referencias", "参考文献", "referências", "referenties",
    "список литературы", "список источников",   # Russian
    "المراجع", "قائمة المراجع",                  # Arabic
    "ביבליוגרפיה", "מקורות",                      # Hebrew
    "ማጣቀሻዎች",                                    # Amharic
    "tài liệu tham khảo",                        # Vietnamese
    "daftar pustaka", "referensi",               # Indonesian
    "รายการอ้างอิง",                               # Thai
}


def _paragraph_already_target(paragraph: str, threshold: float = 0.6,
                               target: str = "") -> bool:
    """단락이 이미 도착언어면 True(번역 생략 신호).

    도착언어가 고유 문자를 쓰면 그 문자 비율로 판단한다. 라틴 문자권이면 문자만으로는
    프랑스어와 영어를 못 가르므로 기능어 감지에 맡기고, 확신이 없으면 False를 준다 —
    여기서 틀리면 번역해야 할 단락이 원문 그대로 남기 때문이다(2026-08-15)."""
    p = paragraph.strip()
    if not p:
        return False
    target = target or target_language()
    if langdetect.has_own_script(target):
        return langdetect.script_ratio(p, target) >= threshold
    return langdetect.looks_like(p, target)


# ★쪽 구분자()를 번역 너머로 실어 나르는 표식 (2026-08-27).
# EPUB 각주 변환기(services/footnotes)는 **쪽 단위**로 각주 묶음을 찾는데, 번역본에는
#  가 하나도 없어서 문서 전체를 한 쪽으로 보고 각주를 거의 못 잡았다 — 그래서 1번
# 각주 뒤에 본문이 통째로 이어져 보였다. 번역 전에 제 문단으로 세워 두고, 번역이
# 끝나면 다시  로 되돌린다.
_PAGE_TOKEN = "[[PAGEBREAK]]"


# 번호로 시작하지만 본문인 단락을 가려낸다 — 각주·참고문헌과 구별한다.
_SENTENCE_END = _re.compile(r"[.!?。？！]\s*$|[다요음임함]\.?\s*$")


def _looks_like_body_sentence(p: str) -> bool:
    """앞의 번호를 떼어 낸 나머지가 «문장»으로 보이는가.

    각주·참고문헌은 대개 짧고 서지 표기(같은 책·p. 12·ibid)를 달고 있다.
    본문 목록·성경 절은 온전한 문장으로 끝난다."""
    rest = _re.sub(r"^\s*\[?\d{1,3}\]?[\s.,):]+\s*", "", p).strip()
    if len(rest) < 25:                    # 너무 짧으면 판단 보류 — 기존대로 각주 처리
        return False
    if _RE_EXPLICIT_CITE.search(rest):    # 서지 표기가 있으면 각주다
        return False
    return bool(_SENTENCE_END.search(rest))


def should_skip_translation(paragraph: str) -> bool:
    """단락 번역 생략 조건: 인용·각주 (이미 목표 언어 단락은 캐시로 별도 처리)."""
    p = paragraph.strip()
    if not p or p == _PAGE_TOKEN:
        return True
    if _FOOTNOTE_DAGGER.match(p):
        return True
    if _CITATION_NUMBERED.match(p):
        return True
    if _CITATION_BULLET.match(p):
        return True
    # OCR 분리 포함 각주 번호 시작 + 짧은 단락
    # 다만 번호로 시작한다고 다 각주가 아니다 — 번호 목록(«1. 사람은 …»)과
    # 성경 절(«31 너희는 남에게 …»)은 본문이다. 설교문을 독일어로 번역했더니
    # 그런 줄만 한국어로 남아 산출물에 섞였다. 번호를 떼어 낸 나머지가 온전한
    # 문장이면 본문으로 본다 — 각주를 몇 개 더 번역하는 손해가, 본문을 통째로
    # 빼먹는 손해보다 훨씬 작다. (2026-08-31)
    if len(p) < 500 and _FOOTNOTE_NUM_START.match(p) and not _looks_like_body_sentence(p):
        return True
    # 짧고 URL 들어간 단락 = 인용일 가능성 (500자 이하 + arXiv/DOI/URL)
    if len(p) < 500 and _CITATION_URL_HEAVY.search(p):
        return True
    return False


def should_drop_paragraph(paragraph: str) -> bool:
    """bilingual에서 완전 제외할 단락 — 번역·미주 어디에도 포함하지 않음.
    페이지 번호, 그래프 Y축 레이블 등 번역 결과물에 불필요한 OCR 잡음."""
    p = paragraph.strip()
    if not p:
        return True
    # 숫자·공백·구두점만으로 이루어진 80자 이하 단락 (페이지번호·그래프레이블)
    if len(p) <= 80 and _PAGE_NUMBER_ONLY.match(p):
        return True
    return False


def find_skip_section_paragraphs(paragraphs: list[str]) -> set[int]:
    """`## References` 헤더 ~ 다음 `## ` 헤더 전까지 단락 인덱스 집합 반환.

    `## Glossary`는 *번역 유지* — 학술 용어 한글 번역이 본 논문 자료로 유용.

    헤더가 없는 미주 영역도 tail 휴리스틱으로 자동 감지 (2026-05-18 추가):
    PDF→MD 변환 과정에서 References/Bibliography 헤더가 누락된 경우, 단락 끝쪽의
    마지막 *narrative* 단락(>=400자, 인용 신호 없음) 이후가 미주로 추정되면 skip.
    """
    skip_idxs: set[int] = set()
    in_skip = False
    for i, p in enumerate(paragraphs):
        stripped = p.strip()
        if stripped.startswith("## "):
            section = stripped[3:].strip().lower()
            if section in _SKIP_SECTION_NAMES:
                in_skip = True
                skip_idxs.add(i)
                continue
            in_skip = False
            continue
        if in_skip:
            skip_idxs.add(i)

    # tail 자동 감지: 헤더 기반 skip이 *없을 때만* 발동 (오탐 방지)
    if not skip_idxs and len(paragraphs) >= 50:
        scan_start = int(len(paragraphs) * 0.6)
        last_narrative = -1
        for i in range(len(paragraphs) - 1, scan_start - 1, -1):
            p = paragraphs[i].strip()
            if (
                len(p) >= 400
                and not _CITATION_URL_HEAVY.search(p)
                and not _CITATION_NUMBERED.match(p)
                and not _CITATION_BULLET.match(p)
                and not _FOOTNOTE_DAGGER.match(p)
                and not _FOOTNOTE_NUM_START.match(p)
            ):
                last_narrative = i
                break
        if 0 <= last_narrative < len(paragraphs) - 5:
            for i in range(last_narrative + 1, len(paragraphs)):
                skip_idxs.add(i)

    return skip_idxs


_HANGUL_RE = _re.compile(r'[가-힣ᄀ-ᇿ㄰-㆏]')

def _needs_translation(stem: str, target: str = "") -> bool:
    """챕터 파일이 아직 없을 때 쓰는 **임시 판단** — 책 제목의 문자만 보고 가린다.

    도착언어가 한국어면 예전과 똑같다: 제목에 한글이 없으면 번역이 필요하다고 본다.
    다른 언어가 도착언어면 제목을 감지해 도착언어와 다른지 본다(2026-08-26 — 예전에는
    '한글이 없으면 번역'이 박혀 있어 도착언어를 바꿔도 한국어 책은 번역 대상이
    되지 않았다).

    제목은 짧아 감지가 확실하지 않다. 모르겠으면 **번역 대기로 보낸다** — 실제 번역
    단계에서 이미 도착언어인 단락은 건너뛰므로 잘못 보내도 손해가 없고, 반대로 빠뜨리면
    사람이 알아채기 어렵다."""
    target = target or target_language()
    if target == "ko":
        return not bool(_HANGUL_RE.search(stem))
    return langdetect.detect(stem)[0] != target


_CLEAN_WORKERS_DEFAULT = 3


def clean_workers() -> int:
    """자간정리 묶음을 동시에 몇 개까지 던질지. codex/claude CLI는 호출마다 별도
    프로세스라 GIL과 무관하게 그대로 병렬로 붙는다(2026-08-14)."""
    try:
        n = int(llm.get_pref("clean_workers", _CLEAN_WORKERS_DEFAULT))
    except (TypeError, ValueError):
        n = _CLEAN_WORKERS_DEFAULT
    return max(1, min(n, 8))


def _ask_breaks(lines: list[str], idxs: list[int], engine: str) -> dict[int, str]:
    """줄바꿈 묶음 하나를 AI에 물어 {줄 인덱스: 'J'|'S'}로. 실패하면 빈 dict —
    답을 못 받은 자리는 공백으로 남아 손대기 전 원문과 같아지므로 그대로 안전하다."""
    if not engine or ":" not in engine:
        return {}
    provider, model = engine.split(":", 1)
    try:
        out = llm.complete(provider, model, kospace.build_system(),
                           kospace.format_questions(lines, idxs), max_tokens=4096)
    except Exception as e:
        append_log(f"WARN: 자간정리 판정 실패 [{engine}] ({type(e).__name__}): {str(e)[:200]}")
        return {}
    return {idxs[n - 1]: v for n, v in kospace.parse_answers(out, len(idxs)).items()}


def _is_mostly_korean(text: str, threshold: float = 0.3) -> bool:
    sample = text[:1000]
    return len(_KO_SCRIPT.findall(sample)) / max(len(sample), 1) >= threshold


def clean_chapter_ko(ch_path: Path, engine: str, progress_cb=None) -> tuple[bool, str]:
    """챕터 TXT의 OCR 줄바꿈을 복원해 <stem>_clean.txt로 저장. (ok, msg).

    AI에는 줄바꿈마다 '붙임/공백'만 묻고(kospace) 공백을 넣는 일은 여기서 한다 —
    본문 글자가 AI를 거치지 않으므로 내용이 바뀔 수 없고, 출력 토큰이 예전 방식의
    10분의 1 수준이라 호출도 훨씬 빠르다(2026-08-14). 묶음은 여러 개를 동시에
    던지며(clean_workers), 판정 결과는 _clean.progress.json에 남겨 중단 후 다시
    부르면 이미 받은 판정은 건너뛰고 이어서 처리한다.

    progress_cb(idx, total, 붙임, 공백, 미판정) — 번역 진행 콜백과 인자 모양을 맞췄다.
    콜백은 항상 이 함수를 부른 스레드에서만 불린다(Streamlit 위젯 갱신이 워커
    스레드에서는 조용히 무시되기 때문)."""
    try:
        text = ch_path.read_text(encoding="utf-8", errors="ignore")
        clean_path = ch_path.with_name(ch_path.stem + "_clean.txt")
        progress_path = ch_path.with_name(ch_path.stem + "_clean.progress.json")
        lines, kinds = kospace.plan(text)
        if not lines:
            return False, "본문 없음"
        pending = kospace.pending_indexes(kinds)
        total = len(pending)
        fingerprint = f"{len(text)}:{hashlib.sha1(text.encode('utf-8')).hexdigest()[:16]}"

        # 이어하기 — 원문이 그대로일 때만(fingerprint 일치) 예전 판정을 재사용한다.
        decided: dict[int, str] = {}
        if progress_path.exists():
            try:
                cached = json.loads(progress_path.read_text(encoding="utf-8"))
                if isinstance(cached, dict) and cached.get("fingerprint") == fingerprint:
                    decided = {int(k): v for k, v in (cached.get("decisions") or {}).items()
                               if v in (kospace.JOIN, kospace.SPACE)}
            except Exception:
                decided = {}

        todo = [i for i in pending if i not in decided]
        batches = [todo[i:i + kospace.BREAKS_PER_CALL]
                   for i in range(0, len(todo), kospace.BREAKS_PER_CALL)]
        done = total - len(todo)

        def _report():
            if progress_cb:
                joined = sum(1 for v in decided.values() if v == kospace.JOIN)
                progress_cb(done, total, joined, len(decided) - joined, done - len(decided))

        _report()
        if batches and engine and ":" in engine:
            with ThreadPoolExecutor(max_workers=min(clean_workers(), len(batches))) as pool:
                futures = {pool.submit(_ask_breaks, lines, b, engine): b for b in batches}
                for fut in as_completed(futures):
                    try:
                        decided.update(fut.result())
                    except Exception as e:
                        append_log(f"WARN: 자간정리 묶음 실패 ({type(e).__name__}): {str(e)[:150]}")
                    done += len(futures[fut])
                    _save_json_atomic(progress_path, {
                        "fingerprint": fingerprint,
                        "decisions": {str(k): v for k, v in decided.items()},
                    })
                    _report()

        for i, v in decided.items():
            if 0 <= i < len(kinds) and kinds[i] is None:
                kinds[i] = v
        out = kospace.render(lines, kinds)
        # 설계상 공백 말고는 달라질 수 없지만, 줄 분해·재조립 실수까지 잡으려고 확인한다.
        if _re.sub(r"\s+", "", out) != _re.sub(r"\s+", "", text):
            return False, "본문이 달라져 저장하지 않음"
        # 물어볼 게 있었는데 한 건도 못 받았으면 저장하지 않는다 — 원문과 다를 바 없는
        # _clean.txt를 남기면 '정리됨'으로 보여 다시 시도할 길이 막힌다.
        if total and not decided:
            return False, "AI 판정을 받지 못했습니다 — 잠시 후 다시 시도하세요"

        clean_path.write_text(out, encoding="utf-8")
        unknown = total - len(decided)
        if unknown:
            # 일부만 받았으면 진행 파일을 남겨 둔다: 받은 판정은 이미 반영됐고,
            # 다시 실행하면 남은 것만 이어서 묻는다(chapters_needing_clean이 이 파일을 본다).
            _save_json_atomic(progress_path, {
                "fingerprint": fingerprint,
                "decisions": {str(k): v for k, v in decided.items()},
            })
        else:
            progress_path.unlink(missing_ok=True)
        joined = sum(1 for v in decided.values() if v == kospace.JOIN)
        paras = sum(1 for k in kinds if k == kospace.PARA) + 1
        return True, (f"{paras}단락 · 줄바꿈 {len(kinds)} "
                      f"(붙임 {joined} · 공백 {len(decided) - joined} · 미판정 {unknown})")
    except Exception as e:
        return False, str(e)[:200]


def translate_one_chapter(ch_path: Path, engine: str, progress_cb=None,
                           want_plain: bool = True, want_bilingual: bool = False) -> tuple[bool, str]:
    """단일 챕터 TXT 번역. want_plain이면 번역본(도착언어 접미사), want_bilingual이면 원문·번역을
    문단별로 나란히 묶은 _bilingual.txt도 저장(둘 다 켜면 둘 다 저장). (ok, msg).

    중단 대비 (2026-07-03): Streamlit rerun 등으로 도중에 죽어도 진행분이
    읽을 수 있는 partial.md로 남는다. 완주하면 번역본으로 확정하고
    partial·progress 캐시를 정리한다.
    (.md인 이유: .txt면 챕터 목록 glob(??_*.txt)에 원문으로 오인된다.)"""
    try:
        text = ch_path.read_text(encoding="utf-8", errors="ignore")
        text = text.replace("\f", "\n\n" + _PAGE_TOKEN + "\n\n")
        _suf = out_suffix()                       # 도착언어에 따라 _ko·_es …
        ko_path = ch_path.with_name(ch_path.stem + _suf + ".txt")
        bilingual_path = ch_path.with_name(ch_path.stem + "_bilingual.txt")
        partial_path = ch_path.with_name(ch_path.stem + _suf + ".partial.md")
        progress_path = ch_path.with_name(ch_path.stem + _suf + ".progress.json")
        if not needs_translation(ch_path):
            if want_plain:
                ko_path.write_text(text.replace(_PAGE_TOKEN, "\f"), encoding="utf-8")
            partial_path.unlink(missing_ok=True)
            progress_path.unlink(missing_ok=True)
            return True, f"이미 {target_language_name()} — 그대로 복사"
        # 원문 언어를 한 번만 감지해 모든 단락 호출에 함께 넘긴다 — 프롬프트에 언어를
        # 못박아 두면 닮은 언어(독일어/네덜란드어)에서 모델이 덜 헷갈린다(2026-08-15).
        _target = target_language()
        src_lang, _src_conf = langdetect.detect(text)
        paras = _split_paragraphs_robust(text)
        out: list[str] = []
        bilingual_pairs: list[tuple[str, str]] = []  # (원문, 번역) — dropped 단락은 제외(out과 동일 기준)
        translated_n = preserved_n = dropped_n = failed_n = resumed_n = api_calls = 0
        total = len(paras) or 1

        def _save_partial():
            tmp = partial_path.with_name(partial_path.name + ".tmp")
            tmp.write_text("\n\n".join(out), encoding="utf-8")
            tmp.replace(partial_path)
        cached_rows: dict[int, dict] = {}
        if progress_path.exists():
            try:
                loaded = json.loads(progress_path.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    cached_rows = {
                        int(row.get("idx")): row
                        for row in loaded
                        if isinstance(row, dict) and isinstance(row.get("idx"), int)
                    }
            except Exception:
                cached_rows = {}
        for idx, p in enumerate(paras, 1):
            cached = cached_rows.get(idx)
            # 캐시 재사용은 '확정된' 결과만 — translated/preserved/dropped.
            # status=="failed"(이전 실행에서 번역 실패로 원문을 보존한 것)는 재사용하면
            # 안 된다. 그러면 이어하기가 실패를 그대로 재생해 영원히 번역이 안 되고
            # (translated_n==0 → 실패 반환) 넘어가 버린다. 실패 단락은 아래로 흘려보내
            # 다시 번역을 시도한다 (2026-07-25).
            if (cached and cached.get("src") == p and isinstance(cached.get("tgt"), str)
                    and cached.get("status") != "failed"):
                status = cached.get("status")
                tgt = cached.get("tgt", "")
                if status == "dropped":
                    dropped_n += 1
                else:
                    out.append(tgt)
                    bilingual_pairs.append((p, tgt))
                    if status == "preserved":
                        preserved_n += 1
                    else:
                        translated_n += 1
                resumed_n += 1
                if progress_cb:
                    progress_cb(idx, total, translated_n, preserved_n, dropped_n, failed_n, resumed_n, api_calls)
                continue
            if should_drop_paragraph(p):
                dropped_n += 1
                cached_rows[idx] = {"idx": idx, "src": p, "tgt": "", "status": "dropped"}
                _save_json_atomic(progress_path, [cached_rows[i] for i in sorted(cached_rows)])
                _save_partial()
                if progress_cb:
                    progress_cb(idx, total, translated_n, preserved_n, dropped_n, failed_n, resumed_n, api_calls)
                continue
            if should_skip_translation(p):
                out.append(p)
                bilingual_pairs.append((p, p))
                preserved_n += 1
                cached_rows[idx] = {"idx": idx, "src": p, "tgt": p, "status": "preserved"}
            else:
                ko = _translate_paragraph(p, engine, src_lang=src_lang, target=_target)
                api_calls += 1
                if _translation_is_valid(p, ko, _target):
                    out.append(ko)
                    bilingual_pairs.append((p, ko))
                    translated_n += 1
                    cached_rows[idx] = {"idx": idx, "src": p, "tgt": ko, "status": "translated"}
                else:
                    out.append(p)
                    bilingual_pairs.append((p, p))
                    failed_n += 1
                    cached_rows[idx] = {"idx": idx, "src": p, "tgt": p, "status": "failed"}
            _save_json_atomic(progress_path, [cached_rows[i] for i in sorted(cached_rows)])
            _save_partial()
            if progress_cb:
                progress_cb(idx, total, translated_n, preserved_n, dropped_n, failed_n, resumed_n, api_calls)
        _src_label = language_name(src_lang) if src_lang else ""
        detail = ((f"{_src_label}→{target_language_name()} · " if _src_label else "")
                  + f"{len(out)}단락 처리 완료 · 재사용 {resumed_n} · 신규번역 {translated_n} · 원문보존 {preserved_n}")
        if dropped_n:
            detail += f" · 삭제 {dropped_n}"
        if failed_n:
            detail += f" · 실패보존 {failed_n}"
        if translated_n == 0:
            ko_path.unlink(missing_ok=True)
            bilingual_path.unlink(missing_ok=True)
            partial_path.unlink(missing_ok=True)
            return False, detail + f" — 유효한 {target_language_name()} 번역 결과가 없습니다"
        if want_plain:
            ko_path.write_text("\n\n".join(out).replace(_PAGE_TOKEN, "\f"),
                               encoding="utf-8")
        if want_bilingual:
            _save_bilingual_atomic(
                bilingual_path,
                [(src + "\n\n" + tgt).replace(_PAGE_TOKEN, "\f")
                 for src, tgt in bilingual_pairs])
        # 챕터 제목도 번역해 사이드카로 저장 — 본문은 번역돼도 파일명에서 뽑는 장 제목은
        # 그대로 영문으로 남아있던 문제(EPUB 등에서 노출) 수정 (2026-08-11).
        # 파일명이 언어 접미사로 끝나서, 챕터 목록의 파생물 필터(is_derived)에 걸린다.
        title_ko_path = ch_path.with_name(ch_path.stem + "_title" + _suf + ".txt")
        orig_title = _re.sub(r"^\d+_", "", ch_path.stem)
        ko_title = translate_title(orig_title, engine, src_lang=src_lang, target=_target)
        if ko_title:
            title_ko_path.write_text(ko_title, encoding="utf-8")
        # 완주 — 중간 산출물 정리 (partial은 _ko.txt로 확정됨, progress 캐시 소진)
        partial_path.unlink(missing_ok=True)
        progress_path.unlink(missing_ok=True)
        return True, detail
    except Exception as e:
        return False, str(e)[:200]
