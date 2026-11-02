import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).parents[1]))
import gpt_audit as A
import gpt_layout as G


def recalculate(data):
    struct.pack_into('<I', data, 512+88, zlib.crc32(data[1024:34*512]) & 0xffffffff)
    struct.pack_into('<I', data, 512+16, 0)
    struct.pack_into('<I', data, 512+16, zlib.crc32(data[512:512+92]) & 0xffffffff)
    return bytes(data)


def fixture():
    data = bytearray(34*512)
    data[512:520] = b'EFI PART'
    struct.pack_into('<II', data, 512+8, 0x10000, 92)
    struct.pack_into('<QQQQ', data, 512+24, 1, 4095, 34, 4062)
    data[512+56:512+72] = b'd'*16
    struct.pack_into('<QII', data, 512+72, 2, 128, 128)
    for index, name in enumerate(('rootfsA', 'rootfsB')):
        offset = 1024 + index*128
        data[offset:offset+16] = b't'*16
        data[offset+16:offset+32] = bytes([index+1])*16
        struct.pack_into('<QQ', data, offset+32, 64+index*64, 127+index*64)
        data[offset+56:offset+128] = name.encode('utf-16le').ljust(72, b'\0')
    return recalculate(data)


class GptAudit(unittest.TestCase):
    def test_shared_parser_preserves_legacy_partition_projection(self):
        value = G.audit_primary_gpt(fixture(), 4096)
        self.assertTrue(value['dualRootfsNamesPresent'])
        self.assertEqual(G.parse_primary_gpt(fixture(), 4096), value['partitions'])
        self.assertEqual([64, 128], [p['start_sector'] for p in value['partitions']])

    def test_crc_corruption_and_truncation_refused(self):
        for offset in (512+24, 1024):
            data = bytearray(fixture()); data[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError): G.audit_primary_gpt(bytes(data), 4096)
        for size in (0, 512, 1024, 34*512-1):
            with self.subTest(size=size), self.assertRaises(ValueError): G.audit_primary_gpt(fixture()[:size], 4096)

    def test_unsupported_header_or_geometry_refused_even_with_valid_crc(self):
        mutations = [(8, '<I', 0x20000), (12, '<I', 96), (20, '<I', 1),
                     (24, '<Q', 2), (32, '<Q', 8191), (40, '<Q', 2),
                     (48, '<Q', 4094), (72, '<Q', 1), (80, '<I', 129), (84, '<I', 136)]
        for offset, encoding, value in mutations:
            data = bytearray(fixture()); struct.pack_into(encoding, data, 512+offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError): G.audit_primary_gpt(recalculate(data), 4096)
        for geometry in (True, 0, 67, 1 << 49, 4097):
            with self.subTest(geometry=geometry), self.assertRaises(ValueError): G.audit_primary_gpt(fixture(), geometry)

    def test_partition_overlap_usable_bounds_and_ambiguous_ids_refused(self):
        cases = [(1024+128+32, '<Q', 100), (1024+32, '<Q', 10), (1024+40, '<Q', 4090)]
        for offset, encoding, value in cases:
            data = bytearray(fixture()); struct.pack_into(encoding, data, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError): G.audit_primary_gpt(recalculate(data), 4096)
        for change in ('duplicate-guid', 'zero-guid', 'duplicate-name', 'invalid-name', 'dirty-unused'):
            data = bytearray(fixture())
            if change == 'duplicate-guid': data[1024+128+16:1024+128+32] = b'\1'*16
            elif change == 'zero-guid': data[1024+16:1024+32] = b'\0'*16
            elif change == 'duplicate-name': data[1024+128+56:1024+128+128] = 'rootfsA'.encode('utf-16le').ljust(72,b'\0')
            elif change == 'invalid-name': data[1024+56:1024+58] = b'\0\xd8'
            else: data[1024+256+100] = 1
            with self.subTest(change=change), self.assertRaises(ValueError): G.audit_primary_gpt(recalculate(data), 4096)

    def test_cli_is_read_only_path_free_exclusive_and_imports_no_exploit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            prefix = root/'primary.bin'; output = root/'audit.json'
            original = fixture(); prefix.write_bytes(original)
            command = [sys.executable, '-I', '-B', str(Path(A.__file__)), '--gpt-prefix', str(prefix),
                       '--disk-sectors', '4096', '--expected-sha256', hashlib.sha256(original).hexdigest(), '--output', str(output)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(0, first.returncode, first.stderr)
            receipt = json.loads(output.read_bytes()); before = output.read_bytes()
            self.assertTrue(receipt['primaryGptChecksPassed'])
            for field in ('protectiveMbrVerified', 'backupGptVerified', 'deviceIdentityVerified', 'filesystemProfileVerified', 'readyForApply', 'deviceWritesPerformed'):
                self.assertIs(False, receipt[field])
            self.assertEqual('unknown', receipt['releaseFamily'])
            self.assertNotIn(str(root), json.dumps(receipt)); self.assertNotIn(str(root), first.stdout)
            self.assertEqual(original, prefix.read_bytes())
            again = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(2, again.returncode); self.assertEqual(before, output.read_bytes())
            output.unlink(); prefix.write_bytes(original[:-1]+b'x')
            bad = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(2, bad.returncode); self.assertFalse(output.exists()); self.assertNotIn(str(root), bad.stderr)
            probe = subprocess.run([sys.executable, '-I', '-B', '-c',
                "import importlib.util,sys; s=importlib.util.spec_from_file_location('a',sys.argv[1]); a=importlib.util.module_from_spec(s); s.loader.exec_module(a); assert not any(n.startswith(('Exploits','usb','tkinter','config')) for n in sys.modules)", str(Path(A.__file__))], capture_output=True, text=True)
            self.assertEqual(0, probe.returncode, probe.stderr)

    def test_regular_bounded_file_and_expected_hash_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); source = root/'source'
            source.write_bytes(fixture())
            with self.assertRaises(ValueError): A.audit_file(source, 4096, '0'*64)
            with self.assertRaises(ValueError): A.audit_file(root, 4096, '0'*64)
            source.write_bytes(b'x'*(G.MAX_PREFIX_BYTES+1))
            with self.assertRaises(ValueError): A.audit_file(source, 4096, '0'*64)


if __name__ == '__main__': unittest.main()
