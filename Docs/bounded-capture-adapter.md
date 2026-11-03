# Bounded read-only capture adapter

`capture_adapter.py` validates a pinned local bundle, stages private copies and
supervises the [dedicated native host](read-only-capture-build.md) for one fixed
read plan. It exports a terminal receipt and retains failures as incomplete.
Python 3.9+ is supported without external Python dependencies.

There is no trusted bundle installed by default. Pins prove that supplied bytes
match an operator-reviewed reference; the adapter does not verify signatures,
build provenance, deployed source or physical identity. `inspect` never launches
a process. `capture` explicitly starts native code and needs a separately reviewed
device window and matched artifacts. No real device was used to test this change.

## Exact pinned inputs

Both inputs are UTF-8 JSON, at most 64 KiB, without duplicate/unknown fields or
nonfinite numbers. SHA-256 arguments cover entire file bytes, including formatting.

The manifest has exactly `schema` (`openjibo.readonly-capture-bundle.v1`),
`sourceRevision` (40 lowercase hex), `os` (`windows`/`macos`/`linux`),
`architecture` (`x86_64`/`arm64`), `protocol` (`openjibo-emmc-readonly.v1`) and
`files`. OS/architecture must match the current host context. Each of 3–19 files
has exactly `{role, name, sha256, sizeBytes}`. Require one of each fixed component:

| Role | Basename |
| --- | --- |
| `host` | `shofel2_t124_readonly.exe` on Windows, otherwise `shofel2_t124_readonly` |
| `payload` | `emmc_server_readonly.bin` |
| `bootstrap` | `intermezzo.bin` |

Optional `runtime` entries are host-appropriate `.dll`, `.dylib` or versioned `.so`
files. Names are unique case-insensitively, single ASCII basenames, without path
traversal, reserved device names or scripts. Each file is at most 16 MiB; total
size is at most 64 MiB. Payload/bootstrap have tighter 128 KiB/256-byte limits.
Every listed file is hash/size checked; missing assets never trigger installation
or a general-purpose fallback. Windows host-only CI output is not a full bundle.
The separate [candidate preparation tool](capture-candidate.md) can join a static
Windows runtime export to an actual ARM build from the same source revision.

Listed runtime files are pinned, but PE/ELF/Mach-O imports are not inspected and
complete dependency closure is not established automatically. The OS loader/
platform libraries remain trusted. Real bundle review must cover non-system
dependencies; capabilities and filenames are not artifact provenance.

The plan has exactly `schema` (`openjibo.readonly-capture-plan.v1`),
`sourceRevision` (matching manifest), `bundleSha256` (manifest file pin), `kind`,
`startSector`, `sectorCount`, `timeoutSeconds`. Supported plans are:

- `primary-gpt-prefix`: start zero and 34–4,096 sectors of 512 bytes.
- `ext-csd`: start zero and count one, producing 512 bytes.

Timeout is an integer from 1–60 seconds. There is no arbitrary offset, executable,
argument string, operation or write mode. Inputs cannot widen native protocol caps.

## Inspect, then explicitly capture

Use `py -3` on Windows in place of `python3`; replace the hash placeholders:

```text
python3 capture_adapter.py inspect --manifest bundle.json --manifest-sha256 MANIFEST_HASH --plan plan.json --plan-sha256 PLAN_HASH --bundle reviewed-bundle
```

Inspection checks pins, contracts, host context and listed file bytes, without
output creation or binary execution (including capabilities). It reports matching
hashes, not approval. After a real bundle, plan and device window are reviewed:

```text
python3 capture_adapter.py capture --manifest bundle.json --manifest-sha256 MANIFEST_HASH --plan plan.json --plan-sha256 PLAN_HASH --bundle reviewed-bundle --output capture-001
```

The output parent must exist and be private; a new result directory is required.
Existing directories are never reused. Use physical local paths, such as macOS
`/private/var` rather than `/var`. Shared checks refuse symlink/reparse/UNC/device
paths. Mount backing and adversarial filesystem races remain outside the ordinary
local-file guarantee. Unix output starts private; Windows needs reviewed parent ACLs.

## Supervision and receipt meaning

Components are rechecked while staging, after capabilities and after the read.
The native host launches directly without shell or inherited stdin. Its reduced
environment omits unrelated credentials and loader injection variables and uses
private runtime search paths plus trusted platform roots. No provider, database,
cloud identity, dependency installer, sudo or automatic retry is used.

Capabilities must exactly match the read-only contract. One monotonic budget
covers component checks/copy, capability/read processes and evidence checks;
filesystem loops check it cooperatively. Diagnostic pipes are drained concurrently
with bounded data: capability stdout 4 KiB, capture stdout 16 KiB, stderr at most
8 KiB (4 KiB during capabilities). Limit violations fail the attempt. Raw capture
text is discarded; receipts contain bounded counts/hashes, not diagnostics. Pipe
EOF is required in addition to initial process exit.

POSIX children use their own session/process group. Windows children start
suspended, enter a kill-on-close job, then resume. Cancellation/timeout triggers
termination, with up to two seconds of process cleanup and short drain grace.
Kernel/filesystem waits are not forcibly bounded; this is not hard realtime or
a sandbox for untrusted pinned code. Artifact review remains necessary.
The [cleanup reliability notes](capture-process-cleanup.md) describe independent
termination/wait/pipe checks, preservation of the first failure, sanitized phase
metadata and refusal of otherwise successful captures when cleanup fails.

Completion requires exit zero, EOF within diagnostic limits, exact-size regular
data, stable hashes and unchanged components. A new root `capture.bin` and
`receipt.json` describe the result. Receipts include raw input pins, canonical
validated objects/hashes, code references, times and sanitized outcomes. They omit
absolute local paths, raw diagnostics, credentials and serial numbers.

Failure receipts have `captureCompleted=false`. Failed data remains incomplete
under `work/`; a failed final export may also leave an unadmitted root copy.
Full-size data after a failed native exit is still incomplete. File presence,
length, a partial/failed receipt or diagnostic silence is not success. Exit 0
means successful inspection or completed receipt export; exit 2 means refusal/
failure. Interrupted exports can require inspection of incomplete local files.

Even completion leaves `readyForApply`, `deviceIdentityVerified`, `resetVerified`
and `robotCompatibilityVerified` false. Capture can load RAM and change boot/
session state. `deviceStateUncertain` remains true after dispatch; EXIT does not
prove normal boot/reconnect. No storage-write command is requested.

## Acceptance and next work

Synthetic process tests cover malformed pins/contracts, component changes,
capability substitution, shared deadlines, cancellation, diagnostic flooding,
descendant pipe holders, output reuse and missing/short/oversized/full-but-failed
files. Native CI runs this public CLI against the actual C host linked to USB/RCM
stubs for prefix and EXT_CSD capture. These tests cannot contact hardware.

Next: reviewed provenance/dependency closure and a fresh hardware window, then
real capture and uncertain-state recovery acceptance. Prefix receipts can feed
the [GPT audit](primary-gpt-audit.md); backup GPT/MBR, device/firmware/filesystem
support and recovery association still precede exact-change conversion preview
or confirmed writer integration. Registration and ownership remain separate.
