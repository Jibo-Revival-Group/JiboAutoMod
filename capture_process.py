"""Bounded native process supervision. No device or platform-loader imports."""
import hashlib
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
            self.api.CloseHandle(self.handle); self.handle = None

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


class Drain:
    def __init__(self, stream, limit, retain):
        self.stream = stream; self.limit = limit; self.retain = retain
        self.bytes = bytearray(); self.count = 0; self.sha = hashlib.sha256()
        self.exceeded = threading.Event(); self.finished = threading.Event()
        self.error = False
        self.thread = threading.Thread(target=self.read, daemon=True)
        self.thread.start()

    def read(self):
        try:
            while True:
                block = self.stream.read(4096)
                if not block: break
                remaining = max(0, self.limit-self.count)
                self.sha.update(block[:remaining])
                if self.retain: self.bytes.extend(block[:remaining])
                self.count = min(self.limit+1, self.count+len(block))
                if self.count > self.limit: self.exceeded.set()
        except (OSError, ValueError): self.error = True
        finally:
            self.stream.close(); self.finished.set()

    def summary(self):
        return dict(observedBytes=self.count, limitExceeded=self.exceeded.is_set(),
                    boundedSha256=self.sha.hexdigest(), rawDiagnosticsRetained=False)


def run(argv, cwd, environment, deadline, cancellation=None, output=None, expected_size=None, capabilities=False):
    """Deadline includes exit and pipe EOF; diagnostic contents never enter summaries."""
    process = None; job = None; stdout = None; stderr = None
    def summary():
        return dict(exitCode=process.poll() if process else None,
                    stdout=stdout.summary() if stdout else None, stderr=stderr.summary() if stderr else None)
    try:
        if cancellation is not None and cancellation.is_set(): raise ProcessFailure('cancelled')
        if time.monotonic() >= deadline: raise ProcessFailure('timeout')
        job = WindowsJob()
        options = dict(cwd=str(cwd), env=environment, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0, shell=False, close_fds=True)
        if os.name == 'nt': options['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP | 4  # CREATE_SUSPENDED
        else: options['start_new_session'] = True
        process = subprocess.Popen([str(value) for value in argv], **options)
        job.attach(process)
        if cancellation is not None and cancellation.is_set(): raise ProcessFailure('cancelled')
        if time.monotonic() >= deadline: raise ProcessFailure('timeout')
        job.resume(process)
        stdout = Drain(process.stdout, 4096 if capabilities else 16384, capabilities)
        stderr = Drain(process.stderr, 4096 if capabilities else 8192, False)
        while True:
            if cancellation is not None and cancellation.is_set(): raise ProcessFailure('cancelled')
            if time.monotonic() >= deadline: raise ProcessFailure('timeout')
            if stdout.exceeded.is_set() or stderr.exceeded.is_set(): raise ProcessFailure('diagnostic-limit')
            if output is not None:
                try: info = Path(output).lstat()
                except FileNotFoundError: info = None
                if info is not None and (not stat.S_ISREG(info.st_mode) or
                    getattr(info, 'st_file_attributes', 0) & 1024 or info.st_size > expected_size):
                    raise ProcessFailure('output-invalid')
            code = process.poll()
            if code is not None and stdout.finished.is_set() and stderr.finished.is_set():
                if time.monotonic() >= deadline: raise ProcessFailure('timeout')
                if cancellation is not None and cancellation.is_set(): raise ProcessFailure('cancelled')
                if stdout.exceeded.is_set() or stderr.exceeded.is_set(): raise ProcessFailure('diagnostic-limit')
                if stdout.error or stderr.error: raise ProcessFailure('diagnostic-read-failed')
                if code != 0: raise ProcessFailure('process-failed')
                return dict(summary=summary(), stdout=bytes(stdout.bytes) if capabilities else None)
            time.sleep(0.02)
    except KeyboardInterrupt:
        raise ProcessFailure('cancelled', summary()) from None
    except ProcessFailure as error:
        error.summary = summary(); raise
    except OSError:
        raise ProcessFailure('process-start-failed', summary()) from None
    finally:
        # Closing a Windows job kills all members. A POSIX session gives this
        # reviewed native process a unique group, including inherited pipe holders.
        if job is not None: job.close()
        if process is not None:
            if os.name != 'nt':
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            elif process.poll() is None:
                process.kill()
            try: process.wait(timeout=2)
            except subprocess.TimeoutExpired: pass
            for drain in (stdout, stderr):
                if drain is not None: drain.finished.wait(timeout=0.2)
            if stdout is None and process.stdout is not None: process.stdout.close()
            if stderr is None and process.stderr is not None: process.stderr.close()
