"""Lossless preparation, independent note policy, and durable translation reuse."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services import translate as tr, translation_plan as plan, pdfcols, convert, footnotes


class PlanTest(unittest.TestCase):
    def prepare(self, text, **kwargs):
        result = plan.build_plan(text, tr._split_paragraphs_robust, **kwargs)
        coverage = result["coverage"]
        self.assertEqual(coverage["source_chars"], coverage["retained_chars"] + coverage["removed_chars"])
        for unit in result["units"]:
            if unit["kind"] == "page":
                continue
            original = list(text[unit["start"]:unit["end"]])
            for start, end in unit["excluded"]:
                for i in range(max(start, unit["start"]), min(end, unit["end"])):
                    original[i-unit["start"]] = " "
            self.assertEqual(plan.compact("".join(original)), plan.compact(unit["text"]))
        return result

    def test_short_sentence_is_not_deleted(self):
        text = "No. " + "A very long meaningful sentence remains important " * 100 + "."
        self.assertEqual(plan.compact("".join(tr._split_paragraphs_robust(text))), plan.compact(text))
        self.prepare(text)

    def test_artificial_split_inside_quotation_is_repaired(self):
        parts = ['An introduction. He describes "some faculty or capacity man',
                 'possesses” that distinguishes “man from other animals.”9']
        repaired = plan.repair_sentence_boundaries(parts)
        self.assertEqual(len(repaired), 1)
        self.assertEqual(plan.compact("".join(repaired)), plan.compact("".join(parts)))
        self.assertIn('man possesses', repaired[0])

    def test_footnote_suffix_and_quote_are_sentence_endings(self):
        for value in ('A completed sentence.”9', 'A completed sentence.⁴',
                      'A completed sentence.[12]', '문장이 끝난다.39'):
            self.assertTrue(plan.ends_sentence(value), value)
        for value in ('Research into A.I.', 'A statement by Dr.', 'some faculty man'):
            self.assertFalse(plan.ends_sentence(value), value)

    def test_rechunk_at_sentence_end_not_line_budget(self):
        sentence = 'A meaningful sentence with several ordinary words.9 '
        text = sentence * 180
        parts = [text[i:i+1500] for i in range(0, len(text), 1500)]
        result = plan.repair_sentence_boundaries(parts)
        self.assertGreater(len(result), 1)
        self.assertTrue(all(plan.ends_sentence(p) for p in result))
        self.assertEqual(plan.compact(''.join(result)), plan.compact(text))

    def test_extremely_long_sentence_is_bounded_and_audited(self):
        text = 'unbroken words ' * 1700
        result = self.prepare(text)
        self.assertTrue(any(u.get('boundary_warning') for u in result['units']))
        self.assertTrue(all(len(u['text']) <= 12000 for u in result['units']))

    def test_final_short_body_never_appended_to_note_or_page(self):
        for protected in ("3 Psalm 8:4.", tr._PAGE_TOKEN):
            self.assertEqual(tr._merge_short_blocks([protected, "No."]), [protected, "No."])

    def test_short_chapter_keeps_note(self):
        self.assertIn("3 Psalm 8:4.", tr._split_paragraphs_robust("3 Psalm 8:4.\n\nNo."))

    def test_note_and_page_stay_in_source_order_with_context(self):
        parts = ["A sentence continues across", "12 Smith, J. explains the important distinction", "\f", "a page boundary."]
        result = self.prepare("\n\n".join(parts))
        units = result["units"]
        self.assertEqual([u["text"] for u in units], parts[:2] + [plan.PAGE, parts[3]])
        self.assertEqual(units[0]["context"]["after"], parts[3])
        self.assertEqual(units[3]["context"]["before"], parts[0])
        self.assertEqual(units[1]["kind"], "note_candidate")

    def test_context_does_not_cross_heading(self):
        units = self.prepare("An unfinished thought\n\n# New Section\n\nAnother thought.")["units"]
        self.assertNotIn("after", units[0]["context"])

    def test_removes_only_repeated_numbered_known_titles(self):
        text = "\n\n".join(f"{n} Culture Making\nA different body fragment {n}." for n in (20, 22, 24))
        result = self.prepare(text, titles=("Culture Making",))
        self.assertEqual(len(result["removed"]), 3)
        self.assertTrue(all("A different body fragment" in u["text"] for u in result["units"]))

    def test_unknown_title_or_repeated_same_number_not_removed(self):
        for title in ("Unknown Book", "Culture Making"):
            result = self.prepare("20 Culture Making\nA body.\n\n" * 3, titles=(title,))
            self.assertFalse(result["removed"])

    def test_broken_splitter_falls_back_to_original(self):
        source = "Keep this.\n\nAnd this too."
        result = plan.build_plan(source, lambda text: ["Keep this."])
        self.assertEqual(result["units"][0]["text"], source)

    def test_layout_hints_protect_unnumbered_note(self):
        note = "An explanatory footnote without a number"
        result = self.prepare("Some body.\n\n" + note, regions=[{"kind": "footnote", "text": note}])
        self.assertEqual(result["units"][1]["kind"], "footnote")

    def test_ambiguous_layout_not_claimed_as_footnote(self):
        text = "Text appearing both in body and a note."
        result = self.prepare(text, regions=[{"kind": kind, "text": text} for kind in ("body", "footnote")])
        self.assertEqual(result["units"][0]["kind"], "body")

    def test_cache_identity_depends_on_context_target_not_position(self):
        unit = {"text": "Same source.", "kind": "body", "context": {}, "start": 0}
        key = plan.cache_key(unit, "ko")
        self.assertEqual(key, plan.cache_key(dict(unit, start=99), "ko"))
        self.assertNotEqual(key, plan.cache_key(unit, "es"))
        self.assertNotEqual(key, plan.cache_key(dict(unit, context={"before": "Different."}), "ko"))

    def test_explanatory_notes_are_translated(self):
        for text in ("1 Smith, J. argues otherwise", "2 This is why it matters, p. 12.",
                     "† The argument continues here", "3 https://example.org shows otherwise",
                     "4 설명이 있는 각주이다. p. 5.", "3.4.2 Artificial Persons", "No."):
            self.assertIsNone(tr.skip_reason(text), text)

    def test_identifiers_and_short_citations_are_retained(self):
        for text in ("123", "https://example.org", "doi:10.1234/abc", "3 Psalm 8:4."):
            self.assertIsNotNone(tr.skip_reason(text), text)

    def test_context_and_retry_instructions_never_become_target_text(self):
        source = "A meaningful fragment"
        with patch.object(tr.llm, "complete", side_effect=[source, "의미가 있는 문장의 일부입니다."]) as complete:
            output = tr._translate_paragraph(source, "test:model", target="ko", context={"after": "continues here."})
        self.assertTrue(output)
        self.assertEqual(complete.call_count, 2)
        for call in complete.call_args_list:
            payload = json.loads(call.args[3])
            self.assertEqual(payload["target_text"], source)
            self.assertEqual(payload["reference_context"]["after"], "continues here.")
            self.assertIn("Translate ONLY target_text", call.args[2])


class CacheTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "01_Test.txt"
        self.source = "First complete sentence.\n\nSecond complete sentence."
        self.path.write_text(self.source, encoding="utf-8")
        for p in (patch.object(tr, "target_language", return_value="ko"),
                  patch.object(tr, "needs_translation", return_value=True),
                  patch.object(tr, "_split_paragraphs_robust", side_effect=lambda text: text.split("\n\n")),
                  patch.object(tr, "translate_title", return_value="시험"),
                  patch.object(tr, "append_log")):
            p.start()
            self.addCleanup(p.stop)

    def sidecar(self, suffix):
        return self.path.with_name("01_Test" + suffix)

    def run_translation(self):
        with patch.object(tr, "_translate_paragraph", return_value="문장의 의미를 옮긴 번역입니다.") as mock:
            ok, msg = tr.translate_one_chapter(self.path, "test", want_bilingual=True)
        self.assertTrue(ok, msg)
        return mock

    def test_completed_cache_survives_and_source_is_unchanged(self):
        self.assertEqual(self.run_translation().call_count, 2)
        self.assertTrue(self.sidecar("_ko.cache.json").exists())
        self.assertFalse(self.sidecar("_ko.progress.json").exists())
        self.assertEqual(self.run_translation().call_count, 0)
        self.assertEqual(self.path.read_text(encoding="utf-8"), self.source)
        audit = json.loads(self.sidecar("_ko.audit.json").read_text(encoding="utf-8"))
        self.assertEqual(len(audit["results"]), 2)

    def test_old_preserved_and_dropped_are_reconsidered(self):
        self.sidecar("_ko.progress.json").write_text(json.dumps([
            {"idx": i, "src": text, "tgt": text, "status": status}
            for i, (text, status) in enumerate(zip(self.source.split("\n\n"), ("preserved", "dropped")), 1)
        ]), encoding="utf-8")
        self.assertEqual(self.run_translation().call_count, 2)

    def test_successful_cache_is_reused_after_index_shift(self):
        self.run_translation()
        self.path.write_text("New introductory sentence.\n\n" + self.source, encoding="utf-8")
        self.assertEqual(self.run_translation().call_count, 1)

    def test_context_change_is_not_reused(self):
        self.path.write_text("An unfinished thought\n\n1 An explanation without a final stop\n\nA final sentence.", encoding="utf-8")
        self.assertEqual(self.run_translation().call_count, 3)
        self.path.write_text(self.path.read_text(encoding="utf-8").replace("final sentence", "different conclusion"), encoding="utf-8")
        self.assertEqual(self.run_translation().call_count, 3)

    def test_completed_bilingual_can_supply_known_target_cache(self):
        self.run_translation()
        self.sidecar("_ko.cache.json").unlink()
        self.sidecar("_ko.status.json").write_text('{"target": "ko", "state": "complete"}', encoding="utf-8")
        self.assertEqual(self.run_translation().call_count, 0)

    def test_removing_context_cannot_import_contextful_bilingual_output(self):
        self.path.write_text("An unfinished thought\n\n1 An explanation without a final stop\n\nA final sentence.", encoding="utf-8")
        self.run_translation()
        self.path.write_text("An unfinished thought", encoding="utf-8")
        self.assertEqual(self.run_translation().call_count, 1)

    def test_old_bilingual_unknown_target_is_not_reused(self):
        self.run_translation()
        self.sidecar("_ko.cache.json").unlink()
        self.sidecar("_ko.status.json").write_text('{}', encoding="utf-8")
        self.assertEqual(self.run_translation().call_count, 2)

    def test_translated_note_can_still_be_linked_for_epub(self):
        source = "The point is explained.39 Further body.\n\n39 This is an explanatory footnote, not just a citation.\fThe next page."
        self.path.write_text(source, encoding="utf-8")
        translations = ["설명한다.39 뒤의 본문이다.", "39 이것은 서지정보만이 아니라 설명을 담은 각주이다.", "다음 쪽이다."]
        with patch.object(tr, "_translate_paragraph", side_effect=translations):
            ok, msg = tr.translate_one_chapter(self.path, "test")
        self.assertTrue(ok, msg)
        output = self.sidecar("_ko.txt").read_text(encoding="utf-8")
        self.assertEqual(output.count("\f"), 1)
        self.assertLess(output.index("39 이것은"), output.index("\f"))
        notes = footnotes.convert(output)
        self.assertEqual(notes.linked, 1)
        self.assertEqual(notes.notes[0].num, 39)


class LayoutTest(unittest.TestCase):
    def test_extraction_records_only_evidenced_note_boundaries(self):
        class Document(list):
            def close(self):
                pass
        regions = []
        with patch.object(pdfcols.pdfium, "PdfDocument", return_value=Document([object(), object()])), \
                patch.object(pdfcols, "_footnote_rule_y", side_effect=[75, None]), \
                patch.object(pdfcols, "_reading_order", side_effect=["Body.", "Unknown layout."]), \
                patch.object(pdfcols, "_notes_text", return_value="12 A footnote."):
            pages, skipped = pdfcols.pdf_to_pages("unused.pdf", regions=regions)
        self.assertEqual(skipped, 0)
        self.assertEqual(pages, ["Body.\n\n12 A footnote.", "Unknown layout."])
        self.assertEqual([r["kind"] for r in regions], ["body", "footnote", "unknown"])
        self.assertEqual(regions[1]["boundary_y"], 75)

    def test_conversion_sidecar_matches_text_and_discards_fallback_hints(self):
        for fallback in (False, True):
            with self.subTest(fallback=fallback), tempfile.TemporaryDirectory() as folder:
                text = "A normal body sentence."
                def extract(path, regions):
                    regions.append({"kind": "footnote", "text": "12 A footnote."})
                    return ("" if fallback else text), 0
                with patch.object(convert.tempfile, "mkdtemp", return_value=folder), \
                        patch.object(pdfcols, "pdf_to_text", side_effect=extract), \
                        patch.object(convert, "_pdftotext_fallback", return_value=text):
                    path, _, error, _ = convert.pdf_to_txt(Path("Book.pdf"))
                self.assertFalse(error)
                data = json.loads(path.with_suffix(".layout.json").read_text(encoding="utf-8"))
                self.assertEqual(data["text_sha256"], plan.digest(path.read_text(encoding="utf-8")))
                self.assertEqual(bool(data["regions"]), not fallback)

    def test_stale_layout_is_ignored(self):
        import config
        with tempfile.TemporaryDirectory() as folder, patch.object(config, "TXT_DIR", Path(folder)):
            source = Path(folder) / "Book.txt"
            source.write_text("Original source", encoding="utf-8")
            source.with_suffix(".layout.json").write_text(json.dumps({
                "text_sha256": plan.digest("Original source"),
                "regions": [{"kind": "footnote", "text": "A note"}],
            }), encoding="utf-8")
            chapter = Path(folder) / "Book" / "01_Chapter.txt"
            self.assertEqual(len(plan.load_layout(chapter)), 1)
            source.write_text("Changed source", encoding="utf-8")
            self.assertEqual(plan.load_layout(chapter), [])


if __name__ == "__main__":
    unittest.main()
