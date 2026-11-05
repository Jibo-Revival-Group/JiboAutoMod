# Read-only pre-provisioning credential intake

`oobe_intake.py` observes a fixed credential path in a pinned storage backup
without requiring an existing region. This is a separate intake contract for
unprovisioned or partial evidence. The credentialed storage/conversion review
keeps its existing strict requirements. No credential or region is invented.

The tool runs with Python 3.9+ on Windows, macOS and Linux using the standard
library. It does not mount a filesystem, run a subprocess, open USB/SSH/network,
write a device, create credentials, enroll an owner or produce a conversion plan.

## Inputs

An ordinary private input directory contains `full-storage.bin`. A separately
pinned manifest has exactly these fields:

```json
{
  "schema": "openjibo.oobe-intake-input.v1",
  "diskSectors": 4096,
  "fullStorage": {"sha256": "<full-backup-hash>", "sizeBytes": 2097152},
  "gptPrefix": {"sha256": "<primary-prefix-hash>", "sizeBytes": 17408},
  "credentialsPartition": "<exact-GPT-name>"
}
```

Numbers above are synthetic examples, not measured Jibo geometry. Hashes are 64
lowercase hex characters. Backup size must equal `diskSectors * 512`, at most
64 GiB. Primary-prefix bytes are read at offset zero, 1024 bytes to 2 MiB, sector
aligned and containing the whole primary GPT table. The selected partition name
is explicit, case-sensitive, 1–36 ASCII letters/digits/dots/hyphens/underscores.
The entire selected partition is at most 4 GiB. CRC, bounds, uniqueness and
non-overlap checks are recomputed; extraction directory numbers are not GPT names.

The fixed partition-root path is `/jibo/credentials.json`. Actual `/var` mount
mapping and installed release remain unverified. No external credential file,
region input, calibration claim or supplied positive report is accepted.

## Run

```powershell
py -3 oobe_intake.py --manifest C:\review\intake-input.json `
  --manifest-sha256 <reviewed-manifest-hash> --inputs C:\review\retained `
  --output C:\review\new-intake
```

```bash
python3 oobe_intake.py --manifest /review/intake-input.json \
  --manifest-sha256 <reviewed-manifest-hash> --inputs /review/retained \
  --output /review/new-intake
```

The output must be new. Exit 0, terminal `intake.json`, matching hashes and
stdout's canonical intake hash indicate completed observation. Exit 2 is refusal.
Partial export is incomplete without a successful command and terminal marker.
The static `intake.html` has no scripts/forms/external resources.

## Typed observations

| Observation | Meaning |
| --- | --- |
| `parent-absent` | The fixed `/jibo` directory entry was not found; review the selected path/profile, not a provisioning assumption |
| `leaf-absent` | The complete supported parent directory scan found no credential entry |
| `empty-file` | A regular zero-byte leaf has a validated empty inline extent header; JSON fields are unobserved |
| `identity-fields-absent-or-blank` | A valid object has only absent/empty-string states for the three selected identity fields |
| `partial-or-unsupported-fields` | Region-only, partial, null, nonstring or unsupported-region observations require manual review |
| `identity-fields-present` | Nonempty string fields and supported region syntax were observed; credentials are not validated |

Field states distinguish `absent`, `blank`, `null`, `unsupported-type`, `present`
and `unobserved`. Only `accessKeyId`, `secretAccessKey` and `region` field names
enter the report. Unknown field names/values are omitted; a boolean records their
presence. A region value is exported only when it matches the existing bounded
lowercase region syntax. Invalid/unknown regions are not substituted or repaired.

The report contains hashes, inode/range locations, directory scan evidence,
field states and a workflow hint. It exports no raw credential file or secret
values. Credential JSON, including embedded secrets, is parsed in memory; memory
erasure is not guaranteed. Keep the backup and report private.

Absent/blank fields are not proof of a factory-new robot, OOBE mode, no prior
owner or safe reset. Deleted credential bytes may still exist elsewhere in the
backup; absence is not erasure. A complete-looking file is not valid credential
or ownership evidence. `factoryStateVerified`, `oobeStateVerified`, credential
validity, physical/release/mount/recovery association and apply readiness stay
false. Workflow hints request review; they authorize no provisioning or write.

## Filesystem and acquisition limits

The full backup is hashed then read through the same descriptor, with observable
mutation checks before export. The existing clean, flat-extent, 32-bit ext4
profile is reused. Sparse/unwritten/deep extents, symlinks, unsupported features,
duplicate selected names and malformed directory records refuse the operation.
Errors are not translated into absence. Directory data must be full blocks and
non-overlapping with selected data/metadata reads. Metadata reads must remain
inside declared filesystem bounds. Zero-byte files are admitted only at this
fixed leaf with an empty valid extent header; the older reader is unchanged.

JSON is bounded to 64 KiB with existing duplicate/nonfinite/depth/node/string
checks. Full parsing of a supported directory must finish before absence can be
reported. Post-hash I/O is bounded to 8192 reads/16 MiB, at most 1 MiB per request,
under a 600-second software budget. Blocking filesystem I/O has no hard deadline;
malicious races that evade metadata checks remain outside this observation.
This is not fsck, allocation-bitmap validation, backup GPT/MBR verification,
trustworthy acquisition or an admitted real firmware profile.

## Synthetic demo

Updated offline-review packages include a separate blank-credential fixture:

```text
python demo_review.py --oobe-intake --open
```

Use `py -3` on Windows or `python3` on macOS/Linux as appropriate. The page is
marked Synthetic demo. Existing `offline-review-2026.11.03-preview.1` archives
remain unchanged and do not contain this newer intake tool/demo. The original
demo continues to exercise the credentialed conversion-review flow separately.

## Software supply

These credential observations do not identify every installed component or determine software licensing. Use the [OOBE software supply and provenance guide](oobe-software-supply.md) to record factory software, missing capabilities and the applicable delivery rights before planning an upgrade.
