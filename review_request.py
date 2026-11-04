#!/usr/bin/env python3
"""Generate pinned inputs and build a v2 or optional v3 offline conversion review."""
import argparse
import json
from pathlib import Path

import importlib.util

spec=importlib.util.spec_from_file_location('conversion_review',Path(__file__).with_name('conversion_review.py'))
V=importlib.util.module_from_spec(spec); spec.loader.exec_module(V)


def build(inputs,output,jetstream_partition,credentials_partition,gpt_recovery=False):
    V.require(type(gpt_recovery) is bool)
    inputs=V.R.ordinary_path(inputs); V.require(inputs.is_dir())
    values={}; pins={}
    for name,filename in V.INPUTS.items():
        raw=V.B.read(inputs/filename,V.P.LIMIT)
        pins[name]=V.sha(raw)
        values[name]=V.E.read_json(inputs/filename,pins[name])[0]
    inventory=values['inventory']; V.P.inventory(inventory)
    firewall=values['firewallInput']; V.F.validate(firewall)
    endpoint=values['endpointInput']
    full=next((item for item in inventory['backups'] if item['kind']=='full-storage'),None)
    V.require(full is not None and type(endpoint) is dict)
    storage=dict(schema='openjibo.storage-file-input.v1',diskSectors=firewall['diskSectors'],
                 fullStorage={name:full[name] for name in ('sha256','sizeBytes')},gptPrefix=firewall['gptPrefix'],
                 partitions=dict(jetstream=jetstream_partition,credentials=credentials_partition),
                 jetstream=endpoint.get('jetstream'),credentialsRegion=endpoint.get('credentialsRegion'))
    V.S.validate(storage)
    storage_raw=V.P.canonical(storage)+b'\n'
    pins['storageInput']=V.sha(storage_raw); values['storageInput']=storage
    manifest=dict(schema='openjibo.conversion-review-input.v3' if gpt_recovery else 'openjibo.conversion-review-input.v2',files=pins)
    manifest_raw=V.P.canonical(manifest)+b'\n'
    return V._assemble(manifest,V.sha(manifest_raw),values,inputs,output,
                       request_files={'review-input.json':manifest_raw,'storage-input.json':storage_raw})


def main():
    class Parser(argparse.ArgumentParser):
        def error(self,message): self.exit(2,'Review request refused; check required arguments. See Docs/conversion-review-bundle.md.\n')
    parser=Parser(description=__doc__)
    for name in ('inputs','output'): parser.add_argument('--'+name,required=True,type=Path)
    for name in ('jetstream-partition','credentials-partition'): parser.add_argument('--'+name,required=True)
    parser.add_argument('--gpt-recovery',action='store_true',help='Build v3 and require protective MBR and both GPT copies to match the pinned backup.')
    args=parser.parse_args()
    try: result=build(args.inputs,args.output,args.jetstream_partition,args.credentials_partition,args.gpt_recovery)
    except (ValueError,OSError,UnicodeError,KeyError,TypeError,V.F.E.Ext4PathError,V.S.F.E.Ext4PathError,
            V.F.F.FirewallPatchError,V.F.A.CaptureFailure,V.B.A.CaptureFailure,RecursionError):
        parser.exit(2,'Review request refused; check retained inputs, explicit partition selection and new output. No complete review was exported.\n')
    print(json.dumps(dict(reviewAssembled=True,reviewSha256=V.P.digest(result),manifestSha256=result['manifestSha256'],
                          inputPinOrigin=result['inputPinOrigin'],completeConversionPlan=False,readyForApply=False),sort_keys=True))


if __name__=='__main__': main()
