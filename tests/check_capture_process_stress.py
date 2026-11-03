"""Repeat synthetic diagnostic floods with bounded, path-free failure observations."""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--source-revision',required=True)
    parser.add_argument('--iterations',type=int,default=100)
    args=parser.parse_args(); assert 1<=args.iterations<=100
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    import test_capture_adapter as fixture
    A=fixture.A
    root=args.output.absolute(); root.mkdir(mode=0o700,exist_ok=False)
    allowed={'capture_adapter.py','capture_process.py','recovery_evidence.py','subprocess.py','pathlib.py'}
    rows=[]; unexpected=[]; deadline=time.monotonic()+180
    for index in range(args.iterations):
        assert time.monotonic()<deadline
        case=fixture.CaptureAdapter(); case.setUp()
        observations=deque(maxlen=16); owned=[]; launcher=case.launcher
        def tracking(mode):
            start=launcher(mode)
            def run(*argv,**kwargs):
                process=start(*argv,**kwargs); owned.append(process); return process
            return run
        case.launcher=tracking
        def trace(frame,event,arg):
            if event=='exception' and isinstance(arg[1],(OSError,ValueError,RuntimeError)):
                filename=Path(frame.f_code.co_filename).name
                if filename in allowed:
                    error=arg[1]; number=getattr(error,'errno',None)
                    observations.append(dict(file=filename,function=frame.f_code.co_name,line=frame.f_lineno,
                        errorType='os-error' if isinstance(error,OSError) else 'value-error' if isinstance(error,ValueError) else 'runtime-error',
                        errorNumber=number if type(number) is int and -4096<=number<=4096 else None))
            return trace
        previous=sys.gettrace()
        try:
            sys.settrace(trace)
            try: receipt=case.capture('diagnostic-limit')
            finally: sys.settrace(previous)
            processes=receipt['processes']
            okay=receipt['outcome']=='diagnostic-limit' and not receipt['captureCompleted'] and receipt['captureDispatchAttempted'] and len(processes)==2
            okay=okay and all(p.get('cleanup',{}).get('checksPassed') is True and p['cleanup']['parentReaped'] and p['cleanup']['drainsFinished'] for p in processes)
            serialized=json.dumps(receipt); assert 'DO_NOT_ECHO' not in serialized and str(case.root) not in serialized
            assert all(not p['stderr']['rawDiagnosticsRetained'] and p['stderr']['observedBytes']<=(4097 if position==0 else 8193) and
                       p['stdout']['observedBytes']<=(4097 if position==0 else 16385) for position,p in enumerate(processes))
            path=root/('case-'+str(index).zfill(3)+'.json'); A.P.export(receipt,path)
            row=dict(iteration=index,outcome=receipt['outcome'],file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                     diagnosticLimitAndCleanupPassed=bool(okay))
            rows.append(row)
            if not okay:
                unexpected.append(dict(iteration=index,outcome=receipt['outcome'],observations=list(observations)))
                break  # Fail the first unexpected result; never retry a capture to hide it.
        finally:
            sys.settrace(previous)
            # Independent test-harness cleanup of our Python fixtures only.
            for process in owned:
                if process.poll() is None: process.kill()
                process.wait(timeout=2)
            case.doCleanups()
    copied=root/'reviewed-source'; copied.mkdir()
    for name in ('capture_adapter.py','capture_process.py','recovery_evidence.py','conversion_plan.py'):
        shutil.copyfile(Path(A.__file__).with_name(name),copied/name)
    for source in (Path(__file__),Path(fixture.__file__),Path(__file__).parent/'fixtures/capture_process_fixture.py'):
        shutil.copyfile(source,copied/source.name)
    proof=dict(schema='openjibo.synthetic-process-stress.v1',sourceRevision=args.source_revision,requestedIterations=args.iterations,
               completedIterations=len(rows),cases=rows,unexpected=unexpected,allExpected=not unexpected and len(rows)==args.iterations,
               originalMacIncidentRootCauseResolved=False,scope='Synthetic Python process/pipe fixtures only; no native loader, USB or hardware',
               files=[dict(file=p.relative_to(root).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(copied.iterdir())],
               deviceWritesPerformed=False,readyForApply=False)
    (root/'proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    if not proof['allExpected']: raise SystemExit('Synthetic process stress failed; retain sanitized proof and inspect the first unexpected case.')
    print('Synthetic process stress passed: '+str(len(rows))+' diagnostic floods, bounded diagnostics and cleanup checks; original macOS root cause unproven.')


if __name__=='__main__': main()
