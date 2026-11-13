"""Bounded native process supervision. No device or platform-loader imports."""
import hashlib
import errno
import os
from pathlib import Path
import signal
import stat
import subprocess
import threading
import time


class ProcessFailure(Exception):
    def __init__(self, code, summary=None):
        super().__init__(code)
        self.code = code
        self.summary = summary or {}


class WindowsJob:
    """Kill-on-close job for the reviewed native host and any descendants."""
    def __init__(self):
        self.handle = None
        if os.name != 'nt': return
        import ctypes as C
        from ctypes import wintypes as W
        class Basic(C.Structure):
            _fields_ = [('processTime', C.c_longlong), ('jobTime', C.c_longlong), ('flags', W.DWORD),
                        ('minWorking', C.c_size_t), ('maxWorking', C.c_size_t), ('active', W.DWORD),
                        ('affinity', C.c_size_t), ('priority', W.DWORD), ('scheduling', W.DWORD)]
        class Counters(C.Structure):
            _fields_ = [(name, C.c_ulonglong) for name in ('readOps','writeOps','otherOps','readBytes','writeBytes','otherBytes')]
        class Extended(C.Structure):
            _fields_ = [('basic', Basic), ('io', Counters), ('processMemory', C.c_size_t),
                        ('jobMemory', C.c_size_t), ('peakProcess', C.c_size_t), ('peakJob', C.c_size_t)]
        self.api = C.WinDLL('kernel32', use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [C.c_void_p, W.LPCWSTR]; self.api.CreateJobObjectW.restype = W.HANDLE
        self.api.SetInformationJobObject.argtypes = [W.HANDLE, C.c_int, C.c_void_p, W.DWORD]
        self.api.SetInformationJobObject.restype = W.BOOL
        self.api.AssignProcessToJobObject.argtypes = [W.HANDLE, W.HANDLE]; self.api.AssignProcessToJobObject.restype = W.BOOL
        self.api.CloseHandle.argtypes = [W.HANDLE]; self.api.CloseHandle.restype = W.BOOL
        class ThreadEntry(C.Structure):
            _fields_=[('size',W.DWORD),('usage',W.DWORD),('threadId',W.DWORD),('processId',W.DWORD),
                      ('basePriority',W.LONG),('deltaPriority',W.LONG),('flags',W.DWORD)]
        self.thread_type=ThreadEntry; self.ctypes=C
        self.api.CreateToolhelp32Snapshot.argtypes=[W.DWORD,W.DWORD]; self.api.CreateToolhelp32Snapshot.restype=W.HANDLE
        self.api.Thread32First.argtypes=[W.HANDLE,C.POINTER(ThreadEntry)]; self.api.Thread32First.restype=W.BOOL
        self.api.Thread32Next.argtypes=[W.HANDLE,C.POINTER(ThreadEntry)]; self.api.Thread32Next.restype=W.BOOL
        self.api.OpenThread.argtypes=[W.DWORD,W.BOOL,W.DWORD]; self.api.OpenThread.restype=W.HANDLE
        self.api.ResumeThread.argtypes=[W.HANDLE]; self.api.ResumeThread.restype=W.DWORD
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle: raise ProcessFailure('process-containment-failed')
        info = Extended(); info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, C.byref(info), C.sizeof(info)):
            self.close(); raise ProcessFailure('process-containment-failed')

    def attach(self, process):
        if self.handle and not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ProcessFailure('process-containment-failed')

    def close(self):
        if self.handle:
            if not self.api.CloseHandle(self.handle): return False
            self.handle = None
        return True

    def resume(self,process):
        if not self.handle: return
        # Popen closes its primary thread handle. Enumerate our still-suspended
        # child's thread, after assigning the job and before any user code runs.
        snapshot=self.api.CreateToolhelp32Snapshot(4,0)  # TH32CS_SNAPTHREAD
        if snapshot in (None,self.ctypes.c_void_p(-1).value): raise ProcessFailure('process-containment-failed')
        try:
            entry=self.thread_type(); entry.size=self.ctypes.sizeof(entry)
            found=self.api.Thread32First(snapshot,self.ctypes.byref(entry))
            while found:
                if entry.processId==process.pid:
                    thread=self.api.OpenThread(2,False,entry.threadId)  # THREAD_SUSPEND_RESUME
                    if not thread: raise ProcessFailure('process-containment-failed')
                    try:
                        if self.api.ResumeThread(thread)==0xffffffff: raise ProcessFailure('process-containment-failed')
                        return
                    finally: self.api.CloseHandle(thread)
                found=self.api.Thread32Next(snapshot,self.ctypes.byref(entry))
            raise ProcessFailure('process-containment-failed')
        finally: self.api.CloseHandle(snapshot)


