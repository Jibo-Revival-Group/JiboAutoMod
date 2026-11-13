"""Build a portable offline-review preview with a generated synthetic demo only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import zipfile

SCRIPTS=('demo_review.py','review_request.py','conversion_review.py','storage_evidence.py','oobe_intake.py','conversion_plan.py',
         'recovery_evidence.py','gpt_audit.py','gpt_layout.py','gpt_recovery.py','firewall_preview.py','firewall_patch.py','ext4_path.py',
         'endpoint_preview.py','capture_bundle.py','capture_adapter.py','capture_process.py','capture_audit.py','pe_imports.py','storage_capacity.py')
DOCS=('offline-preview.md','oobe-storage-intake.md','conversion-preparation.md','conversion-review-bundle.md','storage-file-evidence.md',
      'recovery-file-check.md','primary-gpt-audit.md','gpt-recovery-audit.md','firewall-sector-preview.md','endpoint-file-preview.md',
      'host-support.md','capture-process-cleanup.md','bounded-capture-adapter.md','capture-candidate.md','read-only-capture-build.md','full-storage-backup.md')
DEMO_FILES=('inventory.json','target.json','audit.json','recovery-files.json','firewall-input.json','endpoint-input.json',
            'rootfsA.img','rootfsB.img','gpt-prefix.bin','full-storage.bin','calibration.bin','jetstream.json')


def sha(raw): return hashlib.sha256(raw).hexdigest()


def validate_community_documentation(files):
    """Keep unrelated project plans and private experiments out of the release."""
    excluded=re.compile(rb'Open[ -]?Jibo[ -]?Cloud|JiboExperiments|cloud\.openjibo\.com|CoffeeBreak|'
                        rb'two incoming|incoming (?:factory|units|robots)|OOBE test units are awaiting|'
                        rb'no Mac test host|native Ubuntu laptop',re.IGNORECASE)
    for name,raw in files.items():
        if name.lower().endswith('.md') and (name.rsplit('/',1)[-1]=='oobe-software-supply.md' or excluded.search(raw)):
            raise ValueError('community package contains unrelated project or private test documentation')


def ordinary(path):
    path=Path(path).absolute()
    for part in (path,*path.parents):
        info=part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&1024:
            raise ValueError('ordinary files required')
    return path


def read(path):
    path=ordinary(path); info=path.stat()
    if not stat.S_ISREG(info.st_mode) or not 0<info.st_size<=4194304: raise ValueError('invalid source file')
    raw=path.read_bytes()
    if len(raw)!=info.st_size: raise ValueError('source changed')
    return raw


def package(source,output,revision):
    if not re.fullmatch('[0-9a-f]{40}',revision): raise ValueError('source revision required')
    source=ordinary(source); output=Path(output).absolute(); ordinary(output.parent)
    if output.exists(): raise ValueError('new output required')
    files={name:read(source/name).replace(b'\r\n',b'\n') for name in SCRIPTS}
    files.update({'Docs/'+name:read(source/'Docs'/name).replace(b'\r\n',b'\n') for name in DOCS})
    files['README.md']=files['Docs/offline-preview.md'].replace(b'](conversion-review-bundle.md#',b'](Docs/conversion-review-bundle.md#').replace(b'](oobe-storage-intake.md)',b'](Docs/oobe-storage-intake.md)').replace(b'](gpt-recovery-audit.md)',b'](Docs/gpt-recovery-audit.md)')
    files['CONTRIBUTING.md']=read(source/'CONTRIBUTING.md').replace(b'\r\n',b'\n')
    validate_community_documentation(files)
    files['profiles/S21firewall.v1']=read(source/'profiles/S21firewall.v1')
    if sha(files['profiles/S21firewall.v1'])!='cb34db864fee2e6725fa09a293c60fff003b87348a16553419926ee7cc1a1cc8':
        raise ValueError('profile changed')
    # The fixture generator is repository test code. No operator-supplied backup
    # path is accepted by this builder, so a real backup cannot be bundled by flag.
    sys.path.insert(0,str(source/'tests')); sys.path.insert(0,str(source))
    import test_conversion_review_storage as fixture
    import test_conversion_review as base
    import test_storage_evidence as storage
    import test_conversion_review_gpt as gpt_fixture
    with tempfile.TemporaryDirectory() as temporary:
        retained=Path(temporary).resolve()/'retained'
        values=fixture.fixture(retained)
        gpt_fixture.add_recovery_tables(retained,values)
        del values['storageInput']
        values['audit']['checkedAtUtc']='2000-01-01T00:00:00+00:00'
        values['audit']['auditorSha256']=sha(files['gpt_audit.py'])
        values['audit']['parserSha256']=sha(files['gpt_layout.py'])
        values['inventory']['observedAtUtc']='2000-01-01T00:00:00Z'
        values['inventory']['auditEvidenceSha256']=sha(base.raw_json(values['audit']))
        base.write_inputs(retained,values,Path(temporary)/'unused.json')
        if {p.name for p in retained.iterdir()}!=set(DEMO_FILES): raise ValueError('unexpected demo files')
        files.update({'demo/retained/'+name:read(retained/name) for name in DEMO_FILES})
        disk=bytearray(files['demo/retained/full-storage.bin'])
        blank=storage.filesystem('credentials',b'{"accessKeyId":"","secretAccessKey":"","region":""}')
        layout=base.V.F.G.audit_primary_gpt(files['demo/retained/gpt-prefix.bin'],values['firewallInput']['diskSectors'])
        part=next(p for p in layout['partitions'] if p['name']=='var-test'); start=part['start_sector']*512
        if part['size_sectors']*512!=len(blank): raise ValueError('synthetic partition changed')
        disk[start:start+len(blank)]=blank
        files['demo/oobe/full-storage.bin']=bytes(disk)
        intake=dict(schema='openjibo.oobe-intake-input.v1',diskSectors=values['firewallInput']['diskSectors'],
                    fullStorage=dict(sha256=sha(disk),sizeBytes=len(disk)),gptPrefix=values['firewallInput']['gptPrefix'],credentialsPartition='var-test')
        files['demo/oobe/intake-input.json']=base.raw_json(intake)
    files['Run-Demo.cmd']=(
        '@echo off\r\nsetlocal\r\npushd "%~dp0"\r\n'
        'where py >nul 2>nul\r\nif errorlevel 1 (\r\n  python -I -B demo_review.py --open %*\r\n) else (\r\n  py -3 -I -B demo_review.py --open %*\r\n)\r\n'
        'set "demo_exit=%errorlevel%"\r\npopd\r\nif not "%demo_exit%"=="0" pause\r\nexit /b %demo_exit%\r\n').encode('ascii')
    files['run-demo.sh']=b'#!/bin/sh\nset -eu\nCDPATH= cd -P "$(dirname "$0")"\nexec python3 -I -B demo_review.py --open "$@"\n'
    manifest=dict(schema='openjibo.offline-review-release.v1',sourceRevision=revision,pythonMinimum='3.9',
                  scope='Portable offline review preview; synthetic demo; no native binaries or device payloads',
                  sourceTextNormalization='CRLF-to-LF for Python and Markdown; signature profile unchanged',
                  syntheticDemo=True,hardwareCompatibilityVerified=False,completeConversionPlan=False,readyForApply=False,
                  files=[dict(file=name,sizeBytes=len(raw),sha256=sha(raw)) for name,raw in sorted(files.items())])
    files['release-manifest.json']=json.dumps(manifest,sort_keys=True,indent=2).encode()+b'\n'
    files['SHA256SUMS']=''.join(sha(raw)+'  '+name+'\n' for name,raw in sorted(files.items())).encode('ascii')
    output.mkdir(mode=0o700,exist_ok=False)
    archive=output/'JiboRevival-Offline-Review.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_STORED) as bundle:
        for name,raw in sorted(files.items()):
            entry=zipfile.ZipInfo(name,(2000,1,1,0,0,0)); entry.create_system=3
            entry.external_attr=(stat.S_IFREG|(0o755 if name=='run-demo.sh' else 0o644))<<16
            entry.compress_type=zipfile.ZIP_STORED
            bundle.writestr(entry,raw)
    digest=sha(archive.read_bytes())
    (output/(archive.name+'.sha256')).write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    (output/'release-manifest.json').write_bytes(files['release-manifest.json'])
    return dict(archive=archive.name,sha256=digest,sourceRevision=revision,files=len(files),syntheticDemo=True,readyForApply=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-revision',required=True)
    args=parser.parse_args()
    print(json.dumps(package(args.source,args.output,args.source_revision),sort_keys=True))


if __name__=='__main__': main()
