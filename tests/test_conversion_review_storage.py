import copy
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
import conversion_review as V
import test_conversion_review as base
import test_storage_evidence as storage_fixture
from test_gpt_audit import recalculate


def fixture(inputs,isolated=False):
    values=base.fixture(inputs,isolated)
    prefix=bytearray((inputs/'gpt-prefix.bin').read_bytes())
    config=(inputs/'jetstream.json').read_bytes()
    images={'jetstream':storage_fixture.filesystem('jetstream',config),
            'credentials':storage_fixture.filesystem('credentials',b'{"region":"api","privateKey":"STORAGE_PRIVATE_KEY_FIXTURE"}')}
    disk=bytearray((inputs/'full-storage.bin').read_bytes())
    for index,(role,raw) in enumerate(images.items(),2):
        name='services-test' if role=='jetstream' else 'var-test'
        offset=1024+index*128; start=64+index*128
        prefix[offset:offset+16]=b't'*16; prefix[offset+16:offset+32]=bytes([index+1])*16
        struct.pack_into('<QQ',prefix,offset+32,start,start+127)
        prefix[offset+56:offset+128]=name.encode('utf-16le').ljust(72,b'\0')
        disk[start*512:start*512+len(raw)]=raw
    prefix=recalculate(prefix); disk[:len(prefix)]=prefix
    (inputs/'gpt-prefix.bin').write_bytes(prefix); (inputs/'full-storage.bin').write_bytes(disk)
    values['firewallInput']['gptPrefix']=dict(sha256=base.digest(prefix),sizeBytes=len(prefix))
    full=next(b for b in values['inventory']['backups'] if b['kind']=='full-storage'); full['sha256']=base.digest(disk)
    values['audit']=V.G.audit_file(inputs/'gpt-prefix.bin',4096,base.digest(prefix))
    values['inventory']['auditEvidenceSha256']=base.digest(base.raw_json(values['audit']))
    values['storageInput']=dict(schema='openjibo.storage-file-input.v1',diskSectors=4096,
                                fullStorage={k:full[k] for k in ('sha256','sizeBytes')},gptPrefix=values['firewallInput']['gptPrefix'].copy(),
                                partitions={'jetstream':'services-test','credentials':'var-test'},
                                jetstream=values['endpointInput']['jetstream'].copy(),credentialsRegion='api')
    return values


