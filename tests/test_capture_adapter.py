import copy
import hashlib
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
import capture_adapter as A


class CaptureAdapter(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name).resolve(); self.bundle=self.root/'bundle'; self.bundle.mkdir()
        system,arch=A.context(); host='shofel2_t124_readonly.exe' if system=='windows' else 'shofel2_t124_readonly'
        files=[]
        for role,name in [('host',host),('payload','emmc_server_readonly.bin'),('bootstrap','intermezzo.bin')]:
            data=('synthetic '+role).encode(); (self.bundle/name).write_bytes(data)
            files.append(dict(role=role,name=name,sha256=hashlib.sha256(data).hexdigest(),sizeBytes=len(data)))
        self.manifest=dict(schema='openjibo.readonly-capture-bundle.v1',sourceRevision='a'*40,os=system,architecture=arch,protocol=A.PROTOCOL,files=files)
        self.plan=dict(schema='openjibo.readonly-capture-plan.v1',sourceRevision='a'*40,bundleSha256='',kind='primary-gpt-prefix',startSector=0,sectorCount=34,timeoutSeconds=5)
        self.manifest_path=self.root/'manifest.json'; self.plan_path=self.root/'plan.json'; self.output=self.root/'capture'
        self.real_popen=subprocess.Popen

    def inputs(self):
        self.manifest_path.write_text(json.dumps(self.manifest),encoding='utf-8')
        manifest_pin=hashlib.sha256(self.manifest_path.read_bytes()).hexdigest()
        self.plan['bundleSha256']=manifest_pin
        self.plan_path.write_text(json.dumps(self.plan),encoding='utf-8')
        return (self.manifest_path,manifest_pin,self.plan_path,hashlib.sha256(self.plan_path.read_bytes()).hexdigest(),self.bundle)

    def launcher(self,mode):
        def start(argv,**kwargs):
            # Test-only link replacement at Popen. Production has no interpreter/
            # custom launcher option and can execute only its staged native host.
            self.assertEqual(Path(argv[0]).name,self.manifest['files'][0]['name'])
            kwargs['env']={**kwargs['env'],'CAPTURE_FIXTURE_MODE':mode}
            return self.real_popen([sys.executable,'-I','-B',str(Path(__file__).parent/'fixtures/capture_process_fixture.py'),*argv[1:]],**kwargs)
        return start

    def capture(self,mode='success',cancellation=None):
        values=self.inputs()
        with patch.object(A.N.subprocess,'Popen',side_effect=self.launcher(mode)):
            return A.capture(*values,self.output,cancellation)

    def test_inspection_checks_pins_and_never_launches_any_process(self):
        with patch.object(A.N.subprocess,'Popen',side_effect=AssertionError('process must not launch')):
            value=A.inspect(*self.inputs())
        self.assertTrue(value['fileHashesMatched']); self.assertFalse(value['processLaunched']); self.assertFalse(self.output.exists())

    def test_success_records_exact_hashes_and_no_device_or_apply_claim(self):
        receipt=self.capture()
        self.assertEqual('completed',receipt['outcome']); self.assertTrue(receipt['captureCompleted'])
        data=(self.output/'capture.bin').read_bytes(); self.assertEqual(b'Z'*(34*512),data)
        self.assertEqual(hashlib.sha256(data).hexdigest(),receipt['artifact']['sha256'])
        self.assertTrue(receipt['deviceStateUncertain'])
        for field in ('readyForApply','deviceIdentityVerified','resetVerified','robotCompatibilityVerified','storageWriteCommandsRequested'):
            self.assertIs(False,receipt[field])
        serialized=json.dumps(receipt); self.assertNotIn(str(self.root),serialized)
        self.assertNotIn('DO_NOT_ECHO',serialized)
        self.assertEqual(receipt,json.loads((self.output/'receipt.json').read_bytes()))
        self.assertEqual(A.P.digest(self.plan),receipt['planCanonicalSha256'])

    def test_ext_csd_uses_fixed_command_and_exact_512_bytes(self):
        self.plan.update(kind='ext-csd',sectorCount=1)
        value=self.capture(); self.assertTrue(value['captureCompleted']); self.assertEqual(512,value['artifact']['sizeBytes'])

    def test_failed_process_keeps_full_file_incomplete(self):
        value=self.capture('exit-failure')
        self.assertEqual('process-failed',value['outcome']); self.assertFalse(value['captureCompleted'])
        self.assertEqual(34*512,(self.output/'work/capture.bin').stat().st_size)
        self.assertFalse(value['incompleteArtifact']['admitted']); self.assertFalse((self.output/'capture.bin').exists())

    def test_missing_short_or_oversized_outputs_never_complete(self):
        for index,mode in enumerate(('missing-output','short-output','long-output')):
            self.output=self.root/('case-'+str(index))
            with self.subTest(mode=mode): self.assertFalse(self.capture(mode)['captureCompleted'])

    def test_capability_substitution_duplicate_fields_and_float_types_refuse_before_dispatch(self):
        for index,mode in enumerate(('wrong-capabilities','duplicate-capabilities','float-capabilities')):
            self.output=self.root/('case-'+str(index))
            with self.subTest(mode=mode):
                result=self.capture(mode)
                self.assertEqual('capabilities-rejected',result['outcome']); self.assertFalse(result['captureDispatchAttempted'])

    def test_changed_staged_component_invalidates_capture(self):
        value=self.capture('change-component'); self.assertFalse(value['captureCompleted'])
        self.assertTrue(value['captureDispatchAttempted']); self.assertFalse((self.output/'capture.bin').exists())

    def test_component_change_during_capability_check_refuses_before_read(self):
        value=self.capture('cap-change-component')
        self.assertFalse(value['captureCompleted']); self.assertFalse(value['captureDispatchAttempted'])
        self.assertFalse((self.output/'work/capture.bin').exists())

    def test_diagnostic_flood_is_bounded_and_contents_are_discarded(self):
        value=self.capture('diagnostic-limit')
        self.assertEqual('diagnostic-limit',value['outcome']); self.assertFalse(value['captureCompleted'])
        self.assertNotIn('DO_NOT_ECHO',json.dumps(value)); self.assertFalse(value['processes'][-1]['stderr']['rawDiagnosticsRetained'])
        self.assertLessEqual(value['processes'][-1]['stderr']['observedBytes'],8193)

    def test_whole_budget_includes_capabilities_and_read_process(self):
        self.plan['timeoutSeconds']=1
        started=time.monotonic(); result=self.capture('timeout')
        self.assertEqual('timeout',result['outcome']); self.assertLess(time.monotonic()-started,4)
        self.assertFalse(result['captureCompleted']); self.assertTrue(result['captureDispatchAttempted'])
        self.assertTrue((self.output/'work/capture.bin').exists())

    def test_capability_timeout_does_not_dispatch_a_read(self):
        self.plan['timeoutSeconds']=1
        result=self.capture('cap-timeout')
        self.assertEqual('timeout',result['outcome']); self.assertFalse(result['captureDispatchAttempted'])

    def test_cancellation_terminates_running_capture(self):
        cancellation=threading.Event(); stop=threading.Event()
        def cancel_after_dispatch():
            end=time.monotonic()+3
            while time.monotonic()<end and not stop.wait(0.01):
                if (self.output/'work/capture.bin').exists(): cancellation.set(); return
            cancellation.set()
        watcher=threading.Thread(target=cancel_after_dispatch,daemon=True); watcher.start()
        try: result=self.capture('timeout',cancellation)
        finally: stop.set(); watcher.join(timeout=1)
        self.assertEqual('cancelled',result['outcome']); self.assertFalse(result['captureCompleted'])

    def test_existing_output_is_preserved_before_any_process_launch(self):
        self.output.mkdir(); marker=self.output/'preserved'; marker.write_bytes(b'keep')
        with patch.object(A.N.subprocess,'Popen',side_effect=AssertionError('must not launch')):
            with self.assertRaises(FileExistsError): A.capture(*self.inputs(),self.output)
        self.assertEqual(b'keep',marker.read_bytes())

    def test_pre_cancelled_capture_never_creates_output_or_starts_process(self):
        event=threading.Event(); event.set()
        with patch.object(A.N.subprocess,'Popen',side_effect=AssertionError('must not launch')):
            with self.assertRaisesRegex(A.CaptureFailure,'cancelled'): A.capture(*self.inputs(),self.output,event)
        self.assertFalse(self.output.exists())

    def test_supervision_waits_for_pipe_eof_and_terminates_descendants(self):
        drains=[]; original=A.N.Drain
        def observe(*args):
            drain=original(*args); drains.append(drain); return drain
        try:
            with patch.object(A.N,'Drain',side_effect=observe):
                with self.assertRaises(A.N.ProcessFailure) as failed:
                    A.N.run([sys.executable,'-I','-B',str(Path(__file__).parent/'fixtures/capture_process_fixture.py'),'--child-holder'],
                            self.root,A.environment(self.root),time.monotonic()+1)
            self.assertEqual('timeout',failed.exception.code)
            self.assertTrue(all(drain.finished.wait(0.5) for drain in drains))
        finally:
            file=self.root/'child.pid'
            if file.exists() and not all(d.finished.is_set() for d in drains):
                try: os.kill(int(file.read_text()),signal.SIGTERM)
                except OSError: pass

    def test_missing_or_changed_bundle_file_refuses_before_output_or_process(self):
        values=self.inputs(); (self.bundle/'emmc_server_readonly.bin').write_bytes(b'corrupt')
        with patch.object(A.N.subprocess,'Popen',side_effect=AssertionError('must not launch')):
            with self.assertRaises(A.CaptureFailure): A.capture(*values,self.output)
        self.assertFalse(self.output.exists())

    def test_strict_manifest_and_plan_cannot_widen_source_protocol_or_ranges(self):
        original_manifest=copy.deepcopy(self.manifest); original_plan=copy.deepcopy(self.plan)
        cases=[('manifest',dict(protocol='legacy')),('manifest',dict(os='foreign')),('manifest',dict(architecture='foreign')),
               ('manifest',dict(command='EMMC_WRITE')),('plan',dict(startSector=1)),('plan',dict(sectorCount=True)),
               ('plan',dict(sectorCount=4097)),('plan',dict(kind='arbitrary-read')),('plan',dict(timeoutSeconds=61)),
               ('plan',dict(timeoutSeconds=True)),('plan',dict(sourceRevision='b'*40))]
        for target,changes in cases:
            self.manifest=copy.deepcopy(original_manifest); self.plan=copy.deepcopy(original_plan)
            getattr(self,target).update(changes)
            with self.subTest(target=target,changes=changes),self.assertRaises((A.CaptureFailure,ValueError)): A.inspect(*self.inputs())

    def test_manifest_rejects_missing_payload_runtime_collisions_paths_and_wrong_types(self):
        original=copy.deepcopy(self.manifest)
        for mode in ('missing','role-type','duplicate','path','reserved','runtime-script'):
            self.manifest=copy.deepcopy(original)
            if mode=='missing': self.manifest['files'].pop()
            elif mode=='role-type': self.manifest['files'][0]['role']=[]
            elif mode=='duplicate': self.manifest['files'].append(copy.deepcopy(self.manifest['files'][0]))
            elif mode=='path': self.manifest['files'][0]['name']='../host'
            elif mode=='reserved': self.manifest['files'][0]['name']='CON.exe'
            else: self.manifest['files'].append(dict(role='runtime',name='launch.py',sha256='a'*64,sizeBytes=10))
            with self.subTest(mode=mode),self.assertRaises((A.CaptureFailure,ValueError)): A.inspect(*self.inputs())

    def test_cli_inspection_and_invalid_pin_never_execute_fake_host_or_echo_paths(self):
        values=self.inputs()
        command=[sys.executable,'-I','-B',str(Path(A.__file__)),'inspect','--manifest',str(values[0]),'--manifest-sha256',values[1],
                 '--plan',str(values[2]),'--plan-sha256',values[3],'--bundle',str(values[4])]
        good=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(0,good.returncode,good.stderr); self.assertNotIn(str(self.root),good.stdout)
        command[command.index('--manifest-sha256')+1]='0'*64
        bad=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(2,bad.returncode); self.assertNotIn(str(self.root),bad.stderr); self.assertNotIn('Traceback',bad.stderr)


if __name__=='__main__': unittest.main()
