# -*- coding: utf-8 -*-
"""PDF 뷰어 고정 회귀 테스트 — services/common.open_pdf_view.

이 장치의 존재 이유: `open_path`는 LaunchServices의 **기본 앱**을 쓴다. 그래서 기기마다
다른 PDF 앱이 뜬다 — 실제로 연구자 기기에서는 PDF Expert가 열렸다. 차례를 견주는 창은
어느 맥에서나 같아야 한다.

★경로가 아니라 **번들 ID**로 지정한다. `/System/Applications/Preview.app`은 macOS 판이
바뀌면 옮겨 다니지만 `com.apple.Preview`는 그대로다.
★미리보기가 안 되면 **조용히 기본 앱으로 내려간다** — 창이 안 뜨는 것보다 낫다.
"""
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from services import common


class OpenPdfViewTest(unittest.TestCase):
    def test_맥에서는_미리보기를_번들ID로_부른다(self):
        with mock.patch.object(common.sys, "platform", "darwin"), \
             mock.patch.object(common.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
            self.assertEqual(common.open_pdf_view(Path("/tmp/a.pdf")), "미리보기")
        args = run.call_args[0][0]
        self.assertEqual(args[:3], ["open", "-b", "com.apple.Preview"])

    def test_미리보기가_실패하면_기본앱으로_내려간다(self):
        with mock.patch.object(common.sys, "platform", "darwin"), \
             mock.patch.object(common.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 1, "", "no app")), \
             mock.patch.object(common, "open_path") as op:
            self.assertEqual(common.open_pdf_view(Path("/tmp/a.pdf")), "기본 앱")
        op.assert_called_once()

    def test_예외가_나도_던지지_않는다(self):
        with mock.patch.object(common.sys, "platform", "darwin"), \
             mock.patch.object(common.subprocess, "run", side_effect=OSError("boom")), \
             mock.patch.object(common, "open_path") as op:
            self.assertEqual(common.open_pdf_view(Path("/tmp/a.pdf")), "기본 앱")
        op.assert_called_once()

    def test_윈도우에서는_기본앱에_맡긴다(self):
        """반드시 있는 뷰어가 없으므로 강제할 대상이 없다."""
        with mock.patch.object(common.sys, "platform", "win32"), \
             mock.patch.object(common, "open_path") as op:
            self.assertEqual(common.open_pdf_view(Path("C:/a.pdf")), "기본 앱")
        op.assert_called_once()


if __name__ == "__main__":
    unittest.main()
