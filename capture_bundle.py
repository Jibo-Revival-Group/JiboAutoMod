#!/usr/bin/env python3
"""Prepare a Windows capture candidate using static file inspection only."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat


def sibling(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


A = sibling('capture_adapter')
PE = sibling('pe_imports')
P = A.P
SOURCES = ('shofel2_t124.c', 'emmc_server.c', 'emmc_server.h')
SYSTEM = frozenset(('advapi32 bcrypt cfgmgr32 comdlg32 crypt32 gdi32 iphlpapi kernel32 '
                    'msvcrt ntdll ole32 oleaut32 psapi rpcrt4 secur32 setupapi shell32 '
                    'shlwapi ucrtbase user32 version winmm winusb ws2_32').split())


def require(value):
    if not value: raise ValueError('bundle_review_refused')


def sha(data): return hashlib.sha256(data).hexdigest()


def read(path, limit=PE.MAX_BYTES):
    path = A.R.ordinary_path(path); before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= limit)
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(str(path), flags), 'rb') as source:
        opened = os.fstat(source.fileno()); require(A.R.file_identity(opened) == A.R.file_identity(before))
        raw = source.read(limit+1)
        require(A.R.identity(opened) == A.R.identity(os.fstat(source.fileno())))
    require(len(raw) == before.st_size and A.R.file_identity(before) == A.R.file_identity(path.lstat()))
    return raw


def write(path, raw):
    path = Path(path).absolute(); A.R.ordinary_path(path.parent)
    with os.fdopen(os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o600), 'wb') as target:
        target.write(raw); target.flush(); os.fsync(target.fileno())


def new_directory(path):
    path = Path(path).absolute(); A.R.ordinary_path(path.parent)
    path.mkdir(mode=0o700, exist_ok=False); return path


def system_import(name):
    return name[:-4] in SYSTEM or name.startswith(('api-ms-win-', 'ext-ms-win-'))


def collect_graph(host, runtime):
    """Resolve only regular import names in one explicit compiler runtime directory."""
    graph = []; files = {}; pending = [('shofel2_t124_readonly.exe', read(host), False)]
    runtime = A.R.ordinary_path(runtime); require(runtime.is_dir())
    while pending:
        name, raw, is_dll = pending.pop(0)
        if name in files:
            require(files[name] == raw); continue
        require(len(files) < 17 and sum(map(len, files.values()))+len(raw) <= 66000000)
        inspected = PE.inspect(raw)
        require(inspected['architecture'] == 'x86_64' and inspected['isDll'] is is_dll)
        files[name] = raw
        platform = []; bundled = []
        for dependency in inspected['imports']:
            require(len(dependency) <= 96)
            if system_import(dependency): platform.append(dependency)
            else:
                bundled.append(dependency)
                if dependency not in files:
                    pending.append((dependency, read(runtime/dependency), True))
        graph.append(dict(name=name, sha256=sha(raw), sizeBytes=len(raw),
                          platformImports=platform, bundledImports=bundled))
    return files, sorted(graph, key=lambda item:item['name'])


def export_windows(host, runtime, licenses, revision, source, output):
    require(type(revision) is str and re.fullmatch('[0-9a-f]{40}', revision))
    files, graph = collect_graph(host, runtime)
    # Preserve compiler-prefix license material for subsequent distribution review.
    # This is an inventory, not a determination of license sufficiency.
    licenses = A.R.ordinary_path(licenses); require(licenses.is_dir())
    notices = {}; total = 0; directory_count = 0
    for directory, dirs, names in os.walk(licenses, followlinks=False):
        directory_count += 1
        require(directory_count <= 256 and len(Path(directory).relative_to(licenses).parts) <= 16)
        for child in dirs: require(not (Path(directory)/child).is_symlink()); A.R.ordinary_path(Path(directory)/child)
        require(len(dirs) <= 128)
        for name in names:
            path = Path(directory)/name; relative = path.relative_to(licenses).as_posix()
            require(len(notices) < 1024 and re.fullmatch(r'[A-Za-z0-9_./+ -]{1,240}', relative) and '..' not in relative)
            raw = read(path, 4194304); total += len(raw); require(total <= 33554432)
            notices[relative] = raw
    require(notices)
    sources = {name:read(Path(source)/name, 1048576) for name in SOURCES}
    output = new_directory(output)
    for folder in ('components', 'reviewed-source', 'licenses'): new_directory(output/folder)
    for name, raw in files.items(): write(output/'components'/name, raw)
    for name, raw in sources.items(): write(output/'reviewed-source'/name, raw)
    for name, raw in notices.items():
        target = output/'licenses'/name; target.parent.mkdir(mode=0o700, parents=True, exist_ok=True); write(target, raw)
    report = dict(schema='openjibo.windows-static-components.v1', sourceRevision=revision,
                  os='windows', architecture='x86_64', graph=graph,
                  sources=[dict(file='reviewed-source/'+name, sha256=sha(raw)) for name,raw in sources.items()],
                  licenses=[dict(file='licenses/'+name, sha256=sha(raw), sizeBytes=len(raw)) for name,raw in sorted(notices.items())],
                  inspectorSha256=sha(read(Path(PE.__file__))), exporterSha256=sha(read(Path(__file__))),
                  staticImportClosureChecked=True, fullRuntimeClosureVerified=False, captureApproved=False,
                  scope='Static PE imports; platform imports assumed; dynamic loads and license sufficiency unverified')
    require(len(P.canonical(report)) < P.LIMIT)
    P.export(report, output/'report.json')
    return report


def proof_files(root, proof):
    require(type(proof.get('files')) is list and len(proof['files']) <= 32)
    result = {}
    for item in proof['files']:
        P.exact(item, ('file','sha256'), 'proof_file_fields')
        name = item['file']; require(type(name) is str and re.fullmatch(r'[A-Za-z0-9_./-]{1,160}',name) and '..' not in name and not name.startswith('/'))
        require(name not in result and P.HASH.fullmatch(item['sha256']))
        raw = read(Path(root)/name); require(sha(raw) == item['sha256']); result[name] = raw
    return result


def compose(windows, windows_pin, native, native_pin, revision, output):
    """Join pinned Windows static export and actual ARM build from one CI revision."""
    require(type(revision) is str and re.fullmatch('[0-9a-f]{40}', revision))
    windows = A.R.ordinary_path(windows); native = A.R.ordinary_path(native)
    report = A.pinned_json(windows/'report.json', windows_pin)
    proof = A.pinned_json(native/'proof.json', native_pin)
    require(report.get('schema') == 'openjibo.windows-static-components.v1' and report.get('sourceRevision') == revision)
    require(report.get('os') == 'windows' and report.get('architecture') == 'x86_64')
    require(report.get('staticImportClosureChecked') is True and report.get('fullRuntimeClosureVerified') is False and report.get('captureApproved') is False)
    require(proof.get('sourceRevision') == revision and proof.get('readOnlyPayloadBuilt') is True)
    A.capabilities(P.canonical(proof.get('capabilities')))
    actual = proof_files(native, proof)
    require(type(report.get('sources')) is list and len(report['sources']) == 3)
    require({entry['file'] for entry in report['sources']} == {'reviewed-source/'+name for name in SOURCES})
    for entry in report['sources']:
        raw = read(windows/entry['file'], 1048576); require(sha(raw) == entry['sha256'])
        require(raw.replace(b'\r\n',b'\n') == actual[entry['file']].replace(b'\r\n',b'\n'))
    files, graph = collect_graph(windows/'components/shofel2_t124_readonly.exe', windows/'components')
    require(graph == report.get('graph'))
    require(type(report.get('licenses')) is list and 0 < len(report['licenses']) <= 1024)
    notices = {}; total = 0
    for item in report['licenses']:
        P.exact(item, ('file','sha256','sizeBytes'), 'license_fields')
        name = item['file']; require(type(name) is str and name.startswith('licenses/') and re.fullmatch(r'[A-Za-z0-9_./+ -]{1,249}',name) and '..' not in name)
        require(name not in notices)
        raw = read(windows/name,4194304); total += len(raw); require(total <= 33554432)
        require(sha(raw) == item['sha256'] and len(raw) == item['sizeBytes']); notices[name] = raw
    files['emmc_server_readonly.bin'] = actual['built-components/emmc_server_readonly.bin']
    files['intermezzo.bin'] = actual['built-components/intermezzo.bin']
    require(0 < len(files['emmc_server_readonly.bin']) <= 131072 and 0 < len(files['intermezzo.bin']) <= 256)
    require(sum(map(len,files.values())) <= 67108864)
    roles = {'shofel2_t124_readonly.exe':'host','emmc_server_readonly.bin':'payload','intermezzo.bin':'bootstrap'}
    manifest = dict(schema='openjibo.readonly-capture-bundle.v1', sourceRevision=revision,os='windows',architecture='x86_64',protocol=A.PROTOCOL,
                    files=[dict(role=roles.get(name,'runtime'),name=name,sha256=sha(raw),sizeBytes=len(raw)) for name,raw in sorted(files.items())])
    manifest_raw = P.canonical(manifest)+b'\n'; manifest_pin = sha(manifest_raw)
    plan = dict(schema='openjibo.readonly-capture-plan.v1',sourceRevision=revision,bundleSha256=manifest_pin,
                kind='primary-gpt-prefix',startSector=0,sectorCount=34,timeoutSeconds=30)
    plan_raw = P.canonical(plan)+b'\n'
    output = new_directory(output); bundle = new_directory(output/'bundle')
    for name,raw in files.items(): write(bundle/name,raw)
    for name,raw in notices.items():
        target=output/name; target.parent.mkdir(mode=0o700,parents=True,exist_ok=True); write(target,raw)
    write(output/'manifest.json',manifest_raw); write(output/'plan.json',plan_raw)
    review = dict(schema='openjibo.capture-candidate-review.v1',sourceRevision=revision,manifestSha256=manifest_pin,planSha256=sha(plan_raw),
                  windowsReportSha256=windows_pin,nativeProofSha256=native_pin,staticImportGraph=graph,
                  candidatePrepared=True,captureApproved=False,captureAttempted=False,readyForApply=False,fullRuntimeClosureVerified=False,
                  inputTrust='operator-pinned-not-provenance-authenticated',
                  scope='Local file preparation only; no native execution, USB, physical identity, reset or firmware compatibility verified')
    P.export(review,output/'review.json'); return review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action',required=True)
    export = sub.add_parser('export-windows',help='CI static export; never execute PE files')
    for name in ('host','runtime','licenses','source','output'): export.add_argument('--'+name,required=True,type=Path)
    export.add_argument('--source-revision',required=True)
    join = sub.add_parser('compose',help='Offline candidate and fixed plan; no capture')
    for name in ('windows','native','output'): join.add_argument('--'+name,required=True,type=Path)
    for name in ('windows-sha256','native-sha256','source-revision'): join.add_argument('--'+name,required=True)
    args=parser.parse_args()
    try:
        if args.action=='export-windows': result=export_windows(args.host,args.runtime,args.licenses,args.source_revision,args.source,args.output)
        else: result=compose(args.windows,args.windows_sha256,args.native,args.native_sha256,args.source_revision,args.output)
        print(json.dumps(dict(prepared=True,reportSha256=P.digest(result),captureApproved=False,readyForApply=False)))
    except (ValueError,OSError,UnicodeError,KeyError,TypeError,A.CaptureFailure,RecursionError):
        parser.exit(2,'Bundle review refused; check pinned inputs, source match, imports, notices and new output.\n')


if __name__ == '__main__': main()
