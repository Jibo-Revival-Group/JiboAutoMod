# Dedicated storage-read-only capture build

The `readonly` target creates a separate host loader and eMMC payload. Storage
write/erase handlers are omitted from both at compile time. Arbitrary payload,
memory/fuse dump, boot and debug commands are absent from the restricted host.
The original general-purpose build keeps its existing protocol and behavior.

This is an experimental source/build boundary. No robot was connected to validate
it. A real run still loads device RAM, initializes the controller and changes
boot/session state. Storage-read-only does not mean the robot is unaffected.

## Build and inspect

Use the existing [toolchain prerequisites](host-support.md). On Linux/macOS:

```bash
make -C Exploits/Shofel readonly
Exploits/Shofel/shofel2_t124_readonly --capabilities
```

Outputs are `shofel2_t124_readonly`, `emmc_server_readonly.bin` and
`intermezzo.bin`. Linux/macOS CI builds the host and payload. Windows UCRT64 CI
builds `shofel2_t124_readonly.exe` and tests its host policy; it does not build
the ARM payload/bootstrap in that job. A Windows host-only package is incomplete
for capture. Native runtime/DLL prerequisites remain; these builds do not certify
cross-OS USB access or hardware conversion.

`--capabilities` returns JSON schema `openjibo.storage-readonly-capabilities.v1`
with protocol `openjibo-emmc-readonly.v1`, admitted commands, range limits and
fixed payload filename. `--help` describes the restricted CLI. Both return before
file admission, output creation or USB discovery. They do not authenticate a build.

## Command and protocol boundary

Capture admits only `EMMC_STATUS`, `EMMC_READ` and `EMMC_READ_EXT_CSD`, with an
internal EXIT back to RCM. Capture commands require a separately reviewed device
window and exact capture plan; none was run against hardware in this change.

The pair uses distinct opcodes and a versioned status/limit handshake, refusing
legacy or mismatched payload replies. Host and payload independently admit read
ranges of 1–4,096 sectors, 512 bytes each, below `0x1D60000` sectors. That inherited
Jibo geometry is an admission upper bound, not measured capacity. Status/EXT_CSD/
EXIT require zero range fields. Legacy and unknown opcodes do not dispatch storage
operations in the restricted payload.

Host ranges are strict hexadecimal (optional `0x`), without signs, whitespace,
trailing text, zero count or overflow. Only the Jibo VID/PID is selected; there is
no fallback to another Tegra device. Missing/oversized fixed payload/bootstrap
files or an existing output path fail before USB. No arbitrary operation/payload,
dependency installation, sudo invocation or output overwrite is provided.

Each data batch carries magic/status/address/count before bytes. Failed, short or
substituted responses fail the capture; EXT_CSD errors cannot become successful
zero-filled evidence. Local writes/flush/close and EXIT dispatch are checked.
The restricted host suppresses chip-ID output, uninitialized error memory and
EXT_CSD hex dumps; status uses a bounded summary. Loader progress can still include
local paths, so a future adapter must sanitize retained diagnostics.

## Artifact admission, time bounds and recovery

Fixed filenames, presence checks and capabilities are not authentication. Before
capture, a future adapter must admit an exact reviewed host/payload/bootstrap set
by provenance and hashes, with a private working directory and substitution
checks. Do not rename a general-purpose payload to the restricted filename.

The loader retains USB transport waits, including waiting for RCM; it has no
whole-process deadline. The adapter still needs a reviewed overall budget,
exact range plan, cancellation/termination, expected size/hash checks, evidence
ownership and uncertain-reset recovery. Per-transfer timeouts do not bound the
whole capture, and EXIT dispatch does not prove normal boot/reconnect.

Failures can leave an empty or partial newly created file; a full file may remain
after EXIT failure. File presence/length alone cannot admit evidence. Require
successful process/protocol completion and independent checks, and preserve
failed files as incomplete. The host does not delete them or certify identity.
The separate [GPT audit](primary-gpt-audit.md) still cannot prove backup GPT,
physical association, release/filesystem support or apply readiness.

## Validation

CI builds normal/restricted hosts on Windows/macOS/Linux and payloads on
Linux/macOS. The actual restricted host is linked to USB/RCM test stubs for
execution tests; even successful fixture reads cannot contact a device. Tests
cover refusal before USB, strict ranges, exclusive output, missing artifacts,
multi-batch/boundary reads, EXT_CSD, wrong handshakes/frames, device errors,
truncation, partial evidence and EXIT failure. The shared admission policy is
exercised over 10,000 ranges and all 256 legacy opcode values. Compiler
preprocessing verifies write/erase function removal in the restricted payload
and retention in the original. Actual payload builds are checked for protocol
constants. Real native hosts are invoked only with `--capabilities` in CI.

CI artifacts retain fixture proofs and component hashes. They are build/test
evidence, not an approved capture manifest, device test, restore proof or USB/
driver certification. Fresh device admission and recovery review remain required.
