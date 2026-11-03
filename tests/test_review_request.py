import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
import review_request as Q
import test_conversion_review as base
import test_conversion_review_storage as fixture


class ReviewRequest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); self.inputs=self.root/'inputs'; self.output=self.root/'review'
        self.values=fixture.fixture(self.inputs)
        del self.values['storageInput']
        base.write_inputs(self.inputs,self.values,self.root/'unused-v1.json')

    def build(self): return Q.build(self.inputs,self.output,'services-test','var-test')

    def test_generates_seven_pins_and_complete_review_without_mutating_retained_files(self):
        before={p.name:base.digest(p.read_bytes()) for p in self.inputs.iterdir()}
        with patch.object(subprocess,'Popen',side_effect=AssertionError('no process')): result=self.build()
        self.assertEqual(result['schema'],'openjibo.conversion-review-bundle.v2')
        self.assertEqual(result['inputPinOrigin'],'generated-from-supplied-files')
        manifest_path=self.output/'request/review-input.json'
        manifest=json.loads(manifest_path.read_bytes())
        self.assertEqual(result['manifestSha256'],base.digest(manifest_path.read_bytes()))
        self.assertEqual(set(manifest['files']),set(Q.V.INPUTS_V2))
        self.assertEqual(manifest['files'],result['inputFilePins'])
        self.assertEqual(base.digest((self.output/'request/storage-input.json').read_bytes()),manifest['files']['storageInput'])
        self.assertTrue(result['storageFileEvidenceRecomputed']); self.assertFalse(result['readyForApply'])
        self.assertEqual(before,{p.name:base.digest(p.read_bytes()) for p in self.inputs.iterdir()})
        self.assertIn('request/review-input.json',[item['file'] for item in result['files']])
        self.assertNotIn('STORAGE_PRIVATE_KEY_FIXTURE',json.dumps(result))

    def test_generated_request_replays_with_explicit_storage_manifest_and_same_pins(self):
        result=self.build()
        replay=Q.V.build(self.output/'request/review-input.json',result['manifestSha256'],self.inputs,self.root/'replay',self.output/'request/storage-input.json')
        self.assertEqual(replay['inputFilePins'],result['inputFilePins'])
        self.assertEqual(replay['storageFileSummary'],result['storageFileSummary'])
        self.assertEqual(replay['inputPinOrigin'],'externally-supplied-manifest-pin')
        self.assertFalse((self.inputs/'storage-input.json').exists())

    def test_unknown_or_ambiguous_partition_selection_refused(self):
        for a,b in [('3.services','var-test'),('services-test','services-test'),('../services','var-test')]:
            with self.subTest(a=a,b=b),self.assertRaises(ValueError): Q.build(self.inputs,self.output,a,b)
            self.assertFalse(self.output.exists())

    def test_changing_config_is_not_legitimized_by_generating_new_outer_pins(self):
        path=self.inputs/'jetstream.json'; path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaises(ValueError): self.build()
        self.assertFalse(self.output.exists())

    def test_missing_retained_json_is_refused(self):
        (self.inputs/'endpoint-input.json').unlink()
        with self.assertRaises(OSError): self.build()
        self.assertFalse(self.output.exists())

    def test_existing_output_is_preserved(self):
        self.output.mkdir(); (self.output/'keep').write_bytes(b'keep')
        with self.assertRaises(ValueError): self.build()
        self.assertEqual((self.output/'keep').read_bytes(),b'keep')

    def test_nested_failure_leaves_no_terminal_review(self):
        with patch.object(Q.V.E,'preview',side_effect=ValueError('fixture')),self.assertRaises(ValueError): self.build()
        self.assertFalse((self.output/'review.json').exists())

    def test_cli_runs_isolated_and_redacts_argument_errors(self):
        command=[sys.executable,'-I','-B',str(Path(Q.__file__)),'--inputs',str(self.inputs),'--output',str(self.output),
                 '--jetstream-partition','services-test','--credentials-partition','var-test']
        result=subprocess.run(command,cwd=self.root,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['inputPinOrigin'],'generated-from-supplied-files')
        bad=subprocess.run(command+['--unknown',str(self.root)],cwd=self.root,capture_output=True,timeout=10)
        self.assertEqual(bad.returncode,2); self.assertNotIn(str(self.root).encode(),bad.stderr)


if __name__=='__main__': unittest.main()
