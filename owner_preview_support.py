"""Local, synthetic-only backend for the Jibo Revival owner preview."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import uuid

# Filled by the owner-app builder; a raw source checkout has no bundled demo.
PAYLOAD_MANIFEST_SHA256 = None


def ordinary(path):
    path = Path(path).absolute()
    for component in (path, *path.parents):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 1024:
            raise ValueError('Choose an ordinary local folder for preview results.')
    return path


def resource_root():
    candidate = Path(__file__).resolve().parent / 'offline_payload'
    # Frozen macOS apps link their data into Contents/Resources. Resolve only
    # this fixed bundled location; owner-selected result paths stay alias-free.
    return candidate.resolve(strict=True) if getattr(sys, 'frozen', False) else candidate


def default_output_parent():
    if sys.platform == 'win32':
        root = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
    elif sys.platform == 'darwin':
        root = Path.home() / 'Library/Application Support'
    else:
        root = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state'))
    return root / 'JiboRevival/ConversionPreview'


def verify_payload():
    root = ordinary(resource_root())
    manifest_path = ordinary(root / 'release-manifest.json')
    raw = manifest_path.read_bytes()
    if (not isinstance(PAYLOAD_MANIFEST_SHA256, str) or len(raw) > 1048576 or
            hashlib.sha256(raw).hexdigest() != PAYLOAD_MANIFEST_SHA256):
        raise ValueError('The bundled example is unavailable or changed. Use a fresh preview package.')
    manifest = json.loads(raw)
    if (manifest.get('syntheticDemo') is not True or manifest.get('readyForApply') is not False or
            manifest.get('hardwareCompatibilityVerified') is not False):
        raise ValueError('The bundled example is not a preview.')
    records = manifest['files']
    if not isinstance(records, list) or not 1 <= len(records) <= 100:
        raise ValueError('Invalid example manifest.')
    seen = set()
    for record in records:
        name = record['file']
        part = PurePosixPath(name)
        if (not isinstance(name, str) or name in seen or part.is_absolute() or
                '..' in part.parts or '\\' in name or ':' in name):
            raise ValueError('Invalid example path.')
        seen.add(name)
        path = ordinary(root.joinpath(*part.parts))
        if not path.is_file() or not 0 < path.stat().st_size <= 4194304:
            raise ValueError('Invalid example file.')
        value = path.read_bytes()
        if len(value) != record['sizeBytes'] or hashlib.sha256(value).hexdigest() != record['sha256']:
            raise ValueError('The bundled example changed. Use a fresh preview package.')
    required = {'review_request.py', 'demo/retained/inventory.json', 'demo/retained/full-storage.bin'}
    if not required <= seen:
        raise ValueError('The bundled example is incomplete.')
    allowed = seen | {'release-manifest.json', 'SHA256SUMS'}
    directories = {str(parent) for name in allowed for parent in PurePosixPath(name).parents if str(parent) != '.'}
    pending = [root]
    while pending:
        directory = pending.pop()
        for path in directory.iterdir():
            path = ordinary(path)
            name = path.relative_to(root).as_posix()
            if path.is_dir() and name in directories:
                pending.append(path)
            elif not path.is_file() or name not in allowed:
                raise ValueError('The bundled example contains unexpected files.')
    return root


def prepare_demo(output_parent=None):
    """Generate a new sample review, never selecting or contacting a real robot."""
    root = verify_payload()  # Validate all code/data before loading any module.
    if output_parent is None:
        parent = default_output_parent().absolute()
        # Validate existing ancestors before creating the per-user result folder.
        ancestor = parent
        while not ancestor.exists():
            ancestor = ancestor.parent
        ordinary(ancestor)
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    else:
        parent = Path(output_parent).absolute()
    parent = ordinary(parent)
    if not parent.is_dir():
        raise ValueError('Choose an existing local result folder.')
    output = parent / ('sample-' + uuid.uuid4().hex)
    spec = importlib.util.spec_from_file_location('_owner_review_request', root / 'review_request.py')
    module = importlib.util.module_from_spec(spec)
    previous_bytecode = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
        result = module.build(root / 'demo/retained', output, 'services-test', 'var-test')
    finally:
        sys.dont_write_bytecode = previous_bytecode
    if result.get('readyForApply') is not False or result.get('completeConversionPlan') is not False:
        raise ValueError('Example returned an unsupported capability.')
    page = ordinary(output / 'review.html')
    if not page.is_file():
        raise ValueError('Example report was not created.')
    return dict(reviewFile=str(page), outputDir=str(output),
                summary='The example review is ready. It describes sample data only; no Jibo was connected or changed.',
                syntheticDemo=True, readyForApply=False)
