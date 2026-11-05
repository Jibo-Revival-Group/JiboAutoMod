"""Community releases reject unrelated project notes before building a payload."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('community_package',ROOT/'tools/package_offline_review.py')
P=importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


class CommunityScope(unittest.TestCase):
    def test_repository_docs_are_community_scoped_and_old_research_is_absent(self):
        files={str(path.relative_to(ROOT)):path.read_bytes() for path in (ROOT/'Docs').glob('*.md')}
        files.update({name:(ROOT/name).read_bytes() for name in ('README.md','CONTRIBUTING.md')})
        P.validate_community_documentation(files)
        self.assertNotIn('oobe-software-supply.md',P.DOCS)
        self.assertFalse((ROOT/'Docs/oobe-software-supply.md').exists())

    def test_package_refuses_private_notes_and_separate_project_links_before_output(self):
        for note in (b'The two incoming factory/OOBE robots have not been inventoried.',
                     b'https://github.com/example/JiboExperiments/blob/revision/guide.md',
                     b'OpenJiboCloud subscription setup',b'No Mac test host is available.'):
            with self.subTest(note=note),tempfile.TemporaryDirectory() as temporary:
                source=Path(temporary).resolve()/'source';source.mkdir();(source/'Docs').mkdir()
                for name in P.SCRIPTS:shutil.copyfile(ROOT/name,source/name)
                for name in P.DOCS:shutil.copyfile(ROOT/'Docs'/name,source/'Docs'/name)
                shutil.copyfile(ROOT/'CONTRIBUTING.md',source/'CONTRIBUTING.md')
                path=source/'Docs/offline-preview.md';path.write_bytes(path.read_bytes()+b'\n'+note)
                output=Path(temporary).resolve()/'release'
                with self.assertRaisesRegex(ValueError,'unrelated project or private test'):
                    P.package(source,output,'a'*40)
                self.assertFalse(output.exists())

    def test_existing_data_format_identifiers_remain_accepted(self):
        P.validate_community_documentation({'contract.md':b'Use openjibo.conversion-target.v1 and openjibo-emmc-readonly.v1.'})


if __name__=='__main__':unittest.main()
