#!/usr/bin/env python3
"""Export an offline dual-rootfs firewall sector preview; never apply changes."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import struct
import sys
import time


def sibling(name):
    key='openjibo_preview_'+name
    spec=importlib.util.spec_from_file_location(key,Path(__file__).with_name(name+'.py'))
    module=importlib.util.module_from_spec(spec); sys.modules[key]=module
    spec.loader.exec_module(module); return module


A=sibling('capture_adapter')
E=sibling('ext4_path')
F=sibling('firewall_patch')
G=sibling('gpt_layout')
P=A.P
MAX_IMAGE=4*1024**3
PARTITIONS=('rootfsA','rootfsB')
FIREWALL='/etc/init.d/S21firewall'


def require(value):
    if not value: raise ValueError('firewall_preview_refused')


def sha(raw): return hashlib.sha256(raw).hexdigest()


@contextmanager
def retained_image(path, item, deadline):
    """Hash a bounded regular image, then read it through the same descriptor."""
    path=A.R.ordinary_path(path); original=path.lstat()
    require(stat.S_ISREG(original.st_mode) and original.st_size==item['sizeBytes'])
    flags=os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)
    with os.fdopen(os.open(str(path),flags),'rb') as stream:
        before=os.fstat(stream.fileno()); require(A.R.file_identity(original)==A.R.file_identity(before))
        digest=hashlib.sha256(); size=0
        while True:
            require(time.monotonic()<deadline)
            block=stream.read(min(1048576,item['sizeBytes']-size+1))
            if not block: break
            size+=len(block); require(size<=item['sizeBytes']); digest.update(block)
        require(size==item['sizeBytes'] and digest.hexdigest()==item['sha256'])
        require(A.R.identity(before)==A.R.identity(os.fstat(stream.fileno())))
        read_count=0; read_bytes=0
        def read_at(offset,length):
            nonlocal read_count,read_bytes
            require(type(offset) is int and type(length) is int and 0<=offset and 0<length<=1048576 and offset+length<=size)
            read_count+=1; read_bytes+=length
            require(read_count<=8192 and read_bytes<=16777216 and time.monotonic()<deadline)
            stream.seek(offset); raw=stream.read(length); require(len(raw)==length); return raw
        yield read_at
        require(A.R.identity(before)==A.R.identity(os.fstat(stream.fileno())))
    require(A.R.file_identity(original)==A.R.file_identity(A.R.ordinary_path(path).lstat()))


class PreviewReader(E.Ext4PathReader):
    """A deliberately narrow profile, separate from the existing device writer."""
    def __init__(self,read_at,size):
        raw=read_at(1024,1024)
        u32=lambda offset:struct.unpack_from('<I',raw,offset)[0]
        require(u32(24)<=2)
        block_size=1024<<u32(24)
        require(u32(76)==1 and struct.unpack_from('<H',raw,58)[0]==1)
        require(u32(20)==(1 if block_size==1024 else 0))
        require(1<=u32(32)<=block_size*8 and 1<=u32(40)<=block_size*8)
        require(0<u32(0)<=((u32(4)+u32(32)-1)//u32(32))*u32(40))
        require(u32(92)&~0x3c==0 and u32(96) in (0x40,0x42) and u32(100)&~0x3==0)
        require(struct.unpack_from('<H',raw,254)[0] in (0,32))
        self.inode_count=u32(0); self.metadata=[]
        super().__init__(read_at,size)
        require(self.inode_size%4==0 and self.block_size%self.inode_size==0)

    def _read_exact(self,offset,length):
        self.metadata.append((offset,offset+length))
        return super()._read_exact(offset,length)

    def _read_block(self,block):
        require(0<block<self.blocks_count)
        return E.Ext4PathReader._read_exact(self,block*self.block_size,self.block_size)

    def _parse_extent_node(self,node,expected_depth=None):
        require(len(node)>=12 and struct.unpack_from('<H',node,6)[0]==0)
        require(0<struct.unpack_from('<H',node,2)[0]<=4)
        return super()._parse_extent_node(node,expected_depth)

    def inode(self,number):
        require(1<=number<=self.inode_count)
        inode=super().inode(number)
        require(inode.mode&0xf000 in (0x4000,0x8000) and inode.flags==E.EXT4_EXTENTS_FL)
        require(0<inode.size<=1048576)
        return inode

    def extent_ranges(self,inode):
        extents=self.extents(inode); logical=0; ranges=[]
        for extent in extents:
            require(not extent.unwritten and extent.logical_block==logical)
            logical+=extent.block_count
            ranges.append((extent.physical_block*self.block_size,(extent.physical_block+extent.block_count)*self.block_size))
        require(logical==(inode.size+self.block_size-1)//self.block_size)
        return ranges

    def firewall(self):
        current=self.inode(2); inodes=[current]; ranges=[]
        for part in ('etc','init.d','S21firewall'):
            ranges.extend(self.extent_ranges(current))
            matches=[number for name,number in self.directory_entries(current) if name==part]
            require(len(matches)==1 and matches[0] not in [item.number for item in inodes])
            current=self.inode(matches[0]); inodes.append(current)
        require(current.mode&0xf000==0x8000 and current.size<=65536)
        file_ranges=self.extent_ranges(current); require(len(file_ranges)==1)
        ranges.extend(file_ranges)
        ordered=sorted(ranges); require(all(left[1]<=right[0] for left,right in zip(ordered,ordered[1:])))
        require(all(end<=meta_start or start>=meta_end for start,end in ranges for meta_start,meta_end in self.metadata))
        return current


def validate(manifest):
    P.exact(manifest,('schema','operation','diskSectors','gptPrefix','images'),'preview_manifest_fields')
    require(manifest['schema']=='openjibo.firewall-preview-input.v1' and manifest['operation'] in ('enable','restore'))
    require(type(manifest['diskSectors']) is int and 68<=manifest['diskSectors']<=1<<48)
    P.exact(manifest['gptPrefix'],('sha256','sizeBytes'),'prefix_fields')
    items=[manifest['gptPrefix']]
    require(type(manifest['images']) is list and len(manifest['images'])==2)
    names=set()
    for item in manifest['images']:
        P.exact(item,('partition','sha256','sizeBytes'),'image_fields')
        require(type(item['partition']) is str and item['partition'] in PARTITIONS and item['partition'] not in names)
        names.add(item['partition']); items.append(item)
    for item in items:
        require(type(item['sha256']) is str and P.HASH.fullmatch(item['sha256']))
        require(type(item['sizeBytes']) is int and 1024<=item['sizeBytes']<=MAX_IMAGE and item['sizeBytes']%512==0)
    require(manifest['gptPrefix']['sizeBytes']<=G.MAX_PREFIX_BYTES)


def partition_preview(partition,item,read_at,restore):
    reader=PreviewReader(read_at,item['sizeBytes']); inode=reader.firewall()
    match=F.inspect_firewall_file(reader.read_file(inode,65536))
    physical=reader.physical_offset(inode,match.assignment_offset)
    patch=F.build_sector_patch_from_reader(match,physical,read_at,restore)
    require(1<=patch.sector_count<=2 and (patch.start_sector+patch.sector_count)*512<=item['sizeBytes'])
    expected=F.ASSIGNMENT_ORIGINAL if match.state=='original' else F.ASSIGNMENT_PATCHED
    replacement=F.ASSIGNMENT_ORIGINAL if restore else F.ASSIGNMENT_PATCHED
    relative=physical-patch.start_sector*512
    require(patch.before[:relative]==patch.after[:relative] and patch.before[relative+len(expected):]==patch.after[relative+len(expected):])
    require(patch.after[relative:relative+len(expected)]==replacement)
    changed=[index for index,(before,after) in enumerate(zip(patch.before,patch.after)) if before!=after]
    if changed:
        first=changed[0]//512*512; end=(changed[-1]//512+1)*512
        patch=F.SectorPatch(patch.start_sector+first//512,(end-first)//512,patch.before[first:end],patch.after[first:end],physical)
    result=dict(partition=partition['name'],partitionStartSector=partition['start_sector'],partitionSizeSectors=partition['size_sectors'],
                imageSha256=item['sha256'],file=FIREWALL,inode=inode.number,filesystemUuid=reader.filesystem_uuid,
                fileStateBefore=match.state,fileStateAfter='original' if restore else 'patched',fileSha256Before=match.file_sha256,
                fileSha256After=F.FILE_SHA256_ORIGINAL if restore else F.FILE_SHA256_PATCHED,changeRequired=patch.before!=patch.after,delta=None)
    if result['changeRequired']:
        result['delta']=dict(partitionRelativeStartSector=patch.start_sector,absoluteStartSector=partition['start_sector']+patch.start_sector,
                             sectorCount=patch.sector_count,beforeFile=partition['name']+'.before.bin',afterFile=partition['name']+'.after.bin',
                             beforeSha256=patch.before_sha256,afterSha256=patch.after_sha256,unchangedSurroundingBytesVerified=True,
                             changedBytes=[dict(sectorByteOffset=index,before=before,after=after) for index,(before,after) in enumerate(zip(patch.before,patch.after)) if before!=after])
    return result,patch


def preview(manifest_path,manifest_pin,inputs,output):
    manifest=A.pinned_json(manifest_path,manifest_pin); validate(manifest)
    inputs=A.R.ordinary_path(inputs); require(inputs.is_dir())
    output=Path(output).absolute(); A.R.ordinary_path(output.parent); require(not output.exists())
    deadline=time.monotonic()+600
    with retained_image(inputs/'gpt-prefix.bin',manifest['gptPrefix'],deadline) as read_at:
        raw=b''.join(read_at(offset,min(1048576,manifest['gptPrefix']['sizeBytes']-offset)) for offset in range(0,manifest['gptPrefix']['sizeBytes'],1048576))
        layout=G.audit_primary_gpt(raw,manifest['diskSectors'])
    selected={p['name']:p for p in layout['partitions'] if p['name'] in PARTITIONS}
    require(set(selected)==set(PARTITIONS))
    results=[]; patches=[]
    for name in PARTITIONS:
        item=next(i for i in manifest['images'] if i['partition']==name); partition=selected[name]
        require(item['sizeBytes']==partition['size_sectors']*512)
        with retained_image(inputs/(name+'.img'),item,deadline) as read_at:
            result,patch=partition_preview(partition,item,read_at,manifest['operation']=='restore')
        results.append(result); patches.append(patch)
    result=dict(schema='openjibo.firewall-sector-preview.v1',checkedAtUtc=datetime.now(timezone.utc).isoformat(),
                manifestSha256=manifest_pin,manifestCanonicalSha256=P.digest(manifest),operation=manifest['operation'],
                profile='S21firewall.v1',profileSha256=F.KNOWN_PROFILE_SHA256,layout=layout,partitions=results,
                previewComplete=True,proposedChangedSectors=sum(p.sector_count for r,p in zip(results,patches) if r['changeRequired']),
                executionSupported=False,readyForApply=False,deviceWritesPerformed=False,networkRequestsPerformed=False,
                deviceIdentityVerified=False,filesystemIntegrityVerified=False,releaseCompatibilityVerified=False,
                recoveryAssociationVerified=False,rollbackTested=False,backupGptVerified=False,protectiveMbrVerified=False,
                modeJsonChanged=False,endpointOrCertificateChangesPlanned=False,
                inputTrust='operator-pinned-not-provenance-or-device-authenticated',geometryOrigin='operator-supplied-not-device-measured',
                requiredBeforeApply=['fresh-physical-device-and-release-association','complete-filesystem-and-block-ownership-validation',
                                     'verified-calibration-and-storage-recovery','reviewed-full-conversion-plan-and-owner-confirmation',
                                     'separately-approved-bounded-writer-and-readback','verified-rollback-path'],
                codeSha256=dict(preview=sha(Path(__file__).read_bytes()),ext4Parser=sha(Path(E.__file__).read_bytes()),
                                firewallProfileParser=sha(Path(F.__file__).read_bytes()),gptParser=sha(Path(G.__file__).read_bytes())))
    output.mkdir(mode=0o700,exist_ok=False)
    for item,patch in zip(results,patches):
        if item['changeRequired']:
            for field,raw in [('beforeFile',patch.before),('afterFile',patch.after)]:
                descriptor=os.open(str(output/item['delta'][field]),os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_BINARY',0),0o600)
                with os.fdopen(descriptor,'wb') as stream: stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    P.export(result,output/'preview.json'); return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','inputs','output'): parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--manifest-sha256',required=True)
    args=parser.parse_args()
    try: result=preview(args.manifest,args.manifest_sha256,args.inputs,args.output)
    except (ValueError,OSError,UnicodeError,KeyError,TypeError,struct.error,E.Ext4PathError,F.FirewallPatchError,A.CaptureFailure,RecursionError):
        parser.exit(2,'Firewall preview refused; check pins, both retained images, supported layout and a new output.\n')
    print(json.dumps(dict(previewComplete=True,previewSha256=P.digest(result),proposedChangedSectors=result['proposedChangedSectors'],readyForApply=False)))


if __name__=='__main__': main()
