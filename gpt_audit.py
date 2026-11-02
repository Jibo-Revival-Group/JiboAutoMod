#!/usr/bin/env python3
"""Audit a retained GPT prefix file; no USB, device commands or storage writes."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat


def sibling(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


layout = sibling('gpt_layout')
recovery = sibling('recovery_evidence')


def audit_file(path, total_sectors, expected_sha256):
    recovery.require(type(expected_sha256) is str and recovery.preparation.HASH.fullmatch(expected_sha256))
    path = recovery.ordinary_path(path)
    original = path.lstat()
    recovery.require(stat.S_ISREG(original.st_mode) and 1024 <= original.st_size <= layout.MAX_PREFIX_BYTES)
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(str(path), flags), 'rb') as stream:
        before = os.fstat(stream.fileno())
        recovery.require(stat.S_ISREG(before.st_mode) and recovery.file_identity(before) == recovery.file_identity(original))
        data = stream.read(layout.MAX_PREFIX_BYTES+1)
        recovery.require(len(data) == before.st_size and recovery.identity(before) == recovery.identity(os.fstat(stream.fileno())))
    recovery.require(recovery.file_identity(before) == recovery.file_identity(recovery.ordinary_path(path).lstat()))
    digest = hashlib.sha256(data).hexdigest()
    recovery.require(digest == expected_sha256)
    projected = layout.audit_primary_gpt(data, total_sectors)
    return dict(schema='openjibo.primary-gpt-audit.v1', prefixSha256=digest,
                checkedAtUtc=datetime.now(timezone.utc).isoformat(), layout=projected,
                auditorSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                parserSha256=hashlib.sha256(Path(layout.__file__).read_bytes()).hexdigest(),
                geometryOrigin='operator-supplied-not-device-measured',
                primaryGptChecksPassed=True, protectiveMbrVerified=False, backupGptVerified=False, deviceIdentityVerified=False,
                filesystemProfileVerified=False, releaseFamily='unknown', readyForApply=False,
                deviceWritesPerformed=False, directNetworkRequestsPerformed=False)


def main():
    class Parser(argparse.ArgumentParser):
        def error(self, message): self.exit(2, 'GPT audit refused; check required arguments. See Docs/primary-gpt-audit.md.\n')
    parser = Parser(description=__doc__)
    parser.add_argument('--gpt-prefix', required=True, type=Path)
    parser.add_argument('--disk-sectors', required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = audit_file(args.gpt_prefix, int(args.disk_sectors, 0), args.expected_sha256)
        recovery.preparation.export(result, args.output)
    except (ValueError, OSError, UnicodeError):
        parser.exit(2, 'GPT audit refused; check retained evidence, geometry and new output. See Docs/primary-gpt-audit.md.\n')
    print(json.dumps(dict(auditExported=True, auditSha256=recovery.preparation.digest(result),
                          primaryGptChecksPassed=True, readyForApply=False, deviceWritesPerformed=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
