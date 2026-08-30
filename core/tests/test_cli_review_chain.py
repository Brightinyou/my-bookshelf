import unittest
from unittest import mock

import chapter_wiki


class CodexClaudeReviewChainTest(unittest.TestCase):
    def _patch_common(self):
        return mock.patch.multiple(
            chapter_wiki,
            _length_params=mock.Mock(return_value={
                "pct": 15,
                "target": 1200,
                "n_sub": 3,
                "per_sub": 400,
                "n_cite": 3,
                "n_kw": "5~9",
                "sent_ov": "4~6",
                "max_out": 6000,
            }),
            _glossary=mock.Mock(return_value={}),
        )

    def test_enabled_chain_drafts_with_codex_then_reviews_with_claude(self):
        calls = []

        def fake_complete_json(provider, model, system, prompt, max_tokens=0, **_kwargs):
            calls.append((provider, model))
            if provider == "codex_cli":
                return {"summary": "draft summary", "body": "## draft body"}
            if provider == "claude_cli":
                return {"summary": "reviewed summary", "body": "## reviewed body"}
            raise AssertionError(provider)

        with self._patch_common(), \
             mock.patch.object(chapter_wiki.llm, "wiki_codex_claude_review_enabled", return_value=True), \
             mock.patch.object(chapter_wiki.llm, "wiki_codex_claude_review_available", return_value=True), \
             mock.patch.object(chapter_wiki.llm, "cli_model_or_default",
                               side_effect=lambda p: "default" if p == "codex_cli" else "claude-sonnet-4-6"), \
             mock.patch.object(chapter_wiki.llm, "complete_json", side_effect=fake_complete_json), \
             mock.patch.object(chapter_wiki.gw, "rebuild_citations",
                               side_effect=lambda body, *_args, **_kwargs: (body, [], 0)):
            out = chapter_wiki.generate_chapter("book", "chapter", "source text " * 200)

        self.assertEqual(calls, [
            ("codex_cli", "default"),
            ("claude_cli", "claude-sonnet-4-6"),
        ])
        self.assertEqual(out["summary"], "reviewed summary")
        self.assertEqual(out["body"], "## reviewed body")

    def test_claude_review_failure_preserves_codex_draft(self):
        calls = []

        def fake_complete_json(provider, model, system, prompt, max_tokens=0, **_kwargs):
            calls.append(provider)
            if provider == "codex_cli":
                return {"summary": "draft summary", "body": "## draft body"}
            raise RuntimeError("claude failed")

        with self._patch_common(), \
             mock.patch.object(chapter_wiki.llm, "wiki_codex_claude_review_enabled", return_value=True), \
             mock.patch.object(chapter_wiki.llm, "wiki_codex_claude_review_available", return_value=True), \
             mock.patch.object(chapter_wiki.llm, "cli_model_or_default",
                               side_effect=lambda p: "default" if p == "codex_cli" else "claude-sonnet-4-6"), \
             mock.patch.object(chapter_wiki.llm, "complete_json", side_effect=fake_complete_json), \
             mock.patch.object(chapter_wiki.gw, "rebuild_citations",
                               side_effect=lambda body, *_args, **_kwargs: (body, [], 0)):
            out = chapter_wiki.generate_chapter("book", "chapter", "source text " * 200)

        self.assertEqual(calls, ["codex_cli", "claude_cli"])
        self.assertEqual(out["summary"], "draft summary")
        self.assertEqual(out["body"], "## draft body")


if __name__ == "__main__":
    unittest.main()
