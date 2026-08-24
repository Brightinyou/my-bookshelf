"""AI 재OCR 하네스 — 환각을 막으면서 불량 본문을 다시 읽는다 (2026-08-24).

**왜 필요한가.** `services/textquality`가 불량으로 판정한 책은 PDF에 구워진 OCR
레이어가 한 글자 낱말을 통째로 빠뜨린 상태라 손볼 방법이 없다. 원본 이미지에서
다시 읽는 수밖에 없는데, 시각 판독 모델(Apple Vision)은 각주 번호·따옴표를 흘리고
줄 순서를 뒤섞는다(실측: 인용문 한복판에서 단어가 다른 줄로 튐). LLM 판독은 그
셋을 다 지키지만 **모르는 글자를 그럴듯하게 지어낸다** — 학위논문 인용문에서는
눈에 안 띄는 이쪽이 훨씬 위험하다.

**그래서 하네스의 일은 판독이 아니라 검증이다.** 세 겹으로 막는다.

1. **프롬프트로 막기** — 추측 금지, 못 읽는 글자는 `□`. 맞춤법 교정 금지.
2. **원본 대조로 잡기** — 같은 쪽의 기존 텍스트 레이어와 문자 유사도를 잰다.
   불량 레이어라도 **여러 글자 낱말은 대체로 맞게** 읽혀 있어서 기준선으로 쓸 수
   있다. 실측 보정값(『기술신학』 201쪽):

       레이어 vs 정상 LLM 판독   0.93
       레이어 vs Apple Vision    0.78
       레이어 vs 엉뚱한 쪽        0.03   ← 환각·쪽 어긋남의 하한

   정상 판독과 사고 사이가 0.78 대 0.03으로 크게 벌어져서, 임계 0.55는 정상을
   건드리지 않으면서 사고만 잡는다.
3. **분량으로 잡기** — 출력이 원본 대비 0.5배 미만/2배 초과면 요약했거나 지어냈다.

검증에 걸린 쪽은 **버리지 않고 ⚠️로 표시해 남긴다.** 조용히 지나가는 것이 이
프로젝트에서 반복된 사고의 원인이었다.

쪽 단위로 처리하고 쪽마다 파일로 떨어뜨린다 — 중단해도 이어서 할 수 있고, 문제가
생겼을 때 몇 쪽인지 바로 짚을 수 있다.
"""

import difflib
import json
import re
import shutil
import os
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path

import llm_providers as llm
from services import localocr
from services.common import append_log

# 검증 임계 — 위 실측 보정값 참고
MIN_SIMILARITY = 0.55
MIN_LENGTH_RATIO = 0.5
MAX_LENGTH_RATIO = 2.0
# 원본 쪽이 이보다 짧으면(속표지·장 표제지) 유사도가 요동쳐 대조를 건너뛴다
MIN_BASE_CHARS = 120

# ★pypdfium2는 스레드 안전하지 않다. 워커 4개가 같은 PDF를 동시에 열면
# "Data format error"로 **네 쪽 모두 실패**한다(2026-08-24 병렬화하다 실측).
# 렌더링·텍스트추출은 0.1~0.3초라 직렬화해도 손해가 없고, 느린 쪽(CLI 호출)은
# 그대로 병렬로 남는다.
_PDF_LOCK = threading.Lock()

# 원본 스캔이 144 DPI라 150이면 충분하다 — 실측으로 300dpi와 결과가 동일했다
DEFAULT_DPI = 150
JPEG_QUALITY = 85
# 쪽끼리는 서로 독립이라 동시에 돌릴 수 있다. 실측 4동시 = 벽시계 2.4배 단축
# (배경에 다른 작업이 돌던 상태에서 잰 값이라 실제로는 더 낫다).
DEFAULT_WORKERS = 3
# ★한 호출에 여러 쪽을 넣는 이유 — 비용의 82%가 쪽 내용이 아니라 **호출 오버헤드**다.
# 실측(codex 세션 로그, 2026-08-24): 한 쪽 판독의 입력 18,006토큰 중 14,720이
# codex 자신의 세션 프리앰블(매 호출 고정)이고, 우리 이미지+프롬프트는 3,286뿐이다.
# 쪽마다 새로 켜면 그 14,720을 쪽수만큼 되문다. 4쪽씩 묶으면 쪽당 6,966으로 2.6배,
# 8쪽이면 5,126으로 3.5배 줄어든다. 번역(kospace)이 한 호출에 줄바꿈 200개를
# 처리해 오버헤드를 분산시키는 것과 같은 이치다.
# 4로 잡은 근거: 8 이상은 이득이 완만해지는 데 비해 한 호출이 길어져
# 타임아웃·부분 실패 위험이 커지고, 되돌릴 때 버리는 분량도 커진다.
# 실측(추론 high·도구 차단·150dpi): 4쪽 6,696/쪽 · 8쪽 4,802/쪽 · 12쪽 4,184/쪽.
# 전부 턴 1이지만 12쪽에서 **평균 유사도가 0.925 → 0.811로 떨어졌다** — 한 번에
# 너무 많이 주면 쪽마다의 충실도가 흔들린다. 8쪽이 절약과 품질이 만나는 자리다.
DEFAULT_PAGES_PER_CALL = 8
# LLM으로 같은 쪽을 몇 번 읽을 것인가. 2면 갈리는 자리가 드러나고, 그 자리는 로컬
# Vision(심판)이 대개 갈라 준다. 1로 두면 대조를 아예 건너뛴다.
DEFAULT_PASSES = 2

