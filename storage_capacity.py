"""Derive bounded user-area capacity from a retained EXT_CSD register image."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import re
import stat


SCHEMA = 'openjibo.storage-capacity.v1'
EXT_CSD_BYTES = 512
SECTOR_SIZE_BYTES = 512
SEC_COUNT_OFFSET = 212
SEC_COUNT_BYTES = 4
MAX_USER_AREA_SECTORS = 0x1D60000
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_REPARSE = 0x400


def _require(condition):
    if not condition:
        raise ValueError('storage_capacity_refused')


def _has_reparse(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & _REPARSE)


def _identity(info, windows=None):
    # Windows may report a different ctime between path and handle queries on
    # otherwise unchanged files. POSIX keeps ctime in the mutation guard.
    if windows is None:
        windows = os.name == 'nt'
    fields = (info.st_dev, info.st_ino, info.st_mode, info.st_size,
              getattr(info, 'st_mtime_ns', None))
    if not windows:
        fields += (getattr(info, 'st_ctime_ns', None),)
    return fields + (getattr(info, 'st_nlink', None), getattr(info, 'st_file_attributes', None))


def _ordinary_path(path):
    _require(type(path) is str or isinstance(path, Path))
    value = Path(os.path.abspath(os.fspath(path)))
    _require(value.is_absolute())
    chain = [value, *value.parents]
    for item in chain:
        info = item.lstat()
        _require(not _has_reparse(info))
        if item != value:
            _require(stat.S_ISDIR(info.st_mode))
    info = chain[0].lstat()
    _require(stat.S_ISREG(info.st_mode) and info.st_size == EXT_CSD_BYTES)
    _require(getattr(info, 'st_nlink', 1) == 1)
    return value, info


def _read_ext_csd(path):
    value, before_path = _ordinary_path(path)
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(value, flags)
    try:
        before_fd = os.fstat(fd)
        _require(stat.S_ISREG(before_fd.st_mode) and before_fd.st_size == EXT_CSD_BYTES)
        _require(getattr(before_fd, 'st_nlink', 1) == 1)
        _require(_identity(before_fd) == _identity(before_path))
        chunks = []
        remaining = EXT_CSD_BYTES + 1
        while remaining:
            chunk = os.read(fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b''.join(chunks)
        after_fd = os.fstat(fd)
        after_path = value.lstat()
        _require(_identity(before_fd) == _identity(after_fd) == _identity(after_path))
        _require(len(raw) == EXT_CSD_BYTES)
        return raw
    finally:
        os.close(fd)


def _evidence(raw, source_hash):
    _require(type(raw) is bytes and len(raw) == EXT_CSD_BYTES)
    _require(type(source_hash) is str and _HASH.fullmatch(source_hash))
    sectors = int.from_bytes(raw[SEC_COUNT_OFFSET:SEC_COUNT_OFFSET + SEC_COUNT_BYTES], 'little', signed=False)
    _require(0 < sectors <= MAX_USER_AREA_SECTORS)
    evidence = {
        'schema': SCHEMA,
        'sectorSizeBytes': SECTOR_SIZE_BYTES,
        'storageSectorCount': sectors,
        'sizeBytes': sectors * SECTOR_SIZE_BYTES,
        'sourceHash': source_hash,
        'sourceBytes': EXT_CSD_BYTES,
        'physicalIdentityVerified': False,
        'captureAuthenticityVerified': False,
    }
    validate_evidence(evidence)
    return evidence


def inspect_ext_csd(path):
    """Read one ordinary 512-byte EXT_CSD file and emit capacity metadata only.

    ``sourceHash`` binds the output to the exact local register bytes. It does
    not authenticate capture provenance or tie the bytes to a physical device.
    SEC_COUNT describes the main user area; boot and RPMB partitions are not
    included in this capacity value.
    """
    raw = _read_ext_csd(path)
    return _evidence(raw, hashlib.sha256(raw).hexdigest())


def validate_evidence(value):
    """Strictly validate the canonical evidence object consumed by later plans."""
    fields = {'schema', 'sectorSizeBytes', 'storageSectorCount', 'sizeBytes',
              'sourceHash', 'sourceBytes', 'physicalIdentityVerified',
              'captureAuthenticityVerified'}
    _require(type(value) is dict and set(value) == fields)
    _require(type(value['schema']) is str and value['schema'] == SCHEMA)
    _require(type(value['sectorSizeBytes']) is int and value['sectorSizeBytes'] == SECTOR_SIZE_BYTES)
    sectors = value['storageSectorCount']
    _require(type(sectors) is int and 0 < sectors <= MAX_USER_AREA_SECTORS)
    size = value['sizeBytes']
    _require(type(size) is int and size == sectors * SECTOR_SIZE_BYTES)
    _require(type(value['sourceHash']) is str and _HASH.fullmatch(value['sourceHash']))
    _require(type(value['sourceBytes']) is int and value['sourceBytes'] == EXT_CSD_BYTES)
    _require(type(value['physicalIdentityVerified']) is bool and value['physicalIdentityVerified'] is False)
    _require(type(value['captureAuthenticityVerified']) is bool and value['captureAuthenticityVerified'] is False)
    return value


def _create_new_output(path, payload):
    """Create a metadata file without replacing any existing path."""
    _require(type(path) is str or isinstance(path, Path))
    value = Path(os.path.abspath(os.fspath(path)))
    _require(value.is_absolute())
    parent = value.parent
    for item in [parent, *parent.parents]:
        info = item.lstat()
        _require(not _has_reparse(info) and stat.S_ISDIR(info.st_mode))
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0)
    fd = os.open(value, flags, 0o600)
    created_identity = os.fstat(fd)
    complete = False
    try:
        before = os.fstat(fd)
        _require(stat.S_ISREG(before.st_mode) and before.st_size == 0)
        offset = 0
        while offset < len(payload):
            written = os.write(fd, payload[offset:])
            _require(type(written) is int and written > 0)
            offset += written
        os.fsync(fd)
        after = os.fstat(fd)
        path_after = value.lstat()
        _require((before.st_dev, before.st_ino, before.st_mode) ==
                 (after.st_dev, after.st_ino, after.st_mode))
        _require((after.st_dev, after.st_ino, after.st_mode, after.st_size,
                  getattr(after, 'st_nlink', 1), getattr(after, 'st_file_attributes', None)) ==
                 (path_after.st_dev, path_after.st_ino, path_after.st_mode, path_after.st_size,
                  getattr(path_after, 'st_nlink', 1), getattr(path_after, 'st_file_attributes', None)))
        _require(after.st_size == len(payload))
        complete = True
    finally:
        os.close(fd)
        if not complete:
            try:
                current = value.lstat()
                if ((current.st_dev, current.st_ino) ==
                        (created_identity.st_dev, created_identity.st_ino) and
                        not _has_reparse(current)):
                    value.unlink()
            except OSError:
                pass


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Derive capacity metadata from one retained EXT_CSD file. No device access is performed.')
    parser.add_argument('--input', required=True, help='retained 512-byte EXT_CSD file')
    parser.add_argument('--expected-sha256', required=True, help='expected lowercase SHA-256 of the input')
    parser.add_argument('--output', required=True, help='new JSON file path; existing paths are refused')
    args = parser.parse_args(argv)
    try:
        _require(type(args.expected_sha256) is str and _HASH.fullmatch(args.expected_sha256))
        evidence = inspect_ext_csd(args.input)
        _require(evidence['sourceHash'] == args.expected_sha256)
        payload = (json.dumps(evidence, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')
        _create_new_output(args.output, payload)
        print(json.dumps({'outputHash': hashlib.sha256(payload).hexdigest(),
                          'schema': SCHEMA, 'sourceHash': evidence['sourceHash']},
                         sort_keys=True, separators=(',', ':')))
        return 0
    except (OSError, ValueError, TypeError):
        print('capacity_metadata_refused')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
