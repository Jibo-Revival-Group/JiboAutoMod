import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import stat
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
import storage_capacity as C


def fixture(sectors):
    raw = bytearray((i * 29 + 7) & 0xff for i in range(C.EXT_CSD_BYTES))
    raw[C.SEC_COUNT_OFFSET:C.SEC_COUNT_OFFSET + C.SEC_COUNT_BYTES] = struct.pack('<I', sectors)
    return bytes(raw)


class StorageCapacityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.path = self.root / 'ext-csd.bin'

    def save(self, raw):
        self.path.write_bytes(raw)
        return self.path

    def test_decodes_sector_count_and_hashes_source_without_exporting_bytes(self):
        raw = bytearray(fixture(0x00123456))
        marker = b'CAPACITY_PRIVATE_MARKER'
        raw[40:40 + len(marker)] = marker
        raw = bytes(raw)
        self.save(raw)
        evidence = C.inspect_ext_csd(self.path)
        self.assertEqual(evidence, {
            'schema': 'openjibo.storage-capacity.v1',
            'sectorSizeBytes': 512,
            'storageSectorCount': 0x00123456,
            'sizeBytes': 0x00123456 * 512,
            'sourceHash': hashlib.sha256(raw).hexdigest(),
            'sourceBytes': 512,
            'physicalIdentityVerified': False,
            'captureAuthenticityVerified': False,
        })
        self.assertNotIn(marker.decode(), repr(evidence))
        self.assertIs(C.validate_evidence(evidence), evidence)

    def test_inclusive_sector_capacity_limits(self):
        for sectors in (1, C.MAX_USER_AREA_SECTORS):
            with self.subTest(sectors=sectors):
                self.save(fixture(sectors))
                evidence = C.inspect_ext_csd(self.path)
                self.assertEqual(evidence['storageSectorCount'], sectors)
                self.assertEqual(evidence['sizeBytes'], sectors * 512)

    def test_zero_or_over_upper_capacity_refused_without_default(self):
        for sectors in (0, C.MAX_USER_AREA_SECTORS + 1, 0xffffffff):
            with self.subTest(sectors=sectors):
                self.save(fixture(sectors))
                with self.assertRaises(ValueError):
                    C.inspect_ext_csd(self.path)

    def test_exact_512_byte_source_size_required(self):
        for raw in (b'', b'x' * 511, b'x' * 513):
            with self.subTest(length=len(raw)):
                self.save(raw)
                with self.assertRaises(ValueError):
                    C.inspect_ext_csd(self.path)

    def test_ctime_exception_is_windows_only(self):
        fields = dict(st_dev=1, st_ino=2, st_mode=stat.S_IFREG, st_size=512,
                      st_mtime_ns=3, st_ctime_ns=4, st_nlink=1,
                      st_file_attributes=0)
        before = SimpleNamespace(**fields)
        changed_ctime = dict(fields, st_ctime_ns=5)
        after = SimpleNamespace(**changed_ctime)
        self.assertEqual(C._identity(before, windows=True), C._identity(after, windows=True))
        self.assertNotEqual(C._identity(before, windows=False), C._identity(after, windows=False))

    def test_directory_and_hardlink_aliases_refused(self):
        self.save(fixture(1))
        directory = self.root / 'directory'
        directory.mkdir()
        with self.assertRaises(ValueError):
            C.inspect_ext_csd(directory)

        alias = self.root / 'hardlink.bin'
        os.link(self.path, alias)
        with self.assertRaises(ValueError):
            C.inspect_ext_csd(alias)
        with self.assertRaises(ValueError):
            C.inspect_ext_csd(self.path)

    def test_symlink_alias_refused_when_creation_is_available(self):
        self.save(fixture(1))
        symlink = self.root / 'symlink.bin'
        try:
            os.symlink(self.path, symlink)
        except (OSError, NotImplementedError):
            self.skipTest('Symlink creation unavailable on this host')
        with self.assertRaises(ValueError):
            C.inspect_ext_csd(symlink)

    def test_evidence_schema_ranges_and_bool_integer_rejection(self):
        self.save(fixture(20))
        original = C.inspect_ext_csd(self.path)
        mutations = []
        for field in ('sectorSizeBytes', 'storageSectorCount', 'sizeBytes', 'sourceBytes'):
            value = copy.deepcopy(original)
            value[field] = True
            mutations.append(value)
        value = copy.deepcopy(original); value['storageSectorCount'] = 0; mutations.append(value)
        value = copy.deepcopy(original); value['storageSectorCount'] = C.MAX_USER_AREA_SECTORS + 1; mutations.append(value)
        value = copy.deepcopy(original); value['sizeBytes'] += 512; mutations.append(value)
        value = copy.deepcopy(original); value['sourceHash'] = 'A' * 64; mutations.append(value)
        value = copy.deepcopy(original); value['physicalIdentityVerified'] = True; mutations.append(value)
        value = copy.deepcopy(original); value['captureAuthenticityVerified'] = True; mutations.append(value)
        value = copy.deepcopy(original); value['unexpected'] = 0; mutations.append(value)
        value = copy.deepcopy(original); del value['sourceBytes']; mutations.append(value)
        for bad in mutations:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    C.validate_evidence(bad)

    def test_bool_and_non_path_sources_are_refused(self):
        for bad in (True, False, b'not-a-path', None):
            with self.subTest(bad=type(bad).__name__):
                with self.assertRaises(ValueError):
                    C.inspect_ext_csd(bad)

    def _cli(self, *args):
        return subprocess.run(
            [sys.executable, str(Path(C.__file__).resolve()), *map(str, args)],
            text=True, capture_output=True, check=False)

    def test_cli_requires_expected_hash_and_writes_new_metadata_only(self):
        raw = fixture(1234)
        self.save(raw)
        output = self.root / 'capacity.json'
        result = self._cli('--input', self.path, '--expected-sha256', hashlib.sha256(raw).hexdigest(),
                           '--output', output)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(C.validate_evidence(json.loads(output.read_text('ascii'))),
                         C.inspect_ext_csd(self.path))
        self.assertEqual(set(json.loads(result.stdout)), {'outputHash', 'schema', 'sourceHash'})
        self.assertNotIn(raw.hex(), result.stdout)

    def test_cli_wrong_hash_refuses_without_output(self):
        self.save(fixture(1234))
        output = self.root / 'wrong-hash.json'
        result = self._cli('--input', self.path, '--expected-sha256', '0' * 64, '--output', output)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(output.exists())

    def test_cli_existing_output_is_never_overwritten(self):
        self.save(fixture(1234))
        output = self.root / 'already-there.json'
        output.write_text('keep-me', encoding='ascii')
        result = self._cli('--input', self.path, '--expected-sha256', hashlib.sha256(self.path.read_bytes()).hexdigest(),
                           '--output', output)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(output.read_text('ascii'), 'keep-me')

    def test_cli_help_does_not_need_input_or_create_files(self):
        result = subprocess.run([sys.executable, str(Path(C.__file__).resolve()), '--help'],
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--expected-sha256', result.stdout)
        self.assertIn('No device access is', ' '.join(result.stdout.split()))


if __name__ == '__main__':
    unittest.main()
