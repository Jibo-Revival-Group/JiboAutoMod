#!/usr/bin/env python3
"""Observe pre-provisioning credential state in a pinned offline storage backup."""
import argparse
from datetime import datetime, timezone
import html
import importlib.util
from pathlib import Path
import re
import struct
import time

spec=importlib.util.spec_from_file_location('storage_evidence',Path(__file__).with_name('storage_evidence.py'))
S=importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
F=S.F; B=S.B; P=S.P
FIELDS=('accessKeyId','secretAccessKey','region')
PATH='/jibo/credentials.json'


def require(value):
    if not value: raise ValueError('oobe_intake_refused')


def classify(raw):
    if raw==b'':
        return dict(kind='empty-file',fields={name:'unobserved' for name in FIELDS},region=None,
                    regionSyntax='unobserved',unknownFieldsPresent=False,workflowHint='unprovisioned-evidence-review')
    value=S.parse(raw)
    fields={}
    for name in FIELDS:
        if name not in value: status='absent'
        elif value[name] is None: status='null'
        elif type(value[name]) is not str: status='unsupported-type'
        elif value[name]=='': status='blank'
        else: status='present'
        fields[name]=status
    region=value.get('region')
    valid=type(region) is str and bool(re.fullmatch('[a-z][a-z0-9-]{0,31}',region))
    region_syntax='supported' if valid else ('unobserved' if fields['region'] in ('absent','blank') else 'unsupported')
    if all(state in ('absent','blank') for state in fields.values()):
        kind='identity-fields-absent-or-blank'; hint='unprovisioned-evidence-review'
    elif all(state=='present' for state in fields.values()) and valid:
        kind='identity-fields-present'; hint='credentialed-evidence-review'
    else:
        kind='partial-or-unsupported-fields'; hint='partial-provisioning-review'
    return dict(kind=kind,fields=fields,region=region if valid else None,regionSyntax=region_syntax,
                unknownFieldsPresent=bool(set(value)-set(FIELDS)),workflowHint=hint)


class IntakeReader(F.PreviewReader):
    def check_ranges(self,ranges):
        require(all(0<=a<b<=self.blocks_count*self.block_size for a,b in self.metadata))
        ordered=sorted(ranges)
        require(all(a[1]<=b[0] for a,b in zip(ordered,ordered[1:])))
        require(all(end<=mstart or start>=mend for start,end in ranges for mstart,mend in self.metadata))

    def credentials(self):
        current=self.inode(2); seen={2}; ranges=[]; directories=[]
        for part,location in [('jibo','/'),('credentials.json','/jibo')]:
            require(current.mode&0xf000==0x4000 and current.size%self.block_size==0)
            spans=self.extent_ranges(current); ranges.extend(spans)
            matches=[]
            for name,number in self.directory_entries(current):
                if name==part:
                    require(not matches); matches.append(number)
            raw=b''.join(self._read_at(a,b-a) for a,b in spans)
            require(len(raw)==current.size)
            directories.append(dict(path=location,inode=current.number,sizeBytes=len(raw),sha256=F.sha(raw),
                                    fullyScanned=True,ranges=[dict(partitionByteOffset=a,sizeBytes=b-a) for a,b in spans]))
            if not matches:
                self.check_ranges(ranges)
                return ('parent-absent' if part=='jibo' else 'leaf-absent'),None,[],directories
            number=matches[0]; require(number not in seen and 1<=number<=self.inode_count); seen.add(number)
            if part=='jibo':
                current=self.inode(number)
                continue
            # Only this fixed leaf admits a valid zero-byte extent inode. All
            # nonempty files/directories keep the existing narrow profile.
            leaf=F.E.Ext4PathReader.inode(self,number)
            require(leaf.mode&0xf000==0x8000 and leaf.flags==F.E.EXT4_EXTENTS_FL and leaf.size<=P.LIMIT)
            if leaf.size==0:
                magic,entries,maximum,depth=struct.unpack_from('<HHHH',leaf.block_tree)
                require((magic,entries,maximum,depth)==(0xf30a,0,4,0) and leaf.block_tree[12:]==b'\0'*48)
                file_ranges=[]
            else: file_ranges=self.extent_ranges(leaf)
            self.check_ranges(ranges+file_ranges)
            return 'file-present',leaf,file_ranges,directories
        raise ValueError('oobe_intake_refused')