# codex를 단발 호출로 만드는 비활성 목록. 이 세 개면 충분하다는 것을 실측했다
# (shell_tool·unified_exec = 셸/명령 실행, view_image = 이미지 재조회 루프).
_LEAN_FLAGS = ["--disable", "shell_tool",
               "--disable", "unified_exec",
               "--disable", "view_image"]

BEGIN, END = "<<<BEGIN>>>", "<<<END>>>"
PAGE_MARK = "<<<PAGE %d>>>"
_PAGE_RE = re.compile(r"<<<\s*PAGE\s*(\d+)\s*>>>")

PROMPT = f"""이 이미지들은 한국어 책의 낱쪽을 순서대로 스캔한 것이다. 보이는 글자를 **그대로 옮겨 적어라**.

지켜야 할 것:
- 이미지에 실제로 있는 글자만 적는다. 문맥으로 추측해서 채우지 마라.
- 흐리거나 뭉개져 못 읽는 글자는 □ 하나로 적는다. 그럴듯한 글자로 메우지 마라.
- 맞춤법·문장부호를 고치지 마라. 원문 그대로 적는다.
- ★**인쇄된 줄 끝에서 잘린 낱말은 이어 붙여라.** 종이 폭 때문에 갈라진 것일 뿐이다.
  예: 줄 끝 "알" + 다음 줄 "파고의" → "알파고의" (["알 파고의"]처럼 띄우지 마라)
  마찬가지로 한 낱말이 갈라져 사이에 공백이 생겼으면 붙여라("천문 학"→"천문학").
- ★**줄바꿈은 문단이 바뀔 때만 한다.** 인쇄된 줄마다 바꾸지 마라. 한 문단은 한 줄로.
- 각주 번호(위첨자 숫자)는 본문 해당 위치에 그대로 숫자로 적는다.
- 각주 본문은 본문을 다 적은 뒤 줄을 바꿔, **줄 첫머리에 그 번호를 적고** 한 칸 띄운
  뒤 내용을 적는다. 각주가 여럿이면 번호 오름차순으로 한 줄에 하나씩.
- 쪽 위아래의 러닝헤더(저자명·장제목)와 쪽번호는 적지 않는다.
- 요약하지 마라. 설명·해설·감상을 덧붙이지 마라.
- 이미지에 글자가 없으면 아무것도 적지 않는다.

- 쪽을 건너뛰거나 순서를 바꾸지 마라. 준 이미지 수만큼 그대로 내라.

출력 형식: 이미지마다 아래 표시를 앞에 붙이고 그 쪽 본문만 적어라. 다른 말은 하지 마라.
{BEGIN}
<<<PAGE 1>>>
(첫째 이미지 본문)
<<<PAGE 2>>>
(둘째 이미지 본문)
{END}"""


@dataclass
class PageResult:
    page: int                 # 1-기준 PDF 쪽번호
    status: str               # ok | check | unverified | warn | failed | reading
    chars: int = 0
    base_chars: int = 0
    similarity: float = 0.0
    note: str = ""
    # 2회 판독이 어긋난 자리 — [{"before":…, "a":…, "b":…}] (아래 reconcile 참고)
    disagreements: list = field(default_factory=list)
    # 채택본과 로컬 심판이 어긋난 자리 — 두 LLM이 같이 틀린 경우를 비추는 참고용.
    # 시끄러워서 경고로는 안 올리고 접어 둔 목록으로만 낸다(judge_only_notes 참고).
    judge_notes: list = field(default_factory=list)


# ── 렌더링·기준선 ────────────────────────────────────────────

def page_count(pdf_path: Path) -> int:
    import pypdfium2 as pdfium
    with _PDF_LOCK:
        doc = pdfium.PdfDocument(str(pdf_path))
        try:
            return len(doc)
        finally:
            doc.close()


def render_page(pdf_path: Path, index0: int, out_dir: Path, dpi: int = DEFAULT_DPI) -> Path:
    """한 쪽을 JPEG로 렌더링.

    ★**스캔 원본이 144 DPI다.** 그 위로 올려 봐야 없는 정보가 생기지 않고 올려보낼
    바이트만 는다. 실측(『기술신학』 201쪽): 300dpi PNG 2.88MB와 150dpi JPEG
    0.23MB의 **판독 결과가 글자 하나까지 같았다**(일치도 1.000, 원본 대비 유사도
    둘 다 0.929). 12배 작은 쪽을 쓴다 (2026-08-24)."""
    import pypdfium2 as pdfium
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"p{index0 + 1:04d}.jpg"
    with _PDF_LOCK:
        doc = pdfium.PdfDocument(str(pdf_path))
        try:
            doc[index0].render(scale=dpi / 72).to_pil().convert("RGB").save(
                str(out), quality=JPEG_QUALITY)
        finally:
            doc.close()
    return out


def base_page_text(pdf_path: Path, index0: int) -> str:
    """대조용 기준선 = 그 쪽의 기존 텍스트 레이어. 불량이어도 '여러 글자 낱말'은
    대체로 맞아서 환각·쪽 어긋남을 잡는 데는 충분하다."""
    import pypdfium2 as pdfium
    with _PDF_LOCK:
        doc = pdfium.PdfDocument(str(pdf_path))
        try:
            return doc[index0].get_textpage().get_text_range() or ""
        except Exception:
            return ""
        finally:
            doc.close()


# ── 검증 ─────────────────────────────────────────────────────

_KEEP = re.compile(r"[^가-힣A-Za-z0-9]")


