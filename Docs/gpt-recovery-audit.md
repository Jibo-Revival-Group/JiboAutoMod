# Protective MBR and both GPT copies in a retained backup

`gpt_recovery.py` checks a pinned full-storage file without mounting it, opening
USB/SSH/network, dispatching a native program or changing any input bytes.
It uses Python 3.9+ and the standard library on Windows, macOS and Linux.
These are offline byte checks; actual Mac installation and robot acceptance
remain separate. No Mac is currently available for that hardware test.

From a trusted checkout or updated offline-review archive:

```text
python3 -I -B gpt_recovery.py --full-storage /private/full-storage.bin --disk-sectors 4096 --expected-sha256 RETAINED_FULL_BACKUP_HASH --output /private/new-gpt-recovery.json
```

Use `py -3` on Windows. Replace the synthetic geometry and paths with retained
evidence. The hash is 64 lowercase hex characters, independently retained before
this check. The file size must equal sectors times 512, between 68 sectors and
64 GiB. The parent directory must exist and the output file must be new. Exit 0
and the matching stdout audit hash indicate a completed export; exit 2 is refusal.
An incomplete export after an I/O failure is not evidence of completed checks.
Keep the backup and report private; they retain storage hashes and locations.

## Supported profile

The existing strict primary parser is unchanged. This additional profile requires
GPT revision 1.0, 92-byte headers with zero reserved remainder, exactly 128 entries
of 128 bytes, a primary header at sector 1 and a backup header at the final sector.
The primary table must fit within the first 2 MiB. Header CRCs, table CRCs, disk
GUID agreement, reciprocal header locations, usable bounds and identical entry
arrays are recomputed. The backup table must lie after usable storage and finish
before its header; a gap before the header is allowed. Existing primary checks
also reject overlapping partitions, duplicate identities/names and dirty unused
entries. Unsupported layouts stop the audit rather than being repaired.

The protective MBR needs its signature and exactly one non-bootable 0xEE record,
starting at sector 1 and spanning the remaining disk (capped at 0xffffffff).
All other records must be zero. Hybrid MBRs are refused. CHS fields, boot code
and the MBR disk signature are not interpreted, authenticated or exported.
This is a bounded profile, not general UEFI conformance or a bootability test.
Format reference: [UEFI GPT disk layout](https://uefi.org/specs/UEFI/2.10/05_GUID_Partition_Table_Format.html).

The full file is hashed once, then metadata is read through the same descriptor.
Regular-file, symlink/reparse/path and observable mutation checks apply before
export. Hashing streams at most 1 MiB per read. Subsequent metadata reads are
limited to 16 calls and 3 MiB under a 600-second cooperative software budget;
blocking filesystem I/O has no hard deadline. Malicious races evading metadata
checks, mounted backing storage and authenticity of acquisition remain outside
this contract. Hash agreement is not physical identity or provenance.

## Integrated v3 conversion review

Add `--gpt-recovery` to the documented `review_request.py` command to produce
`openjibo.conversion-review-bundle.v3`. It keeps the seven pinned inputs of v2,
uses an input manifest with schema `openjibo.conversion-review-input.v3`, and
recomputes the MBR/GPT checks through the held full-backup reader. No supplied
positive audit can substitute for those reads. Pinned-manifest replay through
`conversion_review.py` accepts v3 with the same storage-input override as v2.

The result includes `gpt-recovery.json`, its canonical hash and a coverage row.
Only v3 marks `backupGptVerified` and `protectiveMbrVerified` true, explicitly
scoped to retained backup bytes. The primary-only component and filesystem-only
component retain their narrower flags. Physical robot/calibration association,
installed release, runtime mounts, filesystem allocation/integrity, actual restore,
network/TLS/provider acceptance, bounded apply/readback and rollback remain open.
`readyForApply`, execution support and device/network writes stay false.

V1/v2 behavior and defaults remain unchanged. The updated package's synthetic
demo now exercises v3 using fake MBR and backup GPT bytes. Older published ZIPs
are unchanged and do not gain this tool or these checks.
