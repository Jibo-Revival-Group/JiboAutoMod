"""Build, extract and run the portable release as a user would, without a browser."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile


def sha(raw): return hashlib.sha256(raw).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--source-revision',required=True)
    args=parser.parse_args(); source=args.source.resolve(); root=args.output.resolve()
    root.mkdir(mode=0o700,exist_ok=False)
    command=[sys.executable,'-I','-B',str(source/'tools/package_offline_review.py'),'--source',str(source),
             '--source-revision',args.source_revision,'--output',str(root/'release')]
    built=subprocess.run(command,cwd=root,capture_output=True,timeout=60)
    assert built.returncode==0,built.stderr
    summary=json.loads(built.stdout)
    second=command[:]; second[-1]=str(root/'repeat')
    repeat=subprocess.run(second,cwd=root,capture_output=True,timeout=60)
    assert repeat.returncode==0,repeat.stderr
    archive=root/'release/OpenJibo-Offline-Review.zip'
    raw=archive.read_bytes()
    assert raw==(root/'repeat/OpenJibo-Offline-Review.zip').read_bytes()
    assert sha(raw)==summary['sha256']==(root/'release/OpenJibo-Offline-Review.zip.sha256').read_text().split()[0]
    extracted=root/'extracted package'; extracted.mkdir()
    with zipfile.ZipFile(archive) as bundle:
        entries=bundle.infolist()
        assert len(entries)<=100 and sum(i.file_size for i in entries)<=16777216
        for item in entries:
            name=PurePosixPath(item.filename)
            assert not name.is_absolute() and '..' not in name.parts and '\\' not in item.filename and ':' not in item.filename
            path=extracted.joinpath(*name.parts); path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as stream: stream.write(bundle.read(item))
    manifest=json.loads((extracted/'release-manifest.json').read_bytes())
    assert manifest['sourceRevision']==args.source_revision and manifest['syntheticDemo'] and not manifest['readyForApply']
    assert not manifest['hardwareCompatibilityVerified'] and not manifest['completeConversionPlan']
    names={item['file'] for item in manifest['files']}
    assert names|{'release-manifest.json','SHA256SUMS'}=={p.relative_to(extracted).as_posix() for p in extracted.rglob('*') if p.is_file()}
    assert not any(name.startswith(('Exploits/','tests/','tools/','config.py','JiboModTool.py')) or name.endswith(('.exe','.dll','.dylib','.so','.bin')) and not name.startswith('demo/') for name in names)
    for item in manifest['files']:
        content=(extracted/item['file']).read_bytes()
        assert len(content)==item['sizeBytes'] and sha(content)==item['sha256']
        if item['file'].endswith('.py'):
            assert content==(source/item['file']).read_bytes().replace(b'\r\n',b'\n')
    sums={line.split('  ',1)[1]:line.split('  ',1)[0] for line in (extracted/'SHA256SUMS').read_text().splitlines()}
    assert set(sums)==names|{'release-manifest.json'}
    for name,digest in sums.items(): assert sha((extracted/name).read_bytes())==digest
    before={name:sha((extracted/name).read_bytes()) for name in names}
    run=subprocess.run([sys.executable,'-I','-B',str(extracted/'demo_review.py'),'--output',str(root/'demo-result')],
                       cwd=root,capture_output=True,timeout=60)
    assert run.returncode==0,run.stderr
    review=json.loads((root/'demo-result/review.json').read_bytes())
    assert review['schema']=='openjibo.conversion-review-bundle.v3' and review['storageFileEvidenceRecomputed']
    assert review['gptRecoveryEvidenceRecomputed'] and review['backupGptVerified'] and review['protectiveMbrVerified']
    recovery=json.loads((root/'demo-result/gpt-recovery.json').read_bytes())
    assert recovery['entryArraysEqual'] and recovery['verificationScope']=='retained-backup-bytes'
    assert recovery['fullStorage']['sha256']==sha((extracted/'demo/retained/full-storage.bin').read_bytes())
    audit_path=root/'standalone-gpt-recovery.json'
    disk=extracted/'demo/retained/full-storage.bin'
    audit_args=[sys.executable,'-I','-B',str(extracted/'gpt_recovery.py'),'--full-storage',str(disk),
                '--disk-sectors','4096','--expected-sha256',sha(disk.read_bytes()),'--output',str(audit_path)]
    audited=subprocess.run(audit_args,cwd=root,capture_output=True,timeout=30)
    assert audited.returncode==0,audited.stderr
    standalone=json.loads(audit_path.read_bytes())
    for key in ('fullStorage','entryArraysSha256','primaryHeaderSha256','backupHeaderSha256','protectiveMbrSha256'):
        assert standalone[key]==recovery[key]
    assert standalone['backupGptVerified'] and standalone['protectiveMbrVerified'] and not standalone['readyForApply']
    hybrid=bytearray(disk.read_bytes()); hybrid[462]=1
    hybrid_path=root/'synthetic-hybrid.bin'; hybrid_path.write_bytes(hybrid)
    bad_args=audit_args[:]; bad_args[bad_args.index('--full-storage')+1]=str(hybrid_path)
    bad_args[bad_args.index('--expected-sha256')+1]=sha(hybrid)
    refused_path=root/'refused-gpt-recovery.json'; bad_args[-1]=str(refused_path)
    refused=subprocess.run(bad_args,cwd=root,capture_output=True,timeout=30)
    assert refused.returncode==2 and not refused_path.exists()
    assert review['inputPinOrigin']=='generated-from-supplied-files' and not review['readyForApply'] and not review['physicalDeviceAssociationVerified']
    assert json.loads(run.stdout)['syntheticDemo']
    for item in review['files']:
        assert sha((root/'demo-result'/item['file']).read_bytes())==item['sha256']
    env=os.environ.copy(); env['PATH']=str(Path(sys.executable).parent)+os.pathsep+env.get('PATH','')
    launcher=([os.environ.get('COMSPEC','cmd.exe'),'/d','/c','call',str(extracted/'Run-Demo.cmd')] if os.name=='nt' else ['sh',str(extracted/'run-demo.sh')])
    launched=subprocess.run(launcher+['--no-open','--output',str(root/'launcher-result')],cwd=root,env=env,capture_output=True,timeout=60)
    assert launched.returncode==0,launched.stderr
    assert (root/'launcher-result/review.json').is_file()
    intake_run=subprocess.run([sys.executable,'-I','-B',str(extracted/'demo_review.py'),'--oobe-intake','--output',str(root/'intake-result')],
                              cwd=root,capture_output=True,timeout=60)
    assert intake_run.returncode==0,intake_run.stderr
    intake=json.loads((root/'intake-result/intake.json').read_bytes())
    assert intake['syntheticDemo'] and intake['intakeComplete'] and not intake['oobeStateVerified'] and not intake['readyForApply']
    assert intake['credentialObservation']['kind']=='identity-fields-absent-or-blank' and intake['credentialObservation']['region'] is None
    assert set(intake['credentialObservation']['fields'].values())=={'blank'}
    assert b'Synthetic demo' in (root/'intake-result/intake.html').read_bytes()
    assert before=={name:sha((extracted/name).read_bytes()) for name in names}
    for script in ('review_request.py','conversion_review.py','storage_evidence.py','oobe_intake.py','gpt_recovery.py','capture_adapter.py','demo_review.py'):
        help_run=subprocess.run([sys.executable,'-I','-B',str(extracted/script),'--help'],cwd=root,capture_output=True,timeout=10)
        assert help_run.returncode==0,help_run.stderr
    proof=dict(schema='openjibo.offline-review-release-check.v1',sourceRevision=args.source_revision,archiveSha256=sha(raw),
               builderSourceSha256=sha((source/'tools/package_offline_review.py').read_bytes().replace(b'\r\n',b'\n')),
               checkSourceSha256=sha(Path(__file__).read_bytes().replace(b'\r\n',b'\n')),
               repeatedBuildIdentical=True,allPayloadHashesVerified=True,extractedDemoPassed=True,hostLauncherPassed=True,
               inputsUnchanged=True,syntheticOobeIntakePassed=True,syntheticGptRecoveryPassed=True,
               standaloneGptRecoveryPassed=True,hybridMbrRefused=True,syntheticOnly=True,readyForApply=False)
    (root/'release-check.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    print('Portable offline release passed: repeatable archive, all hashes, extracted demo and host launcher; synthetic only.')


if __name__=='__main__': main()
