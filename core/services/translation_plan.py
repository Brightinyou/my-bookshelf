"""Lossless translation view over an immutable source; no AI or filesystem writes.

Page/note boundaries remain output boundaries. Nearby body text may be sent as
read-only context instead of moving footnotes or page markers across sentences.
All offsets refer to the original Python string (Unicode code points).
"""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import unicodedata

VERSION = "structure-v2"
# Unchanged text/role/context can reuse v1 successes. Changed sentence grouping
# naturally has a different key; a planner upgrade alone need not discard it all.
CACHE_VERSION = "structure-v1"
PAGE = "[[PAGEBREAK]]"
NUMBERED = re.compile(r"^\s*(?:\[?\d{1,3}\]?[\s.,):]|†\s|\[\^[^]]+\]:)")
HEADING = re.compile(r"^\s*(?:#{1,6}\s|\d+(?:\.\d+){1,3}\s)")
SENTENCE_END = re.compile(r'''[.!?。！？](?:[”’"')\]]|\[\d{1,4}\]|[\d⁰¹²³⁴⁵⁶⁷⁸⁹])*(?=\s|$)''')
ABBREVIATION = re.compile(r"(?:\b(?:Mr|Mrs|Ms|Dr|Prof|St|vs|etc|cf|vol|pp?)\.|\b(?:[A-Za-z]\.){1,4})$", re.I)


def sentence_ends(text):
    """Conservative stops, including citation numbers after punctuation.

    Initials and common abbreviations are not useful places to cut a sentence.
    False negatives merely make a longer translation unit.
    """
    return [m.end() for m in SENTENCE_END.finditer(text)
            if not ABBREVIATION.search(text[:m.start()+1])]


def ends_sentence(text):
    stops = sentence_ends(text.rstrip())
    return bool(stops and stops[-1] == len(text.rstrip()))


def repair_sentence_boundaries(parts, target=3000, limit=12000):
    """Repair artificial body chunks only; callers exclude notes/pages/headings.

    Join a split sentence before rechunking at sentence ends. An exceptionally
    long sentence without a usable stop still has a bounded request size; the
    remaining fragment boundary is explicitly marked by build_plan.
    """
    groups = []
    for part in parts:
        if groups and not ends_sentence(groups[-1]):
            groups[-1] = groups[-1].rstrip() + " " + part.lstrip()
        else:
            groups.append(part)
    result = []
    for group in groups:
        while len(group) > target:
            stops = sentence_ends(group)
            before = [s for s in stops if s <= target]
            after = [s for s in stops if target < s <= limit]
            cut = before[-1] if before else (after[0] if after else 0)
            if not cut:
                if len(group) <= limit:
                    break
                cut = group.rfind(" ", 0, limit + 1)
                if cut < limit // 2:
                    cut = limit
            result.append(group[:cut].rstrip())
            group = group[cut:].lstrip()
        if group:
            result.append(group)
    return result


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compact(text):
    return re.sub(r"\s+", "", text)


def _letters(text):
    return "".join(c.casefold() for c in unicodedata.normalize("NFC", text) if c.isalpha())


def repeated_headers(text, titles=()):
    """Only isolated, numbered, repeated title lines; never remove their body.

    Legacy TXT often has no page separators. In that case a known title match
    AND three occurrences with changing page numbers are required. Mere numeric
    prefixes, bibliography entries, and matching words within prose are not proof.
    """
    aliases = {_letters(t) for title in titles for t in str(title).split("_") if len(_letters(t)) >= 4}
    candidates = defaultdict(list)
    for match in re.finditer(r"[^\r\n\f]+", text):
        line = match.group().strip()
        if not (4 <= len(line) <= 85) or ends_sentence(line):
            continue
        numbers = re.findall(r"\d+", line)
        letters = _letters(line)
        if (not numbers or letters not in aliases or not re.match(r"^\d", line)
                or re.search(r"https?://|doi|ibid|\bpp?\.", line, re.I)):
            continue
        # The line must precede some text, not just be the tail of a TOC.
        if not text[match.end():].strip():
            continue
        candidates[letters].append((match.start(), match.end(), tuple(numbers)))
    removed = []
    for entries in candidates.values():
        if len(entries) < 3 or len({nums for _, _, nums in entries}) < 3:
            continue
        for start, end, _ in entries:
            removed.append({"start": start, "end": end, "text": text[start:end],
                            "reason": "repeated_numbered_title"})
    return sorted(removed, key=lambda r: r["start"])


def _role(text, note_regions, body_regions):
    if text == PAGE:
        return "page"
    if HEADING.match(text):
        return "heading"
    norm = compact(text)
    if (len(norm) >= 12 and any(norm in region for region in note_regions)
            and not any(norm in region for region in body_regions)):
        return "footnote"
    if NUMBERED.match(text):
        return "note_candidate"
    return "body"