def similarity(a: str, b: str) -> float:
    """문장부호·띄어쓰기를 지우고 글자열끼리 견준다 — 띄어쓰기 정책 차이에 흔들리지
    않게. 0(딴 쪽) ~ 1(동일)."""
    na, nb = _KEEP.sub("", a), _KEEP.sub("", b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


# 원본 레이어가 이만큼 깨져 있으면 유사도 대조 자체가 의미 없다(1,000자당).
# 실측: 대조 불가였던 쪽 17~20 / 정상 대조된 쪽 1~11.
UNREADABLE_BASE_GARBLE = 15.0
# 다만 유사도가 이보다도 낮으면 '원본이 깨져서'가 아니라 **아예 다른 내용**이다.
# 실측: 원본이 깨진 정상 판독 0.22·0.53 / 엉뚱한 쪽·지어낸 문장 0.01~0.06.
ALIGNMENT_FLOOR = 0.15


def verify(ai_text: str, base_text: str) -> tuple[str, float, str]:
    """(status, similarity, note). 걸려도 버리지 않고 표시만 한다."""
    base_len = len(_KEEP.sub("", base_text))
    ai_len = len(_KEEP.sub("", ai_text))
    if not ai_text.strip():
        # 원본도 비어 있으면 그냥 빈 쪽(간지·백지)이다 — 경고할 일이 아니다 (2026-08-24)
        if base_len < 20:
            return "ok", 0.0, "빈 쪽"
        return "warn", 0.0, "판독 결과가 비어 있습니다"
    if base_len < MIN_BASE_CHARS:
        return "ok", 0.0, "원본 쪽이 짧아 대조를 건너뜀"

    sim = similarity(ai_text, base_text)
    ratio = ai_len / base_len
    if sim < MIN_SIMILARITY:
        # 유사도가 낮다고 무조건 AI 잘못이 아니다 — 원본 레이어가 박살난 쪽(차례·판권
        # 등)에서는 **제대로 읽을수록 원본과 멀어진다**. 실측: 『기술신학』 7쪽 원본이
        # `* 겨냬뎌 / 1 _ 가술신확개븐`이라 유사도 0.22였는데 AI 판독은 정확했다.
        # 그래서 둘 중 어느 쪽이 더 한국어다운지 견줘 본다 (2026-08-24).
        from services.textquality import garble_rate
        if sim >= ALIGNMENT_FLOOR and garble_rate(base_text) >= UNREADABLE_BASE_GARBLE:
            return ("unverified", sim,
                    f"원본 레이어가 심하게 깨져 대조 불가(유사도 {sim:.2f}) — AI 판독을 채택했습니다")
        return "warn", sim, f"원본과 유사도 {sim:.2f} (임계 {MIN_SIMILARITY}) — 환각·쪽 어긋남 의심"
    if ratio < MIN_LENGTH_RATIO:
        return "warn", sim, f"분량이 원본의 {ratio:.0%} — 요약했거나 일부를 빠뜨렸을 수 있습니다"
    if ratio > MAX_LENGTH_RATIO:
        return "warn", sim, f"분량이 원본의 {ratio:.0%} — 없는 내용을 덧붙였을 수 있습니다"
    return "ok", sim, ""


# ── 2회 판독 대조 ────────────────────────────────────────────
# 같은 쪽을 두 번 읽으면 **모델이 확신하는 자리는 같게, 헷갈리는 자리는 다르게**
# 나온다. 실측(2026-08-24): 같은 쪽을 설정을 바꿔 가며 여러 번 읽었더니 오독 위치가
# 매번 옮겨 다녔다(`벽돌이`→`변혁이`→`변들이`). 한 번 읽어서는 못 믿는다는 뜻이고,
# 동시에 **두 번 읽으면 그 자리가 드러난다**는 뜻이다.
#
# 기존 유사도 검증이 못 잡던 구멍을 메운다 — 낱말 하나가 바뀌어도 쪽 전체 유사도는
# 0.99대라 통과했다(30쪽 `망원경`→`바벨탑`이 ok 판정으로 지나갔다).

# 문장부호·공백만 다른 것은 굳이 알릴 값어치가 없다
_TRIVIAL = re.compile(r"[\s.,:;()\[\]{}“”‘’\"'`~\-—–"
                      r"\u00b7\u2022\u2219\u318d\u30fb\uff65]+")   # 가운뎃점 변종 포함


def _words(text: str) -> list[str]:
    return text.split()


def _is_trivial(a: str, b: str) -> bool:
    return _TRIVIAL.sub("", a) == _TRIVIAL.sub("", b)


def reconcile(texts: list[str], judge: str = "", context: int = 18) -> tuple[str, list[dict]]:
    """LLM 판독 둘을 견주고, 갈린 자리마다 심판(judge)에게 물어 가른다.

    **어느 쪽이 맞는지는 대개 알 수 없다.** 그래서 첫 판독을 그대로 채택하고 어긋난
    자리만 기록한다 — 본문을 건드리지 않아야 사람이 원문과 대조할 수 있다.

    ★judge(로컬 Vision 판독)는 **동등한 판독자가 아니라 심판**이다. 실측(30쪽):
    Vision을 셋째 판독자로 놓고 견주면 불일치가 15곳인데 그중 11곳이 Vision 잘못
    이었다(`이원론적`→`의원론적`, `신학적`→`신화적`). 본문 정확도는 LLM이 낫다.
    그런데 **LLM 둘이 갈린 자리에서는 Vision이 정확히 갈라 준다**:
        내재하심으로 ↔ 기뻐하심으로  → Vision `내재하심`  → 1차 채택
        통찰을       ↔ 물질을        → Vision `물질을`    → 2차 채택
        베풂이       ↔ 벼룩이        → Vision `벽돌이`    → 둘 다 아님 → ⚠️
    심판이 한쪽을 지지하면 조용히 그쪽을 쓰고, 못 가르면 사람에게 넘긴다.
    이렇게 하면 Vision의 본문 오독은 아예 투표에 들어오지 않는다."""
    texts = [t for t in texts if t and t.strip()]
    if not texts:
        return "", []
    if len(texts) < 2:
        return texts[0], []
    a, b = _words(texts[0]), _words(texts[1])
    jn = _TRIVIAL.sub("", judge) if judge else ""
    picked = list(a)
    diffs: list[dict] = []
    offset, swapped = 0, False
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            continue
        wa, wb = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        if _is_trivial(wa, wb):
            continue
        ka, kb = _TRIVIAL.sub("", wa), _TRIVIAL.sub("", wb)
        if jn and ka and kb:
            in_a, in_b = ka in jn, kb in jn
            if in_a and not in_b:
                continue                      # 심판이 1차를 지지 — 그대로 둔다
            if in_b and not in_a:
                picked[i1 + offset:i2 + offset] = b[j1:j2]
                offset += (j2 - j1) - (i2 - i1)
                swapped = True                # 길이가 같아도 바뀐 것은 바뀐 것이다
                continue                      # 심판이 2차를 지지 — 갈아 끼운다
        diffs.append({"before": " ".join(a[max(0, i1 - 4):i1])[-context:],
                      "a": wa[:60], "b": wb[:60],
                      "judge": "가르지 못함" if jn else ""})
    return (" ".join(picked) if swapped else texts[0]), diffs


def judge_only_notes(adopted: str, judge: str, context: int = 18) -> list[dict]:
    """채택본과 심판이 어긋나는 자리 — **두 LLM 판독이 같이 틀린 경우**를 비춘다.

    ★한계 인정: 두 번 다 같게 틀리면 대조로는 못 잡는다. 실측(30쪽)에서 두 판독이
    모두 `기뻐하심으로`로 읽어(원문 `내재하심으로`) 조용히 통과했다. Vision은 그
    자리를 맞혔으므로, 채택본과 Vision을 견주면 드러난다.

    다만 **이건 경고로 쓰기엔 너무 시끄럽다** — Vision은 본문 정확도가 LLM보다
    낮아서 실측 30쪽에서 15곳이 어긋났고 그중 11곳이 Vision 잘못이었다
    (`이원론적`→`의원론적`). 그래서 `check` 상태로 올리지 않고 **접어 둔 참고
    목록**으로만 남긴다. 정밀 대조가 필요한 쪽에서 사람이 펼쳐 보는 용도다."""
    if not judge.strip() or not adopted.strip():
        return []
    a, b = _words(adopted), _words(judge)
    out: list[dict] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            continue
        wa, wb = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        if _is_trivial(wa, wb) or not wa.strip() or not wb.strip():
            continue
        out.append({"before": " ".join(a[max(0, i1 - 4):i1])[-context:],
                    "a": wa[:60], "b": wb[:60]})
    return out


# ── 공급자 호출 ──────────────────────────────────────────────

def _extract(raw: str) -> str:
    """CLI가 앞뒤로 덧붙인 말을 걷어내고 표시 사이만 꺼낸다."""
    s = (raw or "").strip()
    if BEGIN in s:
        s = s.split(BEGIN, 1)[1]
    if END in s:
        s = s.split(END, 1)[0]
    s = re.sub(r"^```[a-zA-Z]*\n?|```$", "", s.strip())
    return s.strip()


def _read_codex_cli(model: str, imgs: list[Path], timeout: int) -> str:
    cli = llm.codex_cli_path()
    if not cli:
        raise RuntimeError("codex CLI를 찾지 못했습니다")
    # ★★도구를 열어 주면 안 된다. `--dangerously-bypass-approvals-and-sandbox`로
    # 돌렸더니 codex가 이미지를 읽다 말고 **옆에 있는 원본 TXT를 find·rg·sed로
    # 뒤져 커닝**했다(2026-08-24 세션 로그 실측: 한 호출에 exec_command 29회 ·
    # 추론 30회 · 39턴 · 입력 2,491,018토큰).
    #   ① 비용: 매 턴 이미지를 통째로 재전송해 쪽당 토큰이 10배 넘게 튄다.
    #   ② ★검증 무력화: 원본을 보고 베끼면 유사도가 당연히 통과한다 —
    #      환각을 잡으려고 만든 대조가 통째로 무의미해진다.
    # 이미지만 보고 답하게 샌드박스를 켜고, 작업 폴더도 빈 임시 폴더로 격리한다.
    work = Path(tempfile.mkdtemp(prefix="ocr_cwd_"))
    out_file = work / "out.txt"
    args = [cli, "exec", "--skip-git-repo-check", "--sandbox", "read-only",
            "-C", str(work), "-o", str(out_file),
            # ★★에이전트를 '단발 호출'로 만드는 설정 (2026-08-24 실측으로 확정).
            # codex는 기본적으로 도구를 들고 여러 턴을 돈다 — 이미지가 컨텍스트에
            # 눌러앉은 채 매 턴 재전송되므로 비용이 폭증한다(최대 39턴·249만 토큰).
            # OCR엔 도구가 하나도 필요 없다. 이미지는 -i로 이미 붙어 있다.
            #   도구 전면 차단 + 추론 최소  →  턴 1 · 도구 0 · 입력 17,341 · 추론 14
            #   (같은 조건 기존: 턴 중앙 5 · 도구 최대 29 · 입력 중앙 132,771)
            # ⚠️ 추론 강도는 **낮추지 않는다**(config.toml 기본값 그대로 = high).
            #    low로 낮춰 봤지만 토큰은 거의 안 줄고(17,786 vs 17,692) 판독만
            #    흔들렸다. 비용을 줄인 것은 추론이 아니라 **도구 차단**이다.
            #    참고: minimal은 아예 못 쓴다 — web_search와 함께 쓸 수 없다며 400.
            *_LEAN_FLAGS]
    for f in imgs:
        args += ["-i", str(f)]
    if model not in ("default", ""):
        args += ["-m", model]
    args.append("-")
    try:
        r = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
            cwd=str(work), encoding="utf-8", errors="replace",
            input=PROMPT, env=llm._cli_env(), **llm._no_window_kwargs())
        if r.returncode != 0:
            raise RuntimeError(f"codex CLI exit {r.returncode}: {(r.stderr or '')[:200]}")
        raw = out_file.read_text(encoding="utf-8") if out_file.exists() else (r.stdout or "")
        return raw
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _read_claude_cli(model: str, imgs: list[Path], timeout: int) -> str:
    cli = llm.claude_cli_path()
    if not cli:
        raise RuntimeError("claude CLI를 찾지 못했습니다")
    # 같은 이유로 Read만 허용하고, 이미지는 이미 격리 폴더에 있다(_render_isolated)
    listed = "\n".join(f'{i}. "{f}"' for i, f in enumerate(imgs, 1))
    prompt = f'다음 이미지 파일들을 순서대로 Read 도구로 읽어라.\n{listed}\n\n{PROMPT}'
    r = subprocess.run(
        [cli, "-p", prompt, "--model", model or "default", "--output-format", "text",
         "--allowedTools", "Read",
         "--system-prompt", "You transcribe scanned pages verbatim. Never guess."],
        capture_output=True, text=True, timeout=timeout, cwd=str(imgs[0].parent),
        encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
        env=llm._cli_env(), **llm._no_window_kwargs())
    if r.returncode != 0:
        raise RuntimeError(f"claude CLI exit {r.returncode}: {(r.stderr or '')[:200]}")
    return _extract(r.stdout or "")


