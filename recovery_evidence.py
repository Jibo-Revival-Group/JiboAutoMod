#!/usr/bin/env python3
"""Check retained regular recovery files against a conversion inventory, read-only."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat

_spec = importlib.util.spec_from_file_location('conversion_preparation', Path(__file__).with_name('conversion_plan.py'))
preparation = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(preparation)


def require(value):
    preparation.require(value, 'recovery_file_check_refused')


def ordinary_path(path):
    # Refuse direct remote/device paths and reparse/symlink traversal. Mounted
    # filesystem backing and an adversarial directory race are outside this check.
    text = str(path)
    require(not text.startswith(('\\\\', '//')))
    if os.name == 'nt':
        require(':' not in text[2:])  # no alternate data streams
    absolute = Path(path).absolute()
    for component in (absolute, *absolute.parents):
        info = component.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 1024)
    return absolute


def identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def file_identity(info):
    return info.st_dev, info.st_ino, info.st_size


def check_file(path, expected):
    path = ordinary_path(path)
    before_path = path.lstat()
    require(stat.S_ISREG(before_path.st_mode) and before_path.st_size == expected['sizeBytes'])
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    descriptor = os.open(str(path), flags)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and file_identity(before) == file_identity(before_path))
        sha = hashlib.sha256(); size = 0
        while True:
            block = stream.read(min(1048576, expected['sizeBytes'] - size + 1))
            if not block:
                break
            size += len(block)
            require(size <= expected['sizeBytes'])
            sha.update(block)
        require(identity(before) == identity(os.fstat(stream.fileno())))
    require(file_identity(before) == file_identity(ordinary_path(path).lstat()))
    require(size == expected['sizeBytes'] and sha.hexdigest() == expected['sha256'])
    return {'kind': expected['kind'], 'sha256': sha.hexdigest(), 'sizeBytes': size}


def check(audit, files, base_directory, checked_at=None):
    preparation.inventory(audit)
    preparation.exact(files, ('schema', 'files'), 'recovery_file_map_fields')
    require(files['schema'] == 'openjibo.recovery-files.v1' and type(files['files']) is list)
    require(0 < len(files['files']) <= 3)
    paths = {}
    for item in files['files']:
        preparation.exact(item, ('kind', 'path'), 'recovery_file_fields')
        require(type(item['kind']) is str and item['kind'] not in paths)
        require(type(item['path']) is str and 0 < len(item['path']) <= 4096 and '\x00' not in item['path'])
        candidate = Path(item['path'])
        # Test the raw spelling before joining, since Path can normalize //.
        require(not item['path'].startswith(('\\\\', '//')))
        paths[item['kind']] = candidate if candidate.is_absolute() else Path(base_directory) / candidate
    expected = {b['kind']: b for b in audit['backups']}
    require(set(paths) == set(expected) and 'calibration' in expected and
            bool(set(expected).intersection(('affected-storage', 'full-storage'))))
    results = []
    identities = set()
    for kind in sorted(paths):
        # The same inode/file cannot stand in for two distinct recovery artifacts.
        info = ordinary_path(paths[kind]).lstat()
        file_id = info.st_dev, info.st_ino
        require(file_id not in identities); identities.add(file_id)
        results.append(check_file(paths[kind], expected[kind]))
    timestamp = checked_at or datetime.now(timezone.utc)
    require(timestamp.tzinfo is not None and timestamp.utcoffset().total_seconds() == 0)
    return {'schema': 'openjibo.recovery-file-check.v1',
            'inventorySha256': preparation.digest(audit),
            'deviceFingerprintSha256': audit['deviceFingerprintSha256'],
            'auditEvidenceSha256': audit['auditEvidenceSha256'],
            'checkerSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'preparationParserSha256': hashlib.sha256(Path(__file__).with_name('conversion_plan.py').read_bytes()).hexdigest(),
            'checkedAtUtc': timestamp.isoformat(), 'files': results,
            'fileBytesMatchedSuppliedInventory': True,
            'robotAssociationVerified': False, 'restoreTested': False,
            'readyForApply': False, 'deviceWritesPerformed': False,
            'directNetworkRequestsPerformed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('inventory', 'files', 'output'):
        parser.add_argument('--' + option, required=True, type=Path)
    args = parser.parse_args()
    try:
        result = check(preparation.read_input(args.inventory), preparation.read_input(args.files), args.files.absolute().parent)
        preparation.export(result, args.output)
    except (ValueError, OSError, UnicodeError, RecursionError):
        parser.exit(2, 'Recovery file check refused; check retained files, inventory and new output. See Docs/recovery-file-check.md.\n')
    print(json.dumps({'recoveryFileCheckExported': True, 'receiptSha256': preparation.digest(result),
                      'fileBytesMatchedSuppliedInventory': True, 'readyForApply': False,
                      'deviceWritesPerformed': False, 'directNetworkRequestsPerformed': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
