#!/usr/bin/env python3
"""Build a review from the bundled synthetic demo; optionally open its local page."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import uuid
import webbrowser


def main():
    if sys.version_info < (3, 9):
        raise SystemExit('Python 3.9 or newer is required.')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='New output directory; defaults to a unique folder beside this script.')
    parser.add_argument('--open',action='store_true',help='Open the completed local HTML review in your browser.')
    parser.add_argument('--no-open',dest='open',action='store_false',help='Generate without opening a browser (also accepted by launchers).')
    parser.add_argument('--oobe-intake',action='store_true',help='Observe the separate synthetic blank-credential intake fixture.')
    parser.set_defaults(open=False)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    inputs=root/('demo/oobe' if args.oobe_intake else 'demo/retained')
    if not inputs.is_dir():
        parser.exit(2,'Bundled synthetic demo is missing. Use the offline-review release archive.\n')
    name=('demo-oobe-intake-' if args.oobe_intake else 'demo-review-')+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    output=args.output or root/name
    module_name='oobe_intake' if args.oobe_intake else 'review_request'
    spec=importlib.util.spec_from_file_location(module_name,root/(module_name+'.py'))
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    domain_errors=((module.F.E.Ext4PathError,module.B.A.CaptureFailure) if args.oobe_intake else
                   (module.V.F.E.Ext4PathError,module.V.S.F.E.Ext4PathError,module.V.F.F.FirewallPatchError,
                    module.V.F.A.CaptureFailure,module.V.B.A.CaptureFailure))
    errors=(ValueError,OSError,UnicodeError,KeyError,TypeError,RecursionError)+domain_errors
    try:
        if args.oobe_intake:
            manifest=inputs/'intake-input.json'
            result=module.inspect(manifest,module.F.sha(module.B.read(manifest,module.P.LIMIT)),inputs,output,synthetic_demo=True)
        else: result=module.build(inputs,output,'services-test','var-test')
    except errors:
        parser.exit(2,'Synthetic demo refused; check extracted files and a new writable output directory.\n')
    page=Path(output).absolute()/('intake.html' if args.oobe_intake else 'review.html')
    preparation=module.P if args.oobe_intake else module.V.P
    print(json.dumps(dict(syntheticDemo=True,demoKind='oobe-intake' if args.oobe_intake else 'conversion-review',
                          reviewFile=str(page),reviewSha256=preparation.digest(result),readyForApply=False)))
    if args.open: webbrowser.open(page.as_uri())


if __name__=='__main__': main()