def _split_pages(raw: str, count: int) -> list[str]:
    """한 응답에서 쪽별 본문을 갈라낸다. 표시가 없거나 수가 안 맞으면 빈 칸을 채워
    돌려준다 — **넘겨짚어 이어 붙이지 않는다.** 잘못 붙인 본문은 검증도 못 잡는다."""
    body = _extract(raw)
    marks = list(_PAGE_RE.finditer(body))
    if not marks:
        return [body] + [""] * (count - 1) if count == 1 else [""] * count
    out = [""] * count
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        idx = int(m.group(1)) - 1
        if 0 <= idx < count:
            out[idx] = body[m.end():end].strip()
    return out


def read_pages(provider: str, model: str, imgs: list[Path], timeout: int = 600) -> list[str]:
    """이미지 여러 장을 한 번에 판독해 쪽별 본문 목록으로 돌려준다."""
    if provider == "codex_cli":
        raw = _read_codex_cli(model, imgs, timeout)
    elif provider == "claude_cli":
        raw = _read_claude_cli(model, imgs, timeout)
    else:
        raise RuntimeError(f"'{provider}'로는 아직 쪽 판독을 하지 않습니다 — "
                           "구독형 CLI(codex_cli·claude_cli)를 쓰세요")
    return _split_pages(raw, len(imgs))


