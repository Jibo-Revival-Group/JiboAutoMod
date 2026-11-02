import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import recovery_evidence as R


class RecoveryFiles(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        # macOS's default /var temp prefix is itself a symlink. Test real paths
        # so ordinary artifact checks do not implicitly traverse that alias.
        self.root = Path(self.directory.name).resolve()
        self.audit = dict(schema='openjibo.conversion-inventory.v1', deviceFingerprintSha256='a'*64,
                          releaseFamily='v2', observedAtUtc='2026-11-02T00:00:00Z', auditEvidenceSha256='b'*64, backups=[])
        self.files = dict(schema='openjibo.recovery-files.v1', files=[])
        for index, kind in enumerate(('calibration', 'affected-storage')):
            data = bytes([index+1]) * (1048576+19)
            (self.root/kind).write_bytes(data)
            self.audit['backups'].append(dict(kind=kind, sha256=hashlib.sha256(data).hexdigest(), sizeBytes=len(data)))
            self.files['files'].append(dict(kind=kind, path=kind))

    def run_check(self):
        return R.check(self.audit, self.files, self.root, datetime(2026, 11, 2, tzinfo=timezone.utc))

    def test_actual_bytes_are_hashed_with_bounded_streaming_and_no_write(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        result = self.run_check()
        self.assertEqual(result, self.run_check())
        self.assertTrue(result['fileBytesMatchedSuppliedInventory'])
        self.assertEqual(sorted(self.audit['backups'], key=lambda b: b['kind']), result['files'])
        self.assertEqual(R.preparation.digest(self.audit), result['inventorySha256'])
        for field in ('robotAssociationVerified', 'restoreTested', 'readyForApply', 'deviceWritesPerformed', 'directNetworkRequestsPerformed'):
            self.assertIs(False, result[field])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        self.assertNotIn(self.directory.name, json.dumps(result)); self.assertNotIn('path', result['files'][0])

    def test_same_size_tampering_or_wrong_size_refuses(self):
        path = self.root/'calibration'; original = path.read_bytes()
        for data in (b'x'*len(original), original[:-1], original+b'x'):
            path.write_bytes(data)
            with self.assertRaises(ValueError): self.run_check()

    def test_missing_file_or_directory_refuses(self):
        path = self.root/'calibration'; path.unlink()
        with self.assertRaises(OSError): self.run_check()
        path.mkdir()
        with self.assertRaises(ValueError): self.run_check()

    def test_full_storage_is_accepted_as_alternative(self):
        self.audit['backups'][1]['kind'] = 'full-storage'
        self.files['files'][1]['kind'] = 'full-storage'
        self.assertTrue(self.run_check()['fileBytesMatchedSuppliedInventory'])

    def test_incomplete_duplicate_extra_or_unknown_map_refuses(self):
        cases = [[], self.files['files'][:1], self.files['files']*2,
                 [{**self.files['files'][0], 'token': 'secret'}, self.files['files'][1]],
                 [self.files['files'][0], dict(kind='unknown', path='affected-storage')]]
        original = copy.deepcopy(self.files)
        for items in cases:
            self.files = {**original, 'files': items}
            with self.subTest(items=items), self.assertRaises(ValueError): self.run_check()

    def test_mutation_during_read_refuses(self):
        # Simulate a filesystem metadata change observed after hashing, without a timing race.
        original = os.fstat; calls = 0
        def changed(descriptor):
            nonlocal calls
            info = original(descriptor); calls += 1
            if calls == 2:
                from types import SimpleNamespace
                return SimpleNamespace(st_dev=info.st_dev, st_ino=info.st_ino, st_size=info.st_size,
                                       st_mtime_ns=info.st_mtime_ns+1, st_ctime_ns=info.st_ctime_ns)
            return info
        with patch.object(R.os, 'fstat', side_effect=changed), self.assertRaises(ValueError): self.run_check()

    def test_same_hard_link_cannot_fill_two_backup_kinds(self):
        other = self.root/'affected-storage'; other.unlink()
        try: os.link(self.root/'calibration', other)
        except OSError: self.skipTest('Hard links unavailable for this filesystem')
        self.audit['backups'][1].update(sha256=self.audit['backups'][0]['sha256'], sizeBytes=self.audit['backups'][0]['sizeBytes'])
        with self.assertRaises(ValueError): self.run_check()

    def test_symbolic_links_are_refused_when_host_supports_creation(self):
        link = self.root/'link'
        try: link.symlink_to(self.root/'calibration')
        except OSError: self.skipTest('Host does not permit symlink creation')
        self.files['files'][0]['path'] = str(link)
        with self.assertRaises(ValueError): self.run_check()

    def test_remote_device_paths_are_refused_before_open(self):
        for value in ('//server/share/backup', '\\\\server\\share\\backup', '\\\\.\\PhysicalDrive0'):
            self.files['files'][0]['path'] = value
            with self.subTest(value=value), self.assertRaises(ValueError): self.run_check()

    def test_windows_reparse_attributes_are_refused(self):
        from types import SimpleNamespace
        with patch.object(Path, 'lstat', return_value=SimpleNamespace(st_mode=stat_mode(), st_file_attributes=1024)):
            with self.assertRaises(ValueError): R.ordinary_path(self.root/'calibration')

    def test_cli_new_output_only_sanitized_failure_and_no_partial_receipt(self):
        inventory, files, output = [self.root/name for name in ('inventory.json', 'files.json', 'receipt.json')]
        inventory.write_text(json.dumps(self.audit)); files.write_text(json.dumps(self.files))
        command = [sys.executable, '-B', str(Path(R.__file__)), '--inventory', str(inventory), '--files', str(files), '--output', str(output)]
        first = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(0, first.returncode, first.stderr); before = output.read_bytes()
        self.assertNotIn(self.directory.name, first.stdout)
        again = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(2, again.returncode); self.assertEqual(before, output.read_bytes())
        output.unlink(); (self.root/'calibration').write_bytes(b'tampered')
        bad = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(2, bad.returncode); self.assertFalse(output.exists())
        self.assertNotIn(self.directory.name, bad.stderr); self.assertNotIn('Traceback', bad.stderr)


def stat_mode():
    import stat
    return stat.S_IFREG | 0o600


if __name__ == '__main__': unittest.main()
