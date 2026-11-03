# Offline API/Hub configuration preview

`endpoint_preview.py` produces a file-level preview for the observed
`/usr/local/etc/jibo-jetstream-service.json` configuration. It connects an explicit
[hosting target](conversion-preparation.md) to API and Hub routing, without
reading a credentials file, selecting a provider, applying changes or contacting
a robot. Python 3.9+ is supported on Windows, macOS and Linux.

This is one conversion component. Native token/notification routing, SSM bundles,
DNS, certificates, credentials, filesystem allocation and sector changes are
not generated. Every report keeps `completeConversionPlan`, `executionSupported`
and `readyForApply` false. Do not pass its output to an existing writer as an
admitted conversion plan.

## Configuration profile and source evidence

The five observed routing fields are `entrypoint_hostname`, `entrypoint_port`,
`hub_hostname`, `hub_port` and `hub_secure`. They are projected into both
`HubClient.override` and the existing entry at
`HubClient.region-settings[credentialsRegion]`. API and Hub host/port values are
independent. All other parsed JSON values and other region entries are preserved.
No credentials region is invented or changed.

The profile follows the runtime repository's
[conversion helper at reviewed revision 806b5af](https://github.com/transcendentsoftware-jd/JiboExperiments/blob/806b5af72841e60ae7982ee3de3b09315ff40ff8/OpenJibo/scripts/bootstrap/apply-openjibo-conversion.sh)
and [single-robot configuration guide](https://github.com/transcendentsoftware-jd/JiboExperiments/blob/806b5af72841e60ae7982ee3de3b09315ff40ff8/OpenJibo/docs/single-robot-http-self-hosting.md).
The older helper also performs broader changes; this preview does not reproduce
or authorize that apply path. It refuses top-level `regions`/`region-settings`
duplicates, missing active regions, malformed objects, unknown fields in the
selected routing entry/override, and bool/float ports. Other HubClient/root
settings are preserved, but their runtime precedence is not verified.

There is no observed `entrypoint_secure` field in this profile. The target's
scheme records the intended API protocol and its trust requirements; the five
config fields alone do not establish effective API TLS behavior, particularly
for nonstandard ports. Hub TLS intent is projected through `hub_secure`. Both
protocols still need robot-side runtime acceptance.

## Inputs and commands

Retain the Jetstream JSON file locally. Independently record its raw SHA-256
and byte length. Supply the existing `openjibo.conversion-target.v1` target,
without an implicit provider or Hub default. For example:

```json
{
  "schema": "openjibo.conversion-target.v1",
  "mode": "managed",
  "providerId": "selected-provider",
  "apiOrigin": "https://api.example.test:8443"
}
```

The companion manifest has exactly these fields:

```json
{
  "schema": "openjibo.endpoint-preview-input.v1",
  "targetSha256": "<raw-target-file-sha256>",
  "jetstream": {"sha256": "<raw-config-file-sha256>", "sizeBytes": 500},
  "credentialsRegion": "api",
  "hubOrigin": "https://hub.example.test:9443",
  "allowIsolatedHttp": false,
  "certificatePolicy": "preserve-existing"
}
```

Addresses and size above are examples. Supply actual selected origins and file
size. Placeholder hashes are invalid. The region is operator supplied and must
already exist in the config; it is not verified against a live credentials file.
The tool never reads a separate credentials, certificate or private-key file.
The retained config itself may contain private unrelated settings, so keep all
inputs and exported config payloads local.

```powershell
# Windows; choose a new output directory
py -3 endpoint_preview.py --manifest C:\review\endpoint-input.json `
  --manifest-sha256 <manifest-file-sha256> `
  --target C:\review\target.json --target-sha256 <target-file-sha256> `
  --jetstream C:\review\jibo-jetstream-service.json --output C:\review\new-endpoint-preview
```

```bash
# macOS or Linux
python3 endpoint_preview.py --manifest /review/endpoint-input.json \
  --manifest-sha256 <manifest-file-sha256> \
  --target /review/target.json --target-sha256 <target-file-sha256> \
  --jetstream /review/jibo-jetstream-service.json --output /review/new-endpoint-preview
```

Each input is at most 64 KiB. JSON rejects duplicates, nonfinite numbers, excessive
nesting/nodes and integers outside signed 64-bit bounds. Files are regular local
files, without symlink/reparse/device-path/UNC traversal, and are read through
bounded stable-descriptor checks. Pins cover exact file bytes, including
formatting; canonical hashes are separately recorded. Pins do not authenticate
acquisition, build provenance, physical identity or freshness.

Managed and hybrid targets require HTTPS for both origins. Isolated HTTP needs
`allowIsolatedHttp: true` plus an explicit private/link-local IPv4, IPv6 unique-local, or
`.local` destination for every HTTP origin. Public HTTP and unresolved ordinary
DNS names are refused by this narrow profile. An all-HTTPS plan requires the
acknowledgement to be false. DNS resolution, network locality and token issuance
are not checked. No tokenless flag is enabled or provider membership inferred.

## Trust and review output

Only `certificatePolicy: preserve-existing` is supported. HTTPS records chain,
hostname and robot trust-store validation as outstanding requirements. There is
no `insecure` option, CA installation, historical certificate/key import or trust
validation bypass. A custom CA or legacy TLS repair needs its own reviewed
profile and physical acceptance.

`preview.json` reports raw/canonical input pins, selected target and region,
normalized projected routes, known semantic field changes, full before/after
file hashes/sizes, code hashes and remaining gates. Field changes describe
observed additions/replacements; they are not executable JSON Patch instructions.
If an override object is absent, its parent is created in the candidate file.

For a changed config, `jetstream.before.json` preserves the exact retained bytes;
`jetstream.after.json` contains the projected parsed values in canonical JSON.
Formatting and numeric spelling can change on serialization, so this is a
file-level semantic preview, not a byte-preserving sector patch. An already
matching config retains its original hash/format and exports no payload files.
Rollback bytes alone are not a device recovery backup or tested rollback.

Outputs use a new private directory and exclusive creation. Exit 0 means preview
export succeeded; exit 2 means refusal/I/O failure. Existing outputs are never
overwritten. A failed export can leave a partial directory; retain a preview
only after a successful command and complete report/payload hash checks. CLI
diagnostics do not print input paths or config contents.

The remaining complete conversion review must bind this component to the
[firewall preview](firewall-sector-preview.md), device/release association,
filesystem/sector allocation, real recovery evidence, native and notification/
SSM routing, DNS, TLS, provider enrollment, bounded apply/readback and verified
rollback. No device test window is opened by these offline previews.