def read_page(provider: str, model: str, png: Path, timeout: int = 600) -> str:
    """한 쪽만 읽는 옛 인터페이스 — 테스트·단발 확인용."""
    return read_pages(provider, model, [png], timeout)[0]


# ── 비용 안내 ────────────────────────────────────────────────

# 쪽당 대략치: 150dpi 이미지 ≈ 2,200 입력토큰, 한국어 한 쪽 ≈ 1,300 출력토큰.
# 공개 정가($/1M) 기준이며 실제 청구액과 다를 수 있다.
_API_RATES = {
    "anthropic": (5.0, 25.0),
    "openai": (5.0, 25.0),
    "gemini": (2.0, 10.0),
}
_IN_TOK, _OUT_TOK = 2200, 1300


# 구독형 CLI는 돈이 안 나갈 뿐 **주간 사용 한도**를 쓴다 — 이게 실질 비용이다.
#
# 예전 설정(도구 열림·300dpi)에서는 41쪽에 주간 한도 10%가 날아갔다(주당 410쪽).
# 원인은 쪽 내용이 아니라 **에이전트 루프**였다 — 쪽당 입력 중앙 132,771 · 평균
# 497,870 토큰. 도구를 끄고 추론을 낮춰 단발 호출로 만든 뒤 **쪽당 6,647**로
# 떨어졌다(75배). 주간 한도를 204M 토큰으로 역산하면 주당 3만 쪽 규모지만,
# 표본이 크지 않고 쪽마다 분량이 다르므로 **넉넉히 낮춰 잡는다.**
CLI_PAGES_PER_WEEK = 15000


