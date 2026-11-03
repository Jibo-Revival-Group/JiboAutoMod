# Offline storage file evidence

`storage_evidence.py` checks whether a pinned full-storage backup contains the
exact retained Jetstream configuration and the expected credential region. It
resolves two fixed partition-root paths through a narrow ext4 reader, and exports
hashes, inode/extent locations and the region. It runs with Python 3.9+ on Windows,
macOS and Linux, using only the standard library. It performs no mount, subprocess,
USB, SSH, network request or device write.

This is a standalone evidence component. It does not change the existing combined
conversion review contract or remove its path/region coverage gap automatically.
No real firmware image has been admitted as a supported release by its synthetic
tests. A successful result proves consistency within operator-pinned bytes.

## Retained files and manifest

Use an existing private directory containing ordinary local `full-storage.bin`
and `jetstream.json` files. No separate credential file is needed: the reader
opens the credential file inside the backup in memory. Keep the backup private;
it may contain credentials and keys.

The separately pinned manifest has exactly these fields:

```json
{
  "schema": "openjibo.storage-file-input.v1",
  "diskSectors": 4096,
  "fullStorage": {"sha256": "<full-backup-hash>", "sizeBytes": 2097152},
  "gptPrefix": {"sha256": "<primary-prefix-hash>", "sizeBytes": 17408},
  "partitions": {"jetstream": "<exact-GPT-name>", "credentials": "<other-exact-GPT-name>"},
  "jetstream": {"sha256": "<retained-config-hash>", "sizeBytes": 123},
  "credentialsRegion": "us"
}
```

Numbers above are synthetic examples, not Jibo capacity measurements. Hashes are
64 lowercase hexadecimal characters. Backup size must equal `diskSectors * 512`
and be at most 64 GiB. The primary prefix is taken from the backup at byte zero;
there is no separate prefix file. Its size is sector-aligned, 1024 bytes to 2 MiB,
and must include the complete primary entry table. CRC, bounds, unique partition
names/identifiers and non-overlap are recomputed by the primary GPT audit.

Partition names are explicit, case-sensitive, distinct, at most 36 ASCII letters,
digits, dots, hyphens or underscores. The reader does not guess names from
extraction folder numbers. Select them only after examining retained evidence.
Each selected partition is at most 4 GiB. The fixed paths are:

| Role | Partition-root path | Assumed runtime path |
| --- | --- | --- |
| Jetstream | `/etc/jibo-jetstream-service.json` | `/usr/local/etc/jibo-jetstream-service.json` |
| Credentials | `/jibo/credentials.json` | `/var/jibo/credentials.json` |

These runtime paths reflect the source-documented services/var overlays. Reading
the files does not verify that the installed system mounts those partitions there.
`mountMappingVerified`, `installedReleaseVerified` and `deviceIdentityVerified`
remain false. Operator partition selection is recorded explicitly.

Both JSON files are at most 64 KiB. Duplicate keys, nonfinite numbers, excessive
nesting/complexity, oversized strings and non-object roots are refused. Extracted
Jetstream bytes must match `jetstream.json` exactly, including formatting. Its
`HubClient.region-settings` must contain the selected region, with supported
routing fields; any override is also validated. The credential object's top-level
`region` must exactly match `credentialsRegion`, which uses the existing endpoint
preview's lowercase region syntax. No credential issuer, freshness, effective
runtime routing or provider ownership claim follows from this comparison.

## Run and review

Windows:

```powershell
py -3 storage_evidence.py --manifest C:\review\storage-input.json `
  --manifest-sha256 <reviewed-manifest-hash> --inputs C:\review\retained `
  --output C:\review\new-storage-evidence
```

macOS/Linux:

```bash
python3 storage_evidence.py --manifest /review/storage-input.json \
  --manifest-sha256 <reviewed-manifest-hash> --inputs /review/retained \
  --output /review/new-storage-evidence
```

Exit 0 and terminal `evidence.json` indicate a completed export; stdout gives its
canonical JSON hash. Exit 2 indicates refusal. Existing output is never replaced.
An export failure can leave an incomplete new directory; require a successful
command, complete marker and matching hash before using it.

The output contains hashes/sizes, the matched region, GPT-relative and absolute
extent locations, inode numbers, filesystem UUIDs, source hashes and explicit
remaining gates. It does not copy either JSON file or any secret value from them.
The full credential JSON is parsed in memory, including any embedded private
values; `separatePrivateKeyFilesRead=false` means no separate key file is opened.
There is no guarantee of clearing Python process memory after parsing.

## Bounds and remaining work

The backup is hashed through the same read-only descriptor used for later reads.
Observable descriptor/path mutation is checked before completion. Subsequent reads
are bounded to 8192 requests, 16 MiB total and 1 MiB each, within selected GPT
partition bounds. Hashing and reads have a 600-second software budget; blocking
filesystem I/O has no hard deadline. Host filesystem races that evade metadata
checks are outside this evidence claim. The retained config is compared with its
pinned snapshot; later edits to its path do not change those checked bytes.

The ext4 profile reuses the firewall preview's clean revision-one, 1/2/4 KiB,
32-bit, flat-extent constraints. Symlinks, sparse/unwritten/deep extents,
checksumming and unsupported features are refused. Directory sizes must be full
blocks; selected path data extents must not overlap each other or the metadata
read during resolution. This is not fsck, full allocation/ownership validation,
or journal recovery. Backup GPT and protective MBR remain unchecked.

Real release/mount evidence, physical/recovery association, combined review
integration, network/TLS/provider acceptance, complete conversion planning,
bounded apply/readback and rollback remain separate work. `executionSupported`
and `readyForApply` always remain false.