DIAGNOSTIC_CODES = frozenset((
    'handshake-command-transfer-failed', 'handshake-reply-transfer-failed',
    'handshake-protocol-refused', 'handshake-version-refused',
    'handshake-limits-refused', 'handshake-controller-uninitialized',
    'handshake-sector-zero-read-failed', 'handshake-startup-status-refused',
    'exit-transfer-failed',
    'full-capacity-command-failed', 'full-capacity-frame-refused', 'full-capacity-data-failed',
    'full-capacity-invalid', 'full-capacity-mismatch', 'full-read-command-failed',
    'full-read-frame-refused', 'full-read-data-failed', 'full-output-write-failed', 'full-output-sync-failed',
))
DIAGNOSTIC_LINES = {b'OPENJIBO_CAPTURE_DIAGNOSTIC='+code.encode('ascii'): code
                    for code in DIAGNOSTIC_CODES}


class DiagnosticCodes:
    """Recognize complete exact allowlisted lines; discard every other byte."""
    def __init__(self):
        self.codes = set()
        self.pending = bytearray()
        self.overflow = False

    def feed(self, block):
        for value in block:
            if value == 10:
                if not self.overflow:
                    line = bytes(self.pending)
                    if line.endswith(b'\r'): line = line[:-1]
                    code = DIAGNOSTIC_LINES.get(line)
                    if code is not None: self.codes.add(code)
                self.pending.clear(); self.overflow = False
            elif not self.overflow:
                if len(self.pending) < 128: self.pending.append(value)
                else: self.pending.clear(); self.overflow = True

    def finish(self):
        # Unterminated or partial markers are not admitted.
        self.pending.clear(); self.overflow = False


class Drain:
    def __init__(self, stream, limit, retain):
        self.stream = stream; self.limit = limit; self.retain = retain
        self.bytes = bytearray(); self.count = 0; self.sha = hashlib.sha256()
        self.diagnostics = DiagnosticCodes()
        self.lock = threading.Lock()
        self.exceeded = threading.Event(); self.finished = threading.Event()
        self.error = False
        self.thread = threading.Thread(target=self.read, daemon=True)
        self.thread.start()

    def read(self):
        try:
            while True:
                block = self.stream.read(4096)
                if not block: break
                with self.lock:
                    remaining = max(0, self.limit-self.count)
                    self.sha.update(block[:remaining])
                    self.diagnostics.feed(block[:remaining])
                    if self.retain: self.bytes.extend(block[:remaining])
                    self.count = min(self.limit+1, self.count+len(block))
                    if self.count > self.limit: self.exceeded.set()
        except (OSError, ValueError): self.error = True
        finally:
            try: self.stream.close()
            except (OSError, ValueError): self.error = True
            finally:
                with self.lock: self.diagnostics.finish()
                self.finished.set()

    def summary(self):
        with self.lock:
            return dict(observedBytes=self.count, limitExceeded=self.exceeded.is_set(),
                        boundedSha256=self.sha.hexdigest(), rawDiagnosticsRetained=False,
                        diagnosticCodes=sorted(self.diagnostics.codes))