class StorageBoundReview(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); self.inputs=self.root/'inputs'; self.output=self.root/'review'
        self.path=self.root/'review-input.json'; self.values=fixture(self.inputs)

    def build(self):
        pin=base.write_inputs(self.inputs,self.values,self.path)
        return V.build(self.path,pin,self.inputs,self.output)

    def test_v2_recomputes_storage_and_indexes_redacted_evidence_and_html(self):
        base.write_inputs(self.inputs,self.values,self.path)
        before={p.name:base.digest(p.read_bytes()) for p in self.inputs.iterdir()}
        with patch.object(subprocess,'Popen',side_effect=AssertionError('no subprocess')): result=self.build()
        self.assertEqual(result['schema'],'openjibo.conversion-review-bundle.v2')
        for flag in ('storageFileEvidenceRecomputed','jetstreamBackupBytesMatched','credentialRegionBackupBytesMatched'):
            self.assertTrue(result[flag])
        evidence=json.loads((self.output/'storage/evidence.json').read_bytes())
        self.assertEqual(result['storageEvidenceCanonicalSha256'],V.P.digest(evidence))
        self.assertEqual(result['storageFileSummary']['credentialsRegion'],'api')
        self.assertEqual(evidence['fullStorage'],self.values['storageInput']['fullStorage'])
        self.assertEqual(evidence['manifestSha256'],result['inputFilePins']['storageInput'])
        self.assertEqual(result['storageFileSummary']['files'],evidence['files'])
        self.assertEqual(before,{p.name:base.digest(p.read_bytes()) for p in self.inputs.iterdir()})
        for item in result['files']:
            self.assertEqual(base.digest((self.output/item['file']).read_bytes()),item['sha256'])
        self.assertIn('storage/evidence.json',[item['file'] for item in result['files']])
        page=(self.output/'review.html').read_text(encoding='utf-8')
        self.assertIn('Config bytes and region matched; runtime mounts unverified',page)
        self.assertIn('storage/evidence.json',page)
        for raw in (V.P.canonical(result),(self.output/'storage/evidence.json').read_bytes(),page.encode()):
            self.assertNotIn(b'STORAGE_PRIVATE_KEY_FIXTURE',raw); self.assertNotIn(b'PRIVATE_INPUT_FIXTURE',raw)

    def test_byte_matches_leave_mount_release_device_and_apply_unverified(self):
        result=self.build()
        for flag in ('mountMappingVerified','endpointStoragePathAssociationVerified','credentialsRegionAssociationVerified',
                     'physicalDeviceAssociationVerified','releaseCompatibilityVerified','calibrationDeviceAssociationVerified',
                     'completeFilesystemIntegrityVerified','completeConversionPlan','executionSupported','readyForApply','restoreTested'):
            self.assertFalse(result[flag])
        self.assertIn('verified-mount-mapping-and-installed-release',result['requiredBeforeApply'])
        self.assertNotIn('jetstream-filesystem-path-and-credentials-region-to-backup-unverified',result['requiredBeforeApply'])

    def test_cross_component_pins_and_region_cannot_diverge(self):
        original=copy.deepcopy(self.values)
        for case in ('full-hash','full-size','prefix','geometry','jetstream','region'):
            self.values=copy.deepcopy(original); item=self.values['storageInput']
            if case=='full-hash': item['fullStorage']['sha256']='0'*64
            elif case=='full-size': item['fullStorage']['sizeBytes']-=512
            elif case=='prefix': item['gptPrefix']['sha256']='0'*64
            elif case=='geometry': item['diskSectors']-=1
            elif case=='jetstream': item['jetstream']['sha256']='0'*64
            else: item['credentialsRegion']='us'
            with self.subTest(case=case),self.assertRaises(ValueError): self.build()
            self.assertFalse(self.output.exists())

    def test_standalone_positive_report_is_not_an_input(self):
        self.values['storageInput']=dict(schema='openjibo.storage-file-evidence.v1',evidenceComplete=True,readyForApply=True)
        with self.assertRaises(ValueError): self.build()
        self.assertFalse(self.output.exists())

    def test_v2_requires_storage_pin_and_v1_rejects_extra_pin(self):
        pin=base.write_inputs(self.inputs,self.values,self.path)
        manifest=json.loads(self.path.read_bytes()); del manifest['files']['storageInput']
        raw=base.raw_json(manifest); self.path.write_bytes(raw)
        with self.assertRaises(ValueError): V.build(self.path,base.digest(raw),self.inputs,self.output)
        base.write_inputs(self.inputs,self.values,self.path)
        manifest=json.loads(self.path.read_bytes()); manifest['schema']='openjibo.conversion-review-input.v1'
        raw=base.raw_json(manifest); self.path.write_bytes(raw)
        with self.assertRaises(ValueError): V.build(self.path,base.digest(raw),self.inputs,self.output)

    def test_credential_mismatch_inside_rehashed_backup_is_refused(self):
        self.mutate_backup((448*512+13*1024),b'{"region":"bad","privateKey":"STORAGE_PRIVATE_KEY_FIXTURE"}')
        with self.assertRaises(ValueError): self.build()
        self.assertFalse(self.output.exists())

    def mutate_backup(self,offset,data):
        path=self.inputs/'full-storage.bin'; raw=bytearray(path.read_bytes()); raw[offset:offset+len(data)]=data; path.write_bytes(raw)
        pin=base.digest(raw)
        next(b for b in self.values['inventory']['backups'] if b['kind']=='full-storage')['sha256']=pin
        self.values['storageInput']['fullStorage']['sha256']=pin

    def test_storage_config_mismatch_even_with_all_outer_pins_updated_is_refused(self):
        path=self.inputs/'jetstream.json'; raw=path.read_bytes()+b'\n'; path.write_bytes(raw)
        for item in (self.values['endpointInput'],self.values['storageInput']):
            item['jetstream']=dict(sha256=base.digest(raw),sizeBytes=len(raw))
        with self.assertRaises(ValueError): self.build()
        self.assertFalse(self.output.exists())

    def test_wrong_partition_mapping_and_unsupported_filesystem_refused(self):
        original=copy.deepcopy(self.values['storageInput'])
        self.values['storageInput']['partitions']={'jetstream':'rootfsA','credentials':'var-test'}
        with self.assertRaises((ValueError,V.S.F.E.Ext4PathError)): self.build()
        self.values['storageInput']=original
        self.mutate_backup(448*512+1024+58,b'\0\0')
        with self.assertRaises(ValueError): self.build()
        self.assertFalse(self.output.exists())

    def test_shared_checked_reader_used_without_reopening_backup_in_storage_component(self):
        with patch.object(V.S.F,'retained_image',side_effect=AssertionError('duplicate full backup hash')):
            result=self.build()
        self.assertTrue(result['storageFileEvidenceRecomputed'])

    def test_storage_mutation_during_endpoint_component_refuses_terminal_review(self):
        original=V.E.preview
        def changed(*args):
            result=original(*args)
            path=self.inputs/'full-storage.bin'
            with path.open('r+b') as stream: stream.seek(-1,2); stream.write(b'X'); stream.flush()
            return result
        with patch.object(V.E,'preview',side_effect=changed),self.assertRaises(ValueError): self.build()
        self.assertFalse((self.output/'review.json').exists())

    def test_storage_component_error_prevents_terminal_and_partial_success(self):
        with patch.object(V.S,'inspect_reader',side_effect=ValueError('fixture failure')),self.assertRaises(ValueError): self.build()
        self.assertFalse(self.output.exists())

    def test_isolated_mode_cli_runs_outside_checkout_and_requires_terminal_index(self):
        self.values['target'].update(mode='isolated',providerId='self-hosted',apiOrigin='http://192.168.50.20:9000')
        self.values['endpointInput'].update(targetSha256=base.digest(base.raw_json(self.values['target'])),hubOrigin='http://hub.local:9001',allowIsolatedHttp=True)
        pin=base.write_inputs(self.inputs,self.values,self.path)
        command=[sys.executable,'-I','-B',str(Path(V.__file__)),'--manifest',str(self.path),'--manifest-sha256',pin,'--inputs',str(self.inputs),'--output',str(self.output)]
        result=subprocess.run(command,cwd=self.root,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        review=json.loads((self.output/'review.json').read_bytes())
        self.assertEqual(json.loads(result.stdout)['reviewSha256'],V.P.digest(review))
        self.assertTrue(review['storageFileEvidenceRecomputed']); self.assertFalse(review['readyForApply'])


if __name__=='__main__': unittest.main()
