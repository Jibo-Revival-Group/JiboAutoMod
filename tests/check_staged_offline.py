"""Verify the real staged package, from outside its working directory."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    root = parser.parse_args().root.absolute()
    scripts = ('conversion_plan.py', 'recovery_evidence.py', 'gpt_audit.py', 'capture_adapter.py')
    required = (*scripts, 'gpt_layout.py', 'capture_process.py', 'Docs/conversion-preparation.md',
                'Docs/recovery-file-check.md', 'Docs/primary-gpt-audit.md', 'Docs/bounded-capture-adapter.md')
    if not all((root/name).is_file() for name in required):
        raise SystemExit('Staged offline package is incomplete.')
    with tempfile.TemporaryDirectory() as other:
        for script in scripts:
            result = subprocess.run([sys.executable, '-I', '-B', str(root/script), '--help'],
                                    cwd=other, capture_output=True, timeout=10)
            if result.returncode != 0:
                raise SystemExit('Staged offline entry point failed without repository import fallback.')
        probe = subprocess.run([sys.executable, '-I', '-B', '-c',
            "import runpy,sys; runpy.run_path(sys.argv[1],run_name='staged_audit'); assert not any(n.startswith(('Exploits','usb','tkinter','config')) for n in sys.modules)",
            str(root/'capture_adapter.py')], cwd=other, capture_output=True, timeout=10)
        if probe.returncode != 0:
            raise SystemExit('Staged audit imported unexpected device/platform code.')
    print('Staged offline entry points and dependencies passed without device access.')


if __name__ == '__main__': main()
