# One offline conversion review bundle

`conversion_review.py` connects preparation, retained recovery bytes, a GPT
audit, and the firewall/endpoint previews in one command. It recomputes the
components from pinned inputs, compares retained GPT/rootfs bytes with a shared
full-storage backup, and exports a local HTML review plus component records.
Python 3.9+ works on Windows, macOS and Linux without extra dependencies.

It does not invoke a subprocess, mount filesystems, open USB, contact a robot or
provider, or apply changes. This is a combined review of the implemented
components, not a complete conversion plan. `reviewAssembled` is an export
status. `completeConversionPlan`, `executionSupported` and `readyForApply`
always remain false.

## Fixed retained input directory

Prepare these ordinary local files using the existing component contracts:

| File | Contract or contents |
| --- | --- |
| `inventory.json` | [Conversion inventory](conversion-preparation.md), including calibration **and full-storage** hashes/sizes |
| `target.json` | Explicit conversion target: isolated, hybrid or named managed provider |
| `audit.json` | Retained [primary GPT audit](primary-gpt-audit.md) referenced by the inventory |
| `recovery-files.json` | [Recovery file map](recovery-file-check.md) using the fixed names below |
| `firewall-input.json` | [Firewall preview manifest](firewall-sector-preview.md) for both rootfs slots |
| `endpoint-input.json` | [Endpoint preview manifest](endpoint-file-preview.md) referencing the exact target file hash |
| `gpt-prefix.bin` | Complete primary GPT prefix |
| `rootfsA.img`, `rootfsB.img` | Entire retained partition images, matching the firewall manifest |
| `jetstream.json` | Retained Jetstream configuration, matching the endpoint manifest |
| `calibration.bin` | Retained calibration bytes, matching the inventory |
| `full-storage.bin` | Entire retained storage backup, matching the inventory |
| `affected-storage.bin` | Optional additional backup, if listed in inventory/recovery map |

The recovery map must use only `calibration.bin`, `full-storage.bin` and optional
`affected-storage.bin`, associated with their matching kinds. Absolute paths and
directory traversal are refused. Other input directory files are ignored. No
existing exported component reports are accepted in place of these inputs.

This aggregation profile requires full storage so it can compare partition
images with their GPT-derived locations. An affected-storage backup alone is
insufficient here; the simpler preparation/recovery tools still have their
original contracts. Full storage is at most 64 GiB and must exactly equal the
supplied disk sector count times 512. Calibration is at most 64 MiB. Each rootfs
retains the preview's 4 GiB bound. These are tool limits, not measured Jibo sizes.

All six JSON documents are individually pinned in a new manifest:

```json
{
  "schema": "openjibo.conversion-review-input.v1",
  "files": {
    "inventory": "<inventory-file-sha256>",
    "target": "<target-file-sha256>",
    "audit": "<audit-file-sha256>",
    "recoveryFiles": "<recovery-map-file-sha256>",
    "firewallInput": "<firewall-manifest-file-sha256>",
    "endpointInput": "<endpoint-manifest-file-sha256>"
  }
}
```

Pins cover exact file bytes, including formatting. The inventory's
`auditEvidenceSha256` must equal the raw `audit.json` file pin. The endpoint
manifest's `targetSha256` must equal the raw target file pin. Placeholder hashes
are invalid. Retain a separately reviewed hash for this outer manifest too.
JSON inputs are bounded to 64 KiB and parsed with duplicate/nonfinite/complexity
checks. No credential or private-key file is required or opened separately.

```powershell
# Windows; existing input directory, new output directory
py -3 conversion_review.py --manifest C:\review\review-input.json `
  --manifest-sha256 <outer-manifest-file-sha256> --inputs C:\review\retained `
  --output C:\review\new-conversion-review
```

```bash
# macOS or Linux
python3 conversion_review.py --manifest /review/review-input.json \
  --manifest-sha256 <outer-manifest-file-sha256> --inputs /review/retained \
  --output /review/new-conversion-review
```

## Relationships checked

The builder recomputes preparation from the pinned inventory/target and checks
the actual recovery files against the inventory. It recomputes primary GPT
checks and compares the retained audit's prefix hash/layout with current results;
old audit assertions do not establish physical identity or issuer provenance.
The supplied audit must retain its original false identity/apply/backup-GPT/MBR
claims. A fresh GPT result is exported, rather than forwarding arbitrary old
record fields.

While holding an open full-storage descriptor, the builder checks recovery bytes
and compares the prefix at byte zero and each entire rootfs at its GPT-derived
byte offset. Image length must equal the GPT partition length. It then runs both
previews on the separately pinned retained files and verifies their common
layout/target references. The full-storage descriptor is checked for observable
mutation through the component calls. Hashing uses bounded buffers. The storage
association phase checks a 600-second software budget around recovery and range
reads; the recovery stream and blocking filesystem I/O have no hard real-time
deadline. Filesystem races or malicious changes that evade metadata checks are
outside this check.

These relations establish byte consistency with an operator-supplied reference.
They do not establish trustworthy acquisition, freshness, physical association,
the actual installed release, or that calibration belongs to the robot.
The Jetstream file's filesystem path and supplied active credentials region are
**not linked to the storage backup** by this version. That gap is shown in both
the review page and JSON; matching unrelated hashes cannot fill it.

## Review the result

Open `review.html` locally. It has no scripts, forms or external resources. It
shows the selected target, proposed firewall sector count, endpoint change,
checked backup byte ranges, coverage gaps and links to component records.
It contains no apply action. Unrelated private config values are omitted from
the page and summary; full endpoint before/after files can contain those values.

`review.json` records source pins, canonical inventory/target references, checked
byte relationships, explicit false associations, remaining gates and a hash/size
index of all other bundle files, including the HTML page. Its own raw file hash
can be pinned separately; stdout's `reviewSha256` is the canonical JSON hash.
The component reports and payloads remain in `firewall/`, `endpoint/`,
`preparation.json`, `recovery.json` and `gpt-audit.json`. Original backups are not
copied into output. Keep the entire bundle private: neighboring sector bytes and
retained config settings can contain personal data.

Exit 0 means export succeeded. Exit 2 means refusal or I/O failure. Output must
be new; existing files are never overwritten. A nested component/export failure
can leave partial output. **Without a successful command, terminal `review.json`
and matching file hashes, the directory is incomplete.** Never promote partial
component reports to a completed bundle. The terminal marker is written last.
Paths are checked against symlink/reparse/device/UNC traversal. Output directories
use private creation modes; the host OS still controls effective permissions.

The complete conversion still requires filesystem/block ownership and allocation,
Jetstream path/region association, native token/notification/SSM routing, DNS,
effective API/Hub protocol and TLS acceptance, applicable provider enrollment,
physical/release association, actual recovery, confirmed bounded apply/readback
and tested rollback. Existing capture candidates and source tests do not open a
device window or authorize deployment.
