#!/usr/bin/env python3
"""Join a pinned completed capture receipt to a retained primary GPT audit, offline."""
import argparse
import importlib.util
import json
from pathlib import Path


def sibling(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


A=sibling('capture_adapter')
G=sibling('gpt_audit')


def audit(receipt_path, receipt_pin, manifest_path, manifest_pin, plan_path, plan_pin, total_sectors):
    # Checking retained captures is portable; admission validates the original host
    # profile through the manifest rather than requiring that OS on the auditor.
    receipt=A.pinned_json(receipt_path,receipt_pin)
    manifest=A.pinned_json(manifest_path,manifest_pin)
    plan=A.pinned_json(plan_path,plan_pin)
    A.validate_profile(manifest,plan,manifest_pin,plan_pin,manifest.get('os'),manifest.get('architecture'))
    A.require(receipt.get('schema')=='openjibo.readonly-capture-receipt.v1')
    A.require(receipt.get('outcome')=='completed' and receipt.get('captureCompleted') is True and receipt.get('captureDispatchAttempted') is True)
    A.require('incompleteArtifact' not in receipt and receipt.get('readyForApply') is False)
    A.require(receipt.get('manifest')==manifest and receipt.get('plan')==plan)
    for key, expected in (('bundleSha256',manifest_pin),('planSha256',plan_pin),
                          ('manifestCanonicalSha256',A.P.digest(manifest)),('planCanonicalSha256',A.P.digest(plan))):
        A.require(receipt.get(key)==expected)
    A.P.exact(plan,('schema','sourceRevision','bundleSha256','kind','startSector','sectorCount','timeoutSeconds'),'plan_fields')
    A.require(plan['schema']=='openjibo.readonly-capture-plan.v1' and plan['bundleSha256']==manifest_pin)
    A.require(plan['sourceRevision']==manifest.get('sourceRevision')==receipt.get('sourceRevision'))
    A.require(plan['kind']==receipt.get('kind')=='primary-gpt-prefix' and type(plan['startSector']) is int and plan['startSector']==0)
    A.require(type(plan['sectorCount']) is int and 34<=plan['sectorCount']<=4096)
    A.require(type(plan['timeoutSeconds']) is int and 1<=plan['timeoutSeconds']<=60 and receipt.get('timeoutSeconds')==plan['timeoutSeconds'])
    A.require(manifest.get('schema')=='openjibo.readonly-capture-bundle.v1' and manifest.get('protocol')==A.PROTOCOL)
    A.require(type(receipt.get('processes')) is list and len(receipt['processes'])==2)
    A.require(all(type(p) is dict and type(p.get('exitCode')) is int and p['exitCode']==0 for p in receipt['processes']))
    artifact=receipt.get('artifact'); A.P.exact(artifact,('file','sizeBytes','sha256'),'capture_artifact_fields')
    A.require(artifact['file']=='capture.bin' and type(artifact['sizeBytes']) is int and artifact['sizeBytes']==plan['sectorCount']*512)
    path=Path(receipt_path).absolute().parent/'capture.bin'
    A.require(path.lstat().st_size==artifact['sizeBytes'])
    result=G.audit_file(path,total_sectors,artifact['sha256'])
    result['captureEvidence']=dict(receiptSha256=receipt_pin,bundleSha256=manifest_pin,planSha256=plan_pin,
                                   sourceRevision=plan['sourceRevision'],captureReceiptChecked=True,
                                   receiptTrust='operator-pinned-not-provenance-authenticated')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('receipt','manifest','plan','output'): parser.add_argument('--'+name,required=True,type=Path)
    for name in ('receipt-sha256','manifest-sha256','plan-sha256','disk-sectors'): parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    try:
        result=audit(args.receipt,args.receipt_sha256,args.manifest,args.manifest_sha256,args.plan,args.plan_sha256,int(args.disk_sectors,0))
        A.P.export(result,args.output)
    except (ValueError,OSError,UnicodeError,KeyError,TypeError,A.CaptureFailure,RecursionError):
        parser.exit(2,'Capture audit refused; check completed receipt, independent pins, prefix bytes and geometry.\n')
    print(json.dumps(dict(primaryGptChecksPassed=True,captureReceiptChecked=True,readyForApply=False)))


if __name__=='__main__': main()
