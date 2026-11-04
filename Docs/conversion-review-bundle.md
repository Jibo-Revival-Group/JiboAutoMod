# One offline conversion review bundle

For the optional v3 review, add `--gpt-recovery` to `review_request.py`. This
recomputes the protective MBR and both GPT copies in the same pinned full backup.
See [the recovery audit profile](gpt-recovery-audit.md) for limits, replay and
the remaining physical, filesystem and apply gates. Existing v1/v2 defaults
and their narrower coverage remain unchanged.

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

## One-command request and review

When the retained files and six original component JSON inputs below are already
prepared, `review_request.py` generates the seventh storage manifest and all
outer pins, then runs the v2 review. It needs no pre-existing `storage-input.json`
or outer review manifest, and does not modify the retained directory. Explicit
partition selection is required; the names below are placeholders, not defaults.

Windows:

```powershell
py -3 review_request.py --inputs C:\review\retained --output C:\review\new-review `
  --jetstream-partition <exact-config-partition> --credentials-partition <exact-credential-partition>
```

macOS/Linux:

```bash
python3 review_request.py --inputs /review/retained --output /review/new-review \
  --jetstream-partition <exact-config-partition> --credentials-partition <exact-credential-partition>
```

Open the resulting `review.html`. The indexed `request/review-input.json` and
`request/storage-input.json` preserve generated raw-file pins. Stdout contains
the manifest and canonical review hashes. `inputPinOrigin` explicitly records
`generated-from-supplied-files`; generating hashes is not prior human approval or
proof of provenance. The original inventory audit reference and endpoint target
reference must already match their actual supplied files. This command does not
invent device identity, acquire missing backups, produce component inputs, guess
partitions, enroll a provider or apply changes.

For a separately reviewed pinned replay, use `conversion_review.py` with the
generated outer manifest, its reviewed `--manifest-sha256`, original `--inputs`,
a new `--output`, and `--storage-input` pointing to the generated storage manifest.
That optional location override is v2-only and still requires the exact pinned
file bytes. Input pin origin is then `externally-supplied-manifest-pin`.

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
With a v1 input, the Jetstream file's filesystem path and supplied active
credentials region are **not linked to the storage backup**. That gap remains
explicit in both page and JSON. Use the v2 input below to recompute those byte
relationships; runtime mount/release association still remains unverified.

## Storage-bound review v2

Use the same command and retained directory, plus `storage-input.json` following
the [storage file evidence contract](storage-file-evidence.md). Explicitly select
the two GPT partition names after reviewing retained evidence. Do not infer them
from extraction folder numbers. The storage manifest must use exactly the same
full-storage hash/size as the inventory, GPT prefix hash/size and disk sector count
as the firewall input, and Jetstream hash/size and region as the endpoint input.
Any mismatch is refused before creating output.

The outer manifest changes to v2 and adds a seventh raw-file pin:

```json
{
  "schema": "openjibo.conversion-review-input.v2",
  "files": {
    "inventory": "<inventory-file-sha256>",
    "target": "<target-file-sha256>",
    "audit": "<audit-file-sha256>",
    "recoveryFiles": "<recovery-map-file-sha256>",
    "firewallInput": "<firewall-manifest-file-sha256>",
    "endpointInput": "<endpoint-manifest-file-sha256>",
    "storageInput": "<storage-input-file-sha256>"
  }
}
```

The builder resolves the two fixed partition-root files directly through the
held full-storage descriptor, after the existing recovery checks. It does not
invoke the standalone CLI or reopen/hash the entire backup for this added check.
The original recovery checker still separately hashes recovery files. Subsequent
filesystem reads share the 600-second storage budget, with 8192 requests, 16 MiB
total and 1 MiB per request. The existing ext4/JSON limits remain unchanged.
Unsupported filesystem features remain refused; no real release is admitted by
synthetic fixture success.

The output schema is `openjibo.conversion-review-bundle.v2`. It adds recomputed
`storage/evidence.json`, its canonical hash, a summary of file hashes/locations
and matched region, and these explicit statuses:

| Field | Meaning |
| --- | --- |
| `storageFileEvidenceRecomputed` | The builder ran the reader on checked backup bytes |
| `jetstreamBackupBytesMatched` | The partition-root file matches retained configuration exactly |
| `credentialRegionBackupBytesMatched` | The credential file's region matches the endpoint input |
| `mountMappingVerified` | Always false; actual runtime mounts remain unverified |

The existing `endpointStoragePathAssociationVerified` and
`credentialsRegionAssociationVerified` remain false: byte consistency does not
establish which files the installed runtime actually uses. Physical/release,
filesystem integrity/ownership, effective routing/TLS/provider and apply/rollback
claims also remain false. The static page shows the new evidence separately from
these remaining gates. No positive supplied storage report is accepted as input.
The v1 input retains six pins, v1 output and its original unverified coverage;
adding an unversioned extra pin is refused.

The storage component exports hashes and the region, without full credential
contents or embedded secrets. Existing endpoint before/after payloads can still
contain private settings from the retained configuration. Keep the whole bundle
private. A failure at any component or the final storage mutation check prevents
the terminal `review.json`; partial output must not be used as a completed review.

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
