"""Exercise the staged review builder using synthetic retained backup/config data."""
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
    args=parser.parse_args(); tool=args.tool_root.absolute(); root=args.output.absolute(); root.mkdir(mode=0o700,exist_ok=False)
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    import test_conversion_review as fixture
    import test_conversion_review_storage as storage_fixture
    records=[]
    for name in ('managed-https','isolated-http','storage-managed-https','storage-isolated-http','request-managed-https','request-isolated-http'):
        request_mode=name.startswith('request-')
        with_storage=name.startswith(('storage-','request-'))
        case=root/name; case.mkdir(); inputs=case/'inputs'
        values=(storage_fixture.fixture if with_storage else fixture.fixture)(inputs,isolated=name.endswith('isolated-http'))
        manifest=case/'review-input.json'; pin=fixture.write_inputs(inputs,values,manifest)
        if request_mode: (inputs/'storage-input.json').unlink()
        before={p.name:sha(p) for p in inputs.iterdir()}
        command=([sys.executable,'-I','-B',str(tool/'review_request.py'),'--inputs',str(inputs),'--output',str(case/'result'),
                  '--jetstream-partition','services-test','--credentials-partition','var-test'] if request_mode else
                 [sys.executable,'-I','-B',str(tool/'conversion_review.py'),'--manifest',str(manifest),
                  '--manifest-sha256',pin,'--inputs',str(inputs),'--output',str(case/'result')])
        result=subprocess.run(command,
                              cwd=root,capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
        assert str(root) not in result.stdout+result.stderr and 'PRIVATE_INPUT_FIXTURE' not in result.stdout+result.stderr
        summary=json.loads(result.stdout); review=json.loads((case/'result/review.json').read_bytes())
        assert summary['reviewAssembled'] and not summary['completeConversionPlan'] and not summary['readyForApply']
        assert review['reviewAssembled'] and review['manifestSha256']==pin
        assert review['schema']=='openjibo.conversion-review-bundle.'+('v2' if with_storage else 'v1')
        assert review['inputPinOrigin']==('generated-from-supplied-files' if request_mode else 'externally-supplied-manifest-pin')
        assert before=={p.name:sha(p) for p in inputs.iterdir()}
        assert review['inventoryCanonicalSha256']==fixture.V.P.digest(values['inventory'])
        assert review['targetCanonicalSha256']==fixture.V.P.digest(values['target']) and review['target']==values['target']
        for flag in ('completeConversionPlan','executionSupported','readyForApply','endpointStoragePathAssociationVerified','credentialsRegionAssociationVerified',
                     'physicalDeviceAssociationVerified','releaseCompatibilityVerified','calibrationDeviceAssociationVerified','completeFilesystemIntegrityVerified','restoreTested',
                     'backupGptVerified','protectiveMbrVerified','deviceWritesPerformed','networkRequestsPerformed','credentialsChanged','certificatesChanged'):
            assert review[flag] is False
        assert review['inventoryAuditReferenceMatched'] and review['recoveryFilesMatchedInventory'] and review['endpointTargetReferenceMatched']
        assert review['storageFileEvidenceRecomputed'] is with_storage
        assert review['jetstreamBackupBytesMatched'] is with_storage and review['credentialRegionBackupBytesMatched'] is with_storage
        assert not review['mountMappingVerified']
        storage=(inputs/'full-storage.bin').read_bytes()
        assert [r['fullStorageByteOffset'] for r in review['storageByteRelationships']]==[0,64*512,192*512]
        for row in review['storageByteRelationships']:
            retained=(inputs/row['retainedFile']).read_bytes(); offset=row['fullStorageByteOffset']
            assert storage[offset:offset+len(retained)]==retained and row['sizeBytes']==len(retained)
            assert row['sha256']==sha(inputs/row['retainedFile']) and row['bytesMatched']
        for item in review['files']:
            path=case/'result'/item['file']; assert sha(path)==item['sha256'] and path.stat().st_size==item['sizeBytes']
        assert sorted(item['file'] for item in review['files'])==sorted(p.relative_to(case/'result').as_posix() for p in (case/'result').rglob('*') if p.is_file() and p.name!='review.json')
        page=(case/'result/review.html').read_text(encoding='utf-8')
        assert 'Apply unavailable' in page and 'PRIVATE_INPUT_FIXTURE' not in page and '<script' not in page
        assert ('Jetstream bytes and credential region in storage' if with_storage else 'Jetstream path and active region in storage') in page and 'Unverified' in page
        if with_storage:
            evidence=json.loads((case/'result/storage/evidence.json').read_bytes())
            assert fixture.V.P.digest(evidence)==review['storageEvidenceCanonicalSha256']
            assert evidence['manifestSha256']==review['inputFilePins']['storageInput']
            assert evidence['fullStorage']==values['storageInput']['fullStorage']
            assert evidence['credentialsRegion']==values['endpointInput']['credentialsRegion']=='api'
            assert review['storageFileSummary']==dict(credentialsRegion='api',files=evidence['files'])
            assert 'runtime mounts unverified' in page and 'storage/evidence.json' in page
            for item in evidence['files'].values():
                raw=b''.join(storage[span['fullStorageByteOffset']:span['fullStorageByteOffset']+span['allocatedSizeBytes']] for span in item['extents'])[:item['fileSizeBytes']]
                assert fixture.digest(raw)==item['fileSha256']
            for raw in (json.dumps(review),json.dumps(evidence),page):
                assert 'STORAGE_PRIVATE_KEY_FIXTURE' not in raw and 'PRIVATE_INPUT_FIXTURE' not in raw
            assert not any(evidence[key] for key in ('mountMappingVerified','deviceIdentityVerified','installedReleaseVerified','readyForApply'))
        recovery=json.loads((case/'result/recovery.json').read_bytes()); preparation=json.loads((case/'result/preparation.json').read_bytes())
        assert recovery['inventorySha256']==preparation['inventorySha256']==review['inventoryCanonicalSha256']
        assert recovery['fileBytesMatchedSuppliedInventory'] and not recovery['robotAssociationVerified'] and not recovery['restoreTested']
        for key,filename in [('builder','conversion_review.py'),('preparation','conversion_plan.py'),('recovery','recovery_evidence.py'),
                             ('firewall','firewall_preview.py'),('endpoint','endpoint_preview.py'),('gptAuditor','gpt_audit.py')]:
            assert review['codeSha256'][key]==sha(tool/filename)
        if with_storage: assert review['codeSha256']['storageEvidence']==sha(tool/'storage_evidence.py')
        if request_mode:
            assert review['codeSha256']['requestBuilder']==sha(tool/'review_request.py')
            assert sha(case/'result/request/review-input.json')==pin
            assert sha(case/'result/request/storage-input.json')==review['inputFilePins']['storageInput']
        records.append(dict(case=name,reviewFile=name+'/result/review.json',reviewSha256=sha(case/'result/review.json'),readyForApply=False))
    copied=root/'reviewed-source'; copied.mkdir()
    for name in ('conversion_review.py','conversion_plan.py','recovery_evidence.py','gpt_audit.py','gpt_layout.py','firewall_preview.py','firewall_patch.py','ext4_path.py',
                 'endpoint_preview.py','storage_evidence.py','review_request.py','capture_bundle.py','capture_adapter.py','capture_process.py','pe_imports.py'):
        shutil.copyfile(tool/name,copied/name)
    shutil.copyfile(tool/'profiles/S21firewall.v1',copied/'S21firewall.v1')
    files=[dict(file=p.relative_to(root).as_posix(),sha256=sha(p),sizeBytes=p.stat().st_size) for p in sorted(root.rglob('*')) if p.is_file()]
    proof=dict(sourceRevision=args.source_revision,scope='Synthetic retained backup/config fixtures and staged Python review CLI only; no hardware',
               cases=records,files=files,inputsUnchanged=True,networkRequestsPerformed=False,deviceWritesPerformed=False,readyForApply=False)
    (root/'proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    print('Staged conversion review passed: v1/v2 managed/isolated bundles, storage file and region joins, immutable inputs and false apply/association flags; synthetic only.')


if __name__=='__main__': main()
