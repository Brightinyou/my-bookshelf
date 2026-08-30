#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""노트 구획 제목의 단일 출처 (2026-08-31).

요약 노트의 `## 개요`·`## 핵심 인용` 같은 제목은 사람이 읽는 글이면서 동시에
**프로그램이 구획을 찾는 표지**다. 둘을 겸하는 탓에 사고가 났다 — 도착언어를
일본어로 두자 모델이 제목까지 번역해(`## 核心引用`) 뒤따르는 코드가 구획을
찾지 못했고, 인용 검증표가 제자리에 못 들어가고 노트 끝에 하나 더 붙었다.
용어집 정규화는 조용히 건너뛰어졌다.

그래서 두 가지를 여기서 함께 관리한다.

  heading(key)  — **지금 도착언어**의 제목. 새 노트를 쓸 때 쓴다.
  aliases(key)  — **모든 언어**의 제목. 노트를 읽을 때 쓴다.

읽을 때 모든 언어를 받아들이는 것이 중요하다. 보관함에는 이미 한국어로 쓰인
노트가 쌓여 있고, 앞으로 다른 언어의 노트가 섞인다. 쓸 때만 현재 언어를 따르고
읽을 때는 전부 인정해야 옛 노트가 계속 처리된다.
"""
from __future__ import annotations

# key → {언어코드: 제목}. 언어 목록은 services.translate.TARGET_CHOICES 와 같다.
SECTIONS: dict[str, dict[str, str]] = {
    "summary": {
        "ko": "핵심 요약", "en": "Key Summary", "ja": "要約", "zh": "核心摘要",
        "de": "Kurzfassung", "fr": "Résumé", "es": "Resumen", "it": "Sintesi",
        "pt": "Resumo", "nl": "Samenvatting", "ru": "Краткое резюме",
    },
    "overview": {
        "ko": "개요", "en": "Overview", "ja": "概要", "zh": "概述",
        "de": "Überblick", "fr": "Aperçu", "es": "Panorama", "it": "Panoramica",
        "pt": "Visão geral", "nl": "Overzicht", "ru": "Обзор",
    },
    "main": {
        "ko": "주요 내용", "en": "Main Content", "ja": "主要内容", "zh": "主要内容",
        "de": "Hauptinhalt", "fr": "Contenu principal", "es": "Contenido principal",
        "it": "Contenuto principale", "pt": "Conteúdo principal",
        "nl": "Hoofdinhoud", "ru": "Основное содержание",
    },
    "quotes": {
        "ko": "핵심 인용", "en": "Key Quotes", "ja": "主要引用", "zh": "核心引用",
        "de": "Schlüsselzitate", "fr": "Citations clés", "es": "Citas clave",
        "it": "Citazioni chiave", "pt": "Citações principais",
        "nl": "Kernciteten", "ru": "Ключевые цитаты",
    },
    "keywords": {
        "ko": "핵심 키워드", "en": "Key Terms", "ja": "キーワード", "zh": "关键词",
        "de": "Schlüsselbegriffe", "fr": "Mots-clés", "es": "Palabras clave",
        "it": "Parole chiave", "pt": "Palavras-chave",
        "nl": "Kernbegrippen", "ru": "Ключевые термины",
    },
    "toc": {
        "ko": "📋 챕터 목차", "en": "📋 Chapters", "ja": "📋 章目次", "zh": "📋 章节目录",
        "de": "📋 Kapitel", "fr": "📋 Chapitres", "es": "📋 Capítulos",
        "it": "📋 Capitoli", "pt": "📋 Capítulos", "nl": "📋 Hoofdstukken",
        "ru": "📋 Оглавление",
    },
}

# 인용 표의 열 이름. 제목과 달리 구획을 찾는 데 쓰이지 않아 읽기용 별칭이 필요 없다.
TABLE: dict[str, dict[str, str]] = {
    "topic": {
        "ko": "주제", "en": "Topic", "ja": "主題", "zh": "主题", "de": "Thema",
        "fr": "Sujet", "es": "Tema", "it": "Tema", "pt": "Tema",
        "nl": "Onderwerp", "ru": "Тема",
    },
    "quote_raw": {
        "ko": "인용(본문 그대로)", "en": "Quote (verbatim)", "ja": "引用（原文のまま）",
        "zh": "引用（原文）", "de": "Zitat (wörtlich)", "fr": "Citation (texte original)",
        "es": "Cita (literal)", "it": "Citazione (testuale)", "pt": "Citação (literal)",
        "nl": "Citaat (letterlijk)", "ru": "Цитата (дословно)",
    },
    "quote_checked": {
        "ko": "원문 인용(대조 검증)", "en": "Quote (verified against source)",
        "ja": "引用（原文照合済み）", "zh": "引用（原文核对）",
        "de": "Zitat (mit Quelle abgeglichen)", "fr": "Citation (vérifiée)",
        "es": "Cita (verificada)", "it": "Citazione (verificata)",
        "pt": "Citação (verificada)", "nl": "Citaat (geverifieerd)",
        "ru": "Цитата (сверено с оригиналом)",
    },
}

# 노트 첫 줄의 요약 접두사. 제목처럼 코드가 되읽는 표지라 함께 관리한다.
SUMMARY_PREFIX: dict[str, str] = {
    "ko": "요약:", "en": "Summary:", "ja": "要約:", "zh": "摘要：",
    "de": "Zusammenfassung:", "fr": "Résumé :", "es": "Resumen:",
    "it": "Sintesi:", "pt": "Resumo:", "nl": "Samenvatting:", "ru": "Резюме:",
}

FALLBACK = "ko"


def _lang(lang: str | None = None) -> str:
    if lang:
        return lang
    try:
        from services.translate import target_language
        return target_language() or FALLBACK
    except Exception:
        return FALLBACK


def heading(key: str, lang: str | None = None) -> str:
    """지금(또는 지정한) 언어의 구획 제목. 새 노트를 쓸 때 쓴다."""
    table = SECTIONS.get(key, {})
    return table.get(_lang(lang)) or table.get(FALLBACK, key)


def column(key: str, lang: str | None = None) -> str:
    """인용 표의 열 이름."""
    table = TABLE.get(key, {})
    return table.get(_lang(lang)) or table.get(FALLBACK, key)


def aliases(key: str) -> tuple[str, ...]:
    """모든 언어의 제목. 노트를 읽을 때 쓴다 — 옛 한국어 노트도 계속 처리된다.

    긴 것부터 돌려준다. 짧은 제목이 긴 제목의 앞부분과 겹칠 때
    (예: 중국어 '主要内容' 과 일본어 '主要内容') 잘못 끊기지 않게 한다."""
    return tuple(sorted(set(SECTIONS.get(key, {}).values()), key=len, reverse=True))


def md_heading(key: str, lang: str | None = None, level: int = 2) -> str:
    """'## 핵심 인용' 처럼 마크다운 제목 줄 전체."""
    return "#" * level + " " + heading(key, lang)


def is_heading(line: str, key: str) -> bool:
    """이 줄이 그 구획의 제목인가 — 어느 언어로 쓰였든 인정한다."""
    s = line.strip()
    if not s.startswith("#"):
        return False
    body = s.lstrip("#").strip()
    return any(body.startswith(a) for a in aliases(key))


def summary_prefix(lang: str | None = None) -> str:
    """'> **요약:**' 처럼 노트 첫 줄에 붙는 요약 표지 — 지금 언어."""
    return "> **" + (SUMMARY_PREFIX.get(_lang(lang)) or SUMMARY_PREFIX[FALLBACK]) + "**"


def summary_prefixes() -> tuple[str, ...]:
    """모든 언어의 요약 표지 — 노트를 읽을 때. 긴 것부터."""
    return tuple(sorted({"> **" + v + "**" for v in SUMMARY_PREFIX.values()},
                        key=len, reverse=True))