def load_layout(chapter):
    """Use matching extraction hints only; stale sidecars must not label new text."""
    import config as cfg
    path = Path(cfg.TXT_DIR) / (chapter.parent.name + ".layout.json")
    source = path.with_name(chapter.parent.name + ".txt")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("text_sha256") != digest(source.read_text(encoding="utf-8")):
            return []
        regions = data.get("regions", [])
        return [r for r in regions if isinstance(r, dict) and isinstance(r.get("text"), str)] if isinstance(regions, list) else []
    except (OSError, ValueError, TypeError, AttributeError):
        return []


def build_plan(text, splitter, titles=(), regions=()):
    removed = repeated_headers(text, titles)
    masked = list(text)
    for entry in removed:
        masked[entry["start"]:entry["end"]] = " " * (entry["end"] - entry["start"])
    cleaned = "".join(masked)
    note_regions = [compact(r["text"]) for r in regions if r.get("kind") == "footnote" and r.get("text")]
    body_regions = [compact(r["text"]) for r in regions if r.get("kind") == "body" and r.get("text")]
    units, run = [], []
    page = 0

    def emit(start, end, value, kind, page_num):
        units.append({"id": digest(f"{start}:{end}:{value}")[:24], "start": start, "end": end,
                      "page": page_num, "kind": kind, "text": value})

    def flush():
        if not run:
            return
        start, end, page_num = run[0][0], run[-1][1], run[0][2]
        source = cleaned[start:end]
        parts = splitter(source)
        # A splitter cannot drop, duplicate or reorder non-whitespace characters.
        if compact("".join(parts)) != compact(source):
            parts = [source.strip()]
        parts = repair_sentence_boundaries(parts)
        offsets = [i for i in range(start, end) if not cleaned[i].isspace()]
        cursor = 0
        for part in parts:
            count = len(compact(part))
            if count:
                emit(offsets[cursor], offsets[cursor + count - 1] + 1, part, "body", page_num)
                cursor += count
        run.clear()

    pattern = re.compile(r"\f|\[\[PAGEBREAK\]\]|(?:\r?\n[ \t]*){2,}")
    position = 0
    for separator in list(pattern.finditer(cleaned)) + [None]:
        end = separator.start() if separator else len(cleaned)
        value = cleaned[position:end].strip()
        if value:
            start = position + len(cleaned[position:end]) - len(cleaned[position:end].lstrip())
            stop = end - (len(cleaned[position:end]) - len(cleaned[position:end].rstrip()))
            kind = _role(value, note_regions, body_regions)
            if kind == "body":
                run.append((start, stop, page))
            else:
                flush()
                emit(start, stop, value, kind, page)
        if separator:
            if separator.group() in ("\f", PAGE):
                flush()
                emit(separator.start(), separator.end(), PAGE, "page", page)
                page += 1
            position = separator.end()
    flush()
    for i, unit in enumerate(units):
        if (i and unit["kind"] == units[i-1]["kind"] == "body"
                and not ends_sentence(units[i-1]["text"])):
            unit["boundary_warning"] = "sentence_exceeds_safe_request_size"
    # A removed line may lie within a unit's broad span. Record exact excluded
    # spans as well; reconstructing retained characters is deterministic.
    for unit in units:
        unit["excluded"] = [[r["start"], r["end"]] for r in removed
                            if r["start"] < unit["end"] and r["end"] > unit["start"]]
    for i, unit in enumerate(units):
        if unit["kind"] in {"page", "heading"}:
            unit["context"] = {}
            continue
        context = {}
        if unit["kind"] in {"note_candidate", "footnote"} or not ends_sentence(unit["text"]):
            for label, indices in (("before", range(i - 1, max(-1, i - 9), -1)),
                                   ("after", range(i + 1, min(len(units), i + 9)))):
                for j in indices:
                    other = units[j]
                    if abs(other["page"] - unit["page"]) > 1 or other["kind"] == "heading":
                        break
                    if other["kind"] == "body":
                        context[label] = other["text"][-600:] if label == "before" else other["text"][:600]
                        break
        # The second half of a continued sentence needs its preceding page too.
        if i and units[i-1]["kind"] == "page" and unit["kind"] == "body":
            for other in reversed(units[max(0, i-8):i-1]):
                if other["kind"] == "heading":
                    break
                if other["kind"] == "body":
                    if not ends_sentence(other["text"]):
                        context["before"] = other["text"][-600:]
                    break
        unit["context"] = context
    source_chars = len(compact(text.replace("\f", "").replace(PAGE, "")))
    retained = sum(len(compact(u["text"])) for u in units if u["kind"] != "page")
    removed_chars = sum(len(compact(r["text"])) for r in removed)
    if retained + removed_chars != source_chars:
        raise ValueError("Translation plan lost source characters")
    return {"version": VERSION, "source_sha256": digest(text), "offset_unit": "unicode_codepoint",
            "units": units, "removed": removed,
            "coverage": {"source_chars": source_chars, "retained_chars": retained,
                         "removed_chars": removed_chars}}


def cache_key(unit, target):
    return digest(json.dumps([CACHE_VERSION, target, unit["text"], unit["kind"], unit["context"]],
                             ensure_ascii=False, sort_keys=True))
