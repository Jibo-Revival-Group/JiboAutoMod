#!/usr/bin/env python3
"""Inspect a pinned read-only bundle, or explicitly capture with a bounded native process."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import stat
import time


def sibling(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


R = sibling('recovery_evidence')
P = R.preparation
N = sibling('capture_process')
MAX_READ = 4096
UPPER_SECTORS = 0x1D60000
PROTOCOL = 'openjibo-emmc-readonly.v1'


class CaptureFailure(Exception):
    pass


def require(value):
    if not value: raise CaptureFailure('admission-refused')


def context():
    system = {'Windows':'windows', 'Linux':'linux', 'Darwin':'macos'}.get(platform.system())
    arch = {'amd64':'x86_64','x86_64':'x86_64','arm64':'arm64','aarch64':'arm64'}.get(platform.machine().lower())
    require(system is not None and arch is not None)
    return system, arch


def pinned_json(path, expected):
    require(type(expected) is str and P.HASH.fullmatch(expected))
    path = R.ordinary_path(path)
    original = path.lstat(); require(stat.S_ISREG(original.st_mode) and original.st_size <= P.LIMIT)
    flags = os.O_RDONLY | getattr(os,'O_BINARY',0) | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_NONBLOCK',0)
    with os.fdopen(os.open(str(path),flags),'rb') as source:
        before = os.fstat(source.fileno()); require(R.file_identity(before)==R.file_identity(original))
        raw = source.read(P.LIMIT+1)
        require(R.identity(before)==R.identity(os.fstat(source.fileno())))
    require(len(raw) <= P.LIMIT and hashlib.sha256(raw).hexdigest() == expected)
    return json.loads(raw.decode('utf-8'), object_pairs_hook=P.no_duplicates,
                      parse_constant=lambda _: require(False))


def validate(manifest, plan, manifest_pin, plan_pin):
    require(type(manifest_pin) is str and P.HASH.fullmatch(manifest_pin) and type(plan_pin) is str and P.HASH.fullmatch(plan_pin))
    P.exact(manifest, ('schema','sourceRevision','os','architecture','protocol','files'), 'manifest_fields')
    P.exact(plan, ('schema','sourceRevision','bundleSha256','kind','startSector','sectorCount','timeoutSeconds'), 'plan_fields')
    require(manifest['schema'] == 'openjibo.readonly-capture-bundle.v1' and plan['schema'] == 'openjibo.readonly-capture-plan.v1')
    require(type(manifest['sourceRevision']) is str and re.fullmatch(r'[0-9a-f]{40}', manifest['sourceRevision']))
    require(plan['sourceRevision'] == manifest['sourceRevision'] and plan['bundleSha256'] == manifest_pin)
    system, arch = context()
    require(manifest['os'] == system and manifest['architecture'] == arch and manifest['protocol'] == PROTOCOL)
    require(type(plan['timeoutSeconds']) is int and 1 <= plan['timeoutSeconds'] <= 60)
    require(type(plan['startSector']) is int and plan['startSector'] == 0 and type(plan['sectorCount']) is int)
    require((plan['kind'] == 'primary-gpt-prefix' and 34 <= plan['sectorCount'] <= MAX_READ) or
            (plan['kind'] == 'ext-csd' and plan['sectorCount'] == 1))
    require(type(manifest['files']) is list and 3 <= len(manifest['files']) <= 19)
    names = set(); roles = set(); total = 0
    fixed = dict(host='shofel2_t124_readonly.exe' if system == 'windows' else 'shofel2_t124_readonly',
                 payload='emmc_server_readonly.bin', bootstrap='intermezzo.bin')
    for item in manifest['files']:
        P.exact(item, ('role','name','sha256','sizeBytes'), 'component_fields')
        require(type(item['role']) is str and item['role'] in ('host','payload','bootstrap','runtime'))
        require(type(item['name']) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}', item['name']) and '..' not in item['name'])
        name = item['name'].casefold()
        require(name not in names and name.split('.')[0] not in ('con','prn','aux','nul',*[f'com{i}' for i in range(1,10)],*[f'lpt{i}' for i in range(1,10)]))
        names.add(name)
        require(type(item['sha256']) is str and P.HASH.fullmatch(item['sha256']))
        require(type(item['sizeBytes']) is int and 0 < item['sizeBytes'] <= 16777216)
        total += item['sizeBytes']; require(total <= 67108864)
        if item['role'] in fixed:
            require(item['role'] not in roles and item['name'] == fixed[item['role']]); roles.add(item['role'])
            if item['role'] == 'payload': require(item['sizeBytes'] <= 131072)
            if item['role'] == 'bootstrap': require(item['sizeBytes'] <= 256)
        else:
            require(item['role'] == 'runtime')
            require((system == 'windows' and name.endswith('.dll')) or
                    (system == 'macos' and name.endswith('.dylib')) or
                    (system == 'linux' and re.search(r'\.so(?:\.[0-9]+)*$', name)))
    require(roles == set(fixed))
    return dict(manifest=manifest, plan=plan, manifestSha256=manifest_pin, planSha256=plan_pin,
                host=fixed['host'], expectedBytes=plan['sectorCount']*512)


def check_budget(deadline, cancellation):
    if cancellation is not None and cancellation.is_set(): raise CaptureFailure('cancelled')
    if time.monotonic() >= deadline: raise CaptureFailure('timeout')


def check_file(path, item, deadline, cancellation, destination=None):
    check_budget(deadline, cancellation)
    path = R.ordinary_path(path); original = path.lstat()
    require(stat.S_ISREG(original.st_mode) and original.st_size == item['sizeBytes'])
    flags = os.O_RDONLY | getattr(os,'O_BINARY',0) | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_NONBLOCK',0)
    target = None
    try:
        with os.fdopen(os.open(str(path), flags), 'rb') as source:
            before = os.fstat(source.fileno()); require(R.file_identity(before) == R.file_identity(original))
            if destination is not None:
                descriptor = os.open(str(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os,'O_BINARY',0), 0o600)
                target = os.fdopen(descriptor, 'wb')
            digest = hashlib.sha256(); size = 0
            while True:
                check_budget(deadline, cancellation)
                block = source.read(min(1048576, item['sizeBytes']-size+1))
                if not block: break
                size += len(block); require(size <= item['sizeBytes']); digest.update(block)
                if target is not None: target.write(block)
            require(size == item['sizeBytes'] and ('sha256' not in item or digest.hexdigest() == item['sha256']))
            require(R.identity(before) == R.identity(os.fstat(source.fileno())))
        require(R.file_identity(before) == R.file_identity(R.ordinary_path(path).lstat()))
        if target is not None: target.flush(); os.fsync(target.fileno())
        return digest.hexdigest()
    finally:
        if target is not None: target.close()


def inputs(manifest_path, manifest_pin, plan_path, plan_pin):
    return validate(pinned_json(manifest_path, manifest_pin), pinned_json(plan_path, plan_pin), manifest_pin, plan_pin)


def inspect(manifest_path, manifest_pin, plan_path, plan_pin, bundle):
    admitted = inputs(manifest_path, manifest_pin, plan_path, plan_pin)
    deadline = time.monotonic()+admitted['plan']['timeoutSeconds']
    bundle = R.ordinary_path(bundle); require(bundle.is_dir())
    for item in admitted['manifest']['files']: check_file(bundle/item['name'], item, deadline, None)
    return dict(schema='openjibo.readonly-capture-inspection.v1', bundleSha256=manifest_pin, planSha256=plan_pin,
                fileHashesMatched=True, inputTrust='operator-pinned-not-provenance-authenticated',
                processLaunched=False, deviceIdentityVerified=False, readyForApply=False)


def environment(work):
    result = dict(LANG='C', LC_ALL='C')
    if os.name == 'nt':
        for key in ('SystemRoot','WINDIR'):
            if key in os.environ: result[key] = os.environ[key]
        require('SystemRoot' in result)
        result['PATH'] = str(work)+os.pathsep+str(Path(result['SystemRoot'])/'System32')
    else:
        result['PATH'] = '/usr/bin:/bin'
        result['DYLD_LIBRARY_PATH' if platform.system() == 'Darwin' else 'LD_LIBRARY_PATH'] = str(work)
    return result


def capabilities(raw):
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=P.no_duplicates, parse_constant=lambda _: require(False))
    P.exact(value, ('schema','protocol','commands','sectorSizeBytes','maxReadSectors','storageSectorUpperBound','payload'), 'capabilities_fields')
    require(all(type(value[key]) is int for key in ('sectorSizeBytes','maxReadSectors','storageSectorUpperBound')))
    require(value == dict(schema='openjibo.storage-readonly-capabilities.v1', protocol=PROTOCOL,
        commands=['EMMC_STATUS','EMMC_READ','EMMC_READ_EXT_CSD'],sectorSizeBytes=512,maxReadSectors=MAX_READ,
        storageSectorUpperBound=UPPER_SECTORS,payload='emmc_server_readonly.bin'))


def capture(manifest_path, manifest_pin, plan_path, plan_pin, bundle, output, cancellation=None):
    admitted = inputs(manifest_path, manifest_pin, plan_path, plan_pin)
    deadline = time.monotonic()+admitted['plan']['timeoutSeconds']
    bundle = R.ordinary_path(bundle); require(bundle.is_dir())
    for item in admitted['manifest']['files']: check_file(bundle/item['name'], item, deadline, cancellation)
    output = Path(output).absolute(); R.ordinary_path(output.parent)
    output.mkdir(mode=0o700, exist_ok=False)
    work = output/'work'; work.mkdir(mode=0o700)
    data = work/'capture.bin'
    receipt = dict(schema='openjibo.readonly-capture-receipt.v1',bundleSha256=manifest_pin,planSha256=plan_pin,
        startedAtUtc=datetime.now(timezone.utc).isoformat(),timeoutSeconds=admitted['plan']['timeoutSeconds'],
        sourceRevision=admitted['manifest']['sourceRevision'],kind=admitted['plan']['kind'],
        manifest=admitted['manifest'],plan=admitted['plan'],
        manifestCanonicalSha256=P.digest(admitted['manifest']),planCanonicalSha256=P.digest(admitted['plan']),
        outcome='not-started',captureDispatchAttempted=False,captureCompleted=False,readyForApply=False,
        deviceIdentityVerified=False,resetVerified=False,robotCompatibilityVerified=False,storageWriteCommandsRequested=False,
        inputTrust='operator-pinned-not-provenance-authenticated',processes=[],
        adapterSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        supervisorSha256=hashlib.sha256(Path(N.__file__).read_bytes()).hexdigest(),
        recoveryCheckerSha256=hashlib.sha256(Path(R.__file__).read_bytes()).hexdigest(),
        preparationParserSha256=hashlib.sha256(Path(P.__file__).read_bytes()).hexdigest())
    try:
        for item in admitted['manifest']['files']:
            check_file(bundle/item['name'],item,deadline,cancellation,work/item['name'])
        host = work/admitted['host']; host.chmod(0o700)
        child_env = environment(work)
        cap = N.run([host,'--capabilities'],work,child_env,deadline,cancellation,capabilities=True)
        receipt['processes'].append(cap['summary'])
        try: capabilities(cap['stdout'])
        except (ValueError, UnicodeError, CaptureFailure, RecursionError): raise CaptureFailure('capabilities-rejected') from None
        for item in admitted['manifest']['files']: check_file(work/item['name'],item,deadline,cancellation)
        argv = [host,'EMMC_READ','0x0',hex(admitted['plan']['sectorCount']),'capture.bin'] if admitted['plan']['kind']=='primary-gpt-prefix' else [host,'EMMC_READ_EXT_CSD','capture.bin']
        check_budget(deadline,cancellation); receipt['captureDispatchAttempted'] = True
        done = N.run(argv,work,child_env,deadline,cancellation,output=data,expected_size=admitted['expectedBytes'])
        receipt['processes'].append(done['summary'])
        check_budget(deadline,cancellation)
        info = R.ordinary_path(data).lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_size == admitted['expectedBytes'])
        expected = dict(sizeBytes=admitted['expectedBytes'],sha256=check_file(data,dict(sizeBytes=admitted['expectedBytes']),deadline,cancellation))
        for item in admitted['manifest']['files']: check_file(work/item['name'],item,deadline,cancellation)
        check_budget(deadline,cancellation)
        check_file(data,expected,deadline,cancellation,output/'capture.bin')
        check_budget(deadline,cancellation)
        receipt.update(outcome='completed',captureCompleted=True,artifact=dict(file='capture.bin',**expected))
    except N.ProcessFailure as failure:
        receipt['outcome']=failure.code; receipt['processes'].append(failure.summary)
    except CaptureFailure as failure: receipt['outcome']=str(failure)
    except KeyboardInterrupt: receipt['outcome']='cancelled'
    except (OSError, ValueError, UnicodeError): receipt['outcome']='artifact-io-failed'
    if not receipt['captureCompleted'] and data.exists():
        receipt['incompleteArtifact']=dict(file='work/capture.bin',admitted=False)
    receipt['deviceStateUncertain']=receipt['captureDispatchAttempted']
    receipt['finishedAtUtc']=datetime.now(timezone.utc).isoformat()
    P.export(receipt,output/'receipt.json')
    return receipt


def main():
    class Parser(argparse.ArgumentParser):
        def error(self,message): self.exit(2,'Capture adapter refused; check required arguments. See Docs/bounded-capture-adapter.md.\n')
    parser = Parser(description=__doc__)
    parser.add_argument('action',choices=['inspect','capture'])
    for option in ('manifest','manifest-sha256','plan','plan-sha256','bundle'): parser.add_argument('--'+option,required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    try:
        values = (args.manifest,args.manifest_sha256,args.plan,args.plan_sha256,args.bundle)
        if args.action=='inspect':
            require(args.output is None); result=inspect(*values)
        else:
            require(args.output is not None); result=capture(*values,args.output)
        print(json.dumps(dict(outcome=result.get('outcome','inspected'),readyForApply=False,
                              captureCompleted=result.get('captureCompleted',False),receiptSha256=P.digest(result))))
        return 0 if result.get('outcome','completed')=='completed' else 2
    except (CaptureFailure,ValueError,OSError,UnicodeError,RecursionError):
        parser.exit(2,'Capture adapter refused; inspect pinned inputs, local files and a new output. See Docs/bounded-capture-adapter.md.\n')
    except KeyboardInterrupt: parser.exit(130,'Capture interrupted; retain any output as incomplete.\n')


if __name__=='__main__': raise SystemExit(main())
