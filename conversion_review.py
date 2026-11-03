#!/usr/bin/env python3
"""Recompute an offline conversion review bundle; never dispatch a device writer."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import stat
import time


def sibling(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


E=sibling('endpoint_preview')
F=sibling('firewall_preview')
G=sibling('gpt_audit')
S=sibling('storage_evidence')
B=E.B; P=B.P; R=B.A.R
INPUTS=dict(inventory='inventory.json',target='target.json',audit='audit.json',recoveryFiles='recovery-files.json',
            firewallInput='firewall-input.json',endpointInput='endpoint-input.json')
INPUTS_V2=dict(INPUTS,storageInput='storage-input.json')
RECOVERY=dict(calibration='calibration.bin',**{'full-storage':'full-storage.bin','affected-storage':'affected-storage.bin'})
MAX_STORAGE=64*1024**3


def require(value):
    if not value: raise ValueError('conversion_review_refused')


def sha(raw): return hashlib.sha256(raw).hexdigest()


def check_audit(supplied,actual):
    # The supplied record binds the inventory; current code recomputes the GPT
    # data checks. Neither the old record's issuer nor physical origin is trusted.
    require(type(supplied) is dict and supplied.get('schema')=='openjibo.primary-gpt-audit.v1')
    require(supplied.get('primaryGptChecksPassed') is True and supplied.get('prefixSha256')==actual['prefixSha256'])
    require(P.canonical(supplied.get('layout'))==P.canonical(actual['layout']) and supplied.get('geometryOrigin')=='operator-supplied-not-device-measured')
    for key in ('protectiveMbrVerified','backupGptVerified','deviceIdentityVerified','filesystemProfileVerified','readyForApply','deviceWritesPerformed','directNetworkRequestsPerformed'):
        require(supplied.get(key) is False)
    require(supplied.get('releaseFamily')=='unknown')


@contextmanager
def checked_storage(inventory,files,inputs,firewall,layout):
    expected={item['kind']:item for item in inventory['backups']}
    require('full-storage' in expected and 'calibration' in expected)
    require(expected['calibration']['sizeBytes']<=67108864 and all(item['sizeBytes']<=MAX_STORAGE for item in expected.values()))
    full=expected['full-storage']; require(full['sizeBytes']==firewall['diskSectors']*512 and full['sizeBytes']<=MAX_STORAGE)
    P.exact(files,('schema','files'),'recovery_map_fields')
    require(files['schema']=='openjibo.recovery-files.v1' and type(files['files']) is list)
    for item in files['files']:
        P.exact(item,('kind','path'),'recovery_map_entry')
        require(type(item['kind']) is str and item['kind'] in RECOVERY and item['path']==RECOVERY[item['kind']])
    path=R.ordinary_path(inputs/'full-storage.bin'); original=path.lstat()
    require(stat.S_ISREG(original.st_mode) and original.st_size==full['sizeBytes'])
    flags=os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)
    deadline=time.monotonic()+600
    with os.fdopen(os.open(str(path),flags),'rb') as stream:
        before=os.fstat(stream.fileno()); require(R.file_identity(before)==R.file_identity(original))
        recovery=R.check(inventory,files,inputs)
        require(R.identity(before)==R.identity(os.fstat(stream.fileno())) and time.monotonic()<deadline)
        spans=[('gpt-prefix.bin',0,firewall['gptPrefix']['sizeBytes'],firewall['gptPrefix']['sha256'])]
        selected={part['name']:part for part in layout['partitions'] if part['name'] in F.PARTITIONS}
        require(set(selected)==set(F.PARTITIONS))
        for name in F.PARTITIONS:
            item=next(i for i in firewall['images'] if i['partition']==name)
            part=selected[name]; require(item['sizeBytes']==part['size_sectors']*512)
            spans.append((name+'.img',part['start_sector']*512,item['sizeBytes'],item['sha256']))
        matched=[]
        for name,offset,size,expected_sha in spans:
            require(0<=offset and 0<size and offset+size<=full['sizeBytes'])
            stream.seek(offset); digest=hashlib.sha256(); remaining=size
            while remaining:
                require(time.monotonic()<deadline)
                raw=stream.read(min(1048576,remaining)); require(raw)
                digest.update(raw); remaining-=len(raw)
            require(digest.hexdigest()==expected_sha)
            matched.append(dict(retainedFile=name,fullStorageByteOffset=offset,sizeBytes=size,sha256=expected_sha,bytesMatched=True))
        read_count=0; read_bytes=0
        def read_at(offset,length):
            nonlocal read_count,read_bytes
            require(type(offset) is int and type(length) is int and 0<=offset and 0<length<=1048576 and offset+length<=full['sizeBytes'])
            read_count+=1; read_bytes+=length
            require(read_count<=8192 and read_bytes<=16777216 and time.monotonic()<deadline)
            stream.seek(offset); raw=stream.read(length); require(len(raw)==length); return raw
        yield recovery,matched,read_at
        require(R.identity(before)==R.identity(os.fstat(stream.fileno())))
    require(R.file_identity(before)==R.file_identity(R.ordinary_path(path).lstat()))


def render(review):
    esc=lambda value:html.escape(str(value),quote=True)
    rows=''.join('<tr><td>'+esc(name)+'</td><td>'+esc(status)+'</td></tr>' for name,status in review['coverage'].items())
    bindings=''.join('<tr><td>'+esc(row['retainedFile'])+'</td><td>'+esc(row['fullStorageByteOffset'])+'</td><td>'+esc(row['sizeBytes'])+'</td><td>Matched</td></tr>' for row in review['storageByteRelationships'])
    gates=['Confirm the backup, calibration data and installed release belong to the intended robot.',
           ('Verify runtime mount mapping and the installed release for the matched storage files.' if review.get('storageFileEvidenceRecomputed') else
            'Resolve the Jetstream file path and active credentials region from retained storage.'),
           'Complete filesystem, allocation, backup GPT and protective MBR checks.',
           'Plan native token, notification, SSM and DNS changes for the selected target.',
           'Verify effective API/Hub protocols, certificate chains and the robot trust store.',
           'Review the complete conversion and validate confirmed apply, readback and rollback.']
    if review['target']['mode']!='isolated': gates.append('Complete provider ownership, enrollment and issued-credential checks.')
    missing=''.join('<li>'+esc(item)+'</li>' for item in gates)
    records=[('preparation.json','Preparation'),('recovery.json','Retained recovery checks'),('gpt-audit.json','Recomputed GPT audit'),
             ('firewall/preview.json','Firewall sector preview'),('endpoint/preview.json','Endpoint file preview'),('review.json','Bundle record and file hashes')]
    if review.get('inputPinOrigin')=='generated-from-supplied-files':
        records.extend([('request/review-input.json','Generated review input pins'),('request/storage-input.json','Generated storage input')])
    storage_section=''
    if review.get('storageFileEvidenceRecomputed'):
        records.append(('storage/evidence.json','Recomputed storage file evidence'))
        evidence=review['storageFileSummary']
        file_rows=''.join('<tr><td>'+esc(item['partition'])+'</td><td>'+esc(item['partitionRootPath'])+'</td><td>'+esc(item['fileSha256'])+'</td></tr>'
                          for item in evidence['files'].values())
        storage_section=('<section><h2>Configuration and region in the backup</h2><p>Jetstream bytes and credential region matched: '+esc(evidence['credentialsRegion'])+
                         '. Runtime mount mapping and installed release remain unverified.</p><table><tr><th>Selected partition</th><th>Partition-root file</th><th>SHA-256</th></tr>'+file_rows+'</table></section>')
    links=''.join('<li><a href="'+filename+'">'+label+'</a></li>' for filename,label in records)
    target=review['target']
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
            '<title>Conversion review</title><style>body{font:16px system-ui,sans-serif;max-width:960px;margin:40px auto;padding:0 20px;color:#192333;background:#f7f9fc}'
            'h1,h2{line-height:1.2}section{background:white;padding:20px;margin:18px 0;border:1px solid #d9e1ed;border-radius:10px}'
            'table{border-collapse:collapse;width:100%;overflow-wrap:anywhere}th,td{text-align:left;padding:10px;border-bottom:1px solid #e3e8ef}'
            'a{color:#154ab0}li{margin:8px 0}.state{font-weight:700;color:#794500}</style><h1>Conversion review</h1>'
            '<p class="state">Review assembled · Apply unavailable</p><section><h2>Selected target</h2><p>'+esc(target['mode'])+' · '+esc(target['providerId'])+'</p>'
            '<p>API: '+esc(target['apiOrigin'])+'<br>Hub: '+esc(review['hubOrigin'])+'</p><p>Proposed firewall sectors: '+esc(review['proposedFirewallSectors'])+
            '<br>Jetstream file change: '+('Yes' if review['endpointChangeRequired'] else 'Already matches')+'</p></section>'
            '<section><h2>Coverage</h2><table><tr><th>Component</th><th>Result</th></tr>'+rows+'</table></section>'
            '<section><h2>Compared with the full-storage backup</h2><p>Byte consistency does not establish physical robot identity or restoration readiness.</p>'
            '<table><tr><th>Retained file</th><th>Backup byte offset</th><th>Bytes</th><th>Result</th></tr>'+bindings+'</table></section>'
            +storage_section+'<section><h2>Still required before apply</h2><ul>'+missing+'</ul></section><section><h2>Component records</h2><ul>'+links+'</ul></section></html>').encode('utf-8')


def build(manifest_path,manifest_pin,inputs,output,storage_input=None):
    manifest,_=E.read_json(manifest_path,manifest_pin)
    P.exact(manifest,('schema','files'),'review_input_fields')
    require(manifest['schema'] in ('openjibo.conversion-review-input.v1','openjibo.conversion-review-input.v2'))
    with_storage=manifest['schema']=='openjibo.conversion-review-input.v2'
    input_names=INPUTS_V2 if with_storage else INPUTS
    P.exact(manifest['files'],input_names,'review_pin_fields')
    require(storage_input is None or with_storage)
    inputs=R.ordinary_path(inputs); require(inputs.is_dir())
    values={name:E.read_json(storage_input if name=='storageInput' and storage_input is not None else inputs/filename,manifest['files'][name])[0]
            for name,filename in input_names.items()}
    return _assemble(manifest,manifest_pin,values,inputs,output)


def _assemble(manifest,manifest_pin,values,inputs,output,request_files=None):
    """Internal orchestration for pinned-file and generated-request entry points."""
    with_storage=manifest['schema']=='openjibo.conversion-review-input.v2'
    output=Path(output).absolute(); R.ordinary_path(output.parent); require(not output.exists())
    inventory=values['inventory']; target=values['target']; firewall=values['firewallInput']; endpoint=values['endpointInput']
    preparation=P.plan(inventory,target); F.validate(firewall)
    require(inventory['auditEvidenceSha256']==manifest['files']['audit'])
    require(endpoint.get('targetSha256')==manifest['files']['target'])
    storage_result=None
    if with_storage:
        storage=values['storageInput']; S.validate(storage)
        full=next((item for item in inventory['backups'] if item['kind']=='full-storage'),None)
        require(full is not None and storage['fullStorage']==dict(sha256=full['sha256'],sizeBytes=full['sizeBytes']))
        require(storage['diskSectors']==firewall['diskSectors'] and storage['gptPrefix']==firewall['gptPrefix'])
        require(storage['jetstream']==endpoint.get('jetstream') and storage['credentialsRegion']==endpoint.get('credentialsRegion'))
    actual_audit=G.audit_file(inputs/'gpt-prefix.bin',firewall['diskSectors'],firewall['gptPrefix']['sha256'])
    require((inputs/'gpt-prefix.bin').lstat().st_size==firewall['gptPrefix']['sizeBytes'])
    check_audit(values['audit'],actual_audit)
    with checked_storage(inventory,values['recoveryFiles'],inputs,firewall,actual_audit['layout']) as (recovery,bindings,read_at):
        if with_storage:
            storage_result=S.inspect_reader(storage,manifest['files']['storageInput'],B.read(inputs/'jetstream.json',P.LIMIT),read_at)
        B.new_directory(output)
        if request_files:
            require(set(request_files)=={'review-input.json','storage-input.json'})
            require(sha(request_files['review-input.json'])==manifest_pin and sha(request_files['storage-input.json'])==manifest['files']['storageInput'])
            B.new_directory(output/'request')
            for name,raw in request_files.items(): B.write(output/'request'/name,raw)
        if storage_result:
            B.new_directory(output/'storage'); P.export(storage_result,output/'storage/evidence.json')
        firewall_result=F.preview(inputs/INPUTS['firewallInput'],manifest['files']['firewallInput'],inputs,output/'firewall')
        endpoint_result=E.preview(inputs/INPUTS['endpointInput'],manifest['files']['endpointInput'],inputs/INPUTS['target'],manifest['files']['target'],inputs/'jetstream.json',output/'endpoint')
        require(firewall_result['layout']==actual_audit['layout'] and endpoint_result['targetCanonicalSha256']==preparation['targetSha256'])
        for filename,value in [('preparation.json',preparation),('recovery.json',recovery),('gpt-audit.json',actual_audit)]: P.export(value,output/filename)
    storage_gates=(storage_result['requiredBeforeApply'] if storage_result else ['jetstream-filesystem-path-and-credentials-region-to-backup-unverified'])
    blockers=list(dict.fromkeys(preparation['requiredBeforeApply']+preparation['preparationBlockers']+
                               firewall_result['requiredBeforeApply']+endpoint_result['requiredBeforeApply']+
                               storage_gates+['calibration-and-storage-acquisition-to-physical-device-unverified','backup-gpt-and-protective-mbr-unverified']))
    review=dict(schema='openjibo.conversion-review-bundle.v2' if with_storage else 'openjibo.conversion-review-bundle.v1',checkedAtUtc=datetime.now(timezone.utc).isoformat(),
                manifestSha256=manifest_pin,manifestCanonicalSha256=P.digest(manifest),inputFilePins=manifest['files'],
                inputPinOrigin='generated-from-supplied-files' if request_files else 'externally-supplied-manifest-pin',
                inventoryCanonicalSha256=P.digest(inventory),targetCanonicalSha256=P.digest(target),target=target,hubOrigin=endpoint['hubOrigin'],
                suppliedDeviceReferenceSha256=inventory['deviceFingerprintSha256'],suppliedReleaseFamily=inventory['releaseFamily'],
                inventoryAuditReferenceMatched=True,recoveryFilesMatchedInventory=True,storageByteRelationships=bindings,
                endpointTargetReferenceMatched=True,endpointStoragePathAssociationVerified=False,credentialsRegionAssociationVerified=False,
                storageFileEvidenceRecomputed=bool(storage_result),jetstreamBackupBytesMatched=bool(storage_result),credentialRegionBackupBytesMatched=bool(storage_result),
                mountMappingVerified=False,storageEvidenceCanonicalSha256=P.digest(storage_result) if storage_result else None,
                storageFileSummary=dict(credentialsRegion=storage_result['credentialsRegion'],files=storage_result['files']) if storage_result else None,
                physicalDeviceAssociationVerified=False,releaseCompatibilityVerified=False,calibrationDeviceAssociationVerified=False,
                completeFilesystemIntegrityVerified=False,restoreTested=False,backupGptVerified=False,protectiveMbrVerified=False,
                proposedFirewallSectors=firewall_result['proposedChangedSectors'],firewallOperation=firewall_result['operation'],endpointChangeRequired=endpoint_result['changeRequired'],
                coverage={'Preparation':'Supplied fields complete' if preparation['suppliedPreparationFieldsComplete'] else 'Supplied fields incomplete',
                          'Recovery':'File bytes match supplied inventory','Primary GPT':'Recomputed prefix checks passed',
                          'Firewall':'Dual-slot sector preview produced','Endpoints':'Jetstream file preview produced',
                          ('Jetstream bytes and credential region in storage' if storage_result else 'Jetstream path and active region in storage'):
                              'Config bytes and region matched; runtime mounts unverified' if storage_result else 'Unverified','Physical robot and installed release':'Unverified',
                          'Native token / notification / SSM routing':'Not planned','DNS and effective API/Hub TLS':'Unverified',
                          'Filesystem allocation, apply and rollback':'Unverified'},
                reviewAssembled=True,completeConversionPlan=False,executionSupported=False,readyForApply=False,
                deviceWritesPerformed=False,networkRequestsPerformed=False,credentialsChanged=False,certificatesChanged=False,
                inputTrust='operator-pinned-not-provenance-or-device-authenticated',requiredBeforeApply=blockers,
                codeSha256=dict(builder=sha(Path(__file__).read_bytes()),preparation=sha(Path(P.__file__).read_bytes()),
                    recovery=sha(Path(R.__file__).read_bytes()),firewall=sha(Path(F.__file__).read_bytes()),endpoint=sha(Path(E.__file__).read_bytes()),gptAuditor=sha(Path(G.__file__).read_bytes())))
    if storage_result: review['codeSha256']['storageEvidence']=sha(Path(S.__file__).read_bytes())
    if request_files: review['codeSha256']['requestBuilder']=sha(Path(__file__).with_name('review_request.py').read_bytes())
    B.write(output/'review.html',render(review))
    review['files']=[dict(file=path.relative_to(output).as_posix(),sizeBytes=path.stat().st_size,sha256=sha(B.read(path))) for path in sorted(output.rglob('*')) if path.is_file()]
    require(len(review['files'])<=32 and len(P.canonical(review))<P.LIMIT)
    P.export(review,output/'review.json'); return review


def main():
    class Parser(argparse.ArgumentParser):
        def error(self,message): self.exit(2,'Conversion review refused; check required arguments. See Docs/conversion-review-bundle.md.\n')
    parser=Parser(description=__doc__)
    for name in ('manifest','inputs','output'): parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--manifest-sha256',required=True)
    parser.add_argument('--storage-input',type=Path,help='Optional v2 storage manifest location; its pinned bytes are still required.')
    args=parser.parse_args()
    try: result=build(args.manifest,args.manifest_sha256,args.inputs,args.output,args.storage_input)
    except (ValueError,OSError,UnicodeError,KeyError,TypeError,F.E.Ext4PathError,S.F.E.Ext4PathError,F.F.FirewallPatchError,F.A.CaptureFailure,B.A.CaptureFailure,RecursionError):
        parser.exit(2,'Conversion review refused; check pinned inputs, shared backup bytes, supported profiles and new output.\n')
    print(json.dumps(dict(reviewAssembled=True,reviewSha256=P.digest(result),completeConversionPlan=False,readyForApply=False)))


if __name__=='__main__': main()
