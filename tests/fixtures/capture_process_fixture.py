"""Synthetic subprocess, never imports device code or discovers USB."""
import json
import os
from pathlib import Path
import sys
import time
import subprocess

if sys.argv[1]=='--child-holder':
    child=subprocess.Popen([sys.executable,'-I','-B','-c','import time; time.sleep(30)'])
    Path('child.pid').write_text(str(child.pid)); raise SystemExit(0)

mode = os.environ.get('CAPTURE_FIXTURE_MODE','success')
if sys.argv[1]=='--capabilities':
    if mode=='cap-timeout': time.sleep(30)
    value=dict(schema='openjibo.storage-readonly-capabilities.v1',protocol='openjibo-emmc-readonly.v1',
               commands=['EMMC_STATUS','EMMC_READ','EMMC_READ_EXT_CSD'],sectorSizeBytes=512,maxReadSectors=4096,
               storageSectorUpperBound=0x1D60000,payload='emmc_server_readonly.bin')
    if mode=='wrong-capabilities': value['commands'].append('EMMC_WRITE')
    if mode=='float-capabilities': value['sectorSizeBytes']=512.0
    if mode=='duplicate-capabilities':
        print('{"schema":1,"schema":2}'); raise SystemExit(0)
    if mode=='cap-change-component': Path('emmc_server_readonly.bin').write_bytes(b'changed')
    print(json.dumps(value)); raise SystemExit(0)
assert sys.argv[1] in ('EMMC_READ','EMMC_READ_EXT_CSD')
if sys.argv[1]=='EMMC_READ':
    assert sys.argv[2]=='0x0'; size=int(sys.argv[3],16)*512
else: size=512
path=Path(sys.argv[-1]); assert path.name=='capture.bin'
if mode=='missing-output': raise SystemExit(0)
if mode=='timeout': path.write_bytes(b'incomplete'); time.sleep(30)
if mode=='short-output': size-=1
if mode=='long-output': size+=1
path.write_bytes(b'Z'*size)
if mode=='change-component': Path('emmc_server_readonly.bin').write_bytes(b'changed')
if mode=='diagnostic-limit':
    sys.stderr.write('DO_NOT_ECHO_PRIVATE_DIAGNOSTIC'*4096); sys.stderr.flush()
if mode=='exit-failure': raise SystemExit(7)

if mode in ('handshake-reply-failure','failure-marker-exit-zero'):
    sys.stderr.write('DO_NOT_ECHO_PRIVATE_DIAGNOSTIC\nOPENJIBO_CAPTURE_DIAGNOSTIC=handshake-reply-transfer-failed\n')
    sys.stderr.flush()
    raise SystemExit(7 if mode=='handshake-reply-failure' else 0)
