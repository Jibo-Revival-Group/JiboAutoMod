import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import owner_preview as preview


class PreviewControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name).resolve()
        self.output = self.parent / "demo-001"
        self.output.mkdir()
        self.report = self.output / "review.html"
        self.report.write_text("Synthetic demo", encoding="utf-8")
        self.good = {"reviewFile": str(self.report), "outputDir": str(self.output),
                     "summary": "Sample report", "syntheticDemo": True,
                     "readyForApply": False}

    def test_five_steps_are_clear_and_bounded(self):
        self.assertEqual([x[0] for x in preview.STEPS], ["Check setup", "Connect Jibo", "Recovery copy", "Join service", "Verify"])
        controller = preview.PreviewController()
        controller.back()
        self.assertEqual(controller.step, 0)
        for _ in range(7):
            controller.next()
        self.assertEqual(controller.step, 4)
        controller.back()
        self.assertEqual(controller.step, 3)
        self.assertIn("does not make or check a backup", preview.STEPS[2][2])
        self.assertIn("nothing is connected", preview.STEPS[1][2])
        self.assertIn("Real conversion is not available", preview.STEPS[0][2])

    def test_backend_only_receives_requested_parent_and_reports_are_private_samples(self):
        calls = []
        def backend(output_parent=None):
            calls.append(output_parent)
            return self.good
        result = preview.prepare_preview(output_parent=self.parent, backend=backend)
        self.assertEqual(calls, [self.parent])
        self.assertEqual(result["reviewFile"], str(self.report.resolve()))
        self.assertTrue(result["syntheticDemo"])
        self.assertFalse(result["readyForApply"])

    def test_rejects_missing_or_unsafe_flags(self):
        for patch in ({"syntheticDemo": False}, {"syntheticDemo": 1},
                      {"readyForApply": True}, {"readyForApply": None},
                      {"summary": {}}, {"outputDir": None}):
            with self.subTest(patch=patch), self.assertRaises(preview.PreviewError):
                preview.validate_result({**self.good, **patch}, self.parent)

    def test_rejects_unexpected_or_nonexistent_report_paths(self):
        with tempfile.TemporaryDirectory() as other:
            outside = Path(other) / "review.html"
            outside.write_text("demo", encoding="utf-8")
            bad = {**self.good, "reviewFile": str(outside), "outputDir": other}
            with self.assertRaises(preview.PreviewError):
                preview.validate_result(bad, self.parent)
        for patch in ({"reviewFile": "review.html"}, {"reviewFile": str(self.output / "missing.html")},
                      {"outputDir": str(self.parent)}):
            with self.subTest(patch=patch), self.assertRaises(preview.PreviewError):
                preview.validate_result({**self.good, **patch}, self.parent)

    def test_busy_state_and_invalid_result_never_complete(self):
        state = preview.PreviewController()
        with self.assertRaises(preview.PreviewError):
            state.begin()
        for _ in range(4):
            state.next()
        state.begin()
        state.back()
        self.assertEqual(state.step, 4)
        state.complete({**self.good, "readyForApply": True}, self.parent)
        self.assertTrue(state.failed)
        self.assertIsNone(state.result)
        state.begin()
        state.complete(self.good, self.parent)
        self.assertFalse(state.busy)
        self.assertFalse(state.failed)
        self.assertFalse(state.result["readyForApply"])

    def test_smoke_mode_is_headless_and_reports_synthetic_status(self):
        out = io.StringIO()
        with mock.patch.object(preview, "prepare_preview", return_value=self.good) as backend, contextlib.redirect_stdout(out):
            self.assertEqual(preview.main(["--smoke", "--output-parent", str(self.parent)]), 0)
        backend.assert_called_once_with(output_parent=str(self.parent))
        self.assertEqual(json.loads(out.getvalue())["syntheticDemo"], True)
        self.assertEqual(json.loads(out.getvalue())["readyForApply"], False)

    def test_smoke_receipt_supports_windowed_no_stdout(self):
        receipt = self.parent / "smoke-receipt.json"
        with mock.patch.object(preview, "prepare_preview", return_value=self.good), mock.patch.object(preview.sys, "stdout", None):
            self.assertEqual(preview.main(["--smoke", "--output-parent", str(self.parent), "--receipt", str(receipt)]), 0)
        saved = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertIs(saved["syntheticDemo"], True)
        self.assertIs(saved["readyForApply"], False)
        self.assertEqual(saved["reviewFile"], str(self.report))

    def test_existing_receipt_is_preserved_and_reports_failure(self):
        receipt = self.parent / "existing.json"
        receipt.write_text("keep this", encoding="utf-8")
        with mock.patch.object(preview, "prepare_preview", return_value=self.good), mock.patch.object(preview.sys, "stderr", None):
            self.assertEqual(preview.main(["--smoke", "--receipt", str(receipt)]), 1)
        self.assertEqual(receipt.read_text(encoding="utf-8"), "keep this")

    def test_failed_or_unverified_backend_writes_no_receipt(self):
        receipt = self.parent / "result.json"
        def unsafe_backend(output_parent=None):
            return {**self.good, "readyForApply": True}
        real_prepare = preview.prepare_preview
        with mock.patch.object(preview, "prepare_preview", side_effect=lambda **kwargs: real_prepare(backend=unsafe_backend, **kwargs)), contextlib.redirect_stderr(io.StringIO()):
            # A real backend error must not be transformed into a success receipt.
            self.assertEqual(preview.main(["--smoke", "--receipt", str(receipt)]), 1)
        self.assertFalse(receipt.exists())

    def test_failures_do_not_print_exception_details(self):
        err = io.StringIO()
        with mock.patch.object(preview, "prepare_preview", side_effect=ValueError("sensitive test details")), contextlib.redirect_stderr(err):
            self.assertEqual(preview.main(["--smoke"]), 1)
        self.assertNotIn("sensitive test details", err.getvalue())


if __name__ == "__main__":
    unittest.main()
