"""llm_providers.py — 멀티 공급자 LLM 통일 호출 + 키 관리 (2026-06-15)

OpenAI(GPT) / Google(Gemini) / Anthropic(Claude API) + Claude CLI(구독) + Codex CLI(구독).
키는 앱 설정 파일에 저장한 값만 사용한다.
저장 키는 이 컴퓨터 로컬에만 저장하며 저장소/외부로 전송하지 않는다.
"""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import threading
from pathlib import Path
from services.storage import file_lock, write_json_atomic

CONFIG_DIR = Path(os.environ.get("MYBOOKSHELF_CONFIG_DIR") or (Path.home() / ".config" / "mybookshelf"))
KEYS_FILE = CONFIG_DIR / "keys.json"

API_PROVIDERS = ("gemini", "openai", "anthropic")
CLI_PROVIDERS = ("claude_cli", "codex_cli")

# 공급자 레지스트리 — provider 키: {label, models[], hint}
PROVIDERS: dict[str, dict] = {
    "gemini": {
        "label": "Google Gemini",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro"],
        "hint": "Gemini API key",
    },
    "openai": {
        "label": "OpenAI GPT",
        "models": ["gpt-4o", "gpt-4o-mini"],
        "hint": "sk-…",
    },
    "anthropic": {
        "label": "Anthropic Claude (API)",
        "models": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
        "hint": "sk-ant-…",
    },
    "claude_cli": {
        "label": "Claude CLI",
        "models": ["default", "sonnet", "opus", "haiku"],
        "hint": "",
    },
    "codex_cli": {
        "label": "Codex CLI (ChatGPT)",
        "models": ["default"],  # Account-specific IDs are supplied by settings, not guessed.
        "hint": "",
    },
}

# 공급자별 안전 입력 한도 (chars). Gemini=1M 토큰, Claude/GPT=200k/128k 토큰 기준.
# 한국어 기준 roughly 1char≈1token, 영어는 1char≈0.25token — 한국어 기준으로 보수적으로 설정.
MAX_INPUT_CHARS: dict[str, int] = {
    "gemini":    1_900_000,   # Gemini 2.5: 1M 토큰
    "openai":      400_000,   # GPT-4o: 128k 토큰
    "anthropic":   140_000,   # Claude: 200k 토큰 — 출력 여유 60k 확보
    "claude_cli":  140_000,   # Claude CLI: 구독 = API 동일 한도
    "codex_cli":   400_000,   # Codex CLI: OpenAI 모델 기반 (o3/gpt-4o)
}


def _no_window_kwargs() -> dict:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {
        "creationflags": subprocess.CREATE_NO_WINDOW,
        "startupinfo": startupinfo,
    }


def _load_all() -> dict:
    try:
        return json.loads(KEYS_FILE.read_text(encoding="utf-8")) if KEYS_FILE.exists() else {}
    except Exception:
        return {}


def saved_key(provider: str) -> str:
    """Return a key explicitly saved in the app settings screen."""
    all_keys = _load_all()
    return (all_keys.get(provider) or "").strip()


def get_key(provider: str) -> str:
    """Return only the key explicitly saved in the app settings screen."""
    return saved_key(provider)


def key_source(provider: str) -> str:
    if saved_key(provider):
        return "saved"
    return ""


def save_key(provider: str, key: str) -> None:
    """Save keys to keys.json. Empty values clear the saved key."""
    _update_saved({provider: (key or "").strip() or None})


def _update_saved(updates):
    # Desktop resize events and UI settings can arrive in different processes.
    with file_lock(KEYS_FILE.with_suffix(".lock")):
        data = json.loads(KEYS_FILE.read_text(encoding="utf-8")) if KEYS_FILE.exists() else {}
        if all(data.get(k) == v for k, v in updates.items()):
            return
        for key, value in updates.items():
            if value is None:
                data.pop(key, None)
            else:
                data[key] = value
        write_json_atomic(KEYS_FILE, data)
        try:
            os.chmod(KEYS_FILE, 0o600)
        except OSError:
            pass


def has_key(provider: str) -> bool:
    if provider == "claude_cli":
        return claude_cli_available()
    if provider == "codex_cli":
        return codex_cli_available()
    return bool(saved_key(provider))


def masked(provider: str) -> str:
    k = saved_key(provider)
    if not k:
        return ""
    return f"{k[:4]}…{k[-4:]}" if len(k) > 10 else "•" * len(k)


