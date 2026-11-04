import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).parents[1]))
import gpt_recovery as H
from test_gpt_audit import fixture


def header_crc(data, sector):
    offset = sector*512
    struct.pack_into('<I', data, offset+16, 0)
    struct.pack_into('<I', data, offset+16, zlib.crc32(data[offset:offset+92]) & 0xffffffff)


def complete_disk(prefix=None, disk=None, backup_lba=4063):
    """Synthetic 4096-sector disk; never use this generator on robot evidence."""
    prefix = prefix or fixture()
    data = bytearray(disk if disk is not None else b'\0'*(4096*512))
    data[:len(prefix)] = prefix
    data[446:510] = b'\0'*64
    data[446:462] = struct.pack('<B3sB3sII', 0, b'\0\2\0', 0xee, b'\xff'*3, 1, 4095)
    data[510:512] = b'\x55\xaa'
    primary = data[512:1024]
    entries_lba = struct.unpack_from('<Q', primary, 72)[0]
    data[backup_lba*512:(backup_lba+32)*512] = data[entries_lba*512:(entries_lba+32)*512]
    data[4095*512:] = primary
    struct.pack_into('<QQ', data, 4095*512+24, 4095, 1)
    struct.pack_into('<Q', data, 4095*512+72, backup_lba)
    header_crc(data, 4095)
    return bytes(data)


def reader(data, reads=None):
    def read_at(offset, length):
        if reads is not None: reads.append((offset, length))
        assert 0 <= offset and 0 < length <= 1048576 and offset+length <= len(data)
        return bytes(data[offset:offset+length])
    return read_at


