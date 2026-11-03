import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
import capture_audit as C
from test_gpt_audit import fixture


class CaptureAudit(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.raw=fixture(); (self.root/'capture.bin').write_bytes(self.raw)
        self.manifest=dict(schema='openjibo.readonly-capture-bundle.v1',sourceRevision='a'*40,os='windows',architecture='x86_64',protocol=C.A.PROTOCOL,files=[])
        for role,name in (('host','shofel2_t124_readonly.exe'),('payload','emmc_server_readonly.bin'),('bootstrap','intermezzo.bin')):
            self.manifest['files'].append(dict(role=role,name=name,sha256='b'*64,sizeBytes=16))
        self.manifest_pin=self.save('manifest',self.manifest)
        self.plan=dict(schema='openjibo.readonly-capture-plan.v1',sourceRevision='a'*40,bundleSha256=self.manifest_pin,
                       kind='primary-gpt-prefix',startSector=0,sectorCount=34,timeoutSeconds=30)
        self.plan_pin=self.save('plan',self.plan)
        self.receipt=dict(schema='openjibo.readonly-capture-receipt.v1',sourceRevision='a'*40,kind='primary-gpt-prefix',outcome='completed',captureCompleted=True,
                          captureDispatchAttempted=True,readyForApply=False,timeoutSeconds=30,manifest=self.manifest,plan=self.plan,
                          bundleSha256=self.manifest_pin,planSha256=self.plan_pin,manifestCanonicalSha256=C.A.P.digest(self.manifest),planCanonicalSha256=C.A.P.digest(self.plan),
                          processes=[dict(exitCode=0),dict(exitCode=0)],artifact=dict(file='capture.bin',sizeBytes=len(self.raw),sha256=C.G.hashlib.sha256(self.raw).hexdigest()))

    def save(self,name,value):
        raw=json.dumps(value).encode(); (self.root/(name+'.json')).write_bytes(raw); return C.G.hashlib.sha256(raw).hexdigest()

    def audit(self):
        return C.audit(self.root/'receipt.json',self.save('receipt',self.receipt),self.root/'manifest.json',self.manifest_pin,
                       self.root/'plan.json',self.plan_pin,4096)

    def test_completed_capture_joins_pins_and_gpt_checks_without_process_or_authority(self):
        with patch.object(subprocess,'Popen',side_effect=AssertionError('no process')): result=self.audit()
        self.assertTrue(result['primaryGptChecksPassed']); self.assertTrue(result['captureEvidence']['captureReceiptChecked'])
        for key in ('readyForApply','backupGptVerified','deviceIdentityVerified','deviceWritesPerformed'): self.assertFalse(result[key])

    def test_full_bytes_do_not_admit_failed_partial_or_different_receipt(self):
        original=copy.deepcopy(self.receipt)
        for key,value in (('outcome','timeout'),('captureCompleted',False),('captureDispatchAttempted',False),('kind','ext-csd'),
                          ('bundleSha256','b'*64),('planCanonicalSha256','b'*64),('processes',[dict(exitCode=0),dict(exitCode=1)]),
                          ('incompleteArtifact',dict(file='work/capture.bin',admitted=False)),('manifest',{})):
            self.receipt=copy.deepcopy(original); self.receipt[key]=value
            with self.subTest(key=key), self.assertRaises((ValueError,C.A.CaptureFailure)): self.audit()

    def test_relocated_substituted_truncated_and_invalid_gpt_bytes_refused(self):
        original=copy.deepcopy(self.receipt)
        for name in ('../capture.bin','work/capture.bin','other.bin'):
            self.receipt=copy.deepcopy(original); self.receipt['artifact']['file']=name
            with self.assertRaises((ValueError,C.A.CaptureFailure)): self.audit()
        self.receipt=original
        for raw in (self.raw[:-1],b'Z'*len(self.raw)):
            (self.root/'capture.bin').write_bytes(raw)
            with self.assertRaises((ValueError,C.A.CaptureFailure)): self.audit()
        self.receipt['artifact']['sha256']=C.G.hashlib.sha256(b'Z'*len(self.raw)).hexdigest()
        with self.assertRaises(ValueError): self.audit()

    def test_raw_receipt_and_original_input_pins_are_required(self):
        self.save('receipt',self.receipt)
        with self.assertRaises(C.A.CaptureFailure):
            C.audit(self.root/'receipt.json','b'*64,self.root/'manifest.json',self.manifest_pin,self.root/'plan.json',self.plan_pin,4096)
        (self.root/'plan.json').write_bytes(b'{}')
        with self.assertRaises(C.A.CaptureFailure): self.audit()


if __name__=='__main__': unittest.main()
