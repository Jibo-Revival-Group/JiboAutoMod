# Preparing a Windows capture candidate

Python 3.9+ can prepare and inspect a candidate without running the native loader.
This is a review step. It does not authorize capture, authenticate CI provenance,
identify a robot, measure capacity or establish firmware compatibility. Capture
still needs a separately reviewed device window. No device is used by these tools.

## Build evidence and runtime files

The Windows native CI job exports `CaptureComponents-Windows-<source-revision>`.
It includes the actual restricted host, recursively resolved non-system DLLs from
the compiler runtime directory, a static import graph, reviewed C source copies
and compiler-prefix license material. `report.json` pins their bytes. Compiler
location comes from the MSYS build step rather than a hardcoded installation path.

`pe_imports.py` parses bounded PE32+ import directories without loading images.
It supports x86-64 and ARM64 inspection; this export profile requires x86-64.
It rejects malformed/truncated images, path-like names, duplicate imports, more
than 128 imports per image, ambiguous RVA mappings and delay-load tables.
The layout follows Microsoft's [PE format specification](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format).
The export bounds the component graph to 17 images and each image to 16 MiB.

Explicit Windows DLL names and API-set imports are recorded as platform
assumptions. All other imports must resolve in the supplied runtime directory.
This checks the regular static import graph only. Dynamic `LoadLibrary` calls,
DLL search behavior, OS compatibility, USB drivers and complete runtime closure
remain unverified. The license inventory preserves available notices; it does
not determine whether those notices satisfy a proposed distribution's obligations.
Review these before distributing the candidate. There is no automatic install,
driver change, PATH fallback or dependency download.

## Compose from the same CI source revision

Use the Windows export and `ReadOnlyNative-Linux-<source-revision>` from a completed
build of the same reviewed revision. Authenticate the run/source externally and
retain its run metadata. Independently record the raw SHA-256 of each input
`report.json` / `proof.json`; a hash computed from an untrusted download does not
authenticate it. PR builds use the tested merge revision in artifact names;
post-merge Dev builds provide a directly reviewable repository revision.

```powershell
python -I -B capture_bundle.py compose `
  --windows C:\review\windows-components --windows-sha256 <report-file-sha256> `
  --native C:\review\linux-native --native-sha256 <proof-file-sha256> `
  --source-revision <40-hex-revision> --output C:\review\new-candidate
```

Composition rechecks every native proof file, the Windows graph and notices,
capabilities, source revision, and three C source copies (normalizing CRLF only).
It selects only the real `built-components/emmc_server_readonly.bin` and
`built-components/intermezzo.bin`; it never selects the USB-stub fixture bundle.
Output must be new. Failed preparation can leave a partial directory; retain or
discard it explicitly rather than treating it as a complete candidate.

The output contains `bundle/`, `licenses/`, `manifest.json`, `plan.json` and
`review.json`. The fixed plan reads sector 0 through 33 with a 30-second whole
adapter budget. Review reports keep `captureApproved`, `captureAttempted`,
`readyForApply` and `fullRuntimeClosureVerified` false. Input pins cover exact
file bytes; they are operator references, not signatures or physical admission.
Inspect on the matching Windows x86-64 computer using the pins in `review.json`:

```powershell
python -I -B capture_adapter.py inspect `
  --manifest C:\review\new-candidate\manifest.json --manifest-sha256 <manifest-file-sha256> `
  --plan C:\review\new-candidate\plan.json --plan-sha256 <plan-file-sha256> `
  --bundle C:\review\new-candidate\bundle
```

`inspect` never launches native code. `compose` is portable; the resulting
candidate targets Windows x86-64. Linux/macOS bundle exporters and native runtime
closure review remain separate work. Existing cross-platform adapter tests do
not establish live robot compatibility on those systems.

## Audit a later completed capture

After a separately authorized capture, `capture_audit.py` joins its pinned
receipt and the original pinned manifest/plan to the retained `capture.bin`:

```powershell
python -I -B capture_audit.py `
  --receipt C:\capture\receipt.json --receipt-sha256 <receipt-file-sha256> `
  --manifest C:\review\new-candidate\manifest.json --manifest-sha256 <manifest-file-sha256> `
  --plan C:\review\new-candidate\plan.json --plan-sha256 <plan-file-sha256> `
  --disk-sectors <independently-reviewed-sector-count> --output C:\review\new-gpt-audit.json
```

This auditor is portable and never executes a native process. It requires a
completed primary-prefix receipt, two successful process exits, matching raw and
canonical input pins, the exact root artifact name/size/hash and successful
primary GPT checks. Failed/partial/ext-CSD/unrelated receipts cannot be promoted
because a full-size file exists. Receipt assertions are operator-pinned evidence,
not independently authenticated process history. Disk geometry remains operator
supplied. Backup GPT, protective MBR, physical identity, filesystem/release,
restoration and apply readiness remain unverified. See [primary GPT audit](primary-gpt-audit.md)
and [bounded adapter](bounded-capture-adapter.md) for the remaining limits.