def failure_details(error,phase):
    number=getattr(error,'errno',None)
    kind='timeout' if isinstance(error,subprocess.TimeoutExpired) else 'interrupted' if isinstance(error,KeyboardInterrupt) else \
         'os-error' if isinstance(error,OSError) else 'value-error' if isinstance(error,ValueError) else 'runtime-error' if isinstance(error,RuntimeError) else 'other-error'
    return dict(phase=phase,errorType=kind,errorNumber=number if type(number) is int and -4096<=number<=4096 else None)


def cleanup(process,job,stdout,stderr):
    """Attempt every owned cleanup step; never replace the primary failure."""
    result=dict(scope='windows-job' if os.name=='nt' else 'posix-process-group',groupTerminationRequested=False,
                parentTerminationRequested=False,parentReaped=False,parentExitCode=None,drainsFinished=False,
                groupAbsenceCheckRequested=False,groupAbsenceVerified=False,interrupted=False,errors=[],failures=[])
    group_failure=None
    def attempt(code,operation):
        try: return True,operation()
        except (Exception,KeyboardInterrupt) as error:
            result['errors'].append(code)
            result['failures'].append(dict(failure_details(error,code),resolved=False))
            if isinstance(error,KeyboardInterrupt): result['interrupted']=True
            return False,None
    if job is not None:
        closed,value=attempt('job-close-failed',job.close)
        if closed and value is False:
            result['errors'].append('job-close-failed')
            result['failures'].append(dict(phase='job-close-failed',errorType='not-confirmed',errorNumber=None,resolved=False))
        if os.name=='nt' and process is not None: result['groupTerminationRequested']=True
    if process is not None:
        if os.name!='nt':
            result['groupTerminationRequested']=True
            def terminate_group():
                try: os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError: pass
            signalled,_=attempt('group-termination-failed',terminate_group)
            if not signalled:
                observed=result['failures'][-1]
                if observed['errorType']=='os-error' and observed['errorNumber']==errno.EPERM: group_failure=observed
        polled,code=attempt('parent-poll-failed',process.poll)
        if not polled or code is None:
            result['parentTerminationRequested']=True
            def terminate_parent():
                try: process.kill()
                except ProcessLookupError: pass
            attempt('parent-termination-failed',terminate_parent)
        reaped,code=attempt('parent-reap-failed',lambda:process.wait(timeout=2))
        result['parentReaped']=reaped and type(code) is int
        result['parentExitCode']=code if result['parentReaped'] else None
        if reaped and not result['parentReaped']: result['errors'].append('parent-reap-unconfirmed')
        if group_failure is not None and result['parentReaped']:
            # Darwin can return EPERM for a zombie-only group. Never assume an
            # EPERM is harmless: first reap the known parent, then require ESRCH
            # from a signal-0 existence probe. A present/denied group still fails.
            result['groupAbsenceCheckRequested']=True
            def group_absent():
                try: os.killpg(process.pid,0)
                except ProcessLookupError: return True
                return False
            queried,absent=attempt('group-absence-check-failed',group_absent)
            if queried and absent:
                result['groupAbsenceVerified']=True
                result['errors'].remove('group-termination-failed')
                group_failure.update(resolved=True,resolution='group-absent-after-parent-reap')
    finished=[]
    for name,drain in [('stdout',stdout),('stderr',stderr)]:
        if drain is not None:
            waited,done=attempt(name+'-wait-failed',lambda:drain.finished.wait(timeout=0.2))
            finished.append(waited and bool(done))
            if not waited or not done: result['errors'].append(name+'-not-finished')
            if drain.error: result['errors'].append(name+'-drain-failed')
        elif process is not None:
            stream=getattr(process,name,None)
            if stream is not None: attempt(name+'-close-failed',stream.close)
    result['drainsFinished']=all(finished)
    result['checksPassed']=not result['errors']
    return result