def validate(value):
    P.exact(value,('schema','diskSectors','fullStorage','gptPrefix','credentialsPartition'),'intake_manifest_fields')
    require(value['schema']=='openjibo.oobe-intake-input.v1')
    require(type(value['diskSectors']) is int and 68<=value['diskSectors']<=S.MAX_STORAGE//512)
    for name,limit in [('fullStorage',S.MAX_STORAGE),('gptPrefix',F.G.MAX_PREFIX_BYTES)]:
        item=value[name]; P.exact(item,('sha256','sizeBytes'),'intake_pin_fields')
        require(type(item['sha256']) is str and P.HASH.fullmatch(item['sha256']))
        require(type(item['sizeBytes']) is int and 0<item['sizeBytes']<=limit and item['sizeBytes']%512==0)
    require(value['fullStorage']['sizeBytes']==value['diskSectors']*512)
    require(1024<=value['gptPrefix']['sizeBytes']<=value['fullStorage']['sizeBytes'])
    require(type(value['credentialsPartition']) is str and re.fullmatch('[A-Za-z0-9_.-]{1,36}',value['credentialsPartition']))


def inspect(manifest_path,manifest_pin,inputs,output,synthetic_demo=False):
    require(type(synthetic_demo) is bool)
    value,_=S.E.read_json(manifest_path,manifest_pin); validate(value)
    inputs=B.A.R.ordinary_path(inputs); require(inputs.is_dir())
    output=Path(output).absolute(); B.A.R.ordinary_path(output.parent); require(not output.exists())
    with F.retained_image(inputs/'full-storage.bin',value['fullStorage'],time.monotonic()+600) as read_at:
        size=value['gptPrefix']['sizeBytes']
        prefix=b''.join(read_at(a,min(1048576,size-a)) for a in range(0,size,1048576))
        require(F.sha(prefix)==value['gptPrefix']['sha256'])
        layout=F.G.audit_primary_gpt(prefix,value['diskSectors'])
        matches=[part for part in layout['partitions'] if part['name']==value['credentialsPartition']]; require(len(matches)==1)
        partition=matches[0]; start=partition['start_sector']*512; length=partition['size_sectors']*512
        require(2048<=length<=F.MAX_IMAGE)
        def partition_read(offset,count):
            require(type(offset) is int and type(count) is int and 0<=offset and 0<count and offset+count<=length)
            return read_at(start+offset,count)
        reader=IntakeReader(partition_read,length)
        status,inode,spans,directories=reader.credentials()
        raw=None if inode is None else (b'' if inode.size==0 else reader.read_file(inode,P.LIMIT))
        observation=(classify(raw) if raw is not None else
                     dict(kind=status,fields={name:'unobserved' for name in FIELDS},region=None,regionSyntax='unobserved',
                          unknownFieldsPresent=False,workflowHint='unprovisioned-evidence-review' if status=='leaf-absent' else 'path-review-required'))
        file=dict(path=PATH,pathStatus=status,inode=inode.number if inode else None,sizeBytes=len(raw) if raw is not None else None,
                  sha256=F.sha(raw) if raw is not None else None,
                  ranges=[dict(partitionByteOffset=a,fullStorageByteOffset=start+a,sizeBytes=b-a) for a,b in spans])
    result=dict(schema='openjibo.oobe-storage-intake.v1',checkedAtUtc=datetime.now(timezone.utc).isoformat(),syntheticDemo=synthetic_demo,
                manifestSha256=manifest_pin,manifestCanonicalSha256=P.digest(value),fullStorage=value['fullStorage'],gptPrefix=value['gptPrefix'],
                partition=partition,file=file,directoryEvidence=directories,credentialObservation=observation,intakeComplete=True,
                partitionSelection='operator-supplied-exact-gpt-name',runtimeMountMappingVerified=False,installedReleaseVerified=False,
                physicalDeviceAssociationVerified=False,factoryStateVerified=False,oobeStateVerified=False,credentialValidityVerified=False,
                rawCredentialFileExported=False,credentialSecretValuesExported=False,credentialsCreated=False,regionInferred=False,filesystemIntegrityVerified=False,
                blockOwnershipVerified=False,recoveryAssociationVerified=False,conversionPlanProduced=False,executionSupported=False,
                readyForApply=False,deviceWritesPerformed=False,networkRequestsPerformed=False,
                inputTrust='operator-pinned-not-provenance-or-device-authenticated',
                requiredBeforeProvisioning=['device-specific-release-mount-and-recovery-association','review-unprovisioned-or-partial-intake',
                                            'owner-and-device-enrollment-contract','verified-target-and-native-routing',
                                            'bounded-confirmed-write-readback-and-rollback'],
                codeSha256=dict(intake=F.sha(Path(__file__).read_bytes()),storage=F.sha(Path(S.__file__).read_bytes()),
                                filesystemProfile=F.sha(Path(F.__file__).read_bytes()),ext4Parser=F.sha(Path(F.E.__file__).read_bytes()),
                                gptParser=F.sha(Path(F.G.__file__).read_bytes())))
    escape=lambda v:html.escape(str(v),quote=True)
    rows=''.join('<tr><td>'+name+'</td><td>'+escape(state)+'</td></tr>' for name,state in observation['fields'].items())
    page=('<!doctype html><html lang="en"><meta charset="utf-8"><title>OOBE credential intake</title>'
          '<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
          '<style>body{font:16px system-ui;max-width:850px;margin:40px auto;padding:20px}td{padding:10px;border-bottom:1px solid #ddd}</style>'
          '<h1>OOBE credential intake</h1><p>'+('Synthetic demo · ' if synthetic_demo else '')+'Observation complete · Device/OOBE state unverified · Apply unavailable</p>'
          '<p>Selected partition: '+escape(partition['name'])+'<br>Partition-root path: '+PATH+'<br>Path: '+escape(status)+
          '<br>Observation: '+escape(observation['kind'])+'<br>Workflow hint: '+escape(observation['workflowHint'])+'</p>'
          '<table><tr><th>Field</th><th>Observed state</th></tr>'+rows+'</table><p>Region: '+escape(observation['region'] or 'Not established')+'</p>'
          '<p>Absent or blank fields do not prove factory condition, ownership, OOBE mode, valid recovery, or deployment readiness. No credential or region is created.</p>'
          '<p>Keep device-specific recovery and identity associations separate. Unsupported/corrupt filesystems are refused rather than reported as absent.</p>'
          '<a href="intake.json">Report and file hashes</a></html>').encode('utf-8')
    output=B.new_directory(output); B.write(output/'intake.html',page)
    result['files']=[dict(file='intake.html',sizeBytes=len(page),sha256=F.sha(page))]
    B.write(output/'intake.json',P.canonical(result)+b'\n')
    return result


def main():
    class Parser(argparse.ArgumentParser):
        def error(self,message): self.exit(2,'OOBE intake refused; see Docs/oobe-storage-intake.md.\n')
    parser=Parser(description=__doc__)
    for name in ('manifest','inputs','output'): parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--manifest-sha256',required=True)
    args=parser.parse_args()
    try: result=inspect(args.manifest,args.manifest_sha256,args.inputs,args.output)
    except (ValueError,OSError,UnicodeError,KeyError,TypeError,B.A.CaptureFailure,F.E.Ext4PathError,RecursionError):
        parser.exit(2,'OOBE intake refused; check pinned storage, explicit partition, supported profile and new output.\n')
    import json
    print(json.dumps(dict(intakeComplete=True,intakeSha256=P.digest(result),readyForApply=False),sort_keys=True))


if __name__=='__main__': main()
