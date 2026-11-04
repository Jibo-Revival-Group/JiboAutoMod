#!/usr/bin/env python3
"""Audit protective MBR and both GPT copies in a pinned offline full backup."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import struct
import time
import zlib


def sibling(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


G = sibling('gpt_layout')
R = sibling('recovery_evidence')
MAX_STORAGE = 64 * 1024**3


def require(value):
    if not value:
        raise ValueError('gpt_recovery_refused')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def audit_reader(read_at, sectors):
    """Metadata checks only. Caller must hold and authenticate a stable reader."""
    require(type(sectors) is int and 68 <= sectors <= MAX_STORAGE // 512)
    mbr = read_at(0, 512)
    require(type(mbr) is bytes and len(mbr) == 512 and mbr[510:] == b'\x55\xaa')
    records = [mbr[446 + i*16:462 + i*16] for i in range(4)]
    used = [entry for entry in records if entry != b'\0'*16]
    require(len(used) == 1)
    entry = used[0]
    require(entry[0] == 0 and entry[4] == 0xee)
    require(struct.unpack_from('<II', entry, 8) == (1, min(sectors - 1, 0xffffffff)))
    # CHS values, boot code and disk signature are not interpreted or exported.
    primary = read_at(512, 512)
    require(type(primary) is bytes and len(primary) == 512)
    require(primary[:8] == b'EFI PART' and primary[92:] == b'\0'*420)
    entries_lba, count, size = struct.unpack_from('<QII', primary, 72)
    require(count == 128 and size == 128 and entries_lba >= 2)
    prefix_size = entries_lba*512 + count*size
    require(prefix_size <= min(G.MAX_PREFIX_BYTES, sectors*512))
    prefix = b''.join(read_at(offset, min(1048576, prefix_size - offset))
                      for offset in range(0, prefix_size, 1048576))
    layout = G.audit_primary_gpt(prefix, sectors)
    require(prefix[512:1024] == primary and prefix[:512] == mbr)
    backup = read_at((sectors - 1)*512, 512)
    require(type(backup) is bytes and len(backup) == 512)
    require(backup[:16] == primary[:16] and backup[20:24] == b'\0'*4 and backup[92:] == b'\0'*420)
    header_crc = bytearray(backup[:92]); header_crc[16:20] = b'\0'*4
    require(zlib.crc32(header_crc) & 0xffffffff == struct.unpack_from('<I', backup, 16)[0])
    require(struct.unpack_from('<QQ', backup, 24) == (sectors - 1, 1))
    require(backup[40:72] == primary[40:72] and backup[80:92] == primary[80:92])
    backup_lba = struct.unpack_from('<Q', backup, 72)[0]
    require(layout['lastUsableSector'] < backup_lba and backup_lba + 32 <= sectors - 1)
    backup_entries = read_at(backup_lba*512, count*size)
    primary_entries = prefix[entries_lba*512:entries_lba*512 + count*size]
    require(type(backup_entries) is bytes and len(backup_entries) == count*size)
    require(zlib.crc32(backup_entries) & 0xffffffff == struct.unpack_from('<I', backup, 88)[0])
    require(backup_entries == primary_entries)
    return dict(schema='openjibo.gpt-recovery-evidence.v1',
                checkedAtUtc=datetime.now(timezone.utc).isoformat(), verificationScope='retained-backup-bytes',
                sectorSizeBytes=512, suppliedDiskSectors=sectors, partitionCount=len(layout['partitions']),
                firstUsableSector=layout['firstUsableSector'], lastUsableSector=layout['lastUsableSector'],
                primaryEntryArraySector=entries_lba, backupEntryArraySector=backup_lba,
                entryCount=count, entrySizeBytes=size, entryArraysSha256=sha(primary_entries),
                primaryHeaderSha256=sha(primary), backupHeaderSha256=sha(backup), protectiveMbrSha256=sha(mbr),
                primaryGptChecksPassed=True, backupGptVerified=True, protectiveMbrVerified=True, entryArraysEqual=True,
                geometryOrigin='operator-supplied-not-device-measured', chsGeometryVerified=False,
                deviceIdentityVerified=False, installedReleaseVerified=False, filesystemIntegrityVerified=False,
                allocationOwnershipVerified=False, calibrationAssociationVerified=False, restoreTested=False,
                executionSupported=False, readyForApply=False, deviceWritesPerformed=False, networkRequestsPerformed=False,
                codeSha256=dict(auditor=sha(Path(__file__).read_bytes()), primaryParser=sha(Path(G.__file__).read_bytes())))


def audit_file(path, sectors, expected_sha256):
    require(type(sectors) is int and 68 <= sectors <= MAX_STORAGE // 512)
    require(type(expected_sha256) is str and R.preparation.HASH.fullmatch(expected_sha256))
    path = R.ordinary_path(path); original = path.lstat(); total = sectors*512
    require(stat.S_ISREG(original.st_mode) and original.st_size == total)
    deadline = time.monotonic() + 600
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(str(path), flags), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and R.file_identity(before) == R.file_identity(original))
        digest = hashlib.sha256(); consumed = 0
        while consumed < total:
            require(time.monotonic() < deadline)
            block = stream.read(min(1048576, total - consumed)); require(block)
            consumed += len(block); digest.update(block)
        require(not stream.read(1) and digest.hexdigest() == expected_sha256)
        require(R.identity(before) == R.identity(os.fstat(stream.fileno())))
        reads = 0; read_bytes = 0
        def read_at(offset, length):
            nonlocal reads, read_bytes
            require(type(offset) is int and type(length) is int and 0 <= offset and 0 < length <= 1048576 and offset + length <= total)
            reads += 1; read_bytes += length
            require(reads <= 16 and read_bytes <= 3*1048576 and time.monotonic() < deadline)
            stream.seek(offset); raw = stream.read(length); require(len(raw) == length); return raw
        result = audit_reader(read_at, sectors)
        require(R.identity(before) == R.identity(os.fstat(stream.fileno())))
    after_path = R.ordinary_path(path).lstat()
    # Keep timestamps within each stat API: Windows fstat/lstat can expose
    # different ctime values. Both path and descriptor snapshots must be stable.
    require(R.file_identity(before) == R.file_identity(after_path))
    require(R.identity(original) == R.identity(after_path))
    result['fullStorage'] = dict(sha256=expected_sha256, sizeBytes=total)
    result['codeSha256']['pathChecker'] = sha(Path(R.__file__).read_bytes())
    return result


def main():
    class Parser(argparse.ArgumentParser):
        def error(self, message): self.exit(2, 'GPT recovery audit refused; check required arguments. See Docs/gpt-recovery-audit.md.\n')
    parser = Parser(description=__doc__)
    parser.add_argument('--full-storage', type=Path, required=True)
    parser.add_argument('--disk-sectors', required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        R.ordinary_path(args.output.absolute().parent)
        require(not args.output.exists() and not args.output.is_symlink())
        result = audit_file(args.full_storage, int(args.disk_sectors, 0), args.expected_sha256)
        R.preparation.export(result, args.output)
    except (ValueError, OSError, UnicodeError, TypeError, struct.error, RecursionError):
        parser.exit(2, 'GPT recovery audit refused; check pinned backup, supported layout and new output. No device operation was performed.\n')
    print(json.dumps(dict(auditExported=True, auditSha256=R.preparation.digest(result), backupGptVerified=True,
                          protectiveMbrVerified=True, readyForApply=False, deviceWritesPerformed=False)))


if __name__ == '__main__': main()
