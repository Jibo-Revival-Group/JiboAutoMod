"""End-to-end adapter launch of the actual C host linked to USB/RCM stubs."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',required=True,type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('capture',root/'capture_adapter.py')
    adapter=importlib.util.module_from_spec(spec); spec.loader.exec_module(adapter)
    fixture=args.fixture.absolute()
    work=fixture/'adapter-integration'; work.mkdir(exist_ok=False)
    bundle=work/'bundle'; bundle.mkdir()
    system,arch=adapter.context()
    host_name='shofel2_t124_readonly.exe' if os.name=='nt' else 'shofel2_t124_readonly'
    source=fixture/('readonly-host-fixture.exe' if os.name=='nt' else 'readonly-host-fixture')
    shutil.copyfile(source,bundle/host_name)
    for name in ('emmc_server_readonly.bin','intermezzo.bin'):
        shutil.copyfile(fixture/'usb-fixture'/name,bundle/name)
    files=[]
    for role,name in [('host',host_name),('payload','emmc_server_readonly.bin'),('bootstrap','intermezzo.bin')]:
        data=(bundle/name).read_bytes()
        files.append(dict(role=role,name=name,sizeBytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    manifest=dict(schema='openjibo.readonly-capture-bundle.v1',sourceRevision=revision,os=system,architecture=arch,protocol=adapter.PROTOCOL,files=files)
    manifest_path=work/'manifest.json'; manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
    manifest_pin=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    receipts=[]
    for kind,count in [('primary-gpt-prefix',34),('ext-csd',1)]:
        plan=dict(schema='openjibo.readonly-capture-plan.v1',sourceRevision=revision,bundleSha256=manifest_pin,
                  kind=kind,startSector=0,sectorCount=count,timeoutSeconds=10)
        path=work/(kind+'-plan.json'); path.write_text(json.dumps(plan),encoding='utf-8')
        output=work/(kind+'-result')
        launched=subprocess.run([sys.executable,'-I','-B',str(root/'capture_adapter.py'),'capture',
            '--manifest',str(manifest_path),'--manifest-sha256',manifest_pin,'--plan',str(path),
            '--plan-sha256',hashlib.sha256(path.read_bytes()).hexdigest(),'--bundle',str(bundle),'--output',str(output)],
            capture_output=True,text=True,timeout=15)
        assert launched.returncode==0,launched.stderr
        assert json.loads(launched.stdout)['captureCompleted'] is True and str(work) not in launched.stdout
        receipt=json.loads((output/'receipt.json').read_bytes())
        assert receipt['captureCompleted'],receipt['outcome']
        assert len(receipt['processes'])==2 and all(p['cleanup']['checksPassed'] and p['cleanup']['parentReaped'] and p['cleanup']['drainsFinished'] for p in receipt['processes'])
        assert receipt['readyForApply'] is False and receipt['deviceIdentityVerified'] is False and receipt['resetVerified'] is False
        assert (output/'capture.bin').read_bytes()==b'\x5A'*(count*512)
        receipts.append(dict(kind=kind,receiptSha256=adapter.P.digest(receipt),captureCompleted=True,readyForApply=False))
    # Compile-time fixture variants cannot discover real USB and need no runtime
    # environment injection into the production adapter's restricted environment.
    # Full-area integration still uses the linked USB stub, never hardware.
    full_bundle=work/'full-bundle'; full_bundle.mkdir()
    full_host=fixture/('readonly-host-full.exe' if os.name=='nt' else 'readonly-host-full')
    shutil.copyfile(full_host,full_bundle/host_name)
    for name in ('emmc_server_readonly.bin','intermezzo.bin'): shutil.copyfile(bundle/name,full_bundle/name)
    full_manifest=json.loads(json.dumps(manifest))
    full_manifest['files'][0].update(sha256=hashlib.sha256(full_host.read_bytes()).hexdigest(),sizeBytes=full_host.stat().st_size)
    fm=work/'full-manifest.json';fm.write_text(json.dumps(full_manifest),encoding='utf-8');fh=hashlib.sha256(fm.read_bytes()).hexdigest()
    evidence=dict(schema='openjibo.storage-capacity.v1',sectorSizeBytes=512,storageSectorCount=4105,sizeBytes=4105*512,sourceHash='b'*64,sourceBytes=512,physicalIdentityVerified=False,captureAuthenticityVerified=False)
    full_plan=dict(schema='openjibo.readonly-full-storage-plan.v1',sourceRevision=revision,bundleSha256=fh,kind='full-user-area',startSector=0,sectorCount=4105,timeoutSeconds=60,capacityEvidence=evidence)
    fp=work/'full-plan.json';fp.write_text(json.dumps(full_plan),encoding='utf-8');fo=work/'full-result'
    launched=subprocess.run([sys.executable,'-I','-B',str(root/'capture_adapter.py'),'capture',
        '--manifest',str(fm),'--manifest-sha256',fh,'--plan',str(fp),
        '--plan-sha256',hashlib.sha256(fp.read_bytes()).hexdigest(),'--bundle',str(full_bundle),'--output',str(fo)],capture_output=True,text=True,timeout=80)
    assert launched.returncode==0,launched.stderr
    full_receipt=json.loads((fo/'receipt.json').read_bytes());assert full_receipt['captureCompleted'] and full_receipt['independentFinalRehash']
    assert (fo/'full-storage.bin').read_bytes()==b'\x5A'*(4105*512)
    receipts.append(dict(kind='full-user-area-synthetic',receiptSha256=adapter.P.digest(full_receipt),captureCompleted=True,readyForApply=False))
    for mode,code in (('handshake-command-failure','handshake-command-transfer-failed'),
                      ('handshake-reply-failure','handshake-reply-transfer-failed'),
                      ('init-failure','handshake-controller-uninitialized')):
        failure_bundle=work/(mode+'-bundle'); failure_bundle.mkdir()
        failure_host=fixture/('readonly-host-'+mode+('.exe' if os.name=='nt' else ''))
        shutil.copyfile(failure_host,failure_bundle/host_name)
        for name in ('emmc_server_readonly.bin','intermezzo.bin'):
            shutil.copyfile(bundle/name,failure_bundle/name)
        changed=json.loads(json.dumps(manifest))
        changed['files'][0].update(sha256=hashlib.sha256(failure_host.read_bytes()).hexdigest(),sizeBytes=failure_host.stat().st_size)
        mf=work/(mode+'-manifest.json'); mf.write_text(json.dumps(changed),encoding='utf-8')
        mp=hashlib.sha256(mf.read_bytes()).hexdigest()
        failed_plan=dict(schema='openjibo.readonly-capture-plan.v1',sourceRevision=revision,bundleSha256=mp,
                         kind='primary-gpt-prefix',startSector=0,sectorCount=34,timeoutSeconds=10)
        pf=work/(mode+'-plan.json'); pf.write_text(json.dumps(failed_plan),encoding='utf-8')
        output=work/(mode+'-result')
        launched=subprocess.run([sys.executable,'-I','-B',str(root/'capture_adapter.py'),'capture',
            '--manifest',str(mf),'--manifest-sha256',mp,'--plan',str(pf),
            '--plan-sha256',hashlib.sha256(pf.read_bytes()).hexdigest(),'--bundle',str(failure_bundle),'--output',str(output)],
            capture_output=True,text=True,timeout=15)
        assert launched.returncode==2,launched.stderr
        receipt=json.loads((output/'receipt.json').read_bytes()); cli=json.loads(launched.stdout)
        assert receipt['nativeDiagnosticCodes']==[code] and cli['nativeDiagnosticCodes']==[code]
        assert not receipt['captureCompleted'] and receipt['deviceStateUncertain']
        assert receipt['recovery']['normalBootCheckRequired'] and not receipt['recovery']['automaticRetryAllowed']
        assert not receipt['recovery']['normalBootVerified'] and not (output/'capture.bin').exists()
        assert (output/'work/capture.bin').stat().st_size==0
        assert 'USB_FIXTURE_OPEN' not in json.dumps(receipt)
        receipts.append(dict(kind=mode,receiptSha256=adapter.P.digest(receipt),captureCompleted=False,readyForApply=False))
    sources=work/'reviewed-source'; sources.mkdir()
    hashes=[]
    for name in ('capture_adapter.py','capture_process.py','recovery_evidence.py','conversion_plan.py','storage_capacity.py'):
        shutil.copyfile(root/name,sources/name)
        hashes.append(dict(file='reviewed-source/'+name,sha256=hashlib.sha256((sources/name).read_bytes()).hexdigest()))
    (work/'proof.json').write_text(json.dumps(dict(scope='Actual C host with link-time USB stubs; no hardware',receipts=receipts,files=hashes),indent=2)+'\n',encoding='utf-8')
    print('Bounded adapter native integration passed: prefix, EXT_CSD, synthetic full-area and three handshake failures, no hardware access.')


if __name__=='__main__': main()
