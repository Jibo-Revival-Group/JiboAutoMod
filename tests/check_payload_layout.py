"""Verify a cross-built payload's raw image includes zero-initialized storage."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def validate(elf, binary, sections):
    if not elf.startswith(b'\x7fELF\x01\x01') or elf[18:20] != b'\x28\x00':
        raise ValueError('Expected little-endian ARM ELF32')
    if not 4 <= len(binary) <= 131072:
        raise ValueError('Payload size refused')
    allocated = [s for s in sections if 'A' in s['flags']]
    by_name = {s['name']: s for s in allocated}
    if len(by_name) != len(allocated) or not {'.init', '.bss', '.footer'} <= set(by_name):
        raise ValueError('Required unique allocated sections missing')
    base = by_name['.init']['address']
    if base != 0x4000E000:
        raise ValueError('Unexpected entry base')
    covered = bytearray(len(binary))
    for section in allocated:
        offset = section['address'] - base
        size = section['size']
        if offset < 0 or size < 0 or offset + size > len(binary):
            raise ValueError('Allocated section outside raw image')
        if any(covered[offset:offset+size]):
            raise ValueError('Overlapping allocated sections')
        covered[offset:offset+size] = b'\x01' * size
        raw = binary[offset:offset+size]
        if section['type'] == 'NOBITS':
            if any(raw):
                raise ValueError('Nonzero initialization storage')
        elif section['type'] == 'PROGBITS':
            start = section['offset']
            if start + size > len(elf) or raw != elf[start:start+size]:
                raise ValueError('Raw image differs from allocated ELF bytes')
        else:
            raise ValueError('Unsupported allocated section type')
    if any(value for index, value in enumerate(binary) if not covered[index]):
        raise ValueError('Nonzero image padding')
    bss = by_name['.bss']; footer = by_name['.footer']
    if bss['type'] != 'NOBITS' or not bss['size']:
        raise ValueError('BSS initialization region missing')
    if (footer['type'] != 'PROGBITS' or footer['size'] != 4 or
            footer['address'] - base != len(binary)-4 or
            bss['address'] + bss['size'] > footer['address'] or
            binary[-4:] != b'\xef\xbe\xad\xde'):
        raise ValueError('Initialization footer missing or misplaced')
    return dict(base=base, binaryBytes=len(binary), bssOffset=bss['address']-base,
                bssBytes=bss['size'], bssZeroInBinary=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', required=True, type=Path)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--readelf', default='arm-none-eabi-readelf')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--source-revision', required=True)
    args = parser.parse_args()
    env = dict(os.environ, LC_ALL='C')
    report = subprocess.run([args.readelf, '-SW', str(args.elf)], env=env,
                            capture_output=True, text=True, timeout=10, check=True).stdout
    if len(report) > 65536:
        raise ValueError('Section report too large')
    pattern = r'^\s*\[\s*\d+\]\s+(\S+)\s+(\S+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+[0-9a-fA-F]+\s+([A-Z]*)\s+\d+\s+\d+\s+\d+\s*$'
    sections = [dict(name=m[1], type=m[2], address=int(m[3],16),
                     offset=int(m[4],16), size=int(m[5],16), flags=m[6])
                for m in re.finditer(pattern, report, re.M)]
    elf = args.elf.read_bytes(); binary = args.binary.read_bytes()
    result = validate(elf, binary, sections)
    corrupt = bytearray(binary); corrupt[result['bssOffset']] = 1
    cases = [('nonzero-bss', bytes(corrupt)), ('missing-footer', binary[:-4]),
             ('truncated-bss', binary[:result['bssOffset']]),
             ('different-code', bytes([binary[0] ^ 1])+binary[1:])]
    for name, changed in cases:
        try:
            validate(elf, changed, sections)
        except ValueError:
            continue
        raise AssertionError('Accepted corrupted image: '+name)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, data in [('payload.elf', elf), ('payload.bin', binary),
                       ('sections.txt', report.encode())]:
        (args.output/name).write_bytes(data)
    result.update(sourceRevision=args.source_revision, hardwareAccess=False,
                  corruptionRefusals=[name for name, _ in cases],
                  elfSha256=hashlib.sha256(elf).hexdigest(),
                  binarySha256=hashlib.sha256(binary).hexdigest())
    (args.output/'proof.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print('Payload layout passed: allocated bytes match, BSS zero-filled, four corruptions refused; no hardware.')


if __name__ == '__main__':
    main()
