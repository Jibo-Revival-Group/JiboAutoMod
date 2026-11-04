import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
import review_request as Q
import test_conversion_review as base
import test_conversion_review_storage as storage_fixture
from test_gpt_recovery import complete_disk


def add_recovery_tables(inputs, values):
    """Add synthetic GPT redundancy, then bind every existing input to new bytes."""
    prefix_path=inputs/'gpt-prefix.bin'; disk_path=inputs/'full-storage.bin'
    disk=complete_disk(prefix_path.read_bytes(),disk_path.read_bytes())
    prefix=disk[:prefix_path.stat().st_size]
    disk_path.write_bytes(disk); prefix_path.write_bytes(prefix)
    full=next(item for item in values['inventory']['backups'] if item['kind']=='full-storage')
    full['sha256']=base.digest(disk)
    values['firewallInput']['gptPrefix']['sha256']=base.digest(prefix)
    values['audit']=Q.V.G.audit_file(prefix_path,4096,base.digest(prefix))
    values['inventory']['auditEvidenceSha256']=base.digest(base.raw_json(values['audit']))
    if 'storageInput' in values:
        values['storageInput']['fullStorage']['sha256']=base.digest(disk)
        values['storageInput']['gptPrefix']['sha256']=base.digest(prefix)


class ConversionReviewGpt(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); self.inputs=self.root/'inputs'; self.output=self.root/'review'
        self.values=storage_fixture.fixture(self.inputs)
        add_recovery_tables(self.inputs,self.values)
        del self.values['storageInput']
        self.write_inputs()

    def write_inputs(self):
        base.write_inputs(self.inputs,self.values,self.root/'initial-v1.json')

    def build(self): return Q.build(self.inputs,self.output,'services-test','var-test',gpt_recovery=True)

    def test_v3_recomputes_pinned_backup_records_and_keeps_physical_gates(self):
        before={p.name:base.digest(p.read_bytes()) for p in self.inputs.iterdir()}
        with patch.object(subprocess,'Popen',side_effect=AssertionError('no process')): result=self.build()
        self.assertEqual(result['schema'],'openjibo.conversion-review-bundle.v3')
        self.assertTrue(result['backupGptVerified']); self.assertTrue(result['protectiveMbrVerified'])
        self.assertTrue(result['gptRecoveryEvidenceRecomputed']); self.assertTrue(result['storageFileEvidenceRecomputed'])
        proof=json.loads((self.output/'gpt-recovery.json').read_bytes())
        self.assertEqual(Q.V.P.digest(proof),result['gptRecoveryEvidenceCanonicalSha256'])
        self.assertEqual(proof['fullStorage']['sha256'],before['full-storage.bin'])
        manifest=json.loads((self.output/'request/review-input.json').read_bytes())
        self.assertEqual(manifest['schema'],'openjibo.conversion-review-input.v3')
        self.assertEqual(set(manifest['files']),set(Q.V.INPUTS_V2))
        self.assertNotIn('backup-gpt-and-protective-mbr-unverified',result['requiredBeforeApply'])
        self.assertIn('calibration-and-storage-acquisition-to-physical-device-unverified',result['requiredBeforeApply'])
        for key in ('physicalDeviceAssociationVerified','releaseCompatibilityVerified','calibrationDeviceAssociationVerified',
                    'completeFilesystemIntegrityVerified','restoreTested','executionSupported','completeConversionPlan','readyForApply',
                    'deviceWritesPerformed','networkRequestsPerformed'):
            self.assertIs(result[key],False)
        self.assertEqual(before,{p.name:base.digest(p.read_bytes()) for p in self.inputs.iterdir()})
        self.assertNotIn('STORAGE_PRIVATE_KEY_FIXTURE',json.dumps(result)+json.dumps(proof))
        for item in result['files']:
            self.assertEqual(base.digest((self.output/item['file']).read_bytes()),item['sha256'])
        page=(self.output/'review.html').read_text()
        self.assertIn('Backup GPT and protective MBR',page); self.assertIn('gpt-recovery.json',page)
        self.assertIn('Complete filesystem integrity and allocation checks.',page)
        self.assertIn('Apply unavailable',page)

    def test_v3_manifest_replays_with_identical_evidence_bindings(self):
        result=self.build()
        replay=Q.V.build(self.output/'request/review-input.json',result['manifestSha256'],self.inputs,
                         self.root/'replay',self.output/'request/storage-input.json')
        self.assertEqual(replay['schema'],result['schema']); self.assertEqual(replay['inputFilePins'],result['inputFilePins'])
        self.assertEqual(replay['storageFileSummary'],result['storageFileSummary'])
        self.assertTrue(replay['backupGptVerified']); self.assertTrue(replay['protectiveMbrVerified'])

    def test_v2_does_not_silently_gain_recovery_claims(self):
        result=Q.build(self.inputs,self.output,'services-test','var-test')
        self.assertEqual(result['schema'],'openjibo.conversion-review-bundle.v2')
        self.assertFalse(result['backupGptVerified']); self.assertFalse(result['protectiveMbrVerified'])
        self.assertNotIn('gptRecoveryEvidenceRecomputed',result)
        self.assertFalse((self.output/'gpt-recovery.json').exists())

    def test_new_full_backup_hash_cannot_legitimize_missing_backup_gpt_or_hybrid_mbr(self):
        original=(self.inputs/'full-storage.bin').read_bytes()
        for offset in (4095*512,4063*512,462):
            disk=bytearray(original); disk[offset]^=1; (self.inputs/'full-storage.bin').write_bytes(disk)
            full=next(item for item in self.values['inventory']['backups'] if item['kind']=='full-storage')
            full['sha256']=base.digest(disk)
            # For a changed MBR, update the retained prefix/audit too, so refusal
            # comes from the recovery check rather than stale input pins.
            if offset==462:
                prefix_path=self.inputs/'gpt-prefix.bin'; prefix=disk[:prefix_path.stat().st_size]; prefix_path.write_bytes(prefix)
                self.values['firewallInput']['gptPrefix']['sha256']=base.digest(prefix)
                self.values['audit']=Q.V.G.audit_file(prefix_path,4096,base.digest(prefix))
                self.values['inventory']['auditEvidenceSha256']=base.digest(base.raw_json(self.values['audit']))
            self.write_inputs()
            with self.subTest(offset=offset),self.assertRaises(ValueError): self.build()
            self.assertFalse(self.output.exists())

    def test_cli_explicit_v3_and_exclusive_output(self):
        args=[sys.executable,'-I','-B',str(Path(Q.__file__)),'--inputs',str(self.inputs),'--output',str(self.output),
              '--jetstream-partition','services-test','--credentials-partition','var-test','--gpt-recovery']
        first=subprocess.run(args,capture_output=True,text=True)
        self.assertEqual(first.returncode,0,first.stderr)
        saved=(self.output/'review.json').read_bytes()
        self.assertEqual(json.loads(saved)['schema'],'openjibo.conversion-review-bundle.v3')
        again=subprocess.run(args,capture_output=True,text=True)
        self.assertEqual(again.returncode,2); self.assertEqual(saved,(self.output/'review.json').read_bytes())
        self.assertNotIn(str(self.inputs),first.stdout+again.stderr)


if __name__=='__main__': unittest.main()