def cost_notice(provider: str, pages: int) -> str:
    """공급자를 고를 때 띄울 안내. 구독은 돈이 아니라 **한도**를 쓴다."""
    if provider in llm.CLI_PROVIDERS:
        pct = pages / CLI_PAGES_PER_WEEK * 100
        if pct < 25:
            return (f"ℹ️ 구독형 CLI는 추가 과금이 없지만 **주간 사용 한도**를 씁니다 — "
                    f"{pages:,}쪽이면 주간 한도의 약 **{pct:.0f}%**입니다.")
        return (f"⚠️ **구독 한도를 크게 씁니다.** {pages:,}쪽이면 주간 한도의 약 "
                f"**{pct:.0f}%**입니다(실측 41쪽 = 10%). 여러 권을 돌릴 계획이면 "
                "API가 오히려 현실적입니다 — 한도에 걸리지 않고 쪽당 1~4센트 수준입니다.")
    rate = _API_RATES.get(provider)
    if not rate:
        return (f"⚠️ '{provider}'는 사용량만큼 과금됩니다. {pages:,}쪽을 한 번에 돌리기 전에 "
                "몇 쪽만 시험해 비용을 확인하세요.")
    usd = pages * (_IN_TOK * rate[0] + _OUT_TOK * rate[1]) / 1_000_000
    return (f"⚠️ **{provider} API는 쪽마다 과금됩니다.** {pages:,}쪽이면 대략 "
            f"**${usd:,.0f}** (공개 정가 기준 추정, 실제 청구액과 다를 수 있음). "
            "구독형 CLI(codex·claude)를 쓰면 추가 과금이 없습니다.")


# ── 본 작업 ──────────────────────────────────────────────────

def work_dir(out_txt: Path) -> Path:
    return out_txt.with_suffix(out_txt.suffix + ".pages")


