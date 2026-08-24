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
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

import llm_providers as llm
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
DEFAULT_WORKERS = 4

BEGIN, END = "<<<BEGIN>>>", "<<<END>>>"

PROMPT = f"""이 이미지는 한국어 책의 한 쪽을 스캔한 것이다. 보이는 글자를 **그대로 옮겨 적어라**.

지켜야 할 것:
- 이미지에 실제로 있는 글자만 적는다. 문맥으로 추측해서 채우지 마라.
- 흐리거나 뭉개져 못 읽는 글자는 □ 하나로 적는다. 그럴듯한 글자로 메우지 마라.
- 맞춤법·띄어쓰기·문장부호를 고치지 마라. 원문 그대로 적는다.
- 각주 번호(위첨자 숫자)는 본문 해당 위치에 그대로 숫자로 적는다.
- 각주 본문은 본문을 다 적은 뒤 줄을 바꿔 이어 적는다.
- 쪽 위아래의 러닝헤더(저자명·장제목)와 쪽번호는 적지 않는다.
- 요약하지 마라. 설명·해설·감상을 덧붙이지 마라.
- 이미지에 글자가 없으면 아무것도 적지 않는다.

출력 형식: 아래 두 표시 사이에 옮겨 적은 본문만 넣어라. 다른 말은 하지 마라.
{BEGIN}
(여기에 본문)
{END}"""


@dataclass
class PageResult:
    page: int                 # 1-기준 PDF 쪽번호
    status: str               # ok | unverified | warn | failed | reading
    chars: int = 0
    base_chars: int = 0
    similarity: float = 0.0
    note: str = ""


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


def _read_codex_cli(model: str, png: Path, timeout: int) -> str:
    cli = llm.codex_cli_path()
    if not cli:
        raise RuntimeError("codex CLI를 찾지 못했습니다")
    out_file = Path(tempfile.gettempdir()) / f"ocr_{png.stem}.txt"
    args = [cli, "exec", "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox", "-o", str(out_file),
            "-i", str(png)]
    if model not in ("default", ""):
        args += ["-m", model]
    args.append("-")
    try:
        r = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
            cwd=tempfile.gettempdir(), encoding="utf-8", errors="replace",
            input=PROMPT, env=llm._cli_env(), **llm._no_window_kwargs())
        if r.returncode != 0:
            raise RuntimeError(f"codex CLI exit {r.returncode}: {(r.stderr or '')[:200]}")
        raw = out_file.read_text(encoding="utf-8") if out_file.exists() else (r.stdout or "")
        return _extract(raw)
    finally:
        out_file.unlink(missing_ok=True)


def _read_claude_cli(model: str, png: Path, timeout: int) -> str:
    cli = llm.claude_cli_path()
    if not cli:
        raise RuntimeError("claude CLI를 찾지 못했습니다")
    prompt = f'이미지 파일 "{png}" 을 Read 도구로 읽어라.\n\n{PROMPT}'
    r = subprocess.run(
        [cli, "-p", prompt, "--model", model or "default", "--output-format", "text",
         "--allowedTools", "Read",
         "--system-prompt", "You transcribe scanned pages verbatim. Never guess."],
        capture_output=True, text=True, timeout=timeout, cwd=str(png.parent),
        encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
        env=llm._cli_env(), **llm._no_window_kwargs())
    if r.returncode != 0:
        raise RuntimeError(f"claude CLI exit {r.returncode}: {(r.stderr or '')[:200]}")
    return _extract(r.stdout or "")


