# Check retained recovery files

`recovery_evidence.py` reads actual retained backup files and compares every byte's
SHA-256 and total size with an existing conversion inventory. It is a portable,
standard-library Python 3.9+ step for Windows, macOS and Linux. It does not import
USB, exploit or GUI code and opens no robot device. It creates only a new local
receipt; backup files are opened read-only.

This is a file-integrity check. It does not prove that a backup came from the
selected robot, contains a complete/supported storage layout, or can restore the
robot. It does not make a conversion plan executable.

## Run it

Retain the real inventory from [conversion preparation](conversion-preparation.md).
Its backup records must contain the expected hashes and sizes, including
calibration and affected-storage or full-storage. Do not generate expected hashes
from a damaged copy merely to make the comparison pass. The checker requires a
path for every declared backup and refuses missing or extra kinds.

Create a separate local file map. This example uses relative paths, resolved
against the directory containing the map, independently of the current directory:

```json
{
  "schema": "openjibo.recovery-files.v1",
  "files": [
    { "kind": "calibration", "path": "backups/calibration.bin" },
    { "kind": "affected-storage", "path": "backups/affected-storage.bin" }
  ]
}
```

Absolute paths are also accepted. Keep this map local; it contains private paths.
There are exactly two top-level fields and exactly `kind`/`path` on each item.
Duplicate/unknown JSON fields, nonfinite values, maps over 64 KiB and more than
three artifacts are refused. The existing strict conversion inventory parser is
reused rather than introducing a second inventory format.

```powershell
# Windows, from this repository
py -3 recovery_evidence.py --inventory inventory.json --files recovery-files.json --output recovery-check-001.json
```

```bash
# macOS/Linux
python3 recovery_evidence.py --inventory inventory.json --files recovery-files.json --output recovery-check-001.json
```

Choose a new output in an existing directory. Exit 0 means all declared file
bytes matched and a receipt was exported. Exit 2 means the check or export was
refused. Existing receipts are never overwritten, and failed checks export no
receipt. Errors are bounded and do not echo paths or input values. Large images
are streamed in chunks of at most 1 MiB rather than loaded into memory.

## What is checked and recorded

The checker refuses non-regular files, direct UNC/remote/device paths, symbolic
links and Windows reparse points in the inspected path. It also refuses using
one file/hard-link identity for two backup kinds. It compares path identity and
size with the opened file, then checks the opened file's identity, size and
modification/change timestamps before and after hashing. A changed, truncated,
extended or same-size corrupted file fails. The final path must still identify
the same file and size.

This is an ordinary filesystem read, not an immutable snapshot or a defense
against an adversary concurrently replacing directories or restoring metadata.
Windows path and handle timestamp queries can differ, so timestamp stability is
checked on the open handle; path comparisons check identity and size. Filesystem
mount backing is outside the checker: use retained local copies rather than
network mounts. No direct network request or remote URL is used.
Use the physical directory spelling if an ancestor is a system alias (for
example, macOS `/private/var` rather than its `/var` symlink).

The receipt contains the canonical inventory hash, supplied audit/device hashes,
checker/parser code hashes, UTC check time and each checked kind/hash/size. Paths,
serial numbers, credentials and backup contents are absent. The supplied
device/audit hashes are references; the checker cannot authenticate them.

`fileBytesMatchedSuppliedInventory` is true only after all files match.
`robotAssociationVerified`, `restoreTested`, `readyForApply` and
`deviceWritesPerformed` remain false. The existing preparation plan also remains
unchanged and non-executable; it does not treat a supplied receipt as independent
authority. A future orchestrator must bind fresh native audit evidence, supported
layout/profile, retained recovery checks and an exact-change preview before
confirmed apply/readback. Preserve this receipt with the inventory and backups,
then recheck the bytes before any future apply or restore.

## Validation and support limits

The conversion-preparation CI runs both plan/export and file-check tests on
Windows, macOS and Linux using Python 3.9. Tests use synthetic ordinary files,
including a streaming-size artifact, corruption/size mismatch, missing files,
metadata changes, hard links, symlinks where host creation is permitted, map
substitution, exclusive output and sanitized CLI failures. A host that cannot
create test symlinks reports that optional filesystem case as skipped; runtime
symlink/reparse refusal remains in place.

These tests do not certify USB drivers, hardware access, restored calibration,
partition compatibility or conversion on any robot release. The separate
[host support matrix](host-support.md) keeps those acceptance tracks distinct.
