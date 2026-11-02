# Conversion preparation: plan and export

This is the first offline orchestration contract for the easy-button conversion
flow. It connects an explicit hosting choice to supplied device audit and
recovery evidence. It does not detect a robot, verify backup bytes, patch storage,
change a firewall, register ownership or contact a provider. Apply is unavailable
even when all preparation fields are present. The existing device writer is
unchanged.

## Windows, macOS and Linux

See the [Dev host support matrix](host-support.md) to distinguish this portable
planner from the unfinished interactive device adapters and older launchers.

Use Python 3.9 or newer from the repository root. This command has no external
Python dependencies and does not import the exploit, USB or GUI code:

```powershell
# Windows
py -3 conversion_plan.py --inventory inventory.json --target target.json --output plan-001.json
```

```bash
# macOS or Linux
python3 conversion_plan.py --inventory inventory.json --target target.json --output plan-001.json
```

The output must be a new file in an existing directory. Exit 0 means export
succeeded; inspect `preparationBlockers`. Exit 2 means invalid input or an
existing/unwritable output. No existing plan is overwritten. Standard output
contains the canonical plan hash and bounded status fields, not input paths or
credentials. A future GUI can consume the same `plan()` contract.

Cross-OS contract tests cover plan/export behavior. They are not USB-driver,
exploit, hardware conversion, recovery or installed-runtime certification.
Host prerequisites and the selected writer's actual support remain separate.

## Inputs

Supply `openjibo.conversion-inventory.v1` with exactly these fields:

| Field | Value |
| --- | --- |
| `schema` | `openjibo.conversion-inventory.v1` |
| `deviceFingerprintSha256` | 64 lowercase hex characters identifying the audited device evidence |
| `releaseFamily` | `oobe`, `pegasus-v1`, `v2` or `unknown` |
| `observedAtUtc` | UTC ISO timestamp with `Z` or `+00:00` |
| `auditEvidenceSha256` | Hash of the retained audit evidence |
| `backups` | Up to three distinct `{ "kind", "sha256", "sizeBytes" }` records |

Backup kinds are `calibration`, `affected-storage` and `full-storage`. Each
record needs a real retained artifact hash and positive integer size. Planning
requires calibration evidence and affected-storage or full-storage evidence;
missing evidence and an unknown release produce blockers. Do not fill hashes
with invented placeholders to imply readiness. This tool cannot authenticate
supplied evidence, determine its freshness, or check that it belongs to the
robot; those remain explicit pre-apply gates.

For isolated self-hosting, a target input can be:

```json
{
  "schema": "openjibo.conversion-target.v1",
  "mode": "isolated",
  "providerId": "self-hosted",
  "apiOrigin": "http://192.0.2.20:8080"
}
```

The address is a documentation example; replace it with the selected server's
robot-reachable origin. Origins cannot contain credentials, queries, fragments
or paths. Loopback/unspecified origins are rejected because they do not name the
selected server from a robot's perspective. The planner does not prove reachability
or set any robot endpoint.

`hybrid` and `managed` modes require HTTPS and an explicit provider ID. They
record that provider onboarding is required, but do not create a session or
claim identity, entitlement or payment status. Isolated operation does not
require managed membership. No provider is chosen by default.

Unknown input fields, duplicate JSON keys, invalid hashes and oversized inputs
are rejected. Do not include credentials, serial numbers, backup paths or media
in these contracts. The exported plan is a preparation record, not a recovery
backup or an executable filesystem/sector change plan.

## Next integration stages

1. Connect real read-only host/device audit adapters, supported layout evidence
   and immutable recovery verification to this contract.
2. Resolve a supported conversion profile into exact file/sector/certificate
   changes and show them for confirmation.
3. Invoke the proven bounded writer, read back changes and retain rollback
   evidence without widening its write scope.
4. Add nonce-bound provider handoff, remote identity/API/socket/speech checks,
   redacted diagnostics and verified rollback/provider switching.

Keep the robot's installed release, tool computer OS, USB method and selected
hosting OS/CPU in the hardware support matrix. Passing plan/export tests on an
OS does not declare every combination supported.
