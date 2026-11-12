"""Synthetic-only integrity and result-preservation tests for the owner preview."""
import hashlib
import importlib.util
import json
import os
import py_compile
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import owner_preview as preview
import owner_preview_support as support

ROOT = Path(__file__).resolve().parents[1]


class OwnerPreviewSupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stage_temp = tempfile.TemporaryDirectory(prefix="owner-preview-fixture-")
        root = Path(cls.stage_temp.name)
        spec = importlib.util.spec_from_file_location("_owner_fixture_builder", ROOT / "tools" / "build_owner_preview.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        cls.stage = builder.stage(ROOT, root / "built", "0" * 40)
        cls.payload = cls.stage / "offline_payload"

    @classmethod
    def tearDownClass(cls):
        cls.stage_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="owner-preview-case-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload_copy = self.root / "payload"
        shutil.copytree(self.payload, self.payload_copy)
        self.pin = hashlib.sha256((self.payload_copy / "release-manifest.json").read_bytes()).hexdigest()
        self.patch_root = mock.patch.object(support, "resource_root", return_value=self.payload_copy)
        self.patch_pin = mock.patch.object(support, "PAYLOAD_MANIFEST_SHA256", self.pin)
        self.patch_root.start()
        self.patch_pin.start()
        self.addCleanup(self.patch_root.stop)
        self.addCleanup(self.patch_pin.stop)

    def test_code_tamper_is_refused_before_loading_code(self):
        code = self.payload_copy / "review_request.py"
        code.write_text("raise RuntimeError('must not execute')\n", encoding="utf-8")
        with mock.patch.object(support.importlib.util, "spec_from_file_location") as loader:
            with self.assertRaises(ValueError):
                support.prepare_demo(output_parent=self.root)
        loader.assert_not_called()

    def test_unindexed_poisoned_bytecode_is_refused_before_loading(self):
        code = self.payload_copy / "review_request.py"
        original = code.read_bytes()
        marker = self.root / "must-not-execute"
        attack = ("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n").encode("utf-8")
        self.assertLess(len(attack), len(original))
        # Make an otherwise valid timestamp/size cache for the original source.
        code.write_bytes(attack + b"#" * (len(original) - len(attack)))
        timestamp = code.stat()
        py_compile.compile(str(code), doraise=True)
        code.write_bytes(original)
        os.utime(code, ns=(timestamp.st_atime_ns, timestamp.st_mtime_ns))
        self.assertEqual(hashlib.sha256(code.read_bytes()).hexdigest(),
                         next(x["sha256"] for x in json.loads(
                             (self.payload_copy / "release-manifest.json").read_text(encoding="utf-8"))["files"]
                              if x["file"] == "review_request.py"))
        with mock.patch.object(support.importlib.util, "spec_from_file_location") as loader:
            with self.assertRaises(ValueError):
                support.prepare_demo(output_parent=self.root)
        loader.assert_not_called()
        self.assertFalse(marker.exists())

    def test_manifest_tamper_is_refused_even_if_inner_hash_is_fixed(self):
        code = self.payload_copy / "review_request.py"
        code.write_text("raise RuntimeError('must not execute')\n", encoding="utf-8")
        path = self.payload_copy / "release-manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        record = next(item for item in manifest["files"] if item["file"] == "review_request.py")
        record["sha256"] = hashlib.sha256(code.read_bytes()).hexdigest()
        record["sizeBytes"] = code.stat().st_size
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with mock.patch.object(support.importlib.util, "spec_from_file_location") as loader:
            with self.assertRaises(ValueError):
                support.prepare_demo(output_parent=self.root)
        loader.assert_not_called()

    def test_missing_payload_refuses_before_loading_code(self):
        shutil.rmtree(self.payload_copy)
        with mock.patch.object(support.importlib.util, "spec_from_file_location") as loader:
            with self.assertRaises((FileNotFoundError, ValueError)):
                support.prepare_demo(output_parent=self.root)
        loader.assert_not_called()

    def test_bytecode_setting_is_restored_when_builder_fails(self):
        def load(_module):
            self.assertIs(sys.dont_write_bytecode, True)
        def fail(*_args):
            self.assertIs(sys.dont_write_bytecode, True)
            raise ValueError("synthetic build failure")
        fake_spec = types.SimpleNamespace(loader=types.SimpleNamespace(exec_module=load))
        fake_module = types.SimpleNamespace(build=fail)
        with mock.patch.object(sys, "dont_write_bytecode", False), \
             mock.patch.object(support.importlib.util, "spec_from_file_location", return_value=fake_spec), \
             mock.patch.object(support.importlib.util, "module_from_spec", return_value=fake_module):
            with self.assertRaises(ValueError):
                support.prepare_demo(output_parent=self.root)
            self.assertIs(sys.dont_write_bytecode, False)

    def test_first_use_creates_default_folder_with_real_synthetic_backend(self):
        default = self.root / "new-user-state" / "JiboRevival" / "ConversionPreview"
        self.assertFalse(default.exists())
        with mock.patch.object(support, "default_output_parent", return_value=default):
            result = preview.prepare_preview()
        self.assertTrue(default.is_dir())
        self.assertTrue(Path(result["reviewFile"]).is_file())
        self.assertTrue(Path(result["reviewFile"]).is_relative_to(default))
        self.assertIs(result["syntheticDemo"], True)
        self.assertIs(result["readyForApply"], False)

    def test_default_result_folder_rejects_symlink_ancestor(self):
        target = self.root / "target"
        target.mkdir()
        link = self.root / "linked"
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("creating a directory symlink is unavailable")
        with mock.patch.object(support, "default_output_parent", return_value=link / "results"):
            with self.assertRaises(ValueError):
                support.prepare_demo()
        self.assertFalse((target / "results").exists())

    def test_distinct_result_folders_preserve_existing_and_inputs(self):
        manifest = json.loads((self.payload_copy / "release-manifest.json").read_text(encoding="utf-8"))
        tracked = [self.payload_copy / item["file"] for item in manifest["files"]]
        tracked.append(self.payload_copy / "release-manifest.json")
        before = {p.relative_to(self.payload_copy): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
        names_before = {p.relative_to(self.payload_copy) for p in self.payload_copy.rglob("*")}
        existing = self.root / "sample-existing"
        existing.mkdir()
        marker = existing / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        with mock.patch.object(sys, "dont_write_bytecode", False):
            first = support.prepare_demo(output_parent=self.root)
            second = support.prepare_demo(output_parent=self.root)
        self.assertNotEqual(first["outputDir"], second["outputDir"])
        for result in (first, second):
            self.assertTrue(Path(result["reviewFile"]).is_file())
            self.assertTrue(Path(result["reviewFile"]).is_relative_to(self.root))
            self.assertIs(result["syntheticDemo"], True)
            self.assertIs(result["readyForApply"], False)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
        after = {p.relative_to(self.payload_copy): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
        self.assertEqual(before, after)
        names_after = {p.relative_to(self.payload_copy) for p in self.payload_copy.rglob("*")}
        self.assertEqual(names_before, names_after, "preview should not add files to its bundled inputs")


if __name__ == "__main__":
    unittest.main()
