#!/usr/bin/env python3
"""Export a conversion preparation plan. No USB, SSH, network or device writes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

LIMIT = 65536
HASH = re.compile(r'[0-9a-f]{64}')


def require(value, code):
    if not value:
        raise ValueError(code)


def exact(value, keys, code):
    require(type(value) is dict and set(value) == set(keys), code)


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate_input_field')
        result[key] = value
    return result


def read_input(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    require(len(raw) <= LIMIT, 'input_too_large')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=no_duplicates,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_input')))


def inventory(value):
    exact(value, ('schema', 'deviceFingerprintSha256', 'releaseFamily', 'observedAtUtc',
                  'auditEvidenceSha256', 'backups'), 'inventory_fields')
    require(value['schema'] == 'openjibo.conversion-inventory.v1', 'inventory_schema')
    require(all(type(value[key]) is str and HASH.fullmatch(value[key]) for key in
                ('deviceFingerprintSha256', 'auditEvidenceSha256')), 'inventory_hash')
    require(value['releaseFamily'] in ('oobe', 'pegasus-v1', 'v2', 'unknown'), 'release_family')
    try:
        observed = datetime.fromisoformat(value['observedAtUtc'].replace('Z', '+00:00'))
        require(observed.tzinfo is not None and observed.utcoffset().total_seconds() == 0, 'audit_time_utc')
    except (AttributeError, TypeError, ValueError):
        raise ValueError('audit_time_utc') from None
    require(type(value['backups']) is list and len(value['backups']) <= 3, 'backup_inventory')
    kinds = set()
    for backup in value['backups']:
        exact(backup, ('kind', 'sha256', 'sizeBytes'), 'backup_fields')
        require(backup['kind'] in ('calibration', 'affected-storage', 'full-storage')
                and backup['kind'] not in kinds, 'backup_kind')
        kinds.add(backup['kind'])
        require(type(backup['sha256']) is str and HASH.fullmatch(backup['sha256'])
                and type(backup['sizeBytes']) is int and backup['sizeBytes'] > 0, 'backup_identity')
    return value


def target(value):
    exact(value, ('schema', 'mode', 'providerId', 'apiOrigin'), 'target_fields')
    require(value['schema'] == 'openjibo.conversion-target.v1', 'target_schema')
    require(value['mode'] in ('isolated', 'hybrid', 'managed'), 'target_mode')
    require(type(value['providerId']) is str and
            re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,62}', value['providerId']), 'provider_id')
    if value['mode'] == 'isolated':
        require(value['providerId'] == 'self-hosted', 'isolated_provider')
    origin = value['apiOrigin']
    require(type(origin) is str and 0 < len(origin) <= 2048 and
            all(33 <= ord(c) <= 126 for c in origin) and '\\' not in origin and
            '%' not in origin and '#' not in origin and '?' not in origin, 'target_origin')
    try:
        parsed = urlsplit(origin)
        require(parsed.scheme in ('http', 'https') and parsed.hostname and
                parsed.username is None and parsed.password is None and
                not parsed.query and not parsed.fragment and parsed.path in ('', '/') and
                (parsed.port is None or 1 <= parsed.port <= 65535), 'target_origin')
    except ValueError:
        raise ValueError('target_origin') from None
    require(value['mode'] == 'isolated' or parsed.scheme == 'https', 'provider_https_required')
    require(parsed.hostname.lower() not in ('localhost', '127.0.0.1', '::1', '0.0.0.0', '::'),
            'robot_reachable_origin_required')
    return value


def plan(audit, selection):
    inventory(audit)
    target(selection)
    kinds = {item['kind'] for item in audit['backups']}
    blockers = []
    if audit['releaseFamily'] == 'unknown':
        blockers.append('unknown-device-release-needs-audit')
    if 'calibration' not in kinds:
        blockers.append('calibration-recovery-evidence-missing')
    if not kinds.intersection(('affected-storage', 'full-storage')):
        blockers.append('affected-storage-recovery-evidence-missing')
    return {'schema': 'openjibo.conversion-preparation-plan.v1',
            'inventorySha256': digest(audit), 'targetSha256': digest(selection),
            'deviceFingerprintSha256': audit['deviceFingerprintSha256'],
            'releaseFamily': audit['releaseFamily'], 'auditObservedAtUtc': audit['observedAtUtc'],
            'auditEvidenceSha256': audit['auditEvidenceSha256'], 'recoveryEvidence': audit['backups'],
            'target': selection, 'preparationBlockers': blockers,
            'suppliedPreparationFieldsComplete': not blockers,
            'inputOrigin': 'operator-supplied-not-independently-verified',
            'stageOrder': ['audit', 'recovery', 'select-target', 'review-exact-change-plan',
                           'confirm-apply', 'readback', 'provider-handoff', 'verify-turn', 'rollback-export'],
            'requiredBeforeApply': ['native-device-audit-and-supported-profile',
                                    'fresh-audit-and-verified-recovery-bytes',
                                    'exact-file-sector-certificate-change-plan',
                                    'owner-confirmation', 'bounded-profile-writer-and-readback',
                                    'verified-rollback-path'],
            'providerOnboardingRequired': selection['mode'] != 'isolated',
            'managedMembershipRequiredForIsolatedMode': False,
            'executionSupported': False, 'readyForApply': False, 'deviceWritesPerformed': False,
            'networkRequestsPerformed': False, 'cloudOwnershipVerified': False,
            'recoveryBytesVerified': False, 'robotCompatibilityVerified': False}


def export(value, output):
    path = Path(output)
    require(path.parent.is_dir(), 'output_parent_required')
    # Exclusive creation preserves a prior plan. Input paths and credentials are not exported.
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(canonical(value) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', required=True, type=Path)
    parser.add_argument('--target', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        value = plan(read_input(args.inventory), read_input(args.target))
        export(value, args.output)
    except FileExistsError:
        parser.exit(2, 'Output already exists; choose a new plan file.\n')
    except (ValueError, OSError, UnicodeError):
        parser.exit(2, 'Invalid preparation input or output; see Docs/conversion-preparation.md.\n')
    print(json.dumps({'planExported': True, 'planSha256': digest(value),
                      'preparationBlockers': value['preparationBlockers'],
                      'readyForApply': False, 'deviceWritesPerformed': False,
                      'networkRequestsPerformed': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
