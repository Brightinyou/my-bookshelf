# -*- coding: utf-8 -*-
"""원문 언어 감지 회귀 테스트 — services/langdetect.py.

이 앱은 어떤 언어든 설정에서 고른 도착언어로 옮긴다. 감지가 틀렸을 때의 실제 피해는 둘이다:
  1) 이미 도착언어인 책을 다른 언어로 오판 → 멀쩡한 책이 통째로 번역 대기에 들어간다.
  2) 외국어 책을 도착언어로 오판 → 번역 단계를 건너뛰어 원서가 그대로 요약된다.
아래 테스트는 그 두 방향을 모두 막는다.
"""
import unittest

from services import langdetect as ld


SAMPLES = {
    "de": "Der Begriff der Technik ist nicht einfach zu bestimmen, und es wird deutlich, "
          "dass sich die Frage nach dem Wesen der Technik nicht auf eine bloße Definition "
          "reduzieren lässt. Wenn wir über die Möglichkeiten sprechen, müssen wir auch die "
          "Grenzen bedenken.",
    "nl": "Het begrip techniek is niet eenvoudig te bepalen, en het wordt duidelijk dat de "
          "vraag naar het wezen van de techniek niet tot een simpele definitie kan worden "
          "herleid. Wanneer wij over de mogelijkheden spreken, moeten wij ook de grenzen "
          "bedenken.",
    "en": "The concept of technology is not easy to determine, and it becomes clear that the "
          "question of the essence of technology cannot be reduced to a simple definition in "
          "this context.",
    "fr": "Le concept de la technique n'est pas facile à déterminer, et il est clair que la "
          "question de l'essence de la technique ne peut pas être réduite à une simple "
          "définition dans les faits.",
    "la": "Conceptus technicae non facile est determinare, et manifestum est quod quaestio de "
          "essentia technicae ad simplicem definitionem reduci non potest, cum omnia sint in Deo.",
    "ja": "技術の概念を定めることは簡単ではない。技術の本質についての問いが、単なる定義に還元"
          "できないことは明らかである。可能性について語るとき、私たちは限界についても考えなけ"
          "ればならない。",
    "zh": "技術的概念並不容易確定，而且很明顯，關於技術本質的問題不能簡化為一個簡單的定義。"
          "當我們談論可能性時，也必須考慮其界限與條件。",
    "ru": "Понятие техники нелегко определить, и становится ясно, что вопрос о сущности техники "
          "не может быть сведён к простому определению в данных условиях.",
    "ko": "기술의 개념을 정하는 일은 간단하지 않으며, 기술의 본질에 대한 물음이 단순한 정의로 "
          "환원될 수 없다는 것은 분명하다. 가능성을 말할 때 우리는 한계도 함께 생각해야 한다.",
}


class DetectTests(unittest.TestCase):
    def test_each_language_is_identified(self):
        for want, text in SAMPLES.items():
            with self.subTest(lang=want):
                self.assertEqual(ld.detect(text)[0], want)

    def test_german_and_dutch_are_not_confused(self):
        """가장 닮은 한 쌍 — 여기가 무너지면 기능어 사전이 망가진 것."""
        self.assertEqual(ld.detect(SAMPLES["de"])[0], "de")
        self.assertEqual(ld.detect(SAMPLES["nl"])[0], "nl")

    def test_japanese_needs_kana_chinese_does_not(self):
        """가나가 있으면 일본어, 한자만 있으면 중국어."""
        self.assertEqual(ld.detect(SAMPLES["ja"])[0], "ja")
        self.assertEqual(ld.detect(SAMPLES["zh"])[0], "zh")

    def test_korean_with_foreign_quotations_stays_korean(self):
        """한국어 학술서는 원어 인용이 섞여도 한국어여야 한다 — 아니면 번역 대기로 잘못 간다."""
        mixed = SAMPLES["ko"] + " (vgl. Heidegger, Die Frage nach der Technik, 1954) " \
                + SAMPLES["ko"]
        self.assertEqual(ld.detect(mixed)[0], "ko")

    def test_empty_and_symbol_only_text_is_unknown(self):
        self.assertEqual(ld.detect(""), ("", 0.0))
        self.assertEqual(ld.detect("   \n\n  "), ("", 0.0))
        self.assertEqual(ld.detect("123 456 — ... 789")[0], "")


