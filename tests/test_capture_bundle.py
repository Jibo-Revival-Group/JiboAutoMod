import copy
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
import capture_bundle as B


def pe(imports=(),dll=False):
    """Synthetic PE layout only: never executable code or a capture component."""
    data=bytearray(4096); data[:2]=b'MZ'; struct.pack_into('<I',data,0x3c,128)
    data[128:132]=b'PE\0\0'; struct.pack_into('<HHIIIHH',data,132,0x8664,1,0,0,0,240,2|(0x2000 if dll else 0))
    optional=152; struct.pack_into('<H',data,optional,0x20b)
    struct.pack_into('<I',data,optional+60,512); struct.pack_into('<I',data,optional+108,16)
    section=optional+240; struct.pack_into('<IIII',data,section+8,3584,4096,3584,512)
    if imports:
        struct.pack_into('<II',data,optional+120,4096,20*(len(imports)+1))
        name_offset=1024
        for index,name in enumerate(imports):
            struct.pack_into('<IIIII',data,512+index*20,0,0,0,4096+name_offset-512,0)
            encoded=name.encode('ascii')+b'\0'; data[name_offset:name_offset+len(encoded)]=encoded; name_offset+=len(encoded)
    return bytes(data)


class CaptureBundle(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.runtime=self.root/'runtime'; self.runtime.mkdir()
        self.host=self.root/'host.exe'; self.host.write_bytes(pe(('KERNEL32.dll','libusb-1.0.dll')))
        (self.runtime/'libusb-1.0.dll').write_bytes(pe(('libgcc_s_seh-1.dll','api-ms-win-crt-runtime-l1-1-0.dll'),True))
        (self.runtime/'libgcc_s_seh-1.dll').write_bytes(pe(('KERNEL32.dll',),True))
        self.licenses=self.root/'notices'; self.licenses.mkdir(); (self.licenses/'COPYING').write_bytes(b'synthetic notice')
        self.source=self.root/'source'; self.source.mkdir()
        for name in B.SOURCES: (self.source/name).write_bytes((name+'\r\n').encode())
        self.windows=self.root/'windows'; self.native=self.root/'native'; self.native.mkdir()
        self.revision='a'*40

    def export(self):
        return B.export_windows(self.host,self.runtime,self.licenses,self.revision,self.source,self.windows)

    def native_proof(self):
        files=[]
        for name,raw in [*((('reviewed-source/'+name),(name+'\n').encode()) for name in B.SOURCES),
                         ('built-components/emmc_server_readonly.bin',b'synthetic ARM payload'),('built-components/intermezzo.bin',b'synthetic bootstrap')]:
            target=self.native/name; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(raw)
            files.append(dict(file=name,sha256=B.sha(raw)))
        proof=dict(sourceRevision=self.revision,readOnlyPayloadBuilt=True,files=files,
                   capabilities=dict(schema='openjibo.storage-readonly-capabilities.v1',protocol=B.A.PROTOCOL,
                    commands=['EMMC_STATUS','EMMC_READ','EMMC_READ_EXT_CSD'],sectorSizeBytes=512,maxReadSectors=4096,
                    storageSectorUpperBound=0x1D60000,payload='emmc_server_readonly.bin'))
        (self.native/'proof.json').write_text(json.dumps(proof),encoding='utf-8'); return proof

    def compose(self,output='candidate'):
        return B.compose(self.windows,B.sha((self.windows/'report.json').read_bytes()),self.native,
                         B.sha((self.native/'proof.json').read_bytes()),self.revision,self.root/output)

    def test_static_graph_recurses_and_records_platform_assumptions_without_execution(self):
        with patch.object(subprocess,'Popen',side_effect=AssertionError('no process')):
            report=self.export(); self.native_proof(); result=self.compose()
            with patch.object(B.A,'context',return_value=('windows','x86_64')):
                B.A.inspect(self.root/'candidate/manifest.json',result['manifestSha256'],self.root/'candidate/plan.json',result['planSha256'],self.root/'candidate/bundle')
        self.assertEqual(len(report['graph']),3); self.assertFalse(report['fullRuntimeClosureVerified'])
        self.assertFalse(result['captureApproved']); self.assertFalse(result['readyForApply'])
        self.assertEqual((self.root/'candidate/licenses/COPYING').read_bytes(),b'synthetic notice')

    def test_missing_unknown_runtime_and_wrong_architecture_refused(self):
        for raw in (pe(('missing.dll',)),pe(('..\\bad.dll',)),pe(('libusb-1.0.dll',),True)):
            self.host.write_bytes(raw)
            with self.assertRaises((ValueError,OSError)): B.collect_graph(self.host,self.runtime)
        raw=bytearray(pe()); struct.pack_into('<H',raw,132,0xaa64); self.host.write_bytes(raw)
        with self.assertRaises(ValueError): B.collect_graph(self.host,self.runtime)

    def test_pe_rejects_truncation_delay_imports_duplicate_names_and_bad_rvas(self):
        raw=pe(('KERNEL32.dll',))
        for size in (0,63,128,512,4095):
            with self.assertRaises(ValueError): B.PE.inspect(raw[:size])
        for offset,value in ((152+112+13*8,4096),(152+120,0xfffffff0),(512+12,0xfffffff0)):
            altered=bytearray(raw); struct.pack_into('<I',altered,offset,value)
            with self.assertRaises(ValueError): B.PE.inspect(bytes(altered))
        with self.assertRaises(ValueError): B.PE.inspect(pe(('KERNEL32.dll','kernel32.dll')))

    def test_pins_source_revision_payload_and_source_match_are_required(self):
        self.export(); original=self.native_proof()
        for key,value in (('sourceRevision','b'*40),('readOnlyPayloadBuilt',False),('capabilities',{})):
            proof=copy.deepcopy(original); proof[key]=value
            (self.native/'proof.json').write_text(json.dumps(proof),encoding='utf-8')
            with self.assertRaises((ValueError,B.A.CaptureFailure)): self.compose()
        (self.native/'proof.json').write_text(json.dumps(original),encoding='utf-8')
        (self.native/'built-components/emmc_server_readonly.bin').write_bytes(b'substitution')
        with self.assertRaises(ValueError): self.compose()
        self.native_proof()
        report=json.loads((self.windows/'report.json').read_text())
        path=self.windows/'reviewed-source/emmc_server.c'; path.write_bytes(b'different source')
        next(i for i in report['sources'] if i['file'].endswith('/emmc_server.c'))['sha256']=B.sha(path.read_bytes())
        (self.windows/'report.json').write_text(json.dumps(report),encoding='utf-8')
        with self.assertRaises(ValueError): self.compose()

    def test_notice_or_runtime_substitution_and_existing_output_refused(self):
        self.export(); self.native_proof(); self.compose()
        with self.assertRaises(FileExistsError): self.compose()
        (self.windows/'licenses/COPYING').write_bytes(b'changed')
        with self.assertRaises(ValueError): self.compose('other')
        (self.windows/'licenses/COPYING').write_bytes(b'synthetic notice')
        (self.windows/'components/libusb-1.0.dll').write_bytes(pe((),True))
        with self.assertRaises(ValueError): self.compose('other')

    def test_raw_report_pin_and_unsafe_paths_refused(self):
        self.export(); self.native_proof()
        with self.assertRaises(B.A.CaptureFailure):
            B.compose(self.windows,'0'*64,self.native,B.sha((self.native/'proof.json').read_bytes()),self.revision,self.root/'out')
        proof=json.loads((self.native/'proof.json').read_text()); proof['files'][0]['file']='../outside'
        (self.native/'proof.json').write_text(json.dumps(proof),encoding='utf-8')
        with self.assertRaises(ValueError): self.compose()


if __name__=='__main__': unittest.main()