# ── 위키 생성 모델 설정 (provider+model) ──
def first_available_provider_model() -> tuple[str, str]:
    """Return the first configured model, preferring API keys over enabled CLIs."""
    for prov in (*API_PROVIDERS, *CLI_PROVIDERS):
        if prov in PROVIDERS and has_key(prov):
            return prov, PROVIDERS[prov]["models"][0]
    return "gemini", PROVIDERS["gemini"]["models"][0]


def default_provider_model() -> tuple[str, str]:
    """App default. Preserve explicit model IDs, including IDs outside presets."""
    d = _load_all()
    prov = d.get("wiki_provider") or ""
    if prov not in PROVIDERS:
        return first_available_provider_model()
    model = d.get("wiki_model") or PROVIDERS[prov]["models"][0]
    return prov, model


def task_provider_model(task: str) -> tuple[str, str]:
    override = get_pref("task_models", {}).get(task)
    if isinstance(override, dict) and override.get("provider") in PROVIDERS and override.get("model"):
        # Do not silently switch a deliberately configured but unavailable provider.
        return override["provider"], override["model"]
    return default_provider_model()


def wiki_provider_model() -> tuple[str, str]:
    return task_provider_model("summary")


def set_task_model(task: str, provider: str = "", model: str = "") -> None:
    models = dict(get_pref("task_models", {}))
    if provider:
        models[task] = {"provider": provider, "model": _validate_model(provider, model)}
    else:
        models.pop(task, None)
    set_pref("task_models", models)


def _validate_model(provider: str, model: str) -> str:
    model = str(model).strip()
    if provider not in PROVIDERS or not model or any(c.isspace() for c in model):
        raise ValueError("공급자와 공백 없는 모델 ID를 입력하세요")
    return model


def codex_model_catalog() -> dict[str, str]:
    """Read the CLI's local model catalog without contacting an AI provider."""
    root = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    try:
        data = json.loads((root / "models_cache.json").read_text(encoding="utf-8"))
        return {m["slug"]: (m.get("display_name") or m["slug"])
                for m in data.get("models", [])
                if isinstance(m, dict) and isinstance(m.get("slug"), str)
                and m["slug"] and m.get("visibility", "list") == "list"}
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def model_label(provider: str, model: str) -> str:
    if provider == "codex_cli":
        return codex_model_catalog().get(model, model)
    if provider == "claude_cli":
        return {"sonnet": "Claude Sonnet", "opus": "Claude Opus", "haiku": "Claude Haiku"}.get(model, model)
    return model


def model_choices(provider: str) -> list[str]:
    choices = list(PROVIDERS[provider]["models"])
    if provider == "codex_cli":
        choices.extend(codex_model_catalog())
    if provider in CLI_PROVIDERS:
        choices.append(cli_configured_model(provider))
    data = _load_all()
    if data.get("wiki_provider") == provider:
        choices.append(data.get("wiki_model", ""))
    for selected in (data.get("pref_task_models") or {}).values():
        if isinstance(selected, dict) and selected.get("provider") == provider:
            choices.append(selected.get("model", ""))
    return list(dict.fromkeys(m for m in choices if m))

def set_wiki_model(provider: str, model: str) -> None:
    model = _validate_model(provider, model)
    _update_saved({"wiki_provider": provider, "wiki_model": model})


# ── UI 선호 설정 (번역 토글 등 — 재시작해도 유지, 2026-06-11) ──
def get_pref(key: str, default=None):
    return _load_all().get("pref_" + key, default)


def set_pref(key: str, value) -> None:
    _update_saved({"pref_" + key: value})


def cli_model_or_default(provider: str) -> str:
    configured = cli_configured_model(provider)
    if configured:
        return configured
    return (PROVIDERS.get(provider, {}).get("models") or [""])[0]


# CLI가 'default' 모델로 돌 때 세션 헤더에서 확인된 실제 모델명 (요약 노트 기록용)
_CLI_RESULT = threading.local()


def effective_wiki_model() -> str:
    """노트 frontmatter 기록용 실제 모델명 — 'default'면 CLI 헤더에서 잡은 이름."""
    _p, model = wiki_provider_model()
    actual = getattr(_CLI_RESULT, "model", "")
    if model in ("default", "") and getattr(_CLI_RESULT, "provider", "") == _p and actual:
        return actual
    return model


def _cli_env() -> dict:
    """CLI 서브프로세스용 환경 — Finder/launchd로 뜬 앱은 PATH에 /opt/homebrew/bin이
    없어 node 셔뱅 CLI(codex·claude)가 exit 127로 죽는다 (2026-07-09)."""
    env = os.environ.copy()
    cur = env.get("PATH", "")
    parts = cur.split(os.pathsep) if cur else []
    for extra in ("/opt/homebrew/bin", "/usr/local/bin",
                  str(Path.home() / ".local" / "bin"),
                  str(Path.home() / "Library" / "Application Support" / "MyBookshelf" / "node" / "bin")):
        if extra not in parts and Path(extra).is_dir():
            parts.insert(0, extra)
    env["PATH"] = os.pathsep.join(parts)
    return env