def run(argv, cwd, environment, deadline, cancellation=None, output=None, expected_size=None, capabilities=False):
    """Deadline includes exit and pipe EOF; diagnostic contents never enter summaries."""
    process = None; job = None; stdout = None; stderr = None
    failure=None; completed=False; phase='admission'; system_error=None
    def summary():
        value=dict(exitCode=process.returncode if process else None,
                   stdout=stdout.summary() if stdout else None,stderr=stderr.summary() if stderr else None,
                   cleanup=cleanup_result)
        if system_error is not None: value['systemError']=system_error
        return value
    try:
        if cancellation is not None and cancellation.is_set(): raise ProcessFailure('cancelled')
        if time.monotonic() >= deadline: raise ProcessFailure('timeout')
        phase='containment-create'; job = WindowsJob()
        options = dict(cwd=str(cwd), env=environment, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0, shell=False, close_fds=True)
        if os.name == 'nt': options['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP | 4  # CREATE_SUSPENDED
        else: options['start_new_session'] = True
        phase='spawn'; process = subprocess.Popen([str(value) for value in argv], **options)
        phase='containment-attach'; job.attach(process)
        if cancellation is not None and cancellation.is_set(): raise ProcessFailure('cancelled')
        if time.monotonic() >= deadline: raise ProcessFailure('timeout')
        phase='containment-resume'; job.resume(process)
        phase='stdout-drain-start'; stdout = Drain(process.stdout, 4096 if capabilities else 16384, capabilities)
        phase='stderr-drain-start'; stderr = Drain(process.stderr, 4096 if capabilities else 8192, False)
        while True:
            phase='monitor'
            if cancellation is not None and cancellation.is_set(): raise ProcessFailure('cancelled')
            if time.monotonic() >= deadline: raise ProcessFailure('timeout')
            if stdout.exceeded.is_set() or stderr.exceeded.is_set(): raise ProcessFailure('diagnostic-limit')
            if output is not None:
                phase='output-check'
                try: info = Path(output).lstat()
                except FileNotFoundError: info = None
                if info is not None and (not stat.S_ISREG(info.st_mode) or
                    getattr(info, 'st_file_attributes', 0) & 1024 or info.st_size > expected_size):
                    raise ProcessFailure('output-invalid')
            phase='poll'; code = process.poll()
            if code is not None and stdout.finished.is_set() and stderr.finished.is_set():
                if time.monotonic() >= deadline: raise ProcessFailure('timeout')
                if cancellation is not None and cancellation.is_set(): raise ProcessFailure('cancelled')
                if stdout.exceeded.is_set() or stderr.exceeded.is_set(): raise ProcessFailure('diagnostic-limit')
                if stdout.error or stderr.error: raise ProcessFailure('diagnostic-read-failed')
                if code != 0: raise ProcessFailure('process-failed')
                completed=True; break
            phase='poll-wait'; time.sleep(0.02)
    except KeyboardInterrupt:
        failure=ProcessFailure('cancelled')
    except ProcessFailure as error:
        failure=error
    except (OSError,ValueError,RuntimeError) as error:
        system_error=failure_details(error,phase)
        failure=ProcessFailure('process-start-failed' if process is None else 'process-supervision-failed')
    finally:
        cleanup_result=cleanup(process,job,stdout,stderr)
    if failure is None:
        if cleanup_result['interrupted'] or cancellation is not None and cancellation.is_set(): failure=ProcessFailure('cancelled')
        elif not cleanup_result['checksPassed']: failure=ProcessFailure('process-cleanup-failed')
        elif time.monotonic()>=deadline: failure=ProcessFailure('timeout')
        elif not completed: failure=ProcessFailure('process-supervision-failed')
    if failure is not None:
        failure.summary=summary(); raise failure from None
    return dict(summary=summary(),stdout=bytes(stdout.bytes) if capabilities else None)