class GptRecovery(unittest.TestCase):
    def test_both_copies_and_mbr_checked_with_bounded_metadata_reads(self):
        disk = complete_disk(); reads = []
        result = H.audit_reader(reader(disk, reads), 4096)
        self.assertTrue(result['primaryGptChecksPassed'])
        self.assertTrue(result['backupGptVerified']); self.assertTrue(result['protectiveMbrVerified'])
        self.assertTrue(result['entryArraysEqual']); self.assertEqual(result['partitionCount'], 2)
        self.assertLessEqual(len(reads), 8); self.assertLess(sum(size for _, size in reads), 3*1048576)
        for key in ('deviceIdentityVerified','installedReleaseVerified','filesystemIntegrityVerified',
                    'allocationOwnershipVerified','calibrationAssociationVerified','restoreTested',
                    'executionSupported','readyForApply','deviceWritesPerformed','networkRequestsPerformed','chsGeometryVerified'):
            self.assertIs(result[key], False)
        self.assertNotIn('rootfs', json.dumps(result))

    def test_primary_only_old_fixture_is_not_recovery_evidence(self):
        disk = fixture().ljust(4096*512, b'\0')
        self.assertTrue(H.G.audit_primary_gpt(fixture(), 4096))
        with self.assertRaises(ValueError): H.audit_reader(reader(disk), 4096)

    def test_mbr_missing_wrong_size_wrong_start_bootable_and_hybrid_refused(self):
        for offset, raw in ((510,b'\0\0'),(446,b'\x80'),(450,b'\x83'),
                            (454,struct.pack('<I',2)),(458,struct.pack('<I',4094)),(462,b'\x01')):
            data = bytearray(complete_disk()); data[offset:offset+len(raw)] = raw
            with self.subTest(offset=offset), self.assertRaises(ValueError): H.audit_reader(reader(data),4096)

    def test_protective_record_may_occupy_a_different_slot_and_chs_is_not_inferred(self):
        data = bytearray(complete_disk()); data[494:510] = data[446:462]; data[446:462] = b'\0'*16
        data[495:498] = b'\xfe'*3
        result = H.audit_reader(reader(data),4096)
        self.assertTrue(result['protectiveMbrVerified']); self.assertFalse(result['chsGeometryVerified'])

    def test_corrupt_headers_or_arrays_refused(self):
        for offset in (512+16,1024,4063*512,4095*512+16):
            data = bytearray(complete_disk()); data[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError): H.audit_reader(reader(data),4096)

    def test_valid_crc_cannot_hide_reciprocal_header_disagreement(self):
        for offset, fmt, value in ((8,'<I',0x20000),(12,'<I',96),(20,'<I',1),(24,'<Q',4094),
                                   (32,'<Q',2),(40,'<Q',35),(48,'<Q',4061),(56,'<Q',123),
                                   (80,'<I',127),(84,'<I',256),(88,'<I',0)):
            data=bytearray(complete_disk()); struct.pack_into(fmt,data,4095*512+offset,value); header_crc(data,4095)
            with self.subTest(offset=offset),self.assertRaises(ValueError): H.audit_reader(reader(data),4096)

    def test_backup_table_range_checked_before_reading(self):
        for lba in (0,1,100,4062,4064,4095,2**63):
            data=bytearray(complete_disk()); struct.pack_into('<Q',data,4095*512+72,lba); header_crc(data,4095)
            reads=[]
            with self.subTest(lba=lba),self.assertRaises(ValueError): H.audit_reader(reader(data,reads),4096)
            self.assertEqual(len(reads),4)

    def test_backup_table_can_have_a_gap_before_header(self):
        data=bytearray(complete_disk()); struct.pack_into('<Q',data,512+48,4000); header_crc(data,1)
        prefix=bytes(data[:34*512]); data=complete_disk(prefix,backup_lba=4030)
        self.assertEqual(H.audit_reader(reader(data),4096)['backupEntryArraySector'],4030)

    def test_reserved_header_bytes_and_non_128_entry_profiles_refused(self):
        for offset in (512+92,4095*512+92):
            data=bytearray(complete_disk()); data[offset]=1
            with self.subTest(offset=offset),self.assertRaises(ValueError): H.audit_reader(reader(data),4096)
        data=bytearray(complete_disk()); struct.pack_into('<I',data,512+80,127); header_crc(data,1)
        with self.assertRaises(ValueError): H.audit_reader(reader(data),4096)
        for geometry in (True,0,67,4097,H.MAX_STORAGE//512+1):
            with self.subTest(geometry=geometry),self.assertRaises(ValueError): H.audit_reader(reader(complete_disk()),geometry)

    def test_repaired_array_crc_still_requires_identical_entries(self):
        data=bytearray(complete_disk()); data[4063*512+48]^=1
        struct.pack_into('<I',data,4095*512+88,zlib.crc32(data[4063*512:4095*512]) & 0xffffffff)
        header_crc(data,4095)
        with self.assertRaises(ValueError): H.audit_reader(reader(data),4096)

    def test_same_crc_different_backup_array_is_refused(self):
        data=bytearray(complete_disk()); array=bytearray(data[4063*512:4095*512])
        target=zlib.crc32(array); array[48]^=1
        # Solve the linear CRC32 influence of the final 32 bits to construct an
        # actual collision. This proves equality is checked beyond CRCs.
        base=zlib.crc32(array); basis={}
        for bit in range(32):
            trial=bytearray(array); trial[-4+bit//8]^=1 << (bit%8)
            vector=zlib.crc32(trial)^base; mask=1 << bit
            while vector:
                pivot=vector.bit_length()-1
                if pivot not in basis: basis[pivot]=(vector,mask); break
                value,combination=basis[pivot]; vector^=value; mask^=combination
        vector=target^base; mask=0
        while vector:
            value,combination=basis[vector.bit_length()-1]; vector^=value; mask^=combination
        for bit in range(32):
            if mask & (1 << bit): array[-4+bit//8]^=1 << (bit%8)
        self.assertEqual(zlib.crc32(array),target)
        self.assertNotEqual(bytes(array),bytes(data[4063*512:4095*512]))
        data[4063*512:4095*512]=array
        with self.assertRaises(ValueError): H.audit_reader(reader(data),4096)

    def test_same_descriptor_changes_refuse_and_budget_expires(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary).resolve()/'full.bin'; disk=complete_disk(); path.write_bytes(disk)
            original=H.audit_reader
            def mutate(read_at,sectors):
                result=original(read_at,sectors)
                with path.open('r+b') as stream: stream.seek(50000); stream.write(b'x')
                return result
            with patch.object(H,'audit_reader',side_effect=mutate),self.assertRaises(ValueError):
                H.audit_file(path,4096,H.sha(disk))
            path.write_bytes(disk)
            with patch.object(H.time,'monotonic',side_effect=[0,601]),self.assertRaises(ValueError):
                H.audit_file(path,4096,H.sha(disk))

    def test_path_and_descriptor_timestamp_views_are_compared_with_their_own_api(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary).resolve()/'full.bin'; disk=complete_disk(); path.write_bytes(disk)
            real_fstat=H.os.fstat
            def other_ctime(fd):
                value=real_fstat(fd)
                fields={name:getattr(value,name) for name in ('st_mode','st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')}
                fields['st_ctime_ns']+=1000
                return SimpleNamespace(**fields)
            with patch.object(H.os,'fstat',side_effect=other_ctime):
                result=H.audit_file(path,4096,H.sha(disk))
            self.assertTrue(result['backupGptVerified'])

    def test_cli_hash_pins_output_reuse_privacy_and_no_device_imports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); path=root/'PRIVATE_INPUT.bin'; output=root/'audit.json'
            disk=bytearray(complete_disk()); marker=b'PRIVATE_DISK_BOOT_CODE_MARKER!!!'; disk[:len(marker)]=marker
            disk=bytes(disk); path.write_bytes(disk)
            args=[sys.executable,'-I','-B',str(Path(H.__file__)),'--full-storage',str(path),
                  '--disk-sectors','4096','--expected-sha256',H.sha(disk),'--output',str(output)]
            result=subprocess.run(args,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            evidence=json.loads(output.read_bytes()); saved=output.read_bytes()
            self.assertEqual(evidence['fullStorage'],dict(sha256=H.sha(disk),sizeBytes=len(disk)))
            self.assertNotIn('PRIVATE_',json.dumps(evidence)+result.stdout); self.assertEqual(path.read_bytes(),disk)
            again=subprocess.run(args,capture_output=True,text=True)
            self.assertEqual(again.returncode,2); self.assertEqual(output.read_bytes(),saved)
            output.unlink(); args[args.index('--expected-sha256')+1]='0'*64
            bad=subprocess.run(args,capture_output=True,text=True)
            self.assertEqual(bad.returncode,2); self.assertFalse(output.exists()); self.assertNotIn(str(root),bad.stderr)
            probe=subprocess.run([sys.executable,'-I','-B','-c',
                "import importlib.util,sys; s=importlib.util.spec_from_file_location('h',sys.argv[1]); h=importlib.util.module_from_spec(s); s.loader.exec_module(h); assert not any(n.startswith(('Exploits','usb','config','tkinter')) for n in sys.modules)",str(Path(H.__file__))],capture_output=True,text=True)
            self.assertEqual(probe.returncode,0,probe.stderr)


if __name__ == '__main__': unittest.main()
