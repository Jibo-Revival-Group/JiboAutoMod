import copy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
import conversion_review as V
import test_firewall_preview as firewall_fixture
import test_endpoint_preview as endpoint_fixture


def digest(raw): return hashlib.sha256(raw).hexdigest()
def raw_json(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()+b'\n'


def fixture(inputs,isolated=False):
    inputs.mkdir()
    prefix=firewall_fixture.prefix(); images={name:firewall_fixture.image() for name in V.F.PARTITIONS}
    storage=bytearray(4096*512); storage[:len(prefix)]=prefix
    for index,name in enumerate(V.F.PARTITIONS):
        start=(64+index*128)*512; storage[start:start+len(images[name])]=images[name]
        (inputs/(name+'.img')).write_bytes(images[name])
    (inputs/'gpt-prefix.bin').write_bytes(prefix); (inputs/'full-storage.bin').write_bytes(storage)
    (inputs/'calibration.bin').write_bytes(b'SYNTHETIC CALIBRATION ONLY')
    config=endpoint_fixture.config(); (inputs/'jetstream.json').write_bytes(raw_json(config))
    target=dict(schema='openjibo.conversion-target.v1',mode='managed',providerId='example-provider',apiOrigin='https://api.example.test:8443')
    hub='https://hub.example.test:9443'
    if isolated:
        target.update(mode='isolated',providerId='self-hosted',apiOrigin='http://192.168.50.20:9000'); hub='http://hub.local:9001'
    audit=V.G.audit_file(inputs/'gpt-prefix.bin',4096,digest(prefix))
    values=dict(inventory=dict(schema='openjibo.conversion-inventory.v1',deviceFingerprintSha256='a'*64,releaseFamily='v2',
                               observedAtUtc='2026-11-02T12:00:00Z',auditEvidenceSha256=digest(raw_json(audit)),
                               backups=[dict(kind=kind,sha256=digest((inputs/filename).read_bytes()),sizeBytes=(inputs/filename).stat().st_size)
                                        for kind,filename in [('calibration','calibration.bin'),('full-storage','full-storage.bin')]]),
                target=target,audit=audit,recoveryFiles=dict(schema='openjibo.recovery-files.v1',files=[dict(kind=kind,path=filename) for kind,filename in [('calibration','calibration.bin'),('full-storage','full-storage.bin')]]),
                firewallInput=dict(schema='openjibo.firewall-preview-input.v1',operation='enable',diskSectors=4096,
                                   gptPrefix=dict(sha256=digest(prefix),sizeBytes=len(prefix)),
                                   images=[dict(partition=name,sha256=digest(raw),sizeBytes=len(raw)) for name,raw in images.items()]),
                endpointInput=dict(schema='openjibo.endpoint-preview-input.v1',targetSha256=digest(raw_json(target)),
                                   jetstream=dict(sha256=digest(raw_json(config)),sizeBytes=len(raw_json(config))),credentialsRegion='api',
                                   hubOrigin=hub,allowIsolatedHttp=isolated,certificatePolicy='preserve-existing'))
    return values


def write_inputs(inputs,values,manifest_path):
    pins={}
    with_storage='storageInput' in values
    for name,filename in (V.INPUTS_V2 if with_storage else V.INPUTS).items():
        raw=raw_json(values[name]); (inputs/filename).write_bytes(raw); pins[name]=digest(raw)
    manifest=dict(schema='openjibo.conversion-review-input.v2' if with_storage else 'openjibo.conversion-review-input.v1',files=pins)
    raw=raw_json(manifest); manifest_path.write_bytes(raw); return digest(raw)


class ConversionReview(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); self.inputs=self.root/'inputs'; self.output=self.root/'review'
        self.path=self.root/'review-input.json'; self.values=fixture(self.inputs)

    def build(self):
        pin=write_inputs(self.inputs,self.values,self.path)
        return V.build(self.path,pin,self.inputs,self.output)

    def test_recomputes_components_binds_backup_ranges_and_preserves_inputs(self):
        write_inputs(self.inputs,self.values,self.path)
        before={p.name:digest(p.read_bytes()) for p in self.inputs.iterdir()}
        with patch.object(subprocess,'Popen',side_effect=AssertionError('no process')): result=self.build()
        self.assertTrue(result['reviewAssembled']); self.assertTrue(result['recoveryFilesMatchedInventory'])
        self.assertEqual([row['retainedFile'] for row in result['storageByteRelationships']],['gpt-prefix.bin','rootfsA.img','rootfsB.img'])
        self.assertEqual([row['fullStorageByteOffset'] for row in result['storageByteRelationships']],[0,64*512,192*512])
        self.assertEqual(before,{p.name:digest(p.read_bytes()) for p in self.inputs.iterdir()})
        for item in result['files']:
            raw=(self.output/item['file']).read_bytes(); self.assertEqual(digest(raw),item['sha256']); self.assertEqual(len(raw),item['sizeBytes'])
        self.assertFalse(any('full-storage.bin'==item['file'] for item in result['files']))
        for filename in ('preparation.json','recovery.json','gpt-audit.json','firewall/preview.json','endpoint/preview.json','review.html','review.json'): self.assertTrue((self.output/filename).is_file())

    def test_all_component_success_does_not_claim_complete_conversion_or_association(self):
        result=self.build()
        for flag in ('completeConversionPlan','executionSupported','readyForApply','endpointStoragePathAssociationVerified','credentialsRegionAssociationVerified',
                     'physicalDeviceAssociationVerified','releaseCompatibilityVerified','calibrationDeviceAssociationVerified','completeFilesystemIntegrityVerified','restoreTested','backupGptVerified','protectiveMbrVerified'):
            self.assertFalse(result[flag],flag)
        self.assertIn('jetstream-filesystem-path-and-credentials-region-to-backup-unverified',result['requiredBeforeApply'])
        self.assertNotIn('PRIVATE_INPUT_FIXTURE',json.dumps(result))

    def test_target_and_inventory_audit_references_must_match(self):
        self.values['target']['apiOrigin']='https://other.example.test'
        with self.assertRaises(ValueError): self.build()
        self.assertFalse(self.output.exists())
        self.values['target']['apiOrigin']='https://api.example.test:8443'; self.values['inventory']['auditEvidenceSha256']='b'*64
        with self.assertRaises(ValueError): self.build()

    def test_changed_full_backup_range_is_rejected_even_when_inventory_hash_is_updated(self):
        path=self.inputs/'full-storage.bin'; raw=bytearray(path.read_bytes()); raw[64*512+100]^=1; path.write_bytes(raw)
        next(item for item in self.values['inventory']['backups'] if item['kind']=='full-storage')['sha256']=digest(raw)
        with self.assertRaises(ValueError): self.build()
        self.assertFalse(self.output.exists())

    def test_standalone_rootfs_file_must_match_the_backup_bound_pin(self):
        path=self.inputs/'rootfsB.img'; raw=bytearray(path.read_bytes()); raw[-1]^=1; path.write_bytes(raw)
        with self.assertRaises(ValueError): self.build()
        self.assertFalse((self.output/'review.json').exists())

    def test_full_backup_mutation_during_components_prevents_terminal_review(self):
        original=V.E.preview
        def changed(*args):
            result=original(*args)
            with (self.inputs/'full-storage.bin').open('r+b') as stream:
                stream.seek(-1,2); stream.write(b'X'); stream.flush()
            return result
        with patch.object(V.E,'preview',side_effect=changed):
            with self.assertRaises(ValueError): self.build()
        self.assertFalse((self.output/'review.json').exists())

    def test_recovery_requires_actual_full_storage_and_calibration(self):
        for kind in ('full-storage','calibration'):
            original=copy.deepcopy(self.values['inventory']['backups'])
            self.values['inventory']['backups']=[item for item in original if item['kind']!=kind]
            with self.subTest(kind=kind),self.assertRaises(ValueError): self.build()
            self.values['inventory']['backups']=original
        (self.inputs/'calibration.bin').write_bytes(b'altered')
        with self.assertRaises(ValueError): self.build()

    def test_unsupported_external_recovery_paths_are_refused(self):
        self.values['recoveryFiles']['files'][0]['path']='../calibration.bin'
        with self.assertRaises(ValueError): self.build()
        self.assertFalse(self.output.exists())

    def test_supplied_audit_is_compared_to_current_gpt_checks(self):
        self.values['audit']['layout']['partitions'][0]['start_sector']+=1
        self.values['inventory']['auditEvidenceSha256']=digest(raw_json(self.values['audit']))
        with self.assertRaises(ValueError): self.build()
        self.values['audit']['deviceIdentityVerified']=True
        self.values['inventory']['auditEvidenceSha256']=digest(raw_json(self.values['audit']))
        with self.assertRaises(ValueError): self.build()

    def test_isolated_target_and_unknown_release_stay_reviewable_but_blocked(self):
        self.values['target'].update(mode='isolated',providerId='self-hosted',apiOrigin='http://192.168.50.20:9000')
        self.values['endpointInput'].update(targetSha256=digest(raw_json(self.values['target'])),hubOrigin='http://hub.local:9001',allowIsolatedHttp=True)
        self.values['inventory']['releaseFamily']='unknown'
        result=self.build(); self.assertIn('unknown-device-release-needs-audit',result['requiredBeforeApply'])
        self.assertFalse(result['readyForApply']); self.assertEqual(result['target']['mode'],'isolated')

    def test_existing_output_and_bad_root_pin_are_refused(self):
        self.output.mkdir(); (self.output/'keep').write_bytes(b'keep')
        with self.assertRaises(ValueError): self.build()
        self.assertEqual((self.output/'keep').read_bytes(),b'keep')
        with self.assertRaises(ValueError): V.build(self.path,'0'*64,self.inputs,self.root/'other')

    def test_human_review_is_static_escaped_and_omits_private_config(self):
        result=self.build(); raw=(self.output/'review.html').read_text(encoding='utf-8')
        self.assertIn('Apply unavailable',raw); self.assertNotIn('<script',raw); self.assertNotIn('PRIVATE_INPUT_FIXTURE',raw)
        self.assertNotIn(str(self.root),raw)
        unsafe=copy.deepcopy(result); unsafe['hubOrigin']='<script>alert(1)</script>'
        rendered=V.render(unsafe).decode(); self.assertIn('&lt;script&gt;',rendered); self.assertNotIn('<script>',rendered)
        class Links(HTMLParser):
            def __init__(self): super().__init__(); self.links=[]
            def handle_starttag(self,tag,attrs):
                if tag=='a': self.links.append(dict(attrs)['href'])
        parser=Links(); parser.feed(raw)
        self.assertEqual(len(parser.links),6)
        self.assertTrue(all((self.output/path).is_file() for path in parser.links))

    def test_cli_runs_from_unrelated_directory_without_exploit_or_network_imports(self):
        pin=write_inputs(self.inputs,self.values,self.path)
        command=[sys.executable,'-I','-B',str(Path(V.__file__)),'--manifest',str(self.path),'--manifest-sha256',pin,'--inputs',str(self.inputs),'--output',str(self.output)]
        result=subprocess.run(command,cwd=self.root,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr); self.assertNotIn(str(self.root),result.stdout+result.stderr)
        bad=subprocess.run([*command,'--unknown',str(self.root)],cwd=self.root,capture_output=True,text=True,timeout=10)
        self.assertEqual(bad.returncode,2); self.assertNotIn(str(self.root),bad.stdout+bad.stderr)
        probe=subprocess.run([sys.executable,'-I','-B','-c',"import runpy,sys; runpy.run_path(sys.argv[1],run_name='offline_probe'); assert not any(n.startswith(('Exploits','usb','tkinter','config')) for n in sys.modules)",str(Path(V.__file__))],cwd=self.root,capture_output=True,timeout=10)
        self.assertEqual(probe.returncode,0,probe.stderr)


if __name__=='__main__': unittest.main()