def _run_cli_safe(args: list, input_text: str, timeout: int = 600, cwd=None) -> tuple[int, str, str]:
    """CLI 서브프로세스를 subprocess.run(timeout=...)의 Windows 함정을 피해 호출한다.

    codex.CMD처럼 배치파일·셸 래퍼를 거쳐 실제 작업 프로세스를 손자로 띄우는
    CLI(codex.CMD → cmd.exe → node.exe)는, subprocess.run의 timeout이 걸려도
    "직계 자식(cmd.exe)"만 죽고 그 밑의 손자(node.exe, 실제 작업)는 출력 파이프를
    쥔 채 계속 살아남아 communicate()가 타임아웃을 넘겨서까지 영원히 멈춘다
    (2026-08-11 실측: 600초 타임아웃인데 11분 넘게 행 걸림 확인). Windows에서는
    타임아웃 시 taskkill /T로 프로세스 트리 전체를 강제 종료해야 실제로 풀린다."""
    proc = subprocess.Popen(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, cwd=cwd, encoding="utf-8", errors="replace",
        env=_cli_env(), **_no_window_kwargs(),
    )
    try:
        stdout, stderr = proc.communicate(input=input_text, timeout=timeout)
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                            capture_output=True, **_no_window_kwargs())
        else:
            proc.kill()
        try:
            proc.communicate(timeout=10)
        except Exception:
            pass
        raise RuntimeError(f"CLI 시간 초과({timeout}초) — 멈춘 프로세스 트리를 강제 종료했습니다")



# ── CLI 찾기 ──────────────────────────────────────────────────
# npm 전역 설치가 플랫폼 네이티브 바이너리를 못 받으면(--ignore-scripts, --omit=optional,
# 또는 ~/.npm 캐시 권한 문제) "설치 안 됨"만 출력하는 **셰방 없는 텍스트 스텁**이 남는다.
# 실행 비트는 서 있어서 존재 검사·os.access를 통과하고, exec할 때 비로소
# `OSError: [Errno 8] Exec format error`로 죽는다. 실제로 이것 때문에 재OCR
# **316쪽이 통째로 실패**했다 (2026-08-25). 그래서 **쓰기 전에 알맹이를 본다.**
_EXEC_MAGIC = (b"\xcf\xfa\xed\xfe",   # Mach-O 64 리틀엔디언
               b"\xce\xfa\xed\xfe",   # Mach-O 32
               b"\xca\xfe\xba\xbe",   # Mach-O 유니버설
               b"\x7fELF",               # 리눅스
               b"MZ")                     # 윈도우 PE


def _usable_cli(path: Path) -> bool:
    """exec으로 띄울 수 있는 프로그램인가 — 셰방 없는 텍스트 스텁을 걸러낸다."""
    try:
        if not path.is_file() or not os.access(path, os.X_OK):
            return False
        if path.suffix.lower() in (".cmd", ".bat", ".ps1"):
            return True                      # 윈도우는 셸이 해석한다
        with path.open("rb") as stream:
            head = stream.read(4)
    except OSError:
        return False
    return head.startswith(b"#!") or any(head.startswith(m) for m in _EXEC_MAGIC)


def _find_cli(name: str) -> str | None:
    """CLI 실행 파일을 찾는다. **네이티브 설치를 npm 전역보다 먼저** 본다.

    ★`shutil.which`에 앱의 PATH를 그대로 쓰면 안 된다 — Finder/launchd로 뜬 앱의
    PATH에는 ~/.local/bin·/opt/homebrew/bin이 없다. 서브프로세스에 넘기는 것과
    **같은 PATH**로 찾아야 앱과 터미널의 결과가 갈리지 않는다."""
    home = Path.home()
    cands = [home / ".local" / "bin" / name,          # 네이티브 설치(맥·리눅스)
             home / ".local" / "bin" / f"{name}.exe",  # 네이티브 설치(윈도우)
             Path("/opt/homebrew/bin") / name,
             Path("/usr/local/bin") / name,
             Path(os.environ.get("APPDATA", "")) / "npm" / f"{name}.cmd"]
    found = shutil.which(name, path=_cli_env().get("PATH"))
    if found:
        cands.insert(0, Path(found))
    broken: list[str] = []
    for cand in cands:
        if not cand.is_file():
            continue
        if _usable_cli(cand):
            return str(cand)
        broken.append(str(cand))
    if broken:
        _LAST_BROKEN_CLI[name] = broken[0]
    return None


