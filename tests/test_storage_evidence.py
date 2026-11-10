import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import storage_evidence as S
import test_ext4_path as ext4_fixture
from test_firewall_preview import image
from test_gpt_audit import fixture, recalculate


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def filesystem(role, raw):
    builder = ext4_fixture.Ext4PathReaderTests()
    data = bytearray(image())
    parent, filename = S.PATHS[role].strip('/').split('/')
    builder._inode(data, 2, 0x41ed, 1024, 10)
    builder._inode(data, 3, 0x41ed, 1024, 11)
    builder._inode(data, 4, 0x81a4, len(raw), 13, (len(raw) + 1023) // 1024)
    data[10*1024:11*1024] = builder._directory((3, parent, 2))
    data[11*1024:12*1024] = builder._directory((4, filename, 1))
    data[13*1024:17*1024] = b'\0' * 4096
    data[13*1024:13*1024+len(raw)] = raw
    return bytes(data)


class StorageEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.inputs = self.root / 'inputs'
        self.inputs.mkdir()
        self.output = self.root / 'evidence'
        self.path = self.root / 'manifest.json'
        self.config = json.dumps({'HubClient': {'region-settings': {'us': {'hub_port': 443}}}, 'secret': 'CONFIG_PRIVATE_MARKER'}).encode()
        self.credentials = json.dumps({'region': 'us', 'certificate': 'CREDENTIAL_PRIVATE_MARKER', 'privateKey': 'KEY_PRIVATE_MARKER'}).encode()
        self.prefix = bytearray(fixture())
        for i, name in enumerate(('services-test', 'var-test')):
            struct.pack_into('<QQ', self.prefix, 1024+i*128+32, 64+i*128, 191+i*128)
            self.prefix[1024+i*128+56:1024+(i+1)*128] = name.encode('utf-16le').ljust(72, b'\0')
        self.prefix = recalculate(self.prefix)
        self.images = {'jetstream': filesystem('jetstream', self.config), 'credentials': filesystem('credentials', self.credentials)}
        self.manifest = dict(schema='openjibo.storage-file-input.v1', diskSectors=4096,
                             fullStorage={}, gptPrefix={}, jetstream={}, credentialsRegion='us',
                             partitions={'jetstream': 'services-test', 'credentials': 'var-test'})
        self.save()

    def save(self):
        disk = bytearray(4096*512)
        disk[:len(self.prefix)] = self.prefix
        for i, role in enumerate(S.PATHS):
            start = (64+i*128)*512
            disk[start:start+len(self.images[role])] = self.images[role]
        for name, raw, key in [('full-storage.bin', bytes(disk), 'fullStorage'), ('jetstream.json', self.config, 'jetstream')]:
            (self.inputs / name).write_bytes(raw)
            self.manifest[key] = dict(sha256=sha(raw), sizeBytes=len(raw))
        self.manifest['gptPrefix'] = dict(sha256=sha(self.prefix), sizeBytes=len(self.prefix))

    def run_evidence(self):
        raw = json.dumps(self.manifest).encode()
        self.path.write_bytes(raw)
        return S.inspect(self.path, sha(raw), self.inputs, self.output)

    def test_pinned_storage_matches_files_region_and_exact_gpt_offsets_without_exporting_secrets(self):
        before = {p.name: sha(p.read_bytes()) for p in self.inputs.iterdir()}
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('no process')):
            value = self.run_evidence()
        self.assertTrue(value['retainedJetstreamBytesMatched'])
        self.assertTrue(value['credentialRegionMatched'])
        self.assertEqual(value['credentialsRegion'], 'us')
        self.assertEqual(before, {p.name: sha(p.read_bytes()) for p in self.inputs.iterdir()})
        self.assertEqual([p.name for p in self.output.iterdir()], ['evidence.json'])
        serialized = (self.output / 'evidence.json').read_bytes()
        for secret in (b'CONFIG_PRIVATE_MARKER', b'CREDENTIAL_PRIVATE_MARKER', b'KEY_PRIVATE_MARKER'):
            self.assertNotIn(secret, serialized)
        for i, role in enumerate(S.PATHS):
            record = value['files'][role]
            self.assertEqual(record['fileSha256'], sha(self.config if role == 'jetstream' else self.credentials))
            self.assertEqual(record['extents'][0]['fullStorageByteOffset'], (64+i*128)*512+13*1024)
        for flag in ('mountMappingVerified', 'installedReleaseVerified', 'deviceIdentityVerified', 'filesystemIntegrityVerified',
                     'blockAllocationOwnershipVerified', 'readyForApply', 'executionSupported', 'credentialsContentsExported',
                     'deviceWritesPerformed', 'networkRequestsPerformed'):
            self.assertFalse(value[flag])

    def test_legacy_reader_support_does_not_broaden_flat_extent_admission(self):
        data = bytearray(self.images['credentials'])
        ext4_fixture.Ext4PathReaderTests()._legacy_inode(data, 2, 0x41ed, 1024, [10])
        self.images['credentials'] = bytes(data)
        self.save()
        with self.assertRaises(ValueError):
            self.run_evidence()
        self.assertFalse(self.output.exists())

    def test_exact_jetstream_bytes_required_even_if_same_json_semantics(self):
        self.config += b'\n'
        self.save()
        with self.assertRaises(ValueError): self.run_evidence()
        self.assertFalse(self.output.exists())

    def test_region_missing_wrong_type_or_mismatched_is_refused(self):
        for credentials in ({}, {'region': True}, {'region': 'eu'}):
            with self.subTest(credentials=credentials):
                self.images['credentials'] = filesystem('credentials', json.dumps(credentials).encode())
                self.save()
                with self.assertRaises(ValueError): self.run_evidence()
                self.assertFalse(self.output.exists())

    def test_json_duplicates_nonfinite_complexity_and_wrong_root_refused(self):
        for raw in (b'{"region":"us","region":"us"}', b'{"region":"us","x":NaN}', b'[]',
                    b'{"region":"us","x":' + b'['*20 + b'0' + b']'*20 + b'}',
                    b'{"region":"us","x":"' + b'x'*4097 + b'"}', b'not-json'):
            self.images['credentials'] = filesystem('credentials', raw)
            self.save()
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError): self.run_evidence()
            self.assertFalse(self.output.exists())

    def test_unknown_role_alias_partition_and_region_are_not_guessed(self):
        original = copy.deepcopy(self.manifest)
        for case in ('missing', 'unknown', 'same', 'path', 'case', 'region', 'bool'):
            self.manifest = copy.deepcopy(original)
            if case == 'missing': del self.manifest['partitions']['credentials']
            elif case == 'unknown': self.manifest['partitions']['jetstream'] = '3.services'
            elif case == 'same': self.manifest['partitions']['credentials'] = 'services-test'
            elif case == 'path': self.manifest['partitions']['jetstream'] = '../services-test'
            elif case == 'case': self.manifest['partitions']['jetstream'] = 'SERVICES-TEST'
            elif case == 'region': self.manifest['credentialsRegion'] = '../us'
            else: self.manifest['diskSectors'] = True
            with self.subTest(case=case), self.assertRaises(ValueError): self.run_evidence()
            self.assertFalse(self.output.exists())

    def test_missing_config_region_or_invalid_route_refused(self):
        for config in ({}, {'HubClient': {'region-settings': {}}}, {'HubClient': {'region-settings': {'us': {'hub_port': True}}}}):
            self.config = json.dumps(config).encode()
            self.images['jetstream'] = filesystem('jetstream', self.config)
            self.save()
            with self.subTest(config=config), self.assertRaises(ValueError): self.run_evidence()

    def test_bad_prefix_crc_wrong_capacity_and_hash_substitution_refused(self):
        original = copy.deepcopy(self.manifest)
        for case in ('storage-hash', 'prefix-hash', 'size', 'crc'):
            self.manifest = copy.deepcopy(original)
            if case == 'storage-hash': self.manifest['fullStorage']['sha256'] = '0'*64
            elif case == 'prefix-hash': self.manifest['gptPrefix']['sha256'] = '0'*64
            elif case == 'size': self.manifest['fullStorage']['sizeBytes'] -= 512
            else:
                raw = bytearray(self.prefix); raw[1024] ^= 1
                self.prefix = bytes(raw); self.save()
            with self.subTest(case=case), self.assertRaises(ValueError): self.run_evidence()
            self.assertFalse(self.output.exists())

    def test_unsupported_ext_features_and_dirty_filesystem_refused(self):
        baseline = self.images['credentials']
        for offset, fmt, value in ((58, '<H', 0), (96, '<I', 0xc0), (100, '<I', 0x400), (32, '<I', 0), (24, '<I', 0xffffffff)):
            raw = bytearray(baseline)
            struct.pack_into(fmt, raw, 1024+offset, value)
            self.images['credentials'] = bytes(raw); self.save()
            with self.subTest(offset=offset), self.assertRaises(ValueError): self.run_evidence()
            self.assertFalse(self.output.exists())

    def test_symlink_sparse_unwritten_deep_and_metadata_alias_refused(self):
        baseline = self.images['credentials']; inode = 3*1024+3*128
        for case in ('symlink', 'sparse', 'unwritten', 'deep', 'alias', 'oversize'):
            raw = bytearray(baseline)
            if case == 'symlink': struct.pack_into('<H', raw, inode, 0xa1ff)
            elif case == 'sparse': struct.pack_into('<I', raw, inode+52, 1)
            elif case == 'unwritten': struct.pack_into('<H', raw, inode+56, 0x8001)
            elif case == 'deep': struct.pack_into('<H', raw, inode+46, 1)
            elif case == 'alias': struct.pack_into('<I', raw, inode+60, 3)
            else: struct.pack_into('<I', raw, inode+4, 65537)
            self.images['credentials'] = bytes(raw); self.save()
            with self.subTest(case=case), self.assertRaises(ValueError): self.run_evidence()
            self.assertFalse(self.output.exists())

    def test_duplicate_path_or_directory_file_alias_refused(self):
        baseline = self.images['credentials']
        for case in ('duplicate', 'alias'):
            raw = bytearray(baseline)
            if case == 'duplicate':
                struct.pack_into('<B', raw, 10*1024+12+6, 4)
                raw[10*1024+12+8:10*1024+12+12] = b'jibo'
            else: struct.pack_into('<I', raw, 11*1024+24, 2)
            self.images['credentials'] = bytes(raw); self.save()
            with self.subTest(case=case), self.assertRaises(ValueError): self.run_evidence()

    def test_storage_mutation_during_file_resolution_refused_before_export(self):
        original = S.FileReader.file
        def changed(*args):
            value = original(*args)
            with (self.inputs / 'full-storage.bin').open('r+b') as stream:
                stream.seek(-1, os.SEEK_END); stream.write(b'X'); stream.flush(); os.fsync(stream.fileno())
            return value
        with patch.object(S.FileReader, 'file', changed), self.assertRaises(ValueError): self.run_evidence()
        self.assertFalse(self.output.exists())

    def test_soft_deadline_expiry_refused(self):
        with patch.object(S.F.time, 'monotonic', return_value=1000000), patch.object(S.time, 'monotonic', side_effect=[0, 1000000]):
            with self.assertRaises(ValueError): self.run_evidence()
        self.assertFalse(self.output.exists())

    def test_existing_output_refused(self):
        self.output.mkdir(); (self.output / 'keep').write_bytes(b'keep')
        with self.assertRaises(ValueError): self.run_evidence()
        self.assertEqual((self.output / 'keep').read_bytes(), b'keep')

    def test_extent_outside_selected_partition_refused(self):
        raw = bytearray(self.images['credentials'])
        struct.pack_into('<I', raw, 3*1024+3*128+60, 64)
        self.images['credentials'] = bytes(raw); self.save()
        with self.assertRaises(S.F.E.Ext4PathError): self.run_evidence()
        self.assertFalse(self.output.exists())

    def test_input_reparse_entry_refused_before_read(self):
        original = S.B.A.R.ordinary_path
        def blocked(path):
            if Path(path).name == 'jetstream.json': raise ValueError('reparse fixture')
            return original(path)
        with patch.object(S.B.A.R, 'ordinary_path', blocked), self.assertRaises(ValueError): self.run_evidence()
        self.assertFalse(self.output.exists())

    def test_outer_manifest_raw_pin_is_required(self):
        self.path.write_text(json.dumps(self.manifest), encoding='utf-8')
        with self.assertRaises(ValueError): S.inspect(self.path, '0'*64, self.inputs, self.output)

    def test_cli_isolated_imports_and_redacted_failures(self):
        self.run_evidence()
        pin = sha(self.path.read_bytes())
        command = [sys.executable, '-I', '-B', str(Path(S.__file__)), '--manifest', str(self.path),
                   '--manifest-sha256', pin, '--inputs', str(self.inputs), '--output', str(self.root / 'cli')]
        result = subprocess.run(command, cwd=self.root, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['readyForApply'], False)
        command[command.index('--manifest-sha256')+1] = '0'*64
        failure = subprocess.run(command, cwd=self.root, capture_output=True, timeout=30)
        self.assertEqual(failure.returncode, 2)
        self.assertNotIn(str(self.root).encode(), failure.stderr)
        self.assertNotIn(b'Traceback', failure.stderr)


if __name__ == '__main__':
    unittest.main()
