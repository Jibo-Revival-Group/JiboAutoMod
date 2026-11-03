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
        assert receipt['readyForApply'] is False and receipt['deviceIdentityVerified'] is False and receipt['resetVerified'] is False
        assert (output/'capture.bin').read_bytes()==b'\x5A'*(count*512)
        receipts.append(dict(kind=kind,receiptSha256=adapter.P.digest(receipt),captureCompleted=True,readyForApply=False))
    sources=work/'reviewed-source'; sources.mkdir()
    hashes=[]
    for name in ('capture_adapter.py','capture_process.py','recovery_evidence.py','conversion_plan.py'):
        shutil.copyfile(root/name,sources/name)
        hashes.append(dict(file='reviewed-source/'+name,sha256=hashlib.sha256((sources/name).read_bytes()).hexdigest()))
    (work/'proof.json').write_text(json.dumps(dict(scope='Actual C host with link-time USB stubs; no hardware',receipts=receipts,files=hashes),indent=2)+'\n',encoding='utf-8')
    print('Bounded adapter native integration passed: primary prefix and EXT_CSD, no hardware access.')


if __name__=='__main__': main()