def reocr(pdf_path: Path, out_txt: Path, provider: str, model: str = "",
          pages: list[int] | None = None, dpi: int = DEFAULT_DPI,
          workers: int = DEFAULT_WORKERS, pages_per_call: int = DEFAULT_PAGES_PER_CALL,
          passes: int = DEFAULT_PASSES, second_eye: bool = True, progress=None, should_stop=None, timeout: int = 600) -> list[PageResult]:
    """PDF를 쪽마다 다시 읽어 out_txt로 합친다.

    pages는 1-기준 쪽번호 목록(None이면 전체). 이미 읽은 쪽은 건너뛰므로 중단해도
    같은 인자로 다시 부르면 이어서 한다. progress(done, total, PageResult)."""
    pdf_path, out_txt = Path(pdf_path), Path(out_txt)
    total_pages = page_count(pdf_path)
    targets = sorted(pages) if pages else list(range(1, total_pages + 1))
    wd = work_dir(out_txt)
    wd.mkdir(parents=True, exist_ok=True)
    # ★이미지를 책 폴더 옆에 두면 안 된다 — read-only 샌드박스라도 읽기는 되므로
    # codex가 같은 폴더의 원본 TXT를 찾아 커닝할 수 있다(_read_codex_cli 주석 참고).
    # 판독에 필요한 건 이미지뿐이니 아예 격리된 임시 폴더에 렌더한다.
    png_dir = Path(tempfile.mkdtemp(prefix="ocr_img_"))

    log = wd / "_report.json"
    results: dict[int, PageResult] = {}
    if log.exists():
        try:
            for row in json.loads(log.read_text(encoding="utf-8")):
                results[row["page"]] = PageResult(**row)
        except Exception:
            pass

    def _flush():
        rows = [asdict(results[p]) for p in sorted(results)]
        log.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    def _beat(done: int, page: int = 0):
        """심장박동 — 다른 프로세스가 이걸 보고 '아직 도는 중'을 안다."""
        try:
            _hb_path(out_txt).write_text(json.dumps(
                {"beat": time.time(), "pid": os.getpid(), "done": done,
                 "total": len(targets), "page": page, "provider": provider,
                 "page_started": time.time()}, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    todo = [pg for pg in targets
            if not ((wd / f"p{pg:04d}.txt").exists()
                    and results.get(pg) and results[pg].status != "failed")]

    def _one(batch: list[int]) -> list[PageResult]:
        """한 묶음(여러 쪽)을 한 번의 호출로 판독한다 — 워커에서 돈다.

        묶어서 부르되 **검증은 쪽마다 따로** 한다. 묶음 안에서 쪽이 밀리거나 섞이면
        그 쪽의 유사도가 무너지므로 기존 검증이 그대로 잡아낸다."""
        bases = {pg: base_page_text(pdf_path, pg - 1) for pg in batch}
        imgs: list[Path] = []
        try:
            imgs = [render_page(pdf_path, pg - 1, png_dir, dpi) for pg in batch]
            runs = [read_pages(provider, model, imgs, timeout) for _ in range(max(1, passes))]
            # ★둘째 눈 — 로컬 Apple Vision. 공짜·1초·결정적이고 **실패 양상이 달라**
            # LLM을 한 번 더 부르는 것보다 낫다(services/localocr 머리말 참고).
            # 없으면 조용히 건너뛴다.
            judges = (localocr.read(imgs) if (second_eye and localocr.available())
                      else ["" for _ in imgs])
        except Exception as e:
            note = f"{type(e).__name__}: {str(e)[:160]}"
            return [PageResult(pg, "failed", 0, len(bases[pg]), 0.0, note) for pg in batch]
        finally:
            for f in imgs:
                f.unlink(missing_ok=True)

        picked = [reconcile([r[i] for r in runs], judges[i]) for i in range(len(batch))]
        texts = [t for t, _ in picked]
        diffs_by_page = [d for _, d in picked]

        out = []
        for pg, text, diffs in zip(batch, texts, diffs_by_page):
            base = bases[pg]
            if not text.strip() and base.strip():
                # 묶음 응답에서 이 쪽만 비었다 — 표시를 놓쳤거나 건너뛴 것이다.
                # 옆 쪽 본문을 끌어다 메우면 절대 안 된다(검증도 못 잡는다).
                out.append(PageResult(pg, "failed", 0, len(base), 0.0,
                                      "묶음 응답에 이 쪽이 없습니다 — 다시 시도하세요"))
                continue
            status, sim, note = verify(text, base)
            (wd / f"p{pg:04d}.txt").write_text(text, encoding="utf-8")
            if diffs and status == "ok":
                # 유사도는 통과했지만 두 판독이 어긋났다 — 낱말 바꿔치기는 유사도로
                # 안 걸리므로(30쪽 `망원경`→`바벨탑`이 0.988로 통과) 여기서 잡는다
                status = "check"
                note = f"두 판독이 {len(diffs)}곳에서 어긋납니다 — 원문과 대조하세요"
            elif diffs:
                note = (note + f" · 두 판독 {len(diffs)}곳 불일치").strip(" ·")
            out.append(PageResult(pg, status, len(text), len(base), round(sim, 3),
                                  note, diffs,
                                  judge_only_notes(text, judges[batch.index(pg)])))
        return out

    clear_run_state(out_txt)                      # 지난 실행의 중단 표시를 지운다
    per_call = max(1, pages_per_call)
    batches = [todo[i:i + per_call] for i in range(0, len(todo), per_call)]
    done, stopped = len(targets) - len(todo), False
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures: dict = {}

        def _submit_next():
            # 처음부터 전부 제출하지 않는다 — 중단 요청이 와도 큐를 비울 수가 없어진다.
            # 하나 끝날 때마다 하나씩 채워 항상 workers개만 떠 있게 한다.
            if batches and not stopped:
                b = batches.pop(0)
                futures[pool.submit(_one, b)] = b
                _beat(done, b[0])
                if progress:
                    # 묶음을 **시작할 때**도 알린다 — 끝날 때만 알리면 몇 분 동안
                    # 화면이 멈춰 보인다 (2026-08-24 사용자 지적).
                    progress(done, len(targets), PageResult(b[0], "reading"))

        for _ in range(max(1, workers)):
            _submit_next()
        while futures:
            fut = next(as_completed(list(futures)))
            batch = futures.pop(fut)
            for res in fut.result():
                results[res.page] = res
                done += 1
                if progress:
                    progress(done, len(targets), res)
            _flush()
            _beat(done)
            if not stopped and ((should_stop and should_stop()) or _stop_requested(out_txt)):
                stopped = True
                append_log(f"AI 재OCR 중단 요청 — {pdf_path.name} "
                           f"({done}/{len(targets)}쪽까지 하고 멈춤)")
            _submit_next()

    shutil.rmtree(png_dir, ignore_errors=True)
    clear_run_state(out_txt)                      # 끝났음을 알린다(심장박동 제거)
    assemble(pdf_path, out_txt, total_pages)
    ok = sum(1 for r in results.values() if r.status == "ok")
    warn = sum(1 for r in results.values() if r.status == "warn")
    fail = sum(1 for r in results.values() if r.status == "failed")
    append_log(f"AI 재OCR({provider}) {pdf_path.name}: 정상 {ok} · ⚠️ {warn} · 실패 {fail}")
    return [results[p] for p in sorted(results)]


def assemble(pdf_path: Path, out_txt: Path, total_pages: int | None = None) -> Path:
    """쪽 파일을 합쳐 TXT 한 벌로 만든다. 쪽 경계는 파이프라인 관례대로 `\\f`.

    아직 안 읽은 쪽은 기존 텍스트 레이어로 메운다 — 부분 재OCR도 온전한 책이 되게."""
    wd = work_dir(out_txt)
    total_pages = total_pages or page_count(pdf_path)
    parts = []
    for page in range(1, total_pages + 1):
        f = wd / f"p{page:04d}.txt"
        if f.exists():
            parts.append(f.read_text(encoding="utf-8", errors="ignore").strip())
        else:
            parts.append(base_page_text(pdf_path, page - 1).strip())
    out_txt.parent.mkdir(parents=True, exist_ok=True)
    body = "\f".join(parts)
    out_txt.write_text(body, encoding="utf-8")
    # 각주를 살린 Markdown도 함께 낸다 — TXT는 각주 번호가 본문에 맨숫자로 박혀
    # 나중에 인용할 때 사람이 매번 되짚어야 한다 (services/footnotes 머리말 참고).
    try:
        from services import footnotes, layout
        # 각주가 있는 쪽인지 줄 간격으로 미리 재 둔다 — 쪽번호·러닝헤더를 각주로
        # 오인하는 것을 막는다(services/layout 머리말 참고)
        flags = []
        for i in range(total_pages):
            try:
                flags.append(layout.analyze(pdf_path, i, _PDF_LOCK).has_notes)
            except Exception:
                flags.append(True)          # 못 재면 판단을 미루고 텍스트로만 본다
        res = footnotes.convert(body, flags)
        if res.notes:
            out_txt.with_suffix(".md").write_text(res.markdown, encoding="utf-8")
            append_log(f"각주 {len(res.notes)}개 중 {res.linked}개를 본문과 이어 "
                       f"Markdown으로 냈습니다 — {out_txt.with_suffix('.md').name}")
    except Exception as e:
        append_log(f"WARN: 각주 Markdown 생성 실패 ({type(e).__name__}) {str(e)[:120]}")
    return out_txt


def load_report(out_txt: Path) -> list[PageResult]:
    log = work_dir(Path(out_txt)) / "_report.json"
    if not log.exists():
        return []
    try:
        return [PageResult(**row) for row in json.loads(log.read_text(encoding="utf-8"))]
    except Exception:
        return []


# ── 백그라운드 실행 관리 ─────────────────────────────────────
# 한 권이 몇 시간짜리 작업이라 화면을 붙잡고 있을 수 없다. 스레드로 돌리고 진행
# 상황은 작업 폴더의 _report.json으로 남긴다(중단·재시작에도 살아남는다).

# ★상태를 프로세스 메모리에만 두면 안 된다. 예전에는 RUNS 딕셔너리와 살아 있는
# 스레드 객체로 판단했는데, **앱을 다시 깔거나(streamlit이 바뀐 모듈을 리로드)
# 재시작하면 그 딕셔너리가 비면서 돌고 있는 작업을 중단할 수단이 사라졌다.**
# 실제로 그렇게 됐다 — 사용자가 «중단»을 눌렀는데 버튼은 비활성이고 작업은
# 계속 돌았다(2026-08-24). 게다가 자식 codex 프로세스는 부모가 죽어도 살아남는다.
#
# 그래서 **작업 폴더의 파일로** 주고받는다. 어느 프로세스에서 눌러도 통하고,
# 앱이 죽었다 살아나도 이어진다.
#   _running.json — 심장박동(갱신 시각·진행·PID). 오래되면 죽은 작업으로 본다.
#   _stop         — 있으면 멈춘다.
HEARTBEAT_NAME = "_running.json"
STOP_NAME = "_stop"
# 한 쪽이 몇 분씩 걸리므로 넉넉히 잡는다 — 이보다 오래 갱신이 없으면 죽은 것.
STALE_AFTER = 900


def _hb_path(out_txt) -> Path:
    return work_dir(Path(out_txt)) / HEARTBEAT_NAME


def _stop_path(out_txt) -> Path:
    return work_dir(Path(out_txt)) / STOP_NAME


def status(out_txt) -> dict:
    try:
        return json.loads(_hb_path(out_txt).read_text(encoding="utf-8"))
    except Exception:
        return {}


def is_running(out_txt) -> bool:
    st = status(out_txt)
    if not st:
        return False
    if time.time() - st.get("beat", 0) > STALE_AFTER:
        return False                                  # 심장이 멎었다
    pid = st.get("pid")
    return _pid_alive(pid) if isinstance(pid, int) else True


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True                                   # 남의 프로세스지만 살아 있다


def request_stop(out_txt) -> None:
    """어느 프로세스에서 불러도 통한다 — 작업 폴더에 표시를 남긴다."""
    try:
        wd = work_dir(Path(out_txt))
        wd.mkdir(parents=True, exist_ok=True)
        (wd / STOP_NAME).write_text(str(time.time()), encoding="utf-8")
    except Exception:
        pass


def _stop_requested(out_txt) -> bool:
    return _stop_path(out_txt).exists()


def clear_run_state(out_txt) -> None:
    for f in (_hb_path(out_txt), _stop_path(out_txt)):
        try:
            f.unlink(missing_ok=True)
        except Exception:
            pass


def kill_orphans(out_txt) -> int:
    """부모가 죽어 고아가 된 판독 프로세스를 정리한다.

    자식 codex는 부모(스레드를 안고 있던 앱)가 죽어도 살아남는다 — 실측으로
    확인했다. 이어하기 전에 한 번 훑어 준다."""
    import subprocess as sp
    marker = str(work_dir(Path(out_txt)).name)[:40]
    killed = 0
    try:
        out = sp.run(["pgrep", "-f", "codex exec"], capture_output=True, text=True).stdout
        for pid in [int(x) for x in out.split() if x.isdigit()]:
            cmd = sp.run(["ps", "-o", "command=", "-p", str(pid)],
                         capture_output=True, text=True).stdout
            if marker in cmd or "ocr_p" in cmd:
                os.kill(pid, 9)
                killed += 1
    except Exception:
        pass
    return killed


def start_background(pdf_path: Path, out_txt: Path, provider: str, model: str = "",
                     pages: list[int] | None = None, dpi: int = DEFAULT_DPI,
                     workers: int = DEFAULT_WORKERS,
                     pages_per_call: int = DEFAULT_PAGES_PER_CALL,
                     passes: int = DEFAULT_PASSES, second_eye: bool = True,
                     timeout: int = 600) -> None:
    """이미 돌고 있으면 아무 일도 하지 않는다.

    진행 상황·중단 신호는 전부 작업 폴더의 파일로 오간다(위 HEARTBEAT_NAME 주석
    참고). 스레드 객체를 붙들지 않으므로 앱이 리로드돼도 중단할 수 있다."""
    if is_running(out_txt):
        return
    kill_orphans(out_txt)              # 지난번에 부모가 죽어 남은 판독 프로세스 정리
    clear_run_state(out_txt)

    def _worker():
        try:
            reocr(pdf_path, out_txt, provider, model, pages, dpi, workers, pages_per_call,
                  passes, second_eye, timeout=timeout)
        except Exception as e:
            msg = f"{type(e).__name__}: {str(e)[:200]}"
            append_log(f"ERROR: AI 재OCR 실패 — {Path(pdf_path).name}: {msg}")
            try:
                hb = status(out_txt) or {}
                hb.update(error=msg, beat=time.time())
                _hb_path(out_txt).write_text(json.dumps(hb, ensure_ascii=False),
                                             encoding="utf-8")
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True,
                     name=f"reocr-{Path(out_txt).stem[:20]}").start()
