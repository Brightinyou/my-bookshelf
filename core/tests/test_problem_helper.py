"""문제 도우미 (2026-10-13).

«부분완료»로 멈춘 장이 다시 해도 계속 실패했다. 실측(Wester 외 2026, 03·08장):
실패 단락은 «7 20 < 1 11 4 17»(표 숫자 조각)과 «7.3.1 Maya.» 같은 이름 소제목뿐이었다.
  · 지시문은 첫 등장에 «마야(Maya)»를 붙이라 하고, 검사기는 원문과 82% 넘게 닮으면
    떨어뜨렸다 — 짧은 줄에선 지시대로 하면 반드시 떨어진다.
  · 실패가 하나라도 있으면 번역본(_ko.txt)을 아예 쓰지 않았다.
여기서 못 박는 것: 검사기 고침, 사용자가 정한 단락(원문 유지·직접 입력)으로 장이
완성되는 것, AI 제안은 실패 목록 안의 단락만 건드리는 것, 보고서가 본문·개인정보를 빼는 것.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401
import _isolation  # noqa: F401,E402 — 실제 설정·자료 폴더 대신 임시 폴더 (먼저 불러와야 한다)
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

from services import helper
from services import translate as tr

BODY = ("Maya is navigating a big identity shift after stepping away from the religious "
        "tradition she grew up in, and she wants someone to listen without judging her.")
HEADING = "7.3.1 Maya."
TABLE = "7 20 < 1 11 4 17"


def _fake_complete(provider, model, system, prompt, **kw):
    """본문은 번역하고, 소제목은 지시대로 «마야(Maya)»가 아닌 원문 그대로 돌려준다(검사 탈락)."""
    if "Maya is navigating" in prompt:
        return "마야는 자라 온 종교 전통을 떠난 뒤 큰 정체성 변화를 겪고 있으며, 판단 없이 들어 줄 사람을 원한다."
    return HEADING


class ValidatorTest(unittest.TestCase):
    def test_parenthesised_original_on_a_short_heading_passes(self):
        self.assertTrue(tr._translation_is_valid(HEADING, "7.3.1 마야(Maya).", "ko"))
        self.assertTrue(tr._translation_is_valid("7.3.3 Samira.", "7.3.3 사미라(Samira).", "ko"))

    def test_untranslated_heading_still_fails(self):
        self.assertFalse(tr._translation_is_valid(HEADING, HEADING, "ko"))
        self.assertFalse(tr._translation_is_valid(HEADING, "7.3.1 Maya (Maya).", "ko"))

    def test_number_and_symbol_fragment_is_preserved_not_sent(self):
        self.assertEqual(tr.skip_reason(TABLE), "숫자·기호 보존")
        self.assertIsNone(tr.skip_reason(HEADING))


class ChapterTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ch = Path(tmp.name) / "Some Paper" / "08_Appendix.txt"
        self.ch.parent.mkdir()
        self.ch.write_text(f"{HEADING}\n\n{BODY}\n\n{TABLE}\n", encoding="utf-8")
        for p in (mock.patch.object(tr.llm, "complete", side_effect=_fake_complete),
                  mock.patch.object(tr, "target_language", return_value="ko"),
                  mock.patch.object(tr, "translate_title", return_value="부록"),
                  mock.patch.object(tr.jobs, "stop_requested", return_value=False)):
            p.start()
            self.addCleanup(p.stop)

    def _ko(self):
        return self.ch.with_name(self.ch.stem + "_ko.txt")

    def test_stuck_heading_then_keep_original_finishes_the_chapter(self):
        ok, msg = tr.translate_one_chapter(self.ch, "codex_cli:default")
        self.assertFalse(ok)
        self.assertIn("부분완료", msg)
        self.assertFalse(self._ko().exists())               # 예전엔 여기서 영영 멈췄다

        ev = helper.collect(self.ch)
        self.assertEqual([f["src"] for f in ev["failed"]], [HEADING])
        hint = next(h for h in helper.diagnose(ev) if h.get("action"))
        self.assertTrue(hint["bug"])
        self.assertEqual(helper.apply_action(self.ch, hint["action"]), 1)

        with mock.patch.object(tr.llm, "complete", side_effect=AssertionError("AI 를 다시 부르면 안 된다")):
            ok, _ = tr.translate_one_chapter(self.ch, "codex_cli:default")
        self.assertTrue(ok)
        text = self._ko().read_text(encoding="utf-8")
        self.assertIn(HEADING, text)
        self.assertIn("마야는", text)
        self.assertIn(TABLE, text)
        self.assertEqual(helper.failed_paragraphs(self.ch), [])

    def test_manual_translation_is_used_as_is(self):
        tr.translate_one_chapter(self.ch, "codex_cli:default")
        idx = helper.failed_paragraphs(self.ch)[0]["idx"]
        helper.apply_action(self.ch, {"type": "manual", "idx": idx, "text": "7.3.1 마야(Maya)."})
        ok, _ = tr.translate_one_chapter(self.ch, "codex_cli:default")
        self.assertTrue(ok)
        self.assertIn("7.3.1 마야(Maya).", self._ko().read_text(encoding="utf-8"))

    def test_actions_outside_the_failed_list_are_ignored(self):
        tr.translate_one_chapter(self.ch, "codex_cli:default")
        self.assertEqual(helper.apply_action(self.ch, {"type": "keep", "idx": [999]}), 0)
        self.assertEqual(helper.apply_action(self.ch, {"type": "delete_everything"}), 0)
        self.assertEqual(helper.apply_action(self.ch, {"type": "manual", "idx": 1, "text": "  "}), 0)

    def test_ai_proposals_are_filtered_to_failed_paragraphs(self):
        tr.translate_one_chapter(self.ch, "codex_cli:default")
        ev = helper.collect(self.ch)
        idx = ev["failed"][0]["idx"]
        answer = {"answer": "짧은 소제목이라 검사에 걸렸습니다.", "program_bug": True,
                  "bug_summary": "괄호 원어 때문에 유사도 검사 탈락",
                  "actions": [{"type": "keep", "idx": [idx, 42]},
                              {"type": "manual", "idx": 42, "text": "x"},
                              {"type": "run_shell", "cmd": "rm -rf ~"}]}
        with mock.patch.object(helper.llm, "task_provider_model", return_value=("codex_cli", "default")), \
             mock.patch.object(helper.llm, "complete_json", return_value=answer) as call:
            res = helper.ask(ev, [], "왜 실패하나요?")
        self.assertIn(HEADING, call.call_args.args[3])       # 실패 단락을 보여 주고 묻는다
        self.assertEqual(res["actions"], [{"type": "keep", "idx": [idx]}])
        self.assertTrue(res["program_bug"])


class ReportTest(unittest.TestCase):
    EV = {"book": "Some Paper", "chapter": "08_Appendix.txt", "state": "partial",
          "engine": "codex_cli:default", "total": 3, "translated": 1, "error": "",
          "blocked": False, "stopped": False, "target": "ko",
          "failed": [{"idx": 1, "kind": "heading", "src": HEADING}, {"idx": 5, "kind": "text", "src": BODY}],
          "log": [f"[2026-10-13] 경고: {Path.home()}/x 열기 실패 · 문의 someone@example.com 010-1234-5678"],
          "app_version": "v9.9.9", "os": "Darwin"}

    def test_book_text_is_left_out_by_default(self):
        body = helper.report(self.EV)
        self.assertNotIn("Maya", body)
        self.assertNotIn("Some Paper", body)
        self.assertIn("(본문 생략)", body)
        self.assertIn(HEADING, helper.report(self.EV, include_text=True))

    def test_personal_details_are_masked(self):
        body = helper.report(self.EV)
        self.assertNotIn(str(Path.home()), body)
        self.assertNotIn("someone@example.com", body)
        self.assertNotIn("010-1234-5678", body)

    def test_issue_url_stays_short_enough_to_open(self):
        url = helper.issue_url("제목", "가" * 20000)
        self.assertLessEqual(len(url), helper._ISSUE_URL_LIMIT)
        self.assertTrue(url.startswith(helper.REPO_URL + "/issues/new?"))
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["title"], ["제목"])

    def test_mail_link_goes_to_the_developer_and_stays_short(self):
        url = helper.mailto_url("제목", "가" * 5000)
        self.assertTrue(url.startswith("mailto:" + helper.FEEDBACK_EMAIL + "?"))
        self.assertLessEqual(len(url), helper._MAILTO_LIMIT)
        body = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["body"][0]
        self.assertIn("보고서 파일", body)
        self.assertNotIn("+", url)                       # 띄어쓰기가 +로 보이지 않게(%20)
        short = helper.mailto_url("제목 하나", "짧은 보고서")
        self.assertIn("%20", short)


if __name__ == "__main__":
    unittest.main()
