import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
import endpoint_preview as V


def config():
    return {'HubClient':{'region-settings':{'api':{'entrypoint_hostname':'api.jibo.com','entrypoint_port':443,'hub_hostname':'hub.jibo.com','hub_port':443,'hub_secure':True},
                                            'stock-other':{'hub_hostname':'preserve.example.test'}},'retryCount':3},
            'OtherSubsystem':{'privateFixture':'PRIVATE_INPUT_FIXTURE','numbers':[1,True,1.5,None],'unicode':'\u2603'}}


class EndpointPreview(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); self.output=self.root/'output'
        self.target=dict(schema='openjibo.conversion-target.v1',mode='managed',providerId='example-provider',apiOrigin='https://api.example.test:8443')
        self.config=config()
        self.manifest=dict(schema='openjibo.endpoint-preview-input.v1',targetSha256='',jetstream={},credentialsRegion='api',
                           hubOrigin='https://hub.example.test:9443',allowIsolatedHttp=False,certificatePolicy='preserve-existing')

    def save(self,name,value):
        raw=json.dumps(value,ensure_ascii=False,indent=2).encode('utf-8'); path=self.root/name; path.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest(),len(raw)

    def inputs(self):
        target_pin,_=self.save('target.json',self.target); self.manifest['targetSha256']=target_pin
        config_pin,size=self.save('jetstream.json',self.config); self.manifest['jetstream']=dict(sha256=config_pin,sizeBytes=size)
        manifest_pin,_=self.save('manifest.json',self.manifest)
        return self.root/'manifest.json',manifest_pin,self.root/'target.json',target_pin,self.root/'jetstream.json',self.output

    def run_preview(self): return V.preview(*self.inputs())

    def test_explicit_secure_routes_preserve_unrelated_values_and_original_bytes(self):
        args=self.inputs(); original=(self.root/'jetstream.json').read_bytes()
        with patch.object(subprocess,'Popen',side_effect=AssertionError('no process')): result=V.preview(*args)
        self.assertEqual((self.output/'jetstream.before.json').read_bytes(),original)
        after=json.loads((self.output/'jetstream.after.json').read_bytes())
        expected=copy.deepcopy(self.config)
        routes=dict(entrypoint_hostname='api.example.test',entrypoint_port=8443,hub_hostname='hub.example.test',hub_port=9443,hub_secure=True)
        expected['HubClient']['region-settings']['api']=routes; expected['HubClient']['override']=routes
        self.assertEqual(after,expected); self.assertEqual((self.root/'jetstream.json').read_bytes(),original)
        self.assertNotIn('PRIVATE_INPUT_FIXTURE',json.dumps(result))
        for key in ('readyForApply','completeConversionPlan','executionSupported','deviceWritesPerformed','networkRequestsPerformed',
                    'credentialsChanged','certificatesChanged','certificateFilesRead','privateKeyFilesRead','robotCompatibilityVerified'):
            self.assertFalse(result[key])
        self.assertEqual(result['projectedEndpoints']['api']['port'],8443)
        self.assertTrue(all(t['tlsRequired'] and not t['disableCertificateValidationPermitted'] and not t['certificateChainVerified'] for t in result['trustRequirements']))

    def test_isolated_lan_http_requires_explicit_ack_and_independent_hub(self):
        self.target.update(mode='isolated',providerId='self-hosted',apiOrigin='http://192.168.50.20:9000')
        self.manifest.update(hubOrigin='http://hub.local:9001',allowIsolatedHttp=True)
        result=self.run_preview(); self.assertFalse(result['projectedEndpoints']['hub']['secure'])
        self.assertEqual(result['projectedEndpoints']['hub']['port'],9001)
        self.assertIn('isolated-lan-http-is-explicitly-acknowledged-but-network-is-unverified',result['requiredBeforeApply'])

    def test_noop_preserves_noncanonical_input_bytes_and_writes_no_payload(self):
        first=self.run_preview(); self.config=json.loads((self.output/'jetstream.after.json').read_bytes()); self.output=self.root/'noop'
        result=self.run_preview(); self.assertFalse(result['changeRequired']); self.assertFalse(result['formattingMayChange'])
        self.assertEqual(result['beforeSha256'],result['afterSha256']); self.assertEqual(result['semanticChanges'],[])
        self.assertEqual([p.name for p in self.output.iterdir()],['preview.json'])

    def test_active_region_is_required_and_credentials_region_is_never_invented(self):
        self.manifest['credentialsRegion']='open-jibo'
        with self.assertRaises(ValueError): self.run_preview()
        self.assertFalse(self.output.exists())

    def test_unknown_routing_fields_ambiguous_sections_and_wrong_shapes_refused(self):
        original=config()
        cases=[{'regions':{}},{'region-settings':{}},{'HubClient':[]},
               {'HubClient':{'region-settings':{'api':[]}}},
               {'HubClient':{'region-settings':{'api':{'entrypoint_secure':False}}}},
               {'HubClient':{'region-settings':{'api':{}},'override':{'disable_tls':True}}},
               {'HubClient':{'region-settings':{'api':{'hub_port':True}}}}]
        for changes in cases:
            self.config=copy.deepcopy(original); self.config.update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError): self.run_preview()
            self.assertFalse(self.output.exists())

    def test_public_http_localhost_invalid_names_and_managed_downgrades_refused(self):
        original=copy.deepcopy(self.target)
        for origin in ('http://192.168.1.20:9000','https://localhost','https://127.0.0.1','https://api_bad.example.test',
                       'https://-bad.example.test','https://example.test.','https://user:secret@example.test','https://example.test/path','wss://example.test'):
            self.target=dict(original,apiOrigin=origin)
            with self.subTest(origin=origin),self.assertRaises(ValueError): self.run_preview()
        self.target.update(mode='isolated',providerId='self-hosted'); self.manifest.update(allowIsolatedHttp=True,hubOrigin='http://hub.local')
        for origin in ('http://8.8.8.8','http://arbitrary.example.test','http://192.0.2.20','http://[::ffff:192.168.1.20]'):
            self.target['apiOrigin']=origin
            with self.subTest(origin=origin),self.assertRaises(ValueError): self.run_preview()

    def test_http_ack_is_typed_and_required_only_for_http(self):
        for value in (True,1,'yes'):
            self.manifest['allowIsolatedHttp']=value
            with self.subTest(value=value),self.assertRaises(ValueError): self.run_preview()
        self.target.update(mode='isolated',providerId='self-hosted',apiOrigin='http://192.168.1.20')
        self.manifest.update(allowIsolatedHttp=False,hubOrigin='http://hub.local')
        with self.assertRaises(ValueError): self.run_preview()

    def test_no_silent_hub_provider_or_certificate_policy_defaults(self):
        original=copy.deepcopy(self.manifest)
        for key,value in (('hubOrigin',''),('certificatePolicy','disable-validation'),('credentialsRegion','../api')):
            self.manifest=dict(original); self.manifest[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): self.run_preview()
        self.manifest=original; self.target['providerId']=''
        with self.assertRaises(ValueError): self.run_preview()

    def test_all_raw_pins_and_size_are_checked_before_output(self):
        args=self.inputs()
        for index in (1,3):
            altered=list(args); altered[index]='b'*64
            with self.subTest(index=index),self.assertRaises(ValueError): V.preview(*altered)
        (self.root/'jetstream.json').write_bytes(b'{}')
        with self.assertRaises(ValueError): V.preview(*args)
        args=self.inputs(); self.manifest['jetstream']['sizeBytes']+=1
        manifest_pin,_=self.save('manifest.json',self.manifest)
        with self.assertRaises(ValueError): V.preview(args[0],manifest_pin,*args[2:])
        self.assertFalse(self.output.exists())

    def test_duplicate_nonfinite_and_excessive_nesting_refused(self):
        for raw in (b'{"HubClient":{},"HubClient":{}}',b'{"bad":NaN}',b'{"bad":1e999}',b'{"bad":'+b'['*18+b'0'+b']'*18+b'}'):
            path=self.root/'bad.json'; path.write_bytes(raw)
            with self.subTest(raw=raw),self.assertRaises(ValueError): V.read_json(path,hashlib.sha256(raw).hexdigest())

    def test_existing_output_is_preserved(self):
        self.output.mkdir(); (self.output/'keep').write_bytes(b'keep')
        with self.assertRaises(FileExistsError): self.run_preview()
        self.assertEqual((self.output/'keep').read_bytes(),b'keep')

    def test_ipv6_and_default_ports_are_explicit(self):
        self.target.update(mode='isolated',providerId='self-hosted',apiOrigin='http://[fd00::20]')
        self.manifest.update(hubOrigin='https://hub.example.test',allowIsolatedHttp=True)
        result=self.run_preview(); self.assertEqual(result['projectedEndpoints']['api'],dict(hostname='fd00::20',port=80,secure=False))
        self.assertEqual(result['projectedEndpoints']['hub']['port'],443)

    def test_cli_from_unrelated_directory_and_import_probe_are_offline(self):
        args=self.inputs()
        command=[sys.executable,'-I','-B',str(Path(V.__file__)),'--manifest',str(args[0]),'--manifest-sha256',args[1],
                 '--target',str(args[2]),'--target-sha256',args[3],'--jetstream',str(args[4]),'--output',str(args[5])]
        result=subprocess.run(command,cwd=self.root,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr); self.assertNotIn('PRIVATE_INPUT_FIXTURE',result.stdout+result.stderr)
        self.assertNotIn(str(self.root),result.stdout+result.stderr)
        probe=subprocess.run([sys.executable,'-I','-B','-c',"import runpy,sys; runpy.run_path(sys.argv[1],run_name='offline_probe'); assert not any(n.startswith(('Exploits','usb','tkinter','config')) for n in sys.modules)",str(Path(V.__file__))],cwd=self.root,capture_output=True,timeout=10)
        self.assertEqual(probe.returncode,0,probe.stderr)


if __name__=='__main__': unittest.main()
