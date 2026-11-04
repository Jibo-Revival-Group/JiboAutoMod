# Open Jibo offline review preview

This preview lets you try the conversion review flow on Windows, macOS or Linux
with Python 3.9 or newer. No extra Python packages, Docker, USB driver, robot,
credentials or network connection are needed for the bundled demo. Python must
already be installed. Extract the entire ZIP into a writable local folder first.

## Try the synthetic demo

Windows: double-click `Run-Demo.cmd`, or run:

```powershell
py -3 -I -B demo_review.py --open
```

macOS/Linux:

```bash
python3 -I -B demo_review.py --open
```

You can also run `sh run-demo.sh`. If the browser does not open, use the
`reviewFile` path printed by the command. Omit `--open` to generate the review
without opening a browser. Every run creates a new `demo-review-*` directory
beside the script; existing results are preserved. An explicit `--output` must
name a new directory whose parent already exists.

The demo contains generated fake storage, partitions, configuration, calibration
and a fake credential region. It cannot establish anything about your robot.
The HTML page shows recovery/GPT checks, firewall and endpoint previews, matched
configuration/region bytes and the remaining gates. **Apply is unavailable.**
Generated request manifests and a file hash index are retained with each result.

Updated packages run a v3 synthetic review with matching primary/backup GPT
tables and a protective MBR. The [recovery-table audit](gpt-recovery-audit.md)
explains the supported offline profile and the `--gpt-recovery` option for your
retained inputs. Apply, physical identity and actual recovery remain unverified.
Older published archives retain their original demo and tools.

The separate pre-provisioning demo uses a synthetic blank credential file:

```text
python demo_review.py --oobe-intake --open
```

Use the same OS-specific Python command as above. This page is explicitly marked
Synthetic demo and observes missing/blank credential fields without inventing a
region. It does not prove factory/OOBE state or readiness to provision. See
[OOBE storage intake](oobe-storage-intake.md) in Docs for the separate contract.
The older preview.1 release remains unchanged; it has only the original demo.

## Review your retained inputs

Prepare the documented inventory, target, audit, recovery map, firewall/endpoint
inputs and retained backup files. Then use `review_request.py` with explicit GPT
partition choices. See [the one-command flow](conversion-review-bundle.md#one-command-request-and-review)
in the Docs folder (`Docs/conversion-review-bundle.md`). The demo's partition
names are synthetic examples; do not copy them as a real robot profile.

The tool changes no input backup and performs no device write, provider enrollment
or deployment. Runtime mount mapping, installed release, physical identity,
filesystem integrity/ownership, runtime/TLS/provider acceptance, restoration,
bounded apply/readback and rollback still need separate validation. This preview
does not include native executables, device payloads or the interactive device menu.
Some Python dependency modules retain capture-related APIs; no native capture
components are supplied or invoked by the demo/review entry points.

## Verify the download

Compare the ZIP's SHA-256 with the published `.sha256` asset before extracting.
Windows: `Get-FileHash .\OpenJibo-Offline-Review.zip -Algorithm SHA256`.
macOS: `shasum -a 256 OpenJibo-Offline-Review.zip`.
Linux: `sha256sum OpenJibo-Offline-Review.zip`.

`release-manifest.json` records the source commit and each payload hash/size;
`SHA256SUMS` also indexes the manifest. These are integrity records, not signatures
or proof of trustworthy acquisition. Python/Markdown source uses LF line endings;
the exact firmware signature profile is preserved. The synthetic demo and archive
metadata are deterministic so CI can compare all three OS builds byte for byte.

This is a development prerelease of offline review, not hardware conversion or a
hosted cloud release. Real retained configuration and future reviews may contain
private data; keep those inputs and output bundles private.
