import tempfile
import unittest
from pathlib import Path

from firewall_patch import (
    ASSIGNMENT_ORIGINAL,
    ASSIGNMENT_PATCHED,
    EXT_MAGIC,
    EXT_MAGIC_OFFSET,
    FirewallPatchError,
    SECTOR_SIZE,
    SIGNATURE_ORIGINAL,
    apply_patch_to_image,
    build_sector_patch,
    inspect_firewall_image,
)


class FirewallPatchTests(unittest.TestCase):
    def _image(self, signatures, extra=b""):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "rootfs.img"
        data = bytearray(b"\0" * (32 * SECTOR_SIZE))
        data[EXT_MAGIC_OFFSET:EXT_MAGIC_OFFSET + len(EXT_MAGIC)] = EXT_MAGIC
        cursor = 4096
        for signature in signatures:
            data[cursor:cursor + len(signature)] = signature
            cursor += len(signature) + SECTOR_SIZE
        data[cursor:cursor + len(extra)] = extra
        path.write_bytes(data)
        return path

    def test_assignment_patch_preserves_length_and_newline(self):
        self.assertEqual(len(ASSIGNMENT_ORIGINAL), len(ASSIGNMENT_PATCHED))
        self.assertTrue(ASSIGNMENT_ORIGINAL.endswith(b"\n"))
        self.assertTrue(ASSIGNMENT_PATCHED.endswith(b"\n"))

    def test_inspection_ignores_assignment_without_firewall_context(self):
        path = self._image([SIGNATURE_ORIGINAL], extra=ASSIGNMENT_ORIGINAL)
        match = inspect_firewall_image(path)
        self.assertEqual(match.state, "original")

    def test_duplicate_contextual_signatures_fail_closed(self):
        path = self._image([SIGNATURE_ORIGINAL, SIGNATURE_ORIGINAL])
        with self.assertRaisesRegex(FirewallPatchError, "exactly one"):
            inspect_firewall_image(path)

    def test_missing_signature_fails_closed(self):
        path = self._image([], extra=ASSIGNMENT_ORIGINAL)
        with self.assertRaisesRegex(FirewallPatchError, "original=0, patched=0"):
            inspect_firewall_image(path)

    def test_patch_is_sector_aligned_and_changes_only_assignment(self):
        path = self._image([SIGNATURE_ORIGINAL])
        match = inspect_firewall_image(path)
        patch = build_sector_patch(match)
        self.assertEqual(len(patch.before) % SECTOR_SIZE, 0)
        self.assertEqual(len(patch.before), len(patch.after))
        changed = [index for index, pair in enumerate(zip(patch.before, patch.after)) if pair[0] != pair[1]]
        self.assertTrue(changed)
        self.assertLessEqual(len(changed), len(ASSIGNMENT_ORIGINAL))

    def test_patch_and_restore_are_idempotent(self):
        path = self._image([SIGNATURE_ORIGINAL])
        original_size = path.stat().st_size
        patched = apply_patch_to_image(path)
        self.assertEqual(patched.state, "patched")
        self.assertEqual(path.stat().st_size, original_size)
        self.assertEqual(apply_patch_to_image(path).state, "patched")
        restored = apply_patch_to_image(path, restore=True)
        self.assertEqual(restored.state, "original")
        self.assertEqual(path.stat().st_size, original_size)


if __name__ == "__main__":
    unittest.main()