_LAST_BROKEN_CLI: dict[str, str] = {}


def broken_cli_hint(name: str) -> str:
    """찾긴 했는데 못 쓰는 CLI가 있었다면 사람이 고칠 수 있는 말로 알려준다."""
    bad = _LAST_BROKEN_CLI.get(name)
    if not bad:
        return ""
    return (f"'{bad}'가 있지만 실행할 수 없는 껍데기입니다(네이티브 바이너리 누락). "
            f"`npm uninstall -g @anthropic-ai/claude-code` 뒤 공식 설치 관리자로 다시 "
            f"설치하거나, 이미 설치돼 있다면 ~/.local/bin을 PATH 앞에 두세요.")


# ── Claude CLI (구독) ──
def claude_cli_path() -> str | None:
    return _find_cli("claude")


def claude_cli_available() -> bool:
    return bool(get_pref("use_claude_cli", False)) and bool(claude_cli_path())


def claude_cli_installed() -> bool:
    return bool(claude_cli_path())


def set_claude_cli_enabled(enabled: bool) -> None:
    set_pref("use_claude_cli", bool(enabled))


# ── Codex CLI (OpenAI 구독) ──
def codex_cli_path() -> str | None:
    return _find_cli("codex")


def codex_cli_model() -> str:
    """Configured CLI default, not proof of the model used by a request."""
    try:
        cfg_path = Path.home() / ".codex" / "config.toml"
        for line in cfg_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            if s.startswith("["):          # 섹션 시작 = 최상위 설정 끝
                break
            m = re.match(r'^model\s*=\s*["\']([^"\']+)["\']', s)
            if m:
                return m.group(1).strip()
    except Exception:
        pass
    return ""


def claude_cli_model() -> str:
    """Claude CLI가 쓸 모델 (~/.claude/settings.json의 `model`). 없으면 빈 문자열."""
    try:
        d = json.loads((Path.home() / ".claude" / "settings.json").read_text(encoding="utf-8"))
        return str(d.get("model") or "").strip()
    except Exception:
        return ""


def cli_configured_model(provider: str) -> str:
    """CLI 도구 자신이 설정해 둔 모델. 앱 설정보다 이쪽이 실제로 도는 모델이다."""
    if provider == "codex_cli":
        return codex_cli_model()
    if provider == "claude_cli":
        return claude_cli_model()
    return ""


def codex_cli_available() -> bool:
    return bool(get_pref("use_codex_cli", False)) and bool(codex_cli_path())


def codex_cli_installed() -> bool:
    return bool(codex_cli_path())


def set_codex_cli_enabled(enabled: bool) -> None:
    set_pref("use_codex_cli", bool(enabled))


# ── 통일 호출: text-in → text-out ──
def complete(provider: str, model: str, system: str, prompt: str,
             max_tokens: int = 8192, api_key: str | None = None) -> str:
    """선택 공급자/모델로 1회 완성. 키 없거나 호출 실패하면 예외를 던진다."""
    if provider == "claude_cli":
        return _claude_cli(model, system, prompt)
    if provider == "codex_cli":
        return _codex_cli(model, system, prompt)

    key = (api_key or get_key(provider)).strip()
    if not key:
        raise RuntimeError(f"{provider} API 키 없음")

    if provider == "gemini":
        from google import genai
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(model=model, contents=[system, prompt])
        return (resp.text or "").strip()

    if provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()

    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model=model, system=system, max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            b.text for b in resp.content if getattr(b, "type", None) == "text"
        ).strip()

    raise RuntimeError(f"알 수 없는 공급자: {provider}")


def _claude_cli(model: str, system: str, prompt: str) -> str:
    cli = claude_cli_path()
    if not cli:
        raise RuntimeError("claude CLI 없음")
    _CLI_RESULT.provider, _CLI_RESULT.model = "claude_cli", ""
    args = [cli, "-p", "--tools", "", "--system-prompt", system, "--output-format", "text"]
    if model not in ("", "default"):
        args += ["--model", model]
    returncode, stdout, stderr = _run_cli_safe(
        args,
        prompt, timeout=600, cwd=tempfile.gettempdir(),
    )
    if returncode != 0:
        detail = ((stderr or "").strip() + " | " + (stdout or "").strip()).strip(" |")
        raise RuntimeError(f"claude CLI exit {returncode}: {detail[:300]}")
    out = (stdout or "").strip()
    # ~/.claude 자동 메모리 hook이 출력 끝에 붙는 경우 제거
    for marker in ("\n메모리 저장:", "\n저장할 새 메모리 없음"):
        idx = out.rfind(marker)
        if idx != -1:
            out = out[:idx].rstrip()
    return out


