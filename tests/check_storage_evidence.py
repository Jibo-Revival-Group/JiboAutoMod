"""Exercise the staged storage evidence CLI using synthetic bytes only."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_storage_evidence as fixture


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('tool-root', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--source-revision', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[0-9a-f]{40}', args.source_revision)
    tool = args.tool_root.resolve(); output = args.output.resolve()
    output.mkdir(mode=0o700, exist_ok=False)
    case = fixture.StorageEvidence()
    case.setUp()
    try:
        case.path.write_text(json.dumps(case.manifest), encoding='utf-8')
        retained = output / 'retained'
        shutil.copytree(case.inputs, retained)
        manifest = output / 'input.json'
        manifest.write_bytes(case.path.read_bytes())
        before = {p.name: sha(p.read_bytes()) for p in retained.iterdir()}
        command = [sys.executable, '-I', '-B', str(tool / 'storage_evidence.py'), '--manifest', str(manifest),
                   '--manifest-sha256', sha(manifest.read_bytes()), '--inputs', str(retained), '--output', str(output / 'result')]
        run = subprocess.run(command, cwd=output, capture_output=True, timeout=30)
        assert run.returncode == 0, run.stderr
        result = json.loads((output / 'result/evidence.json').read_bytes())
        assert result['evidenceComplete'] and result['retainedJetstreamBytesMatched'] and result['credentialRegionMatched']
        assert result['credentialsRegion'] == 'us'
        canonical = json.dumps(result, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
        assert json.loads(run.stdout)['evidenceSha256'] == sha(canonical)
        disk = (retained / 'full-storage.bin').read_bytes()
        for role in fixture.S.PATHS:
            record = result['files'][role]
            raw = b''.join(disk[item['fullStorageByteOffset']:item['fullStorageByteOffset']+item['allocatedSizeBytes']]
                           for item in record['extents'])[:record['fileSizeBytes']]
            assert sha(raw) == record['fileSha256']
            assert raw == (case.config if role == 'jetstream' else case.credentials)
        for flag in ('readyForApply', 'executionSupported', 'deviceIdentityVerified', 'installedReleaseVerified', 'mountMappingVerified',
                     'credentialsContentsExported', 'deviceWritesPerformed', 'networkRequestsPerformed'):
            assert result[flag] is False
        report = (output / 'result/evidence.json').read_bytes()
        assert not any(marker in report for marker in (b'CONFIG_PRIVATE_MARKER', b'CREDENTIAL_PRIVATE_MARKER', b'KEY_PRIVATE_MARKER'))
        value = json.loads(manifest.read_bytes()); value['credentialsRegion'] = 'eu'
        wrong = output / 'mismatch.json'; wrong.write_text(json.dumps(value), encoding='utf-8')
        denied = command[:]
        denied[denied.index('--manifest')+1] = str(wrong)
        denied[denied.index('--manifest-sha256')+1] = sha(wrong.read_bytes())
        denied[denied.index('--output')+1] = str(output / 'refused')
        refusal = subprocess.run(denied, cwd=output, capture_output=True, timeout=30)
        assert refusal.returncode == 2 and not (output / 'refused').exists()
        assert before == {p.name: sha(p.read_bytes()) for p in retained.iterdir()}
        sources = output / 'reviewed-source'; sources.mkdir()
        for name in ('storage_evidence.py', 'firewall_preview.py', 'firewall_patch.py', 'ext4_path.py', 'gpt_layout.py',
                     'endpoint_preview.py', 'capture_bundle.py', 'capture_adapter.py', 'capture_process.py',
                     'conversion_plan.py', 'recovery_evidence.py', 'pe_imports.py'):
            shutil.copyfile(tool / name, sources / name)
        for name in ('check_storage_evidence.py', 'test_storage_evidence.py', 'test_firewall_preview.py', 'test_ext4_path.py', 'test_gpt_audit.py'):
            shutil.copyfile(Path(__file__).parent / name, sources / name)
        (sources / 'profiles').mkdir()
        shutil.copyfile(tool / 'profiles/S21firewall.v1', sources / 'profiles/S21firewall.v1')
        shutil.copyfile(tool / 'Docs/storage-file-evidence.md', sources / 'storage-file-evidence.md')
        files = [dict(file=p.relative_to(output).as_posix(), sizeBytes=p.stat().st_size, sha256=sha(p.read_bytes()))
                 for p in sorted(output.rglob('*')) if p.is_file()]
        proof = dict(schema='openjibo.synthetic-storage-file-proof.v1', sourceRevision=args.source_revision,
                     syntheticOnly=True, fullStorageByteJoinsVerified=True, regionMismatchRefused=True,
                     inputsUnchanged=True, noSecretValuesExported=True, readyForApply=False, files=files)
        (output / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    finally:
        case.doCleanups()
    print('Staged storage file evidence passed: exact backup byte joins, credential region, redacted export and mismatch refusal; synthetic only.')


if __name__ == '__main__':
    main()
