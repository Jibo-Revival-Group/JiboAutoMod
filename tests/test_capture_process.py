import io
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
import capture_process as N


class DiagnosticParsing(unittest.TestCase):
    def test_all_codes_accept_only_complete_exact_lines_across_every_split(self):
        for code in N.DIAGNOSTIC_CODES:
            for ending in (b'\n',b'\r\n'):
                raw=b'OPENJIBO_CAPTURE_DIAGNOSTIC='+code.encode()+ending
                for split in range(len(raw)+1):
                    parser=N.DiagnosticCodes(); parser.feed(raw[:split]); parser.feed(raw[split:])
                    parser.finish(); self.assertEqual(parser.codes,{code})
                    self.assertEqual(parser.pending,bytearray())

    def test_unknown_embedded_long_truncated_and_non_ascii_lines_are_discarded(self):
        marker=b'OPENJIBO_CAPTURE_DIAGNOSTIC=handshake-reply-transfer-failed'
        for raw in (b'private '+marker+b'\n',marker+b' private\n',marker,
                    marker+b'\r\r\n',marker+b'\xff\n',b'x'*129+marker+b'\n',
                    b'OPENJIBO_CAPTURE_DIAGNOSTIC=unknown\n'):
            parser=N.DiagnosticCodes(); parser.feed(raw); parser.finish()
            self.assertEqual(parser.codes,set()); self.assertEqual(parser.pending,bytearray())

    def test_overflow_recovers_at_newline_and_codes_are_bounded_and_deduplicated(self):
        parser=N.DiagnosticCodes(); parser.feed(b'x'*8192+b'\n')
        marker=b'OPENJIBO_CAPTURE_DIAGNOSTIC=exit-transfer-failed\n'
        parser.feed(marker*1000); parser.finish()
        self.assertEqual(parser.codes,{'exit-transfer-failed'})

    def test_drain_records_codes_with_counts_hashes_and_no_raw_bytes(self):
        raw=b'DO_NOT_ECHO_PRIVATE\nOPENJIBO_CAPTURE_DIAGNOSTIC=handshake-command-transfer-failed\n'
        drain=N.Drain(io.BytesIO(raw),8192,False); self.assertTrue(drain.finished.wait(2))
        value=drain.summary(); self.assertEqual(value['diagnosticCodes'],['handshake-command-transfer-failed'])
        self.assertEqual(drain.bytes,bytearray()); self.assertNotIn('DO_NOT_ECHO',json.dumps(value))

    def test_markers_beyond_diagnostic_budget_are_not_admitted(self):
        raw=b'x'*20+b'\nOPENJIBO_CAPTURE_DIAGNOSTIC=exit-transfer-failed\n'
        drain=N.Drain(io.BytesIO(raw),20,False); self.assertTrue(drain.finished.wait(2))
        self.assertTrue(drain.exceeded.is_set()); self.assertEqual(drain.summary()['diagnosticCodes'],[])


class FakeProcess:
    pid=12345
    def __init__(self,flood=True):
        self.stdout=io.BytesIO(b'')
        self.stderr=io.BytesIO(b'DO_NOT_ECHO_PRIVATE_DIAGNOSTIC'*4096 if flood else b'')
        self.returncode=None if flood else 0
        self.waits=0; self.killed=False
    def poll(self): return self.returncode
    def kill(self): self.killed=True; self.returncode=-9
    def wait(self,timeout): self.waits+=1; return self.returncode


class FakeJob:
    def attach(self,process): pass
    def resume(self,process): pass
    def close(self): return True