class BookLevelTests(unittest.TestCase):
    """책 단위 감지 — 첫 장 하나만 보면 안 된다(실측: 『서양철학사』 1장이 독일어
    참고문헌으로 뒤덮여 한국어 번역서가 '독일어'로 잡혔다)."""

    def _write(self, tmp, names_texts):
        out = []
        for name, text in names_texts:
            f = tmp / name
            f.write_text(text, encoding="utf-8")
            out.append(f)
        return out

    def test_foreign_bibliography_in_first_chapter_does_not_flip_the_book(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            german_frontmatter = ("M. P. Nilsson, Geschichte der griechischen Religion "
                                  "(1941). U. von Wilamowitz-Moellendorff, Der Glaube der "
                                  "Hellenen (1931). Zeitschrift für philosophische Forschung, "
                                  "und die Frage nach dem Wesen der Sache ist nicht einfach.")
            files = self._write(tmp, [
                ("01_서론.txt", german_frontmatter),
                ("02_본문.txt", SAMPLES["ko"]),
                ("03_본문.txt", SAMPLES["ko"]),
                ("04_본문.txt", SAMPLES["ko"]),
            ])
            self.assertEqual(ld.detect_file(files[0])[0], "de")   # 1장만 보면 독일어
            self.assertEqual(ld.detect_book(files)[0], "ko")      # 책 전체로는 한국어

    def test_empty_input(self):
        self.assertEqual(ld.detect_book([]), ("", 0.0))


class NameTests(unittest.TestCase):
    def test_names_follow_ui_language(self):
        self.assertEqual(ld.name("de", "ko"), "독일어")
        self.assertEqual(ld.name("de", "en"), "German")
        self.assertEqual(ld.name("la", "en"), "Latin")

    def test_unknown_code_passes_through(self):
        self.assertEqual(ld.name("", "ko"), "")
        self.assertEqual(ld.name("xx", "ko"), "xx")

    def test_every_language_has_both_names(self):
        for code, pair in ld.LANGUAGES.items():
            self.assertEqual(len(pair), 2, code)
            self.assertTrue(all(pair), code)



class TargetLanguageHelpersTests(unittest.TestCase):
    """도착언어 판정 보조 — 고유 문자를 쓰는 언어와 라틴 문자권은 방법이 다르다."""

    def test_own_script_languages(self):
        self.assertTrue(ld.has_own_script("ko"))
        self.assertTrue(ld.has_own_script("ja"))
        self.assertTrue(ld.has_own_script("ru"))
        self.assertFalse(ld.has_own_script("en"))
        self.assertFalse(ld.has_own_script("de"))

    def test_script_ratio(self):
        self.assertGreater(ld.script_ratio(SAMPLES["ko"], "ko"), 0.5)
        self.assertLess(ld.script_ratio(SAMPLES["en"], "ko"), 0.05)
        self.assertGreater(ld.script_ratio(SAMPLES["en"], "en"), 0.9)   # 라틴 비율
        self.assertEqual(ld.script_ratio("", "ko"), 0.0)

    def test_looks_like_uses_script_for_korean(self):
        self.assertTrue(ld.looks_like(SAMPLES["ko"], "ko"))
        self.assertFalse(ld.looks_like(SAMPLES["en"], "ko"))
        self.assertFalse(ld.looks_like(SAMPLES["de"], "ko"))

    def test_looks_like_distinguishes_latin_languages(self):
        """영어 도착일 때 프랑스어 단락을 '이미 도착언어'로 보면 번역을 건너뛴다."""
        self.assertTrue(ld.looks_like(SAMPLES["en"], "en"))
        self.assertFalse(ld.looks_like(SAMPLES["fr"], "en"))
        self.assertFalse(ld.looks_like(SAMPLES["de"], "en"))

    def test_short_latin_text_is_not_claimed(self):
        """표본이 짧아 확신이 없으면 False — 애매할 땐 번역하는 쪽이 안전하다."""
        self.assertFalse(ld.looks_like("Hello there.", "en"))

    def test_looks_like_empty_code(self):
        self.assertFalse(ld.looks_like(SAMPLES["en"], ""))

if __name__ == "__main__":
    unittest.main()
