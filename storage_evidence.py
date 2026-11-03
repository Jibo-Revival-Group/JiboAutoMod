#!/usr/bin/env python3
"""Check Jetstream bytes and credential region inside a pinned offline backup."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

import importlib.util


def sibling(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


F = sibling('firewall_preview')
E = sibling('endpoint_preview')
B = E.B
P = B.P
PATHS = {'jetstream': '/etc/jibo-jetstream-service.json', 'credentials': '/jibo/credentials.json'}
RUNTIME_PATHS = {'jetstream': '/usr/local/etc/jibo-jetstream-service.json', 'credentials': '/var/jibo/credentials.json'}
MAX_STORAGE = 64 * 1024**3


def require(value):
    if not value:
        raise ValueError('storage_evidence_refused')


def parse(raw):
    require(0 < len(raw) <= P.LIMIT)
    def integer(text):
        require(len(text) <= 20)
        return int(text)
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=P.no_duplicates,
                       parse_int=integer, parse_constant=lambda _: require(False))
    E.bounded_tree(value)
    require(type(value) is dict)
    return value


class FileReader(F.PreviewReader):
    """Reuse the narrow clean, flat-extent profile without broadening admission."""
    def file(self, path):
        current = self.inode(2)
        seen = {current.number}
        ranges = []
        for part in path.strip('/').split('/'):
            require(current.mode & 0xf000 == 0x4000)
            require(current.size % self.block_size == 0)
            ranges.extend(self.extent_ranges(current))
            matches = [number for name, number in self.directory_entries(current) if name == part]
            require(len(matches) == 1 and matches[0] not in seen)
            current = self.inode(matches[0])
            seen.add(current.number)
        require(current.mode & 0xf000 == 0x8000 and current.size <= P.LIMIT)
        file_ranges = self.extent_ranges(current)
        ranges.extend(file_ranges)
        ordered = sorted(ranges)
        require(all(a[1] <= b[0] for a, b in zip(ordered, ordered[1:])))
        require(all(end <= mstart or start >= mend for start, end in ranges for mstart, mend in self.metadata))
        return current, file_ranges


def validate(value):
    P.exact(value, ('schema', 'diskSectors', 'fullStorage', 'gptPrefix', 'partitions', 'jetstream', 'credentialsRegion'), 'storage_manifest_fields')
    require(value['schema'] == 'openjibo.storage-file-input.v1')
    require(type(value['diskSectors']) is int and 68 <= value['diskSectors'] <= MAX_STORAGE // 512)
    for name, limit in [('fullStorage', MAX_STORAGE), ('gptPrefix', F.G.MAX_PREFIX_BYTES), ('jetstream', P.LIMIT)]:
        item = value[name]
        P.exact(item, ('sha256', 'sizeBytes'), 'storage_pin_fields')
        require(type(item['sha256']) is str and P.HASH.fullmatch(item['sha256']))
        require(type(item['sizeBytes']) is int and 0 < item['sizeBytes'] <= limit)
    require(value['fullStorage']['sizeBytes'] == value['diskSectors'] * 512)
    require(1024 <= value['gptPrefix']['sizeBytes'] <= value['fullStorage']['sizeBytes'])
    require(value['gptPrefix']['sizeBytes'] % 512 == 0)
    P.exact(value['partitions'], PATHS, 'storage_roles')
    for name in value['partitions'].values():
        require(type(name) is str and re.fullmatch(r'[A-Za-z0-9_.-]{1,36}', name))
    require(len(set(value['partitions'].values())) == 2)
    require(type(value['credentialsRegion']) is str and re.fullmatch('[a-z][a-z0-9-]{0,31}', value['credentialsRegion']))


def inspect(manifest_path, manifest_pin, inputs, output):
    value, _ = E.read_json(manifest_path, manifest_pin)
    validate(value)
    inputs = B.A.R.ordinary_path(inputs)
    require(inputs.is_dir())
    output = Path(output).absolute()
    B.A.R.ordinary_path(output.parent)
    require(not output.exists())
    retained = B.read(inputs / 'jetstream.json', P.LIMIT)
    require(len(retained) == value['jetstream']['sizeBytes'] and F.sha(retained) == value['jetstream']['sha256'])
    # Parse before opening the large storage file; JSON/region validation is repeated
    # against the bytes read through the pinned backup descriptor below.
    parse(retained)
    deadline = time.monotonic() + 600
    results = {}
    with F.retained_image(inputs / 'full-storage.bin', value['fullStorage'], deadline) as read_at:
        prefix = b''.join(read_at(offset, min(1048576, value['gptPrefix']['sizeBytes'] - offset))
                          for offset in range(0, value['gptPrefix']['sizeBytes'], 1048576))
        require(F.sha(prefix) == value['gptPrefix']['sha256'])
        layout = F.G.audit_primary_gpt(prefix, value['diskSectors'])
        for role, path in PATHS.items():
            matches = [part for part in layout['partitions'] if part['name'] == value['partitions'][role]]
            require(len(matches) == 1)
            part = matches[0]
            start, size = part['start_sector'] * 512, part['size_sectors'] * 512
            require(2048 <= size <= F.MAX_IMAGE)
            def partition_read(offset, length):
                require(type(offset) is int and type(length) is int and 0 <= offset and 0 < length and offset + length <= size)
                return read_at(start + offset, length)
            reader = FileReader(partition_read, size)
            inode, ranges = reader.file(path)
            raw = reader.read_file(inode, P.LIMIT)
            parsed = parse(raw)
            if role == 'jetstream':
                require(raw == retained)
                client = parsed.get('HubClient')
                require(type(client) is dict and type(client.get('region-settings')) is dict)
                require(value['credentialsRegion'] in client['region-settings'])
                E.routing_entry(client['region-settings'][value['credentialsRegion']])
                if 'override' in client:
                    E.routing_entry(client['override'])
            else:
                require(type(parsed.get('region')) is str and parsed['region'] == value['credentialsRegion'])
            results[role] = dict(partition=part['name'], partitionStartSector=part['start_sector'],
                                 partitionSizeSectors=part['size_sectors'], partitionRootPath=path,
                                 assumedRuntimePath=RUNTIME_PATHS[role], inode=inode.number,
                                 filesystemUuid=reader.filesystem_uuid, fileSizeBytes=len(raw), fileSha256=F.sha(raw),
                                 extents=[dict(partitionByteOffset=a, fullStorageByteOffset=start + a, allocatedSizeBytes=b - a)
                                          for a, b in ranges])
    result = dict(schema='openjibo.storage-file-evidence.v1', checkedAtUtc=datetime.now(timezone.utc).isoformat(),
                  manifestSha256=manifest_pin, manifestCanonicalSha256=P.digest(value),
                  fullStorage=value['fullStorage'], gptPrefix=value['gptPrefix'], files=results,
                  credentialsRegion=value['credentialsRegion'], retainedJetstreamBytesMatched=True,
                  credentialRegionMatched=True, evidenceComplete=True,
                  partitionSelection='operator-supplied-exact-gpt-names', runtimePaths='documented-assumptions-not-verified-mounts',
                  mountMappingVerified=False, installedReleaseVerified=False, deviceIdentityVerified=False,
                  filesystemIntegrityVerified=False, blockAllocationOwnershipVerified=False,
                  backupGptVerified=False, protectiveMbrVerified=False, recoveryAssociationVerified=False,
                  credentialsContentsExported=False, separatePrivateKeyFilesRead=False, credentialsChanged=False,
                  executionSupported=False, readyForApply=False, deviceWritesPerformed=False, networkRequestsPerformed=False,
                  inputTrust='operator-pinned-not-provenance-or-device-authenticated',
                  requiredBeforeApply=['verified-mount-mapping-and-installed-release', 'physical-device-and-recovery-association',
                                       'filesystem-integrity-and-block-ownership-checks', 'complete-conversion-review',
                                       'robot-runtime-network-tls-and-provider-acceptance', 'bounded-apply-readback-and-rollback'],
                  codeSha256={name: F.sha(Path(module.__file__).read_bytes()) for name, module in
                              [('filesystemProfile', F), ('ext4Parser', F.E), ('gptParser', F.G),
                               ('endpointParser', E), ('byteReader', B), ('preparation', P), ('pathChecker', B.A.R)]})
    result['codeSha256']['storageEvidence'] = F.sha(Path(__file__).read_bytes())
    output = B.new_directory(output)
    B.write(output / 'evidence.json', P.canonical(result) + b'\n')
    return result


def main():
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            self.exit(2, 'Storage evidence refused; check required arguments. See Docs/storage-file-evidence.md.\n')
    parser = Parser(description=__doc__)
    for name in ('manifest', 'inputs', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    try:
        result = inspect(args.manifest, args.manifest_sha256, args.inputs, args.output)
    except (ValueError, OSError, UnicodeError, KeyError, TypeError, B.A.CaptureFailure, F.E.Ext4PathError, RecursionError):
        parser.exit(2, 'Storage evidence refused; check pinned files and supported profile. No complete evidence was exported.\n')
    print(json.dumps(dict(evidenceComplete=True, evidenceSha256=P.digest(result), readyForApply=False), sort_keys=True))


if __name__ == '__main__':
    main()
