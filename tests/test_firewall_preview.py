import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
import firewall_preview as V
import test_ext4_path as ext4_fixture
from test_gpt_audit import fixture,recalculate


def image(patched=False,file_block=13):
    raw=bytearray(ext4_fixture.Ext4PathReaderTests()._image())
    struct.pack_into('<I',raw,1024,16)
    struct.pack_into('<I',raw,1024+20,1)
    struct.pack_into('<H',raw,1024+58,1)
    struct.pack_into('<I',raw,1024+76,1)
    original=V.F.SIGNATURE_ORIGINAL
    data=V.F.SIGNATURE_PATCHED if patched else original
    inode_offset=3*1024+4*128
    count=(len(data)+1023)//1024
    struct.pack_into('<HHI',raw,inode_offset+52+4,count,0,file_block)
    raw[13*1024:13*1024+len(data)]=b'\0'*len(data)
    raw[file_block*1024:file_block*1024+len(data)]=data
    return bytes(raw)


def prefix():
    raw=bytearray(fixture())
    for index in range(2): struct.pack_into('<QQ',raw,1024+index*128+32,64+index*128,191+index*128)
    return recalculate(raw)


class FirewallPreview(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); self.inputs=self.root/'inputs'; self.inputs.mkdir()
        self.output=self.root/'preview'; self.path=self.root/'manifest.json'
        self.manifest=dict(schema='openjibo.firewall-preview-input.v1',operation='enable',diskSectors=4096,gptPrefix={},images=[])
        self.set_file('gpt-prefix.bin',prefix())
        for name in V.PARTITIONS: self.set_file(name+'.img',image())

    def set_file(self,name,raw):
        (self.inputs/name).write_bytes(raw); item=dict(sha256=hashlib.sha256(raw).hexdigest(),sizeBytes=len(raw))
        if name=='gpt-prefix.bin': self.manifest['gptPrefix']=item
        else:
            partition=name[:-4]; self.manifest['images']=[i for i in self.manifest['images'] if i['partition']!=partition]
            self.manifest['images'].append(dict(partition=partition,**item))

    def run_preview(self):
        raw=json.dumps(self.manifest).encode(); self.path.write_bytes(raw)
        return V.preview(self.path,hashlib.sha256(raw).hexdigest(),self.inputs,self.output)

    def test_dual_slot_preview_preserves_inputs_and_only_changes_assignment_bytes(self):
        before={p.name:p.read_bytes() for p in self.inputs.iterdir()}
        with patch.object(subprocess,'Popen',side_effect=AssertionError('no process')): result=self.run_preview()
        self.assertTrue(result['previewComplete']); self.assertEqual(len(result['partitions']),2)
        for item in result['partitions']:
            delta=item['delta']; raw_before=(self.output/delta['beforeFile']).read_bytes(); raw_after=(self.output/delta['afterFile']).read_bytes()
            source=before[item['partition']+'.img']; start=delta['partitionRelativeStartSector']*512
            self.assertEqual(raw_before,source[start:start+len(raw_before)])
            self.assertEqual(delta['absoluteStartSector'],item['partitionStartSector']+delta['partitionRelativeStartSector'])
            self.assertEqual(hashlib.sha256(raw_after).hexdigest(),delta['afterSha256'])
            reconstructed=source[:start]+raw_after+source[start+len(raw_after):]
            expected=source.replace(V.F.SIGNATURE_ORIGINAL,V.F.SIGNATURE_PATCHED)
            self.assertEqual(reconstructed,expected)
            self.assertEqual(delta['changedBytes'],[dict(sectorByteOffset=i,before=a,after=b) for i,(a,b) in enumerate(zip(raw_before,raw_after)) if a!=b])
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.inputs.iterdir()})
        for flag in ('readyForApply','executionSupported','deviceWritesPerformed','deviceIdentityVerified','filesystemIntegrityVerified','modeJsonChanged','endpointOrCertificateChangesPlanned'):
            self.assertFalse(result[flag])

    def test_restore_and_mixed_slot_noop_are_explicit(self):
        self.set_file('rootfsA.img',image(True)); self.set_file('rootfsB.img',image(True))
        result=self.run_preview(); self.assertEqual(result['proposedChangedSectors'],0)
        self.assertEqual([p.name for p in self.output.iterdir()],['preview.json'])
        self.output=self.root/'restore'; self.manifest['operation']='restore'; self.set_file('rootfsB.img',image(False))
        result=self.run_preview(); self.assertTrue(result['partitions'][0]['changeRequired']); self.assertFalse(result['partitions'][1]['changeRequired'])
        self.assertEqual(result['partitions'][0]['fileStateAfter'],'original')

    def test_both_slots_and_exact_gpt_sizes_required_before_output(self):
        original=copy.deepcopy(self.manifest)
        for change in ('missing','size','unknown','duplicate','bool'):
            self.manifest=copy.deepcopy(original)
            if change=='missing': self.manifest['images'].pop()
            elif change=='size': self.manifest['images'][1]['sizeBytes']-=512
            elif change=='unknown': self.manifest['images'][1]['partition']='rootfsC'
            elif change=='duplicate': self.manifest['images'][1]['partition']='rootfsA'
            else: self.manifest['diskSectors']=True
            with self.subTest(change=change), self.assertRaises(ValueError): self.run_preview()
            self.assertFalse(self.output.exists())

    def test_hash_substitution_and_existing_output_are_refused(self):
        (self.inputs/'rootfsB.img').write_bytes(image(True))
        with self.assertRaises(ValueError): self.run_preview()
        self.assertFalse(self.output.exists())
        self.set_file('rootfsB.img',image()); self.output.mkdir(); marker=self.output/'keep'; marker.write_bytes(b'keep')
        with self.assertRaises(ValueError): self.run_preview()
        self.assertEqual(marker.read_bytes(),b'keep')

    def test_unknown_or_corrupt_profile_is_refused_even_with_matching_image_pin(self):
        raw=bytearray(image()); raw[13*1024+20]^=1; self.set_file('rootfsB.img',bytes(raw))
        with self.assertRaises(V.F.FirewallPatchError): self.run_preview()
        self.assertFalse(self.output.exists())

    def test_dirty_checksumming_64bit_and_unknown_ext_features_are_refused(self):
        for offset,fmt,value in ((58,'<H',0),(76,'<I',0),(24,'<I',0xffffffff),(32,'<I',0),
                                 (96,'<I',0x44),(96,'<I',0xc0),(96,'<I',0x240),(100,'<I',0x400),(92,'<I',0x400)):
            raw=bytearray(image()); struct.pack_into(fmt,raw,1024+offset,value); self.set_file('rootfsB.img',bytes(raw))
            with self.subTest(offset=offset,value=value), self.assertRaises(ValueError): self.run_preview()
            self.assertFalse(self.output.exists())

    def test_unwritten_sparse_deep_duplicate_and_metadata_alias_mappings_refused(self):
        for case in ('unwritten','hole','deep','alias','duplicate'):
            raw=bytearray(image()); inode=3*1024+4*128
            if case=='unwritten': struct.pack_into('<H',raw,inode+56,0x8004)
            elif case=='hole': struct.pack_into('<I',raw,inode+52,1)
            elif case=='deep': struct.pack_into('<H',raw,inode+46,1)
            elif case=='alias': struct.pack_into('<I',raw,inode+60,3)
            else: struct.pack_into('<I',raw,10*1024,3)  # '.' aliases etc inode; path uniqueness still resolved below
            if case=='duplicate':
                # Add a second matching name by replacing the root '..' entry name.
                struct.pack_into('<B',raw,10*1024+12+6,3); raw[10*1024+12+8:10*1024+12+11]=b'etc'
            self.set_file('rootfsB.img',bytes(raw))
            with self.subTest(case=case), self.assertRaises((ValueError,V.E.Ext4PathError,V.F.FirewallPatchError)): self.run_preview()
            self.assertFalse(self.output.exists())

    def test_gpt_corruption_wrong_capacity_and_partition_aliases_refused(self):
        raw=bytearray(prefix()); raw[1024]^=1; self.set_file('gpt-prefix.bin',bytes(raw))
        with self.assertRaises(ValueError): self.run_preview()
        self.set_file('gpt-prefix.bin',prefix()); self.manifest['diskSectors']=8192
        with self.assertRaises(ValueError): self.run_preview()

    def test_raw_manifest_pin_required(self):
        self.path.write_text(json.dumps(self.manifest),encoding='utf-8')
        with self.assertRaises(V.A.CaptureFailure): V.preview(self.path,'0'*64,self.inputs,self.output)

    def test_image_mutation_during_resolution_refuses_before_export(self):
        original=V.partition_preview
        def changing(*args):
            result=original(*args)
            path=self.inputs/(args[0]['name']+'.img')
            with path.open('r+b') as stream: stream.seek(-1,os.SEEK_END); stream.write(b'X'); stream.flush(); os.fsync(stream.fileno())
            return result
        with patch.object(V,'partition_preview',side_effect=changing):
            with self.assertRaises(ValueError): self.run_preview()
        self.assertFalse(self.output.exists())

    def test_resolved_file_can_move_without_hardcoded_sector_assumptions(self):
        self.set_file('rootfsB.img',image(file_block=20))
        result=self.run_preview(); left,right=result['partitions']
        self.assertEqual(right['delta']['partitionRelativeStartSector']-left['delta']['partitionRelativeStartSector'],14)

    def test_cli_is_portable_path_free_and_has_no_device_imports(self):
        raw=json.dumps(self.manifest).encode(); self.path.write_bytes(raw)
        command=[sys.executable,'-I','-B',str(Path(V.__file__)),'--manifest',str(self.path),'--manifest-sha256',hashlib.sha256(raw).hexdigest(),'--inputs',str(self.inputs),'--output',str(self.output)]
        result=subprocess.run(command,cwd=self.root,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr); self.assertNotIn(str(self.root),result.stdout)
        probe=subprocess.run([sys.executable,'-I','-B','-c',"import runpy,sys; runpy.run_path(sys.argv[1],run_name='offline_probe'); assert not any(n.startswith(('Exploits','usb','tkinter','config')) for n in sys.modules)",str(Path(V.__file__))],cwd=self.root,capture_output=True,timeout=10)
        self.assertEqual(probe.returncode,0,probe.stderr)


if __name__=='__main__': unittest.main()