def read_page(provider: str, model: str, png: Path, timeout: int = 600) -> str:
    if provider == "codex_cli":
        return _read_codex_cli(model, png, timeout)
    if provider == "claude_cli":
        return _read_claude_cli(model, png, timeout)
    raise RuntimeError(
        f"'{provider}'로는 아직 쪽 판독을 하지 않습니다 — 구독형 CLI(codex_cli·claude_cli)를 쓰세요")


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
# 실측(2026-08-24, codex 구독): 300dpi로 41쪽 처리에 주간 한도의 10% 소진
# → 주당 약 410쪽. 373쪽짜리 책 한 권이 한 주치를 거의 다 먹는다.
CLI_PAGES_PER_WEEK = 410


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
          workers: int = DEFAULT_WORKERS, progress=None, should_stop=None, timeout: int = 600) -> list[PageResult]:
    """PDF를 쪽마다 다시 읽어 out_txt로 합친다.

    pages는 1-기준 쪽번호 목록(None이면 전체). 이미 읽은 쪽은 건너뛰므로 중단해도
    같은 인자로 다시 부르면 이어서 한다. progress(done, total, PageResult)."""
    pdf_path, out_txt = Path(pdf_path), Path(out_txt)
    total_pages = page_count(pdf_path)
    targets = sorted(pages) if pages else list(range(1, total_pages + 1))
    wd = work_dir(out_txt)
    wd.mkdir(parents=True, exist_ok=True)
    png_dir = wd / "_png"

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

    todo = [pg for pg in targets
            if not ((wd / f"p{pg:04d}.txt").exists()
                    and results.get(pg) and results[pg].status != "failed")]

    def _one(page: int) -> PageResult:
        """한 쪽 판독 — 워커에서 돈다. 쪽끼리 공유 상태가 없어 그대로 병렬로 돌 수 있다."""
        base = base_page_text(pdf_path, page - 1)
        img = None
        try:
            img = render_page(pdf_path, page - 1, png_dir, dpi)
            text = read_page(provider, model, img, timeout)
            status, sim, note = verify(text, base)
            (wd / f"p{page:04d}.txt").write_text(text, encoding="utf-8")
            return PageResult(page, status, len(text), len(base), round(sim, 3), note)
        except Exception as e:
            return PageResult(page, "failed", 0, len(base), 0.0,
                              f"{type(e).__name__}: {str(e)[:160]}")
        finally:
            if img is not None:
                img.unlink(missing_ok=True)

    done, stopped = len(targets) - len(todo), False
    pending = list(todo)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures: dict = {}

        def _submit_next():
            # 처음부터 전부 제출하지 않는다 — 중단 요청이 와도 큐를 비울 수가 없어진다.
            # 하나 끝날 때마다 하나씩 채워 항상 workers개만 떠 있게 한다.
            if pending and not stopped:
                pg = pending.pop(0)
                futures[pool.submit(_one, pg)] = pg
                if progress:
                    # 쪽을 **시작할 때**도 알린다 — 끝날 때만 알리면 한 쪽이 몇 분
                    # 걸리는 동안 화면이 멈춰 보인다 (2026-08-24 사용자 지적).
                    progress(done, len(targets), PageResult(pg, "reading"))

        for _ in range(max(1, workers)):
            _submit_next()
        while futures:
            fut = next(as_completed(list(futures)))
            page = futures.pop(fut)
            results[page] = fut.result()
            done += 1
            _flush()
            if progress:
                progress(done, len(targets), results[page])
            if should_stop and should_stop() and not stopped:
                stopped = True
                append_log(f"AI 재OCR 중단 요청 — {pdf_path.name} "
                           f"({done}/{len(targets)}쪽까지 하고 멈춤)")
            _submit_next()

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
    out_txt.write_text("\f".join(parts), encoding="utf-8")
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

RUNS: dict[str, dict] = {}


def run_key(pdf_path) -> str:
    import unicodedata
    return unicodedata.normalize("NFC", Path(pdf_path).stem)


def is_running(pdf_path) -> bool:
    st = RUNS.get(run_key(pdf_path))
    return bool(st and st.get("thread") and st["thread"].is_alive())


def status(pdf_path) -> dict:
    return RUNS.get(run_key(pdf_path), {})


def request_stop(pdf_path) -> None:
    st = RUNS.get(run_key(pdf_path))
    if st:
        st["stop"] = True


def start_background(pdf_path: Path, out_txt: Path, provider: str, model: str = "",
                     pages: list[int] | None = None, dpi: int = DEFAULT_DPI,
                     workers: int = DEFAULT_WORKERS, timeout: int = 600) -> None:
    """이미 돌고 있으면 아무 일도 하지 않는다."""
    import threading
    key = run_key(pdf_path)
    if is_running(pdf_path):
        return
    state = {"stop": False, "done": 0, "total": len(pages) if pages else page_count(pdf_path),
             "page": 0, "started": time.time(), "error": "", "provider": provider,
             "out_txt": str(out_txt)}
    RUNS[key] = state

    def _progress(done, total, res):
        state.update(done=done, total=total, page=res.page, last=res.status,
                     page_started=time.time() if res.status == "reading" else
                     state.get("page_started", time.time()))

    def _worker():
        try:
            reocr(pdf_path, out_txt, provider, model, pages, dpi,
                  progress=_progress, should_stop=lambda: state["stop"], timeout=timeout)
        except Exception as e:
            state["error"] = f"{type(e).__name__}: {str(e)[:200]}"
            append_log(f"ERROR: AI 재OCR 실패 — {Path(pdf_path).name}: {state['error']}")

    th = threading.Thread(target=_worker, daemon=True, name=f"reocr-{key[:20]}")
    state["thread"] = th
    th.start()
