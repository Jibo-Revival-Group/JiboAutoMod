# Host support in the Dev branch

Use an entry point that actually exists in the selected checkout or release.
The older standalone `jibo_automod.py`, `.sh` and `.bat` commands in the historical
README reference are not shipped by the restructured Dev branch.

| Entry point | Windows | macOS | Linux | What passing means |
| --- | --- | --- | --- | --- |
| `conversion_plan.py` | Plan/export contracts in CI | Plan/export contracts in CI | Plan/export contracts in CI | Validates supplied preparation fields and exports a new plan; never applies it |
| `recovery_evidence.py` | File-check contracts in CI | File-check contracts in CI | File-check contracts in CI | Streams retained regular backup files and compares supplied hash/size; does not prove robot association or restoration |
| `gpt_audit.py` | Retained GPT-prefix tests in CI | Retained GPT-prefix tests in CI | Retained GPT-prefix tests in CI | Validates a narrow primary-table profile; does not capture hardware or enable conversion |
| `firewall_preview.py` | Retained image preview tests | Retained image preview tests | Retained image preview tests | Exports exact dual-slot firewall sector deltas for review; no apply or full filesystem/robot acceptance |
| `endpoint_preview.py` | Retained config tests | Retained config tests | Retained config tests | Projects explicit API/Hub settings and trust requirements; no credential/certificate changes or complete conversion plan |
| Dedicated `readonly` build | Host/policy tests; no ARM payload build in Windows job | Host/payload build and policy tests | Host/payload build and policy tests | Compile-time write exclusion and stub transport checks; no hardware admission |
| `capture_adapter.py` | Process/job and stub-native tests | Process/group and stub-native tests | Process/group and stub-native tests | Pinned supplied components, fixed plans and bounded supervision; hardware/provenance/dependency acceptance remains separate |
| `Exploits/Shofel` native compilation | UCRT64 loader build in CI | Toolchain build in CI | Toolchain build in CI | Compiles the selected native targets; does not prove USB access or device writes |
| `JiboModTool.py` interactive device menu | Adapter missing: `Exploits/Platform/Windows` is an empty placeholder file | Darwin adapter missing | Generic Linux adapter exists | Developer integration only; not a complete cross-OS conversion release |

The planner uses Python 3.9 or newer without external dependencies. The menu
contains Python `match` statements and needs Python 3.10 or newer plus its
declared dependencies. Do not import the menu to call the planner: the menu
initializes dependencies and opens interactive choices at import time.

For plan/export commands and input contracts, use
[conversion preparation](conversion-preparation.md). Plans always retain
`readyForApply: false`. Neither a supplied backup hash nor successful compilation
proves supported partitions, fresh audit evidence, actual recovery bytes,
ownership or safe conversion.

## Windows native build environment

Use a single MSYS2 UCRT64 environment for compiler, pkg-config and libusb:

```bash
pacman -S --needed make mingw-w64-ucrt-x86_64-gcc \
  mingw-w64-ucrt-x86_64-pkgconf mingw-w64-ucrt-x86_64-libusb
pkg-config --cflags --libs libusb-1.0
make -C Exploits/Shofel shofel2_t124
```

MSYS2 documents the [MINGW64-to-UCRT64 migration](https://www.msys2.org/news/#2026-10-24-mingw64-deprecation-update)
and publishes the [UCRT64 libusb package](https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-libusb).
Do not mix the old environment's compiler or library paths with UCRT64. The
Windows CI target builds the host loader, not a fully validated payload and
device conversion. USB drivers, device admission, backups and readback still
need a dedicated hardware test. Installing a build dependency does not install
a robot driver or change a robot.

## Completing the easy-button flow

The [dedicated capture build](read-only-capture-build.md) supplies a narrower
host/payload pair for a future native audit adapter. Provenance, full-operation
deadlines, USB/driver admission, device association and recovery remain separate.

The next implementation is a shared audit/plan orchestrator with explicit
OS adapters, leaving the proven bounded device writer intact. Add read-only
prerequisite/USB detection, supported-layout audit, immutable recovery
verification, exact-change preview, confirmed apply/readback, selected-provider
handoff and verified rollback. Test the host OS, USB method and installed robot
release as separate dimensions. Do not turn a Linux helper into a Windows or
Darwin writer by changing path syntax alone.

The server hosting matrix is separate from the conversion computer's OS. The
neutral runtime's `OpenJibo/docs/platform-setup-guide.md` documents Compose,
Linux-engine/CPU requirements, self-hosted setup and image acceptance limits.
