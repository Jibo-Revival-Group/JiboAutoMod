# Audit retained primary GPT evidence

`gpt_audit.py` inspects a retained regular file containing the beginning of a
512-byte-sector storage image, starting at LBA 0. It runs on Python 3.9+ without
external dependencies on Windows, macOS and Linux. It imports no USB, exploit,
GUI or platform adapter and issues no device command. The shared pure parser is
also used by the existing firewall plugin's legacy GPT checks; extracting it does
not add an apply operation or change that writer's admission policy.

This is an offline evidence step toward native audit and exact-change preview.
It is not device detection, a supported conversion profile or permission to write.

## Inputs and command

Retain the primary GPT prefix and its expected SHA-256. Supply independently
reviewed storage capacity in 512-byte sectors; the auditor does not measure it.
Do not use a full device image or live device path here. The prefix must be
between 1 KiB and 2 MiB and include the entire declared primary partition table.

```powershell
# Windows: replace each placeholder with retained evidence and reviewed geometry
py -3 gpt_audit.py --gpt-prefix primary-prefix.bin --disk-sectors DISK_SECTORS --expected-sha256 EXPECTED_SHA256 --output primary-audit-001.json
```

```bash
# macOS/Linux
python3 gpt_audit.py --gpt-prefix primary-prefix.bin --disk-sectors DISK_SECTORS --expected-sha256 EXPECTED_SHA256 --output primary-audit-001.json
```

Disk sectors may be decimal or `0x` hexadecimal. Expected SHA-256 is 64 lowercase
hex characters. It must describe the retained artifact, rather than a replacement
hash invented after corruption. The file's hash must match before parsing.
The [recovery check](recovery-file-check.md) remains a separate check of actual
retained calibration/storage artifacts; a GPT prefix is not a recovery backup.

The auditor reuses regular-file, no-symlink/reparse, identity and stable-open-handle
metadata checks from that checker. Use physical directory spellings (for example
macOS `/private/var`) and retained local copies. It refuses direct UNC/device
paths; mount backing and adversarial directory replacement remain outside the
ordinary filesystem-read guarantee.

Choose a new output in an existing private directory. Exit 0 means the primary
checks passed and a receipt was exported. Exit 2 is a bounded refusal with no
input paths/values in diagnostics. Existing receipts are never overwritten.

## Checked profile

The narrow offline profile checks primary header and entry-array CRCs, revision
1.0 and 92-byte header, reserved field, current/backup LBA consistency with supplied
capacity, nonzero disk ID, bounded table geometry, usable range and partition bounds.
It supports at most 128 entries of 128 bytes each. It rejects overlapping
partitions, duplicate/zero partition IDs, ambiguous normalized names, malformed
UTF-16 names and dirty unused entries. Unsupported formats fail instead of being
treated as a known Jibo profile.

The receipt includes prefix/code hashes, audit time, supplied geometry and the
partition name/start/size projection. It omits raw disk/partition IDs and local
paths. Partition labels are retained evidence, not authenticated device identity;
keep the receipt private. `dualRootfsNamesPresent` only reports that both normalized
rootfs names occur. It does not validate filesystem contents, release family,
calibration, certificates, provider endpoint or patch compatibility.

`primaryGptChecksPassed` records these checks only. `protectiveMbrVerified`,
`backupGptVerified`, `deviceIdentityVerified`, `filesystemProfileVerified`,
`readyForApply` and `deviceWritesPerformed` remain false. `releaseFamily` remains
`unknown`, and geometry is explicitly operator-supplied. The audit time is when
the retained file was checked, not when hardware was captured. The receipt does
not automatically become a conversion inventory or trusted physical fingerprint.

## Next adapter and acceptance

Next is an explicitly read-only native capture adapter with pinned tool/operation
admission, reviewed geometry, bounded ranges/deadlines, unique evidence output and
no write capability. Combine fresh device association, supported filesystem/profile
evidence, verified recovery bytes and exact file/sector/certificate preview before
confirmed apply and readback. The existing mixed read/write plugin is not imported
as that adapter.

The [dedicated storage-read-only build](read-only-capture-build.md) now removes
write/erase handlers from a separate host/payload pair. It is a source/build
prerequisite with stub checks, not hardware acceptance or a bounded capture adapter.

CI runs the offline audit on Python 3.9 across Windows/macOS/Linux and separately
tests the legacy writer/parser projection. Release staging includes all three
offline entry points and their dependencies and invokes them from an unrelated
working directory before packaging. These tests use synthetic files and do not
certify USB, drivers, real hardware conversion or restoration. See the separate
[host matrix](host-support.md).
