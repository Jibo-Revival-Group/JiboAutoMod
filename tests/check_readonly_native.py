"""Compile the real host with link-time USB stubs and test without hardware."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--real-host', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    native = root/'Exploits/Shofel'
    output = args.output.absolute(); output.mkdir(parents=True, exist_ok=False)
    suffix = '.exe' if os.name == 'nt' else ''
    include = ['-I', str(native/'include')]
    flags = ['-std=c11', '-D_DEFAULT_SOURCE', '-D_DARWIN_C_SOURCE']
    ro = ['-DOPENJIBO_READ_ONLY=1']
    def run(command, **kwargs):
        return subprocess.run([str(part) for part in command], capture_output=True, text=True,
                              errors='replace', timeout=30, **kwargs)
    def compile_program(name, sources, readonly=True):
        executable = output/(name+suffix)
        result = run([args.compiler, *flags, *(ro if readonly else []), *include, *sources, '-o', executable])
        if result.returncode != 0: raise SystemExit('Native fixture compilation failed.\n'+result.stderr)
        return executable
    host = compile_program('readonly-host-fixture', [native/'exploit/shofel2_t124.c', root/'tests/native/readonly_usb_stub.c'])
    policy = compile_program('readonly-policy', [root/'tests/native/readonly_policy.c'])
    legacy = compile_program('legacy-protocol', [root/'tests/native/legacy_protocol.c'], readonly=False)
    for executable in (policy, legacy):
        result = run([executable]); assert result.returncode == 0, result.stderr
    # Inspect the actual compiler's payload translation in both modes, not a text grep of directives.
    for readonly in (False, True):
        processed = run([args.compiler, '-E', '-P', *(ro if readonly else []), *include, native/'payloads/emmc_server.c'])
        assert processed.returncode == 0, processed.stderr
        for forbidden in ('write_emmc_sector(', 'erase_emmc_sectors('):
            assert (forbidden in processed.stdout) == (not readonly), forbidden
        (output/('payload-readonly.i' if readonly else 'payload-legacy.i')).write_text(processed.stdout, encoding='utf-8')
    results = []
    def invoke(arguments, mode='', usb=False, success=False):
        result = run([host, *arguments], env={**os.environ, 'READONLY_FIXTURE_MODE': mode}, cwd=output)
        assert (result.returncode == 0) == success, (arguments, mode, result.stdout, result.stderr)
        assert ('USB_FIXTURE_OPEN' in result.stderr) == usb, (arguments, result.stderr)
        assert 'Chip ID:' not in result.stdout
        results.append(dict(scenario=mode or str(arguments[0]) if arguments else 'no-args',
                            exitCode=result.returncode, usbStubReached=usb))
        return result
    capabilities = json.loads(invoke(['--capabilities'], success=True).stdout)
    assert capabilities['commands'] == ['EMMC_STATUS', 'EMMC_READ', 'EMMC_READ_EXT_CSD']
    assert capabilities['protocol'] == 'openjibo-emmc-readonly.v1' and capabilities['maxReadSectors'] == 4096
    invoke(['--help'], success=True)
    for operation in ('EMMC_WRITE', 'EMMC_ERASE', 'MEM_DUMP', 'READ_FUSES', 'BOOT_BCT', 'PAYLOAD', 'DUMP_STACK', '-dbg', '--unknown'):
        invoke([operation]); invoke([operation, '0', '1', 'ignored'])
    invoke([]); invoke(['EMMC_STATUS', 'extra'])
    for start, count in [('0','0'), ('0','1001'), ('1d60000','1'), ('1d5ffff','2'), ('ffffffff','2'),
                         ('100000000','1'), ('0','ffffffffffffffff'), ('-1','1'), ('+1','1'), (' 1','1'),
                         ('0x','1'), ('1garbage','1'), ('1','1tail'), ('','1')]:
        invoke(['EMMC_READ', start, count, 'invalid-range.bin'])
    # Presence admission happens before USB/output creation. Contents here are
    # synthetic because send_rcm_cmd is also a link stub in this fixture.
    missing = output/'missing-artifacts.bin'
    invoke(['EMMC_READ','0','1',str(missing)]); assert not missing.exists()
    (output/'emmc_server_readonly.bin').write_bytes(b'synthetic payload')
    invoke(['EMMC_STATUS'])
    (output/'intermezzo.bin').write_bytes(b'synthetic bootstrap')
    preserved = output/'preserved.bin'; preserved.write_bytes(b'keep original')
    invoke(['EMMC_READ','0','1',str(preserved)])
    assert preserved.read_bytes() == b'keep original'
    invoke(['EMMC_STATUS'], usb=True, success=True)
    invoke(['EMMC_STATUS'], mode='clock-warning', usb=True, success=True)
    for index, (start, count) in enumerate([(0,9), (0,4096), (0x1D5FFFF,1)]):
        path = output/('read-'+str(index)+'.bin')
        invoke(['EMMC_READ',hex(start),hex(count),str(path)], usb=True, success=True)
        assert path.read_bytes() == b'\x5A'*(count*512)
    ext = output/'ext-csd.bin'
    invoke(['EMMC_READ_EXT_CSD',str(ext)], usb=True, success=True)
    assert ext.read_bytes() == b'\x5A'*512
    for mode in ('legacy-payload','wrong-limits','init-failure','sector-zero-failure','read-failure','wrong-frame',
                 'wrong-sector','wrong-count','short-header','short-data','control-zero','late-read-failure','exit-failure'):
        path = output/(mode+'.bin')
        invoke(['EMMC_READ','0','9',str(path)], mode=mode, usb=True)
        expected = 4096 if mode == 'late-read-failure' else 4608 if mode == 'exit-failure' else 0
        assert path.stat().st_size == expected
    ext_failed = output/'ext-csd-error.bin'
    invoke(['EMMC_READ_EXT_CSD',str(ext_failed)], mode='read-failure', usb=True)
    assert ext_failed.stat().st_size == 0
    if args.real_host:
        # This exact command returns before USB discovery. Never run a real capture in CI.
        actual = run([args.real_host.absolute(), '--capabilities'])
        assert actual.returncode == 0 and json.loads(actual.stdout) == capabilities
    files = [native/'exploit/shofel2_t124.c',native/'payloads/emmc_server.c',native/'include/emmc_server.h',host,policy,legacy]
    payload = native/'emmc_server_readonly.bin'
    if args.real_host: files.append(args.real_host.absolute())
    if os.name != 'nt':
        assert payload.is_file() and 0 < payload.stat().st_size <= 131072
        binary = payload.read_bytes()
        assert (0x524F0001).to_bytes(4,'little') in binary and (0x524F4441).to_bytes(4,'little') in binary
        files.extend([payload,native/'intermezzo.bin'])
    proof = dict(scope='USB link stubs and compiler/build evidence only; no hardware', scenarios=results,
                 policyRangeCases=10000, legacyOpcodesRefused=256, capabilities=capabilities,readOnlyPayloadBuilt=os.name != 'nt',
                 files=[dict(file=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files])
    (output/'proof.json').write_text(json.dumps(proof,indent=2)+'\n', encoding='utf-8')
    print('Read-only native fixture passed: '+str(len(results))+' host scenarios, 10000 ranges, payload handler exclusion, no hardware access.')


if __name__ == '__main__': main()
