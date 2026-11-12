"""Stage or freeze the synthetic-only desktop preview; never operate a robot."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
import platform
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import zipfile


def stage(source, output, revision):
    source = source.absolute()
    output = output.absolute()
    if output.exists():
        raise ValueError('Use a new build output directory.')
    spec = importlib.util.spec_from_file_location('portable_builder', source / 'tools/package_offline_review.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.ordinary(output.parent)
    output.mkdir()
    builder.package(source, output / 'portable', revision)
    root = output / 'stage'
    payload = root / 'offline_payload'
    payload.mkdir(parents=True)
    with zipfile.ZipFile(output / 'portable/JiboRevival-Offline-Review.zip') as archive:
        for item in archive.infolist():
            name = PurePosixPath(item.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in item.filename or ':' in item.filename:
                raise ValueError('Invalid staged payload path.')
            path = payload.joinpath(*name.parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(archive.read(item))
    pin = hashlib.sha256((payload / 'release-manifest.json').read_bytes()).hexdigest()
    support = (source / 'owner_preview_support.py').read_text(encoding='utf-8')
    marker = 'PAYLOAD_MANIFEST_SHA256 = None'
    if support.count(marker) != 1:
        raise ValueError('Expected one payload pin placeholder.')
    (root / 'owner_preview_support.py').write_text(support.replace(marker, 'PAYLOAD_MANIFEST_SHA256 = ' + repr(pin)), encoding='utf-8')
    shutil.copyfile(source / 'owner_preview.py', root / 'owner_preview.py')
    shutil.copyfile(source / 'Docs/owner-preview.md', root / 'README.md')
    builder.validate_community_documentation({'README.md': (root / 'README.md').read_bytes()})
    proof = dict(schema='jiborevival.owner-preview-stage.v1', sourceRevision=revision,
                 syntheticDemo=True, readyForApply=False, hardwareCompatibilityVerified=False,
                 payloadManifestSha256=pin,
                 applicationSources={name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                                     for name in ('owner_preview.py', 'owner_preview_support.py', 'tools/build_owner_preview.py')})
    (output / 'stage-check.json').write_text(json.dumps(proof, indent=2)+'\n', encoding='utf-8')
    return root


def smoke(executable, args, output, label):
    parent = output / (label + '-results')
    parent.mkdir()
    receipt = output / (label + '-receipt.json')
    env = os.environ.copy()
    if not args:
        empty_path = output / (label + '-empty-path')
        empty_path.mkdir()
        env['PATH'] = str(empty_path)
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
    subprocess.run([str(executable), *args, '--smoke', '--output-parent', str(parent),
                    '--receipt', str(receipt)], cwd=output, check=True, timeout=120,
                   stdout=subprocess.DEVNULL, env=env)
    result = json.loads(receipt.read_bytes())
    if result.get('syntheticDemo') is not True or result.get('readyForApply') is not False:
        raise ValueError('Unexpected smoke capability.')
    report = Path(result['reviewFile'])
    if not report.is_file() or not report.is_relative_to(parent):
        raise ValueError('Smoke report is missing or outside result directory.')
    review = json.loads((report.parent / 'review.json').read_bytes())
    if any(review.get(key) is not False for key in ('readyForApply', 'completeConversionPlan', 'executionSupported')):
        raise ValueError('Underlying example review claims device capability.')


def freeze(root, output, revision):
    import importlib.metadata
    name = 'JiboRevival-Conversion-Preview'
    licenses = root / 'licenses'
    licenses.mkdir()
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.is_file():
        python_license = Path(__file__).resolve().parent / 'licenses/Python-LICENSE.txt'
    shutil.copyfile(python_license, licenses / 'Python-LICENSE.txt')
    distribution = importlib.metadata.distribution('pyinstaller')
    for item in distribution.files or []:
        if 'licenses' in str(item).lower() and Path(item).name.lower().endswith(('.txt', '.rst')):
            shutil.copyfile(distribution.locate_file(item), licenses / ('PyInstaller-' + Path(item).name))
    # The Tcl/Tk notice is supplied with source, independently of host packaging.
    shutil.copyfile(Path(__file__).resolve().parent / 'licenses/Tcl-Tk-license.txt', licenses / 'Tcl-Tk-license.txt')
    shutil.copyfile(Path(__file__).resolve().parent / 'licenses/Tk-license.txt', licenses / 'Tk-license.txt')
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
               '--windowed', '--noupx', '--name', name, '--distpath', str(output / 'dist'),
               '--workpath', str(output / 'build'), '--specpath', str(output / 'spec'),
               '--paths', str(root), '--add-data', str(root / 'offline_payload') + ':offline_payload',
               '--add-data', str(root / 'README.md') + ':.',
               '--add-data', str(licenses) + ':licenses', str(root / 'owner_preview.py')]
    # Payload modules load by pinned file path, so static freezer discovery cannot
    # see their stdlib imports. Collect those names without executing the files.
    hidden = set()
    for path in (root / 'offline_payload').glob('*.py'):
        for node in ast.walk(ast.parse(path.read_bytes())):
            if isinstance(node, ast.Import):
                hidden.update(item.name for item in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                hidden.add(node.module)
    for module in sorted(hidden - {'__future__'}):
        if module.split('.')[0] not in sys.stdlib_module_names:
            raise ValueError('Unexpected non-stdlib payload dependency: ' + module)
        command.extend(['--hidden-import', module])
    subprocess.run(command, cwd=root, check=True, timeout=600)
    app = output / 'dist' / (name + '.app' if sys.platform == 'darwin' else name)
    executable = (app / 'Contents/MacOS' / name if sys.platform == 'darwin' else
                  app / (name + ('.exe' if sys.platform == 'win32' else '')))
    smoke(executable, [], output, 'frozen')
    label = {'win32': 'Windows', 'darwin': 'macOS'}.get(sys.platform, 'Linux')
    machine = platform.machine().lower()
    arch = 'arm64' if machine in ('arm64', 'aarch64') else 'x64' if machine in ('amd64', 'x86_64') else machine
    asset_name = name + '-' + label + '-' + arch
    extracted = output / 'extracted'
    extracted.mkdir()
    if sys.platform == 'darwin':
        archive = output / (asset_name + '.zip')
        # Preserve framework symlinks, executable modes and app metadata.
        subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(app), str(archive)], check=True)
        subprocess.run(['ditto', '-x', '-k', str(archive), str(extracted)], check=True)
    elif sys.platform == 'win32':
        archive = output / (asset_name + '.zip')
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(app.rglob('*')):
                if path.is_file():
                    bundle.write(path, path.relative_to(app.parent))
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(extracted)
    else:
        archive = output / (asset_name + '.tar.gz')
        with tarfile.open(archive, 'x:gz') as bundle:
            bundle.add(app, arcname=app.name)
        with tarfile.open(archive) as bundle:
            bundle.extractall(extracted, filter='data')
    extracted_executable = extracted / app.name / executable.relative_to(app)
    smoke(extracted_executable, [], output, 'extracted')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / (archive.name + '.sha256')).write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
    (output / 'owner-app-check.json').write_text(json.dumps(dict(
        sourceRevision=revision, architecture=arch, archive=archive.name, sha256=digest, syntheticDemo=True,
        readyForApply=False, frozenSmokePassed=True, extractedSmokePassed=True,
        runtimePathExcludesPython=True, signed=False,
        hardwareCompatibilityVerified=False), indent=2)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--freeze', action='store_true')
    args = parser.parse_args()
    root = stage(args.source, args.output, args.source_revision)
    smoke(sys.executable, [str(root / 'owner_preview.py')], args.output.absolute(), 'source')
    if args.freeze:
        freeze(root, args.output.absolute(), args.source_revision)
    print('Synthetic owner preview staged and checked; physical conversion unavailable.')


if __name__ == '__main__':
    main()
