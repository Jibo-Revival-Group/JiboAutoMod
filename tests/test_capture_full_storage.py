import hashlib,json,sys,tempfile,threading,types,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
import capture_adapter as A

class FullCaptureTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve();self.bundle=self.root/'bundle';self.bundle.mkdir();self.output=self.root/'out';system,arch=A.context();host='shofel2_t124_readonly.exe' if system=='windows' else 'shofel2_t124_readonly';files=[]
  for role,name in [('host',host),('payload','emmc_server_readonly.bin'),('bootstrap','intermezzo.bin')]:
   b=('synthetic '+role).encode();(self.bundle/name).write_bytes(b);files.append(dict(role=role,name=name,sizeBytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
  self.manifest=dict(schema='openjibo.readonly-capture-bundle.v1',sourceRevision='a'*40,os=system,architecture=arch,protocol=A.PROTOCOL,files=files)
  self.evidence=dict(schema='openjibo.storage-capacity.v1',sectorSizeBytes=512,storageSectorCount=8,sizeBytes=4096,sourceHash='b'*64,sourceBytes=512,physicalIdentityVerified=False,captureAuthenticityVerified=False)
  self.plan=dict(schema='openjibo.readonly-full-storage-plan.v1',sourceRevision='a'*40,bundleSha256='',kind='full-user-area',startSector=0,sectorCount=8,timeoutSeconds=30,capacityEvidence=self.evidence)
  self.mp=self.root/'manifest.json';self.pp=self.root/'plan.json';self.calls=[]
 def inputs(self):
  self.mp.write_text(json.dumps(self.manifest));mh=hashlib.sha256(self.mp.read_bytes()).hexdigest();self.plan['bundleSha256']=mh;self.pp.write_text(json.dumps(self.plan));return (self.mp,mh,self.pp,hashlib.sha256(self.pp.read_bytes()).hexdigest(),self.bundle)
 def fake_run(self,argv,work,env,deadline,cancellation=None,output=None,expected_size=None,capabilities=False):
  self.calls.append(list(map(str,argv)));summary={'stdout':{'diagnosticCodes':[]},'stderr':{'diagnosticCodes':[]},'exitCode':0}
  if capabilities:
   c=dict(schema='openjibo.storage-readonly-full-capabilities.v1',protocol=A.PROTOCOL,command='EMMC_READ_FULL',sectorSizeBytes=512,maxReadSectors=4096,storageSectorUpperBound=A.UPPER_SECTORS,capacitySource='EXT_CSD.SEC_COUNT')
   return {'stdout':json.dumps(c).encode(),'summary':summary}
  self.assertEqual(argv[1:],['EMMC_READ_FULL','0x8','capture.bin']);Path(output).write_bytes(b'X'*expected_size);return {'summary':summary,'stdout':None}
 def test_full_plan_separate_and_exact(self):
  admitted=A.inputs(*self.inputs()[:4]);self.assertTrue(admitted['full']);self.assertEqual(4096,admitted['expectedBytes'])
  for update in ({'schema':'openjibo.readonly-capture-plan.v1'},{'sectorCount':9},{'timeoutSeconds':21601},{'startSector':1},{'kind':'primary-gpt-prefix'}):
   original=self.plan.copy();self.plan.update(update)
   with self.assertRaises((ValueError,A.CaptureFailure)):A.inputs(*self.inputs()[:4])
   self.plan=original
 def test_malformed_top_level_plan_is_cleanly_refused(self):
  for plan in ([],None,'bad',42):
   with self.assertRaises(A.CaptureFailure):A.validate_profile(self.manifest,plan,'a'*64,'b'*64,*A.context())
 def test_linux_mount_detection_prefers_nearest_and_decodes_spaces(self):
  text=('1 0 0:1 / / rw - ext4 /dev/root rw\n'
        '2 1 0:2 / /mnt/usb\\040drive rw - vfat /dev/fake rw\n'
        '3 2 0:3 / /mnt/usb\\040drive/nested rw - ext4 /dev/other rw\n')
  self.assertEqual(A.linux_mount_type('/mnt/usb drive/data',text),'vfat')
  self.assertEqual(A.linux_mount_type('/mnt/usb drive/nested/data',text),'ext4')
  self.assertEqual(A.linux_mount_type('/mnt/usbx/data',text),'ext4')
 def test_known_linux_fat_refused_before_native(self):
  self.plan['sectorCount']=2**23;self.evidence['storageSectorCount']=2**23;self.evidence['sizeBytes']=2**32
  with patch.object(A.platform,'system',return_value='Linux'),patch('builtins.open',unittest.mock.mock_open(read_data='1 0 0:1 / / rw - vfat /dev/fake rw\n')),patch.object(A.N,'run',side_effect=AssertionError('no native process')):
   with self.assertRaises(A.CaptureFailure):A.capture(*self.inputs(),self.output)
  self.assertFalse(self.output.exists())
 def test_inspect_requires_destination_and_never_launches(self):
  with patch.object(A.N,'run',side_effect=AssertionError('no native process')):
   with self.assertRaises(A.CaptureFailure):A.inspect(*self.inputs())
   x=A.inspect(*self.inputs(),output=self.output)
  self.assertEqual(x['destinationBudget']['hostCopies'],2);self.assertEqual(x['destinationBudget']['requiredBytes'],8192+sum(f['sizeBytes'] for f in self.manifest['files'])+64*1024*1024);self.assertFalse(self.output.exists())
 def test_insufficient_space_precedes_native(self):
  with patch.object(A.shutil,'disk_usage',return_value=types.SimpleNamespace(free=1)),patch.object(A.N,'run',side_effect=AssertionError('no native process')):
   with self.assertRaises(A.CaptureFailure):A.capture(*self.inputs(),self.output)
  self.assertFalse(self.output.exists())
 def test_acl_failure_precedes_native(self):
  with patch.object(A,'secure_full_output',side_effect=A.CaptureFailure('private-output-unavailable')),patch.object(A.N,'run',side_effect=AssertionError('no native process')):
   with self.assertRaises(A.CaptureFailure):A.capture(*self.inputs(),self.output)
 def test_existing_output_and_known_small_file_limit_refused(self):
  self.output.mkdir()
  with patch.object(A.N,'run',side_effect=AssertionError('no native process')):
   with self.assertRaises(A.CaptureFailure):A.capture(*self.inputs(),self.output)
  self.output.rmdir()
  with patch.object(A,'known_small_file_limit',return_value=True),patch.object(A.N,'run',side_effect=AssertionError('no native process')):
   with self.assertRaises(A.CaptureFailure):A.capture(*self.inputs(),self.output)
 def test_untrusted_or_inconsistent_capacity_fails_before_launch(self):
  self.evidence['physicalIdentityVerified']=True
  with patch.object(A.N,'run',side_effect=AssertionError('no native process')):
   with self.assertRaises(ValueError):A.capture(*self.inputs(),self.output)
  self.assertFalse(self.output.exists())
 def test_bad_capabilities_never_dispatch_capture(self):
  def bad(*args,**kwargs):
   result=self.fake_run(*args,**kwargs);result['stdout']=b'{}';return result
  with patch.object(A.N,'run',side_effect=bad):r=A.capture(*self.inputs(),self.output)
  self.assertFalse(r['captureCompleted']);self.assertFalse(r['captureDispatchAttempted']);self.assertEqual(len(self.calls),1)
 def test_full_success_uses_exact_command_and_rehashes_final_copy(self):
  with patch.object(A.N,'run',side_effect=self.fake_run):r=A.capture(*self.inputs(),self.output)
  self.assertEqual(r['outcome'],'completed');self.assertEqual(r['artifact']['file'],'full-storage.bin');self.assertEqual(r['recovery']['action'],'review-device-state-before-normal-boot');self.assertTrue(r['independentFinalRehash']);self.assertFalse(r['physicalIdentityVerified']);self.assertFalse(r['restoreVerified']);self.assertEqual(r['capacitySourceSha256'],'b'*64);self.assertEqual(len(self.calls),2);self.assertEqual(self.calls[0][1],'--full-capabilities');self.assertEqual(hashlib.sha256((self.output/'full-storage.bin').read_bytes()).hexdigest(),r['artifact']['sha256'])
 def test_short_output_is_incomplete(self):
  def short(*a,**kw):
   r=self.fake_run(*a,**kw)
   if not kw.get('capabilities'):Path(kw['output']).write_bytes(b'X')
   return r
  with patch.object(A.N,'run',side_effect=short):r=A.capture(*self.inputs(),self.output)
  self.assertFalse(r['captureCompleted']);self.assertFalse((self.output/'full-storage.bin').exists())
 def test_final_rehash_failure_is_not_completed(self):
  original=A.check_file
  def check(path,*a,**kw):
   if Path(path)==self.output/'full-storage.bin':raise A.CaptureFailure('synthetic-final-hash-failed')
   return original(path,*a,**kw)
  with patch.object(A.N,'run',side_effect=self.fake_run),patch.object(A,'check_file',side_effect=check):r=A.capture(*self.inputs(),self.output)
  self.assertFalse(r['captureCompleted']);self.assertFalse(r['independentFinalRehash'])
 def test_interrupted_final_copy_is_recorded_inadmissible(self):
  original=A.check_file
  def check(path,item,deadline,cancellation,destination=None):
   if destination is not None and Path(destination)==self.output/'full-storage.bin':
    Path(destination).write_bytes(b'partial');raise A.CaptureFailure('cancelled')
   return original(path,item,deadline,cancellation,destination)
  with patch.object(A.N,'run',side_effect=self.fake_run),patch.object(A,'check_file',side_effect=check):r=A.capture(*self.inputs(),self.output)
  self.assertFalse(r['captureCompleted']);self.assertEqual(r['incompleteFinalArtifact'],{'file':'full-storage.bin','admitted':False});self.assertEqual((self.output/'full-storage.bin').read_bytes(),b'partial');self.assertFalse(r['independentFinalRehash'])
 def test_final_copy_corruption_is_recorded_inadmissible(self):
  original=A.check_file
  def check(path,item,deadline,cancellation,destination=None):
   if Path(path)==self.output/'full-storage.bin':Path(path).write_bytes(b'Z'*item['sizeBytes'])
   return original(path,item,deadline,cancellation,destination)
  with patch.object(A.N,'run',side_effect=self.fake_run),patch.object(A,'check_file',side_effect=check):r=A.capture(*self.inputs(),self.output)
  self.assertFalse(r['captureCompleted']);self.assertEqual(r['incompleteFinalArtifact'],{'file':'full-storage.bin','admitted':False});self.assertFalse(r['independentFinalRehash'])
 def test_cancel_before_launch(self):
  event=threading.Event();event.set()
  with patch.object(A.N,'run',side_effect=AssertionError('no native process')):
   with self.assertRaises(A.CaptureFailure):A.capture(*self.inputs(),self.output,cancellation=event)
 def test_full_capabilities_reject_changed_contract(self):
  c=dict(schema='openjibo.storage-readonly-full-capabilities.v1',protocol=A.PROTOCOL,command='EMMC_READ_FULL',sectorSizeBytes=512,maxReadSectors=4096,storageSectorUpperBound=A.UPPER_SECTORS,capacitySource='EXT_CSD.SEC_COUNT')
  A.full_capabilities(json.dumps(c).encode());c['maxReadSectors']=8192
  with self.assertRaises(A.CaptureFailure):A.full_capabilities(json.dumps(c).encode())
if __name__=='__main__':unittest.main()