"""Exercise staged read-only credential intake using synthetic backups only."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_oobe_intake as fixture


def sha(raw): return hashlib.sha256(raw).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('tool-root','output'): parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--source-revision',required=True)
    args=parser.parse_args(); assert re.fullmatch('[0-9a-f]{40}',args.source_revision)
    tool=args.tool_root.resolve(); output=args.output.resolve(); output.mkdir(mode=0o700,exist_ok=False)
    observed={}
    for name in ('parent-absent','leaf-absent','empty-file','empty-object','blank-fields','partial','populated','corrupt-directory'):
        case=fixture.OobeIntake(); case.setUp()
        try:
            if name in ('parent-absent','leaf-absent'): case.absent(parent=name=='parent-absent')
            elif name=='empty-file':
                raw=bytearray(case.case.images['credentials']); offset=3*1024+3*128
                struct.pack_into('<I',raw,offset+4,0); struct.pack_into('<H',raw,offset+42,0)
                raw[offset+52:offset+100]=b'\0'*48; case.image(raw)
            elif name=='corrupt-directory':
                raw=bytearray(case.case.images['credentials']); raw[11*1024+4:11*1024+6]=b'\0\0'; case.image(raw)
            else:
                value={'empty-object':{},'blank-fields':dict(accessKeyId='',secretAccessKey='',region=''),
                       'partial':dict(region='us'),
                       'populated':dict(accessKeyId='PRIVATE_ACCESS_MARKER',secretAccessKey='PRIVATE_SECRET_MARKER',region='us')}[name]
                case.credential(value)
            root=output/name; root.mkdir(); retained=root/'inputs'; retained.mkdir()
            disk=(case.inputs/'full-storage.bin').read_bytes(); (retained/'full-storage.bin').write_bytes(disk)
            manifest=root/'input.json'; manifest.write_text(json.dumps(case.manifest()),encoding='utf-8')
            command=[sys.executable,'-I','-B',str(tool/'oobe_intake.py'),'--manifest',str(manifest),
                     '--manifest-sha256',sha(manifest.read_bytes()),'--inputs',str(retained),'--output',str(root/'result')]
            run=subprocess.run(command,cwd=output,capture_output=True,timeout=30)
            if name=='corrupt-directory':
                assert run.returncode==2 and not (root/'result').exists()
                assert run.stdout==b'' and b'PRIVATE_' not in run.stderr
                observed[name]='refused'
                continue
            assert run.returncode==0,run.stderr
            result=json.loads((root/'result/intake.json').read_bytes())
            canonical=json.dumps(result,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')
            assert json.loads(run.stdout)['intakeSha256']==sha(canonical)
            assert result['intakeComplete'] and not result['syntheticDemo']
            for flag in ('factoryStateVerified','oobeStateVerified','physicalDeviceAssociationVerified','credentialValidityVerified',
                         'installedReleaseVerified','runtimeMountMappingVerified','recoveryAssociationVerified','filesystemIntegrityVerified',
                         'blockOwnershipVerified','rawCredentialFileExported','credentialSecretValuesExported','credentialsCreated',
                         'regionInferred','conversionPlanProduced','executionSupported','readyForApply','deviceWritesPerformed','networkRequestsPerformed'):
                assert result[flag] is False
            observation=result['credentialObservation']; observed[name]=observation
            expected={'parent-absent':'path-review-required','partial':'partial-provisioning-review',
                      'populated':'credentialed-evidence-review'}.get(name,'unprovisioned-evidence-review')
            assert observation['workflowHint']==expected
            assert observation['region']==('us' if name in ('partial','populated') else None)
            start=result['partition']['start_sector']*512
            for item in result['directoryEvidence']:
                raw=b''.join(disk[start+r['partitionByteOffset']:start+r['partitionByteOffset']+r['sizeBytes']] for r in item['ranges'])
                assert item['fullyScanned'] and len(raw)==item['sizeBytes'] and sha(raw)==item['sha256']
            item=result['file']
            if item['pathStatus']=='file-present':
                raw=b''.join(disk[r['fullStorageByteOffset']:r['fullStorageByteOffset']+r['sizeBytes']] for r in item['ranges'])[:item['sizeBytes']]
                assert len(raw)==item['sizeBytes'] and sha(raw)==item['sha256']
            for path in (root/'result').iterdir(): assert b'PRIVATE_' not in path.read_bytes()
            assert (retained/'full-storage.bin').read_bytes()==disk
        finally: case.doCleanups()
    sources=output/'reviewed-source'; sources.mkdir()
    for name in ('oobe_intake.py','storage_evidence.py','firewall_preview.py','firewall_patch.py','ext4_path.py','gpt_layout.py',
                 'endpoint_preview.py','capture_bundle.py','capture_adapter.py','capture_process.py','conversion_plan.py','recovery_evidence.py','pe_imports.py'):
        shutil.copyfile(tool/name,sources/name)
    for name in ('check_oobe_intake.py','test_oobe_intake.py','test_storage_evidence.py','test_firewall_preview.py','test_ext4_path.py','test_gpt_audit.py'):
        shutil.copyfile(Path(__file__).parent/name,sources/name)
    (sources/'profiles').mkdir(); shutil.copyfile(tool/'profiles/S21firewall.v1',sources/'profiles/S21firewall.v1')
    shutil.copyfile(tool/'Docs/oobe-storage-intake.md',sources/'oobe-storage-intake.md')
    files=[dict(file=p.relative_to(output).as_posix(),sizeBytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(output.rglob('*')) if p.is_file()]
    proof=dict(schema='openjibo.synthetic-oobe-intake-proof.v1',sourceRevision=args.source_revision,syntheticOnly=True,
               observations=observed,fullStorageByteJoinsVerified=True,corruptDirectoryRefused=True,inputsUnchanged=True,
               noSecretValuesExported=True,readyForApply=False,files=files)
    (output/'proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    print('Staged OOBE intake passed: seven typed observations, corrupt-directory refusal, backup byte joins and redacted output; synthetic only.')


if __name__=='__main__': main()
