"""Exercise payload dispatch with inert MMIO/ROM boundaries; never open USB.

Initialization duration is a model input, not a measured hardware duration.
This checker preserves the actual entry dispatcher and command guard, replacing
storage initialization, MMIO, ROM transport, sector-zero reads and reset.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

def replace_body(source, name, body):
    match = re.search(r"\b" + re.escape(name) + r"\([^;{}]*\)\s*\{", source)
    if not match:
        raise ValueError(name)
    start = match.end()
    depth = 1
    pos = start
    while depth:
        depth += (source[pos] == "{") - (source[pos] == "}")
        pos += 1
    return source[:start] + "\n" + body + "\n" + source[pos-1:]



def build_model(native):
    source = (native / "payloads/emmc_server.c").read_text()
    
    attribute = '__attribute__((section(".init")))'
    assert source.count(attribute) == 1
    source = source.replace(attribute, '')
    marker = 'typedef void (*ep1_x_imm_t)(void *buffer, u32 size, u32 *num_xfer);'
    assert source.count(marker) == 1
    source = source.replace(marker, marker + r'''
    extern int printf(const char *, ...);
    static u32 simulated_ms, elapsed_ms, init_calls, replies, read_calls, reply_ms, reported;
    static u32 requested_op = EMMC_CMD_STATUS, simulated_error;
    static void fake_out(void *buffer, u32 size, u32 *count) {
        struct emmc_cmd_s *cmd = buffer;
        cmd->op = read_calls++ ? EMMC_CMD_EXIT : requested_op;
        cmd->start_sector = 0; cmd->num_sectors = 0;
        *count = read_calls == 1 ? reported : sizeof(*cmd);
    }
    static u32 saved[128];
    static void fake_in(void *buffer, u32 size, u32 *count) {
        if (init_calls != 1) __builtin_trap();
        ++replies; reply_ms = elapsed_ms; *count = size;
        if (size == 512) for (u32 i=0; i<128; ++i) saved[i] = ((u32*)buffer)[i];
    }
    ''')
    for bits in (8, 16, 32):
        source = replace_body(source, 'read' + str(bits), '(void)addr; return 0;')
        source = replace_body(source, 'write' + str(bits), '(void)addr; (void)val;')
    source = replace_body(source, 'enter_rcm', 'return;')
    source = replace_body(source, 'init_sdmmc4', '++init_calls; elapsed_ms += simulated_ms; init_error = simulated_error; sdmmc4_initialized = !simulated_error;')
    source = replace_body(source, 'read_emmc_sector', '(void)sector; for (u32 i=0; i<128; ++i) buffer[i]=0; return 0;')
    for direction in ('out_read', 'in_write'):
        old = '(ep1_x_imm_t)(BOOTROM_EP1_' + ('OUT_READ' if direction == 'out_read' else 'IN_WRITE') + '_IMM | 1)'
        assert source.count(old) == 1
        source = source.replace(old, 'fake_out' if direction == 'out_read' else 'fake_in')
    source += r'''
    static u32 decimal(const char *s) { u32 n=0; while (*s) n=n*10+(*s++-'0'); return n; }
    int main(int argc, char **argv) {
        if (argc != 5) return 2;
        reported=decimal(argv[1]); simulated_ms=decimal(argv[2]);
        if (decimal(argv[3])) requested_op=3;
        simulated_error=decimal(argv[4]);
        entry();
        printf("{\"initCalls\":%u,\"replies\":%u,\"replyMs\":%u,\"magic\":%u,\"initialized\":%u,\"initError\":%u}\n",
            init_calls,replies,reply_ms,saved[0],saved[2],saved[1]);
        return 0;
    }
    '''
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--source-revision', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    native = root/'Exploits/Shofel'
    output = args.output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    model = output/'model.c'
    model.write_text(build_model(native), encoding='utf-8')
    headers = ('types.h', 't124.h', 'emmc.h', 'emmc_server.h')
    for name in headers:
        (output/name).write_bytes((native/'include'/name).read_bytes())
    executable = output/('model.exe' if os.name == 'nt' else 'model')
    compiled = subprocess.run([args.compiler, '-std=c99', '-DOPENJIBO_READ_ONLY=1',
        '-D__arm__=1', '-Wno-int-to-pointer-cast', '-I', str(output), str(model),
        '-o', str(executable)], capture_output=True, text=True, timeout=30)
    if compiled.returncode:
        raise RuntimeError(compiled.stderr)
    header = (native/'include/mini_libusb.h').read_text()
    deadline = int(re.search(r'^#define USB_BULK_TIMEOUT (\d+)$', header, re.M)[1])
    cases = [(n,0,0,0) for n in (0,4,11,12,13)]
    cases += [(12,n,0,0) for n in (deadline-1,deadline,deadline+1,24000)]
    cases += [(12,0,1,0),(12,0,0,2)]
    results = []
    for length, ms, legacy, error in cases:
        process = subprocess.run([str(executable), str(length), str(ms), str(legacy),
            str(error)], capture_output=True, text=True, timeout=2, check=True)
        got = json.loads(process.stdout)
        admitted = length == 12 and not legacy
        assert got['initCalls'] == int(admitted) and got['replies'] == int(admitted)
        if admitted:
            assert got['replyMs'] == ms and got['magic'] == 0x524F0001
            assert got['initialized'] == int(not error) and got['initError'] == error
        results.append(dict(reportedBytes=length, simulatedInitializationMs=ms,
            legacyOpcode=bool(legacy), injectedInitError=error, observed=got))
    # Keep the original inputs alongside the generated model for review.
    for name, path in [('original.c', native/'payloads/emmc_server.c'),
                       ('mini_libusb.h', native/'include/mini_libusb.h'),
                       ('emmc_server.h', native/'include/emmc_server.h')]:
        (output/name).write_bytes(path.read_bytes())
    proof = dict(sourceRevision=args.source_revision, hardwareAccess=False,
        scope='Copied payload dispatcher with inert MMIO, ROM, storage and reset boundaries',
        limitations=['Not a BootROM emulator', 'Model duration is not measured hardware timing',
                     'Does not prove a hardware failure cause or restoration readiness'],
        hostBulkTimeoutMs=deadline, scenarios=results,
        files=[dict(file=p.name, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
               for p in sorted(output.iterdir()) if p.is_file()])
    (output/'proof.json').write_text(json.dumps(proof,indent=2)+'\n', encoding='utf-8')
    print('Payload dispatch model passed: '+str(len(results))+' scenarios; no hardware access.')


if __name__ == '__main__':
    main()
