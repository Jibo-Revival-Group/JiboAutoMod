import copy
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
import oobe_intake as I
import test_storage_evidence as storage
import test_ext4_path as ext4


class OobeIntake(unittest.TestCase):
    def setUp(self):
        self.case=storage.StorageEvidence(); self.case.setUp(); self.addCleanup(self.case.doCleanups)
        self.root=self.case.root; self.inputs=self.case.inputs; self.output=self.root/'intake'; self.path=self.root/'intake-input.json'

    def manifest(self):
        value=self.case.manifest
        return dict(schema='openjibo.oobe-intake-input.v1',diskSectors=value['diskSectors'],
                    fullStorage=value['fullStorage'].copy(),gptPrefix=value['gptPrefix'].copy(),credentialsPartition='var-test')

    def inspect(self,value=None):
        raw=json.dumps(value or self.manifest()).encode(); self.path.write_bytes(raw)
        return I.inspect(self.path,I.F.sha(raw),self.inputs,self.output)

    def image(self,raw):
        self.case.images['credentials']=bytes(raw); self.case.save()

    def credential(self,value):
        self.image(storage.filesystem('credentials',json.dumps(value).encode()))

    def absent(self,parent=False):
        raw=bytearray(self.case.images['credentials']); builder=ext4.Ext4PathReaderTests()
        if parent: raw[10*1024:11*1024]=builder._directory((3,'other',2))
        else: raw[11*1024:12*1024]=builder._directory()
        self.image(raw)

    def test_missing_leaf_is_backed_by_complete_parent_scan_and_does_not_claim_oobe(self):
        self.absent()
        before=I.F.sha((self.inputs/'full-storage.bin').read_bytes())
        with patch.object(subprocess,'Popen',side_effect=AssertionError('no process')): result=self.inspect()
        self.assertEqual(result['file']['pathStatus'],'leaf-absent')
        self.assertIsNone(result['file']['sha256'])
        self.assertEqual(result['credentialObservation']['workflowHint'],'unprovisioned-evidence-review')
        self.assertEqual([d['path'] for d in result['directoryEvidence']],['/','/jibo'])
        self.assertTrue(all(d['fullyScanned'] for d in result['directoryEvidence']))
        self.assertEqual(before,I.F.sha((self.inputs/'full-storage.bin').read_bytes()))
        self.assertFalse(result['factoryStateVerified']); self.assertFalse(result['oobeStateVerified'])

    def test_missing_parent_is_path_review_not_an_unprovisioned_claim(self):
        self.absent(parent=True); result=self.inspect()
        self.assertEqual(result['file']['pathStatus'],'parent-absent')
        self.assertEqual(result['credentialObservation']['workflowHint'],'path-review-required')
        self.assertEqual(len(result['directoryEvidence']),1)

    def test_empty_object_blank_and_missing_fields_remain_distinct_observations(self):
        for index,value in enumerate(({},dict(region='',accessKeyId='',secretAccessKey=''),dict(region=''))):
            self.output=self.root/str(index); self.credential(value); result=self.inspect()
            observation=result['credentialObservation']
            self.assertEqual(observation['kind'],'identity-fields-absent-or-blank')
            self.assertIsNone(observation['region']); self.assertFalse(result['regionInferred'])
            for name in I.FIELDS: self.assertEqual(observation['fields'][name],'blank' if name in value else 'absent')

    def test_null_nonstring_partial_and_unsupported_regions_are_manual_review(self):
        for index,value in enumerate((dict(region=None),dict(region=1),dict(region='us',accessKeyId='a'),
                                      dict(region='UNSUPPORTED',accessKeyId='a',secretAccessKey='s'))):
            self.output=self.root/str(index); self.credential(value); observation=self.inspect()['credentialObservation']
            self.assertEqual(observation['kind'],'partial-or-unsupported-fields')
            self.assertEqual(observation['workflowHint'],'partial-provisioning-review')
            if value['region']!='us': self.assertIsNone(observation['region'])

    def test_complete_field_presence_is_not_credential_validity_or_conversion_readiness(self):
        self.credential(dict(region='api',accessKeyId='PRIVATE_ACCESS',secretAccessKey='PRIVATE_SECRET',extra='PRIVATE_EXTRA'))
        result=self.inspect(); observation=result['credentialObservation']
        self.assertEqual(observation['kind'],'identity-fields-present'); self.assertEqual(observation['region'],'api')
        self.assertTrue(observation['unknownFieldsPresent'])
        for flag in ('credentialValidityVerified','physicalDeviceAssociationVerified','factoryStateVerified','oobeStateVerified','recoveryAssociationVerified',
                     'filesystemIntegrityVerified','blockOwnershipVerified','runtimeMountMappingVerified','installedReleaseVerified','conversionPlanProduced',
                     'credentialsCreated','rawCredentialFileExported','credentialSecretValuesExported','executionSupported','readyForApply','deviceWritesPerformed','networkRequestsPerformed'):
            self.assertFalse(result[flag])
        for path in self.output.iterdir(): self.assertNotIn(b'PRIVATE_',path.read_bytes())

    def test_valid_zero_byte_leaf_has_empty_hash_and_no_invented_json_fields(self):
        raw=bytearray(self.case.images['credentials']); offset=3*1024+3*128
        struct.pack_into('<I',raw,offset+4,0); struct.pack_into('<H',raw,offset+42,0)
        raw[offset+52:offset+100]=b'\0'*48; self.image(raw)
        result=self.inspect(); self.assertEqual(result['file']['sizeBytes'],0)
        self.assertEqual(result['file']['sha256'],I.F.sha(b''))
        self.assertEqual(result['credentialObservation']['kind'],'empty-file')
        self.assertEqual(set(result['credentialObservation']['fields'].values()),{'unobserved'})

    def test_intake_success_does_not_bypass_credentialed_storage_review(self):
        self.credential(dict(region='',accessKeyId='',secretAccessKey=''))
        self.assertTrue(self.inspect()['intakeComplete'])
        with self.assertRaises(ValueError): self.case.run_evidence()
        self.assertFalse(self.case.output.exists())

    def test_empty_inode_with_unvalidated_extent_header_is_refused(self):
        raw=bytearray(self.case.images['credentials']); offset=3*1024+3*128
        struct.pack_into('<I',raw,offset+4,0); self.image(raw)
        with self.assertRaises(ValueError): self.inspect()
        self.assertFalse(self.output.exists())

    def test_corrupt_parent_directory_is_not_reported_as_absent(self):
        self.absent(); raw=bytearray(self.case.images['credentials'])
        struct.pack_into('<H',raw,11*1024+4,7); self.image(raw)
        with self.assertRaises(I.F.E.Ext4PathError): self.inspect()
        self.assertFalse(self.output.exists())

    def test_duplicate_paths_symlinks_sparse_and_metadata_aliases_refused(self):
        baseline=self.case.images['credentials']; offset=3*1024+3*128
        for case in ('duplicate','symlink','sparse','unwritten','deep','alias'):
            raw=bytearray(baseline)
            if case=='duplicate': raw[11*1024:12*1024]=ext4.Ext4PathReaderTests()._directory((4,'credentials.json',1),(5,'credentials.json',1))
            elif case=='symlink': struct.pack_into('<H',raw,offset,0xa1ff)
            elif case=='sparse': struct.pack_into('<I',raw,offset+52,1)
            elif case=='unwritten': struct.pack_into('<H',raw,offset+56,0x8001)
            elif case=='deep': struct.pack_into('<H',raw,offset+46,1)
            else: struct.pack_into('<I',raw,offset+60,3)
            self.image(raw)
            with self.subTest(case=case),self.assertRaises(ValueError): self.inspect()
            self.assertFalse(self.output.exists())

    def test_dirty_unsupported_and_corrupt_filesystems_refuse_even_when_leaf_is_missing(self):
        self.absent(); baseline=self.case.images['credentials']
        for field,fmt,value in ((58,'<H',0),(96,'<I',0xc0),(100,'<I',0x400),(24,'<I',0xffffffff)):
            raw=bytearray(baseline); struct.pack_into(fmt,raw,1024+field,value); self.image(raw)
            with self.subTest(field=field),self.assertRaises(ValueError): self.inspect()
            self.assertFalse(self.output.exists())

    def test_invalid_json_does_not_become_unprovisioned_intake(self):
        for index,raw in enumerate((b'null',b'[]',b'{"region":"api","region":"api"}',b'{"region":NaN}',b'not-json')):
            self.output=self.root/str(index); self.image(storage.filesystem('credentials',raw))
            with self.assertRaises(ValueError): self.inspect()
            self.assertFalse(self.output.exists())

    def test_wrong_pins_partition_and_geometry_refused_before_output(self):
        original=self.manifest()
        for case in ('hash','prefix','partition','size','capacity','extra'):
            value=copy.deepcopy(original)
            if case=='hash': value['fullStorage']['sha256']='0'*64
            elif case=='prefix': value['gptPrefix']['sha256']='0'*64
            elif case=='partition': value['credentialsPartition']='4.var'
            elif case=='size': value['fullStorage']['sizeBytes']-=512
            elif case=='capacity': value['diskSectors']=True
            else: value['credentialsRegion']='api'
            with self.subTest(case=case),self.assertRaises(ValueError): self.inspect(value)
            self.assertFalse(self.output.exists())

    def test_storage_mutation_prevents_terminal_output(self):
        original=I.IntakeReader.credentials
        def changed(*args):
            value=original(*args)
            with (self.inputs/'full-storage.bin').open('r+b') as stream:
                stream.seek(-1,os.SEEK_END); stream.write(b'X'); stream.flush(); os.fsync(stream.fileno())
            return value
        with patch.object(I.IntakeReader,'credentials',changed),self.assertRaises(ValueError): self.inspect()
        self.assertFalse(self.output.exists())

    def test_existing_output_and_bad_outer_pin_preserve_files(self):
        self.output.mkdir(); (self.output/'keep').write_bytes(b'keep')
        with self.assertRaises(ValueError): self.inspect()
        self.assertEqual((self.output/'keep').read_bytes(),b'keep')
        with self.assertRaises(ValueError): I.inspect(self.path,'0'*64,self.inputs,self.root/'other')

    def test_cli_isolated_redacted_and_indexes_static_page(self):
        self.absent(); self.inspect(); pin=I.F.sha(self.path.read_bytes())
        command=[sys.executable,'-I','-B',str(Path(I.__file__)),'--manifest',str(self.path),'--manifest-sha256',pin,
                 '--inputs',str(self.inputs),'--output',str(self.root/'cli')]
        result=subprocess.run(command,cwd=self.root,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr); self.assertFalse(json.loads(result.stdout)['readyForApply'])
        report=json.loads((self.root/'cli/intake.json').read_bytes())
        self.assertEqual(json.loads(result.stdout)['intakeSha256'],I.P.digest(report))
        item=report['files'][0]; self.assertEqual(item['sha256'],I.F.sha((self.root/'cli'/item['file']).read_bytes()))
        self.assertNotIn('<script',(self.root/'cli/intake.html').read_text())


if __name__=='__main__': unittest.main()