class CaptureProcess(unittest.TestCase):
    def execute(self,process,job=None,killpg=None,system='posix',launcher=None,drain=None):
        namespace=SimpleNamespace(name=system,killpg=killpg or (lambda *_:None))
        with patch.object(N,'os',namespace),patch.object(N,'signal',SimpleNamespace(SIGKILL=9)),\
             patch.object(N,'WindowsJob',return_value=job or FakeJob()),\
             patch.object(N.subprocess,'CREATE_NEW_PROCESS_GROUP',512,create=True),\
             patch.object(N.subprocess,'Popen',side_effect=launcher or (lambda *_,**__:process)),\
             patch.object(N,'Drain',side_effect=drain or N.Drain):
            return N.run(['synthetic-host'],Path.cwd(),{},time.monotonic()+2)

    def test_group_kill_error_keeps_original_failure_and_still_reaps_parent(self):
        process=FakeProcess()
        def failed_group(*_): raise OSError(1,'DO_NOT_ECHO_PRIVATE_TERMINATION')
        local_os=SimpleNamespace(name='posix',killpg=failed_group)
        with patch.object(N,'os',local_os),patch.object(N,'signal',SimpleNamespace(SIGKILL=9)),patch.object(N,'WindowsJob',FakeJob),patch.object(N.subprocess,'Popen',return_value=process):
            with self.assertRaises(N.ProcessFailure) as caught:
                N.run(['synthetic-host'],Path.cwd(),{},time.monotonic()+2)
        self.assertEqual(caught.exception.code,'diagnostic-limit')
        self.assertTrue(process.killed); self.assertEqual(process.waits,1)
        self.assertNotIn('DO_NOT_ECHO',json.dumps(caught.exception.summary))
        cleanup=caught.exception.summary['cleanup']
        self.assertFalse(cleanup['checksPassed']); self.assertTrue(cleanup['parentReaped'])
        self.assertIn('group-termination-failed',cleanup['errors'])
        self.assertEqual(cleanup['failures'][0]['errorNumber'],1)

    def test_job_close_error_does_not_skip_parent_cleanup_or_mask_diagnostic_limit(self):
        class BrokenJob(FakeJob):
            def close(self): raise OSError(5,'DO_NOT_ECHO_PRIVATE_CLOSE')
        process=FakeProcess()
        with self.assertRaises(N.ProcessFailure) as caught: self.execute(process,job=BrokenJob())
        self.assertEqual(caught.exception.code,'diagnostic-limit'); self.assertTrue(process.killed); self.assertEqual(process.waits,1)
        self.assertIn('job-close-failed',caught.exception.summary['cleanup']['errors'])
        self.assertNotIn('DO_NOT_ECHO',json.dumps(caught.exception.summary))

    def test_success_is_not_returned_when_cleanup_fails(self):
        def failed_group(*_): raise OSError(1,'DO_NOT_ECHO')
        process=FakeProcess(False)
        with self.assertRaises(N.ProcessFailure) as caught: self.execute(process,killpg=failed_group)
        self.assertEqual(caught.exception.code,'process-cleanup-failed'); self.assertEqual(process.waits,1)
        self.assertEqual(caught.exception.summary['exitCode'],0)
        self.assertTrue(caught.exception.summary['cleanup']['parentReaped'])

    def test_windows_close_false_is_an_explicit_failure(self):
        class UnconfirmedJob(FakeJob):
            def close(self): return False
        process=FakeProcess(False)
        with self.assertRaises(N.ProcessFailure) as caught: self.execute(process,job=UnconfirmedJob(),system='nt')
        self.assertEqual(caught.exception.code,'process-cleanup-failed')
        self.assertEqual(caught.exception.summary['cleanup']['scope'],'windows-job'); self.assertEqual(process.waits,1)

    def test_pipe_close_error_signals_finished_and_is_not_success(self):
        class BrokenClose(io.BytesIO):
            def close(self):
                super().close(); raise OSError(5,'DO_NOT_ECHO_PRIVATE_PIPE')
        process=FakeProcess(False); process.stderr=BrokenClose(b'')
        with self.assertRaises(N.ProcessFailure) as caught: self.execute(process)
        self.assertEqual(caught.exception.code,'diagnostic-read-failed')
        self.assertTrue(caught.exception.summary['cleanup']['drainsFinished'])
        self.assertIn('stderr-drain-failed',caught.exception.summary['cleanup']['errors'])
        self.assertNotIn('DO_NOT_ECHO',json.dumps(caught.exception.summary))

    def test_spawn_error_reports_only_static_phase_type_and_errno(self):
        def refused(*_,**__): raise OSError(11,'DO_NOT_ECHO_PRIVATE_SPAWN')
        with self.assertRaises(N.ProcessFailure) as caught: self.execute(None,launcher=refused)
        self.assertEqual(caught.exception.code,'process-start-failed')
        self.assertEqual(caught.exception.summary['systemError'],dict(phase='spawn',errorType='os-error',errorNumber=11))
        self.assertNotIn('DO_NOT_ECHO',json.dumps(caught.exception.summary))

    def test_poll_value_error_still_kills_and_reaps_parent(self):
        class BadPoll(FakeProcess):
            def poll(self): raise ValueError('DO_NOT_ECHO_PRIVATE_POLL')
        process=BadPoll(False)
        with self.assertRaises(N.ProcessFailure) as caught: self.execute(process)
        self.assertEqual(caught.exception.code,'process-supervision-failed')
        self.assertEqual(caught.exception.summary['systemError'],dict(phase='poll',errorType='value-error',errorNumber=None))
        self.assertTrue(process.killed); self.assertEqual(process.waits,1)
        self.assertTrue(caught.exception.summary['cleanup']['parentReaped'])

    def test_reap_timeout_does_not_hide_primary_error_or_skip_pipe_checks(self):
        class BadWait(FakeProcess):
            def wait(self,timeout): self.waits+=1; raise subprocess.TimeoutExpired('DO_NOT_ECHO_PRIVATE_COMMAND',timeout)
        process=BadWait()
        with self.assertRaises(N.ProcessFailure) as caught: self.execute(process)
        self.assertEqual(caught.exception.code,'diagnostic-limit')
        cleanup=caught.exception.summary['cleanup']; self.assertFalse(cleanup['parentReaped']); self.assertTrue(cleanup['drainsFinished'])
        self.assertTrue(any(row['phase']=='parent-reap-failed' and row['errorType']=='timeout' for row in cleanup['failures']))
        self.assertNotIn('DO_NOT_ECHO',json.dumps(caught.exception.summary))

    def test_partial_drain_start_failure_closes_unowned_pipe_and_reaps(self):
        original=N.Drain; calls=[]
        def fail_second(*args):
            calls.append(1)
            if len(calls)==2: raise RuntimeError('DO_NOT_ECHO_PRIVATE_THREAD')
            return original(*args)
        process=FakeProcess(False)
        with self.assertRaises(N.ProcessFailure) as caught: self.execute(process,drain=fail_second)
        self.assertEqual(caught.exception.code,'process-supervision-failed')
        self.assertEqual(caught.exception.summary['systemError'],dict(phase='stderr-drain-start',errorType='runtime-error',errorNumber=None))
        self.assertTrue(process.stderr.closed); self.assertEqual(process.waits,1)

    def test_cleanup_interrupt_still_reaps_and_prevents_success(self):
        class InterruptedJob(FakeJob):
            def close(self): raise KeyboardInterrupt()
        process=FakeProcess(False)
        with self.assertRaises(N.ProcessFailure) as caught: self.execute(process,job=InterruptedJob())
        self.assertEqual(caught.exception.code,'cancelled')
        self.assertTrue(caught.exception.summary['cleanup']['interrupted']); self.assertEqual(process.waits,1)

    def test_permission_error_resolved_only_by_absence_after_parent_reap(self):
        calls=[]; process=FakeProcess(False)
        def signal_group(pid,signal):
            calls.append(signal)
            if signal==9: raise PermissionError(1,'DO_NOT_ECHO')
            self.assertEqual(process.waits,1)
            raise ProcessLookupError(3,'DO_NOT_ECHO')
        result=self.execute(process,killpg=signal_group)
        cleanup=result['summary']['cleanup']
        self.assertEqual(calls,[9,0]); self.assertTrue(cleanup['checksPassed']); self.assertTrue(cleanup['groupAbsenceVerified'])
        self.assertEqual(cleanup['errors'],[]); self.assertTrue(cleanup['failures'][0]['resolved'])
        self.assertEqual(cleanup['failures'][0]['resolution'],'group-absent-after-parent-reap')

    def test_present_group_does_not_resolve_permission_failure(self):
        def signal_group(pid,signal):
            if signal==9: raise PermissionError(1,'DO_NOT_ECHO')
        with self.assertRaises(N.ProcessFailure) as caught: self.execute(FakeProcess(False),killpg=signal_group)
        self.assertEqual(caught.exception.code,'process-cleanup-failed')
        cleanup=caught.exception.summary['cleanup']; self.assertTrue(cleanup['groupAbsenceCheckRequested']); self.assertFalse(cleanup['groupAbsenceVerified'])
        self.assertIn('group-termination-failed',cleanup['errors'])

    def test_denied_absence_probe_remains_a_failure(self):
        def signal_group(pid,signal): raise PermissionError(1 if signal==9 else 13,'DO_NOT_ECHO')
        with self.assertRaises(N.ProcessFailure) as caught: self.execute(FakeProcess(False),killpg=signal_group)
        cleanup=caught.exception.summary['cleanup']; self.assertFalse(cleanup['groupAbsenceVerified'])
        self.assertIn('group-termination-failed',cleanup['errors']); self.assertIn('group-absence-check-failed',cleanup['errors'])
        self.assertNotIn('DO_NOT_ECHO',json.dumps(caught.exception.summary))

    def test_permission_error_not_resolved_when_parent_reap_is_unconfirmed(self):
        calls=[]
        def signal_group(pid,signal): calls.append(signal); raise PermissionError(1,'DO_NOT_ECHO')
        class BadWait(FakeProcess):
            def wait(self,timeout): raise subprocess.TimeoutExpired('DO_NOT_ECHO',timeout)
        with self.assertRaises(N.ProcessFailure) as caught: self.execute(BadWait(False),killpg=signal_group)
        cleanup=caught.exception.summary['cleanup']; self.assertFalse(cleanup['groupAbsenceCheckRequested']); self.assertFalse(cleanup['parentReaped'])
        self.assertEqual(calls,[9]); self.assertIn('group-termination-failed',cleanup['errors'])

    def test_other_group_errors_are_not_resolved_by_a_probe(self):
        calls=[]
        def signal_group(pid,signal): calls.append(signal); raise OSError(5,'DO_NOT_ECHO')
        with self.assertRaises(N.ProcessFailure) as caught: self.execute(FakeProcess(False),killpg=signal_group)
        self.assertEqual(caught.exception.code,'process-cleanup-failed'); self.assertEqual(calls,[9])
        self.assertFalse(caught.exception.summary['cleanup']['groupAbsenceCheckRequested'])


if __name__=='__main__': unittest.main()