def _codex_cli(model: str, system: str, prompt: str) -> str:
    cli = codex_cli_path()
    if not cli:
        raise RuntimeError("codex CLI 없음")
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    _CLI_RESULT.provider, _CLI_RESULT.model = "codex_cli", ""
    with tempfile.TemporaryDirectory(prefix="mb_codex_") as work:
        out_file = Path(work) / "out.txt"
        args = [cli, "exec", "--skip-git-repo-check", "--ephemeral",
                "--sandbox", "read-only", "--disable", "shell_tool",
                "--disable", "unified_exec", "--disable", "view_image", "-o", str(out_file)]
        if model not in ("default", ""):
            args += ["-m", model]
        returncode, stdout, stderr = _run_cli_safe(args + ["-"], full_prompt, timeout=600, cwd=work)
        if returncode:
            detail = ((stderr or "").strip() + " | " + (stdout or "").strip())[-600:]
            raise RuntimeError(f"codex CLI exit {returncode}: {detail}")
        match = re.search(r"(?m)^model:\s*(\S+)", (stdout or "") + (stderr or ""))
        if match:
            _CLI_RESULT.model = match.group(1)
        return out_file.read_text(encoding="utf-8").strip() if out_file.exists() else (stdout or "").strip()


class ModelConfigurationError(RuntimeError):
    """A non-retryable provider/model/authentication problem."""


def configuration_error(error: Exception) -> bool:
    status = getattr(error, "status_code", None)
    text = str(error).lower()
    return status in (401, 403, 404) or any(token in text for token in (
        "does not exist", "do not have access", "model_not_found", "not supported",
        "invalid model", "invalid api key", "incorrect api key", "authentication",
        "not logged in", "401 unauthorized", "403 forbidden", "404 not found", "cli 없음"))


def _strip_fence(t: str) -> str:
    t = (t or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(json)?|```$", "", t.strip()).strip()
    return t


def complete_json(provider: str, model: str, system: str, prompt: str,
                  max_tokens: int = 16384, api_key: str | None = None, retries: int = 5) -> dict:
    """JSON 출력 통일(공급자별 JSON 모드). 위키 생성용. 실패 시 재시도(429는 65초)."""
    if provider in ("claude_cli", "codex_cli"):
        # API 키 불필요 — CLI 구독 사용. 재시도 루프에서 처리.
        key = ""
    else:
        key = (api_key or get_key(provider)).strip()
        if not key:
            raise RuntimeError(f"{provider} API 키 없음")
    last = None
    for attempt in range(retries):
        try:
            if provider == "claude_cli":
                txt = _claude_cli(model, system or "Output only one valid JSON object.",
                                  prompt + "\n\n반드시 유효한 JSON 객체 하나만 출력하라.")
            elif provider == "codex_cli":
                txt = _codex_cli(model, system or "Output only one valid JSON object.",
                                 prompt + "\n\n반드시 유효한 JSON 객체 하나만 출력하라.")
            elif provider == "gemini":
                from google import genai
                client = genai.Client(api_key=key)
                contents = [system, prompt] if system else prompt
                resp = client.models.generate_content(
                    model=model, contents=contents,
                    config={"temperature": 0.3, "response_mime_type": "application/json",
                            "max_output_tokens": max_tokens})
                txt = resp.text or ""
            elif provider == "openai":
                from openai import OpenAI
                client = OpenAI(api_key=key)
                resp = client.chat.completions.create(
                    model=model, max_tokens=max_tokens, temperature=0.3,
                    response_format={"type": "json_object"},
                    messages=[{"role": "system", "content": system or "Output only valid JSON."},
                              {"role": "user", "content": prompt}])
                txt = resp.choices[0].message.content or ""
            elif provider == "anthropic":
                import anthropic
                client = anthropic.Anthropic(api_key=key)
                resp = client.messages.create(
                    model=model, system=system or "Output only one valid JSON object.",
                    max_tokens=max_tokens, temperature=0.3,
                    messages=[{"role": "user", "content": prompt + "\n\n반드시 유효한 JSON 객체 하나만 출력하라."}])
                txt = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            else:
                raise RuntimeError(f"JSON 미지원 공급자: {provider}")
            return json.loads(_strip_fence(txt))
        except Exception as e:
            last = e
            if attempt >= retries - 1:
                raise
            m = str(e).lower()
            is_429 = "429" in m or "resource_exhausted" in m or "rate_limit" in m or "overloaded" in m
            time.sleep(65 if is_429 else 4)
    raise last
