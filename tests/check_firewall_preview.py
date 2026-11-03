"""Exercise the staged public preview CLI using synthetic images; no hardware."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool-root',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--source-revision',required=True)
    args=parser.parse_args()
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    import test_firewall_preview as fixture
    V=fixture.V
    root=args.output.absolute(); root.mkdir(mode=0o700,exist_ok=False)
    tool=args.tool_root.absolute()
    receipts=[]
    for operation in ('enable','restore'):
        case=root/operation; case.mkdir(); inputs=case/'inputs'; inputs.mkdir()
        raw_files={'gpt-prefix.bin':fixture.prefix(),'rootfsA.img':fixture.image(False),'rootfsB.img':fixture.image(True)}
        for name,raw in raw_files.items(): (inputs/name).write_bytes(raw)
        manifest=dict(schema='openjibo.firewall-preview-input.v1',operation=operation,diskSectors=4096,
                      gptPrefix=dict(sha256=sha(inputs/'gpt-prefix.bin'),sizeBytes=len(raw_files['gpt-prefix.bin'])),
                      images=[dict(partition=name,sha256=sha(inputs/(name+'.img')),sizeBytes=len(raw_files[name+'.img'])) for name in V.PARTITIONS])
        manifest_path=case/'manifest.json'; manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
        result=subprocess.run([sys.executable,'-I','-B',str(tool/'firewall_preview.py'),
                               '--manifest',str(manifest_path),'--manifest-sha256',sha(manifest_path),'--inputs',str(inputs),'--output',str(case/'result')],
                              cwd=root,capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
        summary=json.loads(result.stdout); assert summary['previewComplete'] and not summary['readyForApply']
        path=case/'result/preview.json'; preview=json.loads(path.read_bytes())
        assert preview['manifestSha256']==sha(manifest_path) and preview['manifestCanonicalSha256']==V.P.digest(manifest)
        assert preview['profileSha256']==V.F.KNOWN_PROFILE_SHA256
        for flag in ('readyForApply','executionSupported','deviceWritesPerformed','networkRequestsPerformed','deviceIdentityVerified',
                     'filesystemIntegrityVerified','releaseCompatibilityVerified','recoveryAssociationVerified','rollbackTested',
                     'modeJsonChanged','endpointOrCertificateChangesPlanned'):
            assert preview[flag] is False
        for key,name in [('preview','firewall_preview.py'),('ext4Parser','ext4_path.py'),('firewallProfileParser','firewall_patch.py'),('gptParser','gpt_layout.py')]:
            assert preview['codeSha256'][key]==sha(tool/name)
        assert sum(p['changeRequired'] for p in preview['partitions'])==1
        for partition in preview['partitions']:
            name=partition['partition']; source=raw_files[name+'.img']
            assert (inputs/(name+'.img')).read_bytes()==source
            expected=fixture.image(operation=='enable')
            if partition['changeRequired']:
                delta=partition['delta']; before=case/'result'/delta['beforeFile']; after=case/'result'/delta['afterFile']
                assert sha(before)==delta['beforeSha256'] and sha(after)==delta['afterSha256']
                start=delta['partitionRelativeStartSector']*512
                assert before.read_bytes()==source[start:start+delta['sectorCount']*512]
                assert source[:start]+after.read_bytes()+source[start+after.stat().st_size:]==expected
                assert delta['absoluteStartSector']==partition['partitionStartSector']+delta['partitionRelativeStartSector']
            else: assert partition['delta'] is None and source==expected
        receipts.append(dict(operation=operation,previewFile=path.relative_to(root).as_posix(),previewSha256=sha(path),
                             proposedChangedSectors=preview['proposedChangedSectors'],readyForApply=False))
    copied=root/'reviewed-source'; copied.mkdir()
    for name in ('firewall_preview.py','ext4_path.py','firewall_patch.py','gpt_layout.py'):
        shutil.copyfile(tool/name,copied/name)
    shutil.copyfile(tool/'profiles/S21firewall.v1',copied/'S21firewall.v1')
    files=[dict(file=path.relative_to(root).as_posix(),sha256=sha(path),sizeBytes=path.stat().st_size) for path in sorted(root.rglob('*')) if path.is_file()]
    proof=dict(sourceRevision=args.source_revision,scope='Synthetic images and staged public Python CLI only; no hardware',
               operations=receipts,files=files,inputsUnchanged=True,deviceWritesPerformed=False,readyForApply=False)
    (root/'proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    print('Staged firewall preview passed: enable/restore, mixed original/patched slots, exact bytes and no input mutation; synthetic only.')


if __name__=='__main__': main()
