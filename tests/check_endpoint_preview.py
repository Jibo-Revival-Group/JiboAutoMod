"""Exercise staged endpoint CLI with synthetic retained configs; no network/device."""
import argparse
import copy
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
    args=parser.parse_args(); tool=args.tool_root.absolute(); root=args.output.absolute(); root.mkdir(mode=0o700,exist_ok=False)
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    import test_endpoint_preview as fixture
    records=[]
    for name in ('managed-https','isolated-http','unchanged'):
        case=root/name; case.mkdir()
        config=fixture.config()
        target=dict(schema='openjibo.conversion-target.v1',mode='managed',providerId='example-provider',apiOrigin='https://api.example.test:8443')
        manifest=dict(schema='openjibo.endpoint-preview-input.v1',targetSha256='',jetstream={},credentialsRegion='api',hubOrigin='https://hub.example.test:9443',allowIsolatedHttp=False,certificatePolicy='preserve-existing')
        routes=dict(entrypoint_hostname='api.example.test',entrypoint_port=8443,hub_hostname='hub.example.test',hub_port=9443,hub_secure=True)
        if name=='isolated-http':
            target.update(mode='isolated',providerId='self-hosted',apiOrigin='http://192.168.50.20:9000')
            manifest.update(hubOrigin='http://192.168.50.21:9001',allowIsolatedHttp=True)
            routes=dict(entrypoint_hostname='192.168.50.20',entrypoint_port=9000,hub_hostname='192.168.50.21',hub_port=9001,hub_secure=False)
        if name=='unchanged':
            config['HubClient']['region-settings']['api']=dict(routes); config['HubClient']['override']=dict(routes)
        expected=copy.deepcopy(config); expected['HubClient']['region-settings']['api']=dict(routes); expected['HubClient']['override']=dict(routes)
        for filename,value in [('jetstream.json',config),('target.json',target)]: (case/filename).write_text(json.dumps(value,indent=2),encoding='utf-8')
        manifest['targetSha256']=sha(case/'target.json'); manifest['jetstream']=dict(sha256=sha(case/'jetstream.json'),sizeBytes=(case/'jetstream.json').stat().st_size)
        (case/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        original=(case/'jetstream.json').read_bytes()
        result=subprocess.run([sys.executable,'-I','-B',str(tool/'endpoint_preview.py'),
                               '--manifest',str(case/'manifest.json'),'--manifest-sha256',sha(case/'manifest.json'),
                               '--target',str(case/'target.json'),'--target-sha256',sha(case/'target.json'),
                               '--jetstream',str(case/'jetstream.json'),'--output',str(case/'result')],
                              cwd=root,capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
        assert str(root) not in result.stdout+result.stderr and 'PRIVATE_INPUT_FIXTURE' not in result.stdout+result.stderr
        summary=json.loads(result.stdout); preview=json.loads((case/'result/preview.json').read_bytes())
        assert summary['previewComplete'] and not summary['readyForApply'] and preview['previewComplete']
        assert preview['target']==target and preview['targetSha256']==sha(case/'target.json') and preview['manifestSha256']==sha(case/'manifest.json')
        assert preview['beforeSha256']==sha(case/'jetstream.json') and (case/'jetstream.json').read_bytes()==original
        for flag in ('completeConversionPlan','executionSupported','readyForApply','deviceWritesPerformed','networkRequestsPerformed','robotCompatibilityVerified',
                     'credentialsChanged','certificatesChanged','privateKeyFilesRead','certificateFilesRead','nativeLibraryChangesPlanned','notificationOrSsmChangesPlanned','dnsChangesPlanned','sectorChangesPlanned','providerOwnershipVerified'):
            assert preview[flag] is False
        assert preview['changeRequired']==(name!='unchanged')
        if preview['changeRequired']:
            assert (case/'result/jetstream.before.json').read_bytes()==original
            assert json.loads((case/'result/jetstream.after.json').read_bytes())==expected
            assert sha(case/'result/jetstream.after.json')==preview['afterSha256']
        else:
            assert preview['afterSha256']==preview['beforeSha256'] and preview['semanticChanges']==[]
            assert sorted(p.name for p in (case/'result').iterdir())==['preview.json']
        assert all(not entry['certificateChainVerified'] and not entry['trustStoreCompatibilityVerified'] and not entry['disableCertificateValidationPermitted'] for entry in preview['trustRequirements'])
        for key,filename in [('preview','endpoint_preview.py'),('preparation','conversion_plan.py'),('byteReader','capture_bundle.py'),('pathChecker','recovery_evidence.py')]:
            assert preview['codeSha256'][key]==sha(tool/filename)
        records.append(dict(case=name,previewFile=name+'/result/preview.json',previewSha256=sha(case/'result/preview.json'),changeRequired=preview['changeRequired'],readyForApply=False))
    copied=root/'reviewed-source'; copied.mkdir()
    for name in ('endpoint_preview.py','conversion_plan.py','capture_bundle.py','recovery_evidence.py','capture_adapter.py','capture_process.py','pe_imports.py'):
        shutil.copyfile(tool/name,copied/name)
    files=[dict(file=p.relative_to(root).as_posix(),sha256=sha(p),sizeBytes=p.stat().st_size) for p in sorted(root.rglob('*')) if p.is_file()]
    proof=dict(sourceRevision=args.source_revision,scope='Synthetic configs and staged Python CLI only; no network/device',cases=records,files=files,
               inputsUnchanged=True,networkRequestsPerformed=False,deviceWritesPerformed=False,readyForApply=False)
    (root/'proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    print('Staged endpoint preview passed: HTTPS, isolated HTTP and no-op; exact parsed values and immutable inputs; synthetic only.')


if __name__=='__main__': main()
