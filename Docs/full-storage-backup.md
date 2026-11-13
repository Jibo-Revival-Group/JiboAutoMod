# Full user-area backup

The restricted capture tools have a separate full user-area profile. It measures
the card's EXT_CSD sector count again before streaming the image, sends bounded
read commands and verifies the retained file. It issues no installed-OS boot,
configuration-write or conversion command.

This is an experimental acquisition path. Synthetic tests and successful builds
do not qualify a robot, firmware, USB setup or recovery procedure. Capture loads
RAM and initializes hardware; storage-read-only operation can still affect the
device's session state. Review a matched bundle and an attended device procedure
before using `capture`. There is no automatic retry or fallback writer.

For an unprovisioned device, preserving a backup before the first normal boot
retains the best available pre-setup reference. A normal boot can update storage.
Inspect physical condition and identify the intended device first, keeping other
devices disconnected from the capture computer. Entering recovery mode and
returning from it remain separately attended hardware steps.

## Measure capacity first

Use a completed, reviewed `ext-csd` capture from the intended device. This older
profile reads exactly 512 bytes and has a maximum 60-second adapter budget.
Derive capacity from its retained file and independently recorded SHA-256:

```text
python3 storage_capacity.py --input ext-csd-capture/capture.bin --expected-sha256 EXT_CSD_HASH --output capacity.json
```

Use `py -3` instead of `python3` on Windows. The decoder reads the four-byte
little-endian EXT_CSD SEC_COUNT field, refuses missing, malformed, zero or
out-of-range evidence, and exports metadata rather than register bytes. Its hash
binds that local file; it does not prove the capture's authenticity or which
physical device supplied it. Keep the capacity capture associated with the
intended device. The full read checks the live count against the plan again.

The count describes the eMMC main user area. Boot partitions, RPMB and fuses are
outside this backup profile. The inherited `0x1D60000` admission limit is an upper
bound, not a default capacity or a measurement.
The field layout and decoding follow the Linux kernel's
[EXT_CSD definitions](https://github.com/torvalds/linux/blob/master/include/linux/mmc/mmc.h)
and [eMMC capacity handling](https://github.com/torvalds/linux/blob/master/drivers/mmc/core/mmc.c).

## Prepare an exact full plan

Use a matched [read-only bundle](read-only-capture-build.md), including the host,
ARM payload, bootstrap and required reviewed runtime libraries. The bundle
manifest contract is unchanged. The host must also support `--full-capabilities`.
The native action is `EMMC_READ_FULL expected_sector_count new_file`; its count
is hexadecimal and must equal the EXT_CSD measurement before the image READ
commands. The existing controller/handshake initialization already includes a
sector-zero read; it is not a capacity or full-image measurement.
Each wire READ remains limited to 4,096 sectors using the existing read-only
protocol and framed replies. Existing short `EMMC_READ` limits are unchanged.

A full plan uses schema `openjibo.readonly-full-storage-plan.v1`, kind
`full-user-area`, start zero, the measured sector count, a 1–21,600 second overall
budget, and the exact `capacityEvidence` object from `capacity.json`:

```json
{
  "schema": "openjibo.readonly-full-storage-plan.v1",
  "sourceRevision": "<reviewed-40-hex-source-revision>",
  "bundleSha256": "<manifest-file-sha256>",
  "kind": "full-user-area",
  "startSector": 0,
  "sectorCount": 8192,
  "timeoutSeconds": 21600,
  "capacityEvidence": {
    "schema": "openjibo.storage-capacity.v1",
    "sectorSizeBytes": 512,
    "storageSectorCount": 8192,
    "sizeBytes": 4194304,
    "sourceHash": "<ext-csd-file-sha256>",
    "sourceBytes": 512,
    "physicalIdentityVerified": false,
    "captureAuthenticityVerified": false
  }
}
```

The numbers are synthetic examples. Copy the actual measured values; never use
example geometry for a real device. Record the entire plan file's SHA-256 after
review. The v1 GPT-prefix and EXT_CSD schemas cannot be widened into full plans.

## Inspect destination, then capture

Choose an existing private parent directory on a filesystem that supports files
larger than the measured backup. FAT32 cannot store a normal full user-area image.
Known unsupported Windows and Linux FAT formats are refused; unknown filesystems
and macOS file-size capability are not automatically qualified. Do not use the robot itself as the
destination. Keep the computer and device supplied with power and prevent sleep
for the reviewed capture window. The complete operation may take hours.

```text
python3 capture_adapter.py inspect --manifest bundle.json --manifest-sha256 MANIFEST_HASH --plan full-plan.json --plan-sha256 PLAN_HASH --bundle reviewed-bundle --output new-backup
```

Full inspection requires the proposed new output path. It checks input/component
pins and available space without creating the directory or launching a binary.
Reserve at least twice the measured image size, component sizes and 64 MiB extra:
the adapter keeps a working capture and a verified final copy on the host. These
are two host copies of one device acquisition, not two independent device reads
or copies on separate physical drives. Leave additional operating-system space.

After the bundle, plan, destination and device window are reviewed:

```text
python3 capture_adapter.py capture --manifest bundle.json --manifest-sha256 MANIFEST_HASH --plan full-plan.json --plan-sha256 PLAN_HASH --bundle reviewed-bundle --output new-backup
```

The new output directory is made private before native code starts. The adapter
checks capacity, per-command framing, total size, completion/EXIT, file writes and
sync, and separately rehashes the final copy. One overall budget includes copies
and verification. Progress is bounded; raw diagnostics do not enter receipts.

## Keep a completed result intact

Success requires exit 0 and a terminal `receipt.json` with `outcome=completed`
and `captureCompleted=true`. The retained full artifact is `full-storage.bin`;
the working copy remains under `work/`. Retain its recorded size/hash and receipt
privately. This filename can feed the existing [offline intake](oobe-storage-intake.md)
after its explicit input manifest and primary-prefix evidence are prepared.
The existing `capture_audit.py` remains a v1 primary-GPT-prefix checker; it does
not automatically admit this full receipt or qualify restoration.

A short file, timeout, cancellation, protocol/capacity mismatch, output failure
or failed EXIT is incomplete even if a file exists at the expected size. Keep
failed artifacts distinct; do not retry automatically or treat them as backups.
Follow the [recovery guidance](bounded-capture-adapter.md#failure-diagnostics-and-recovery)
for uncertain device state. The full profile requests review before normal boot.
For a device whose first normal boot is being preserved, keep that decision
attended: normal boot may change the original state before a backup is verified.
Verified normal boot is still separate, never an automatic capture action.

File hashes, capacity and completed transport do not establish physical identity,
factory state, OOBE status, installed release, calibration association, restore
readiness or authority to apply changes. Those flags remain false. A second
physical acquisition, independent retained copy or restore exercise needs its
own reviewed procedure; a host rehash alone does not provide those guarantees.
