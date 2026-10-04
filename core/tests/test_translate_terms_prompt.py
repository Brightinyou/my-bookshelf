# -*- coding: utf-8 -*-
"""번역 지시문의 용어 규칙 — services/translate.build_translate_system.

2026-10-04 연구자 보고: 번역본 본문에 agent·accountability·ethics 같은 낱말이
영어로 남았다(『AI and Ethics When Human Beings Collaborate With AI Agents』 109단락 중
42단락). 지시문의 «Preserve technical terms … as-is» 를 모델이 «학술 용어는 영어로
둔다»로 읽었기 때문이다. 연구자가 정한 규칙은 «고유명사·보통명사 다 번역하고
(원어)를 넣는다»이다.

실제 엔진(codex_cli:default)으로 같은 세 단락을 비교한 결과, 본문에 남은 영어 낱말이
45개 → 2개(둘 다 원문이 낱말 자체를 다루는 responsabilidad·“responsibility”)였다.
여기서는 그 규칙이 지시문에서 다시 빠지지 않게 못 박는다.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
import unittest

from services import translate as tr


class TranslateTermsPromptTest(unittest.TestCase):
    def test_학술_용어를_원어로_두라는_지시가_없다(self):
        prompt = tr.build_translate_system("en", "ko")
        self.assertNotIn("Preserve technical terms", prompt)

    def test_모든_낱말을_번역하고_첫_등장에_원어를_붙인다(self):
        prompt = tr.build_translate_system("en", "ko")
        self.assertIn("Translate EVERY word into Korean, including technical terms", prompt)
        self.assertIn("original in parentheses", prompt)
        self.assertIn("책무성(accountability)", prompt)

    def test_제목도_번역_대상이다(self):
        self.assertIn("titles of works", tr.build_translate_system("en", "ko").split("Keep as-is only")[0])

    def test_한국어_예시는_한국어_도착일_때만(self):
        prompt = tr.build_translate_system("en", "de")
        self.assertIn("Translate EVERY word into German", prompt)
        self.assertNotIn("책무성", prompt)


if __name__ == "__main__":
    unittest.main()
