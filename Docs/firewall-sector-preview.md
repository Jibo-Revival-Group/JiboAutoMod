# Offline firewall sector preview

`firewall_preview.py` previews one existing conversion step: the known
`S21firewall.v1` developer-access assignment in both bootable rootfs slots.
It reads pinned retained images and exports exact proposed sector bytes. It
does not invoke a writer, mount an image, open USB, contact a robot or select a
provider. Python 3.9+ works on Windows, macOS and Linux without extra dependencies.

This is a component preview, not a complete conversion plan. `/var/jibo/mode.json`,
endpoints, certificates, ownership and managed enrollment are outside its scope.
The older device writer is unchanged. Results always keep `executionSupported`
and `readyForApply` false, even if both files match the profile.

## Retained inputs and exact pins

Use an ordinary local input directory containing exactly these required names:

| File | Meaning |
| --- | --- |
| `gpt-prefix.bin` | Retained primary GPT prefix, including its complete entry array |
| `rootfsA.img` | Entire partition image for the exact `rootfsA` GPT entry |
| `rootfsB.img` | Entire partition image for the exact `rootfsB` GPT entry |

Other input directory files are ignored. Files must be regular, with no symlink,
reparse, device-path or UNC traversal. They are opened read-only. Each rootfs
image must exactly match its GPT partition length and be at most 4 GiB. The
prefix is at most 2 MiB. Full file hashes are streamed through bounded buffers;
metadata reads then use the same descriptor and refuse observable mutation.
Directory races or malicious changes that evade filesystem metadata are outside
this check. None of the files is accepted as proof of a particular physical robot.

Supply a UTF-8 JSON manifest, at most 64 KiB, with exactly:

```json
{
  "schema": "openjibo.firewall-preview-input.v1",
  "operation": "enable",
  "diskSectors": 4096,
  "gptPrefix": {"sha256": "<actual-file-sha256>", "sizeBytes": 17408},
  "images": [
    {"partition": "rootfsA", "sha256": "<actual-image-sha256>", "sizeBytes": 65536},
    {"partition": "rootfsB", "sha256": "<actual-image-sha256>", "sizeBytes": 65536}
  ]
}
```

Numbers illustrate a synthetic fixture, not Jibo capacity. Supply independently
reviewed disk geometry and real retained file hashes/sizes. Placeholder hashes
are invalid. `operation` must explicitly be `enable` or `restore`; unknown fields,
duplicate keys, bool/float sizes, missing or duplicate slots are refused.
Pin the entire manifest file separately using its raw SHA-256, including formatting.
Pins establish byte consistency with the operator's reference; they do not
authenticate acquisition, firmware, provenance or physical identity.

```powershell
# Windows; existing input directory, new output directory
py -3 firewall_preview.py --manifest C:\review\firewall-input.json `
  --manifest-sha256 <manifest-file-sha256> --inputs C:\review\retained `
  --output C:\review\new-firewall-preview
```

```bash
# macOS or Linux
python3 firewall_preview.py --manifest /review/firewall-input.json \
  --manifest-sha256 <manifest-file-sha256> --inputs /review/retained \
  --output /review/new-firewall-preview
```

Exit 0 means the component preview was exported. Exit 2 means refusal or I/O
failure. Existing outputs are never overwritten. Invalid inputs are refused
before creating output. An export failure can leave a partial directory; only a
successful command plus complete `preview.json` and matching payload hashes
constitute an exported preview. CLI diagnostics omit input paths and image data.

## What is checked

The shared primary GPT auditor checks header/entry CRCs, partition bounds,
non-overlap and unambiguous names. Both exact slot names and complete matching
image sizes are required. Capacity remains operator supplied; no backup GPT,
protective MBR or acquisition receipt is verified here.

The preview has a narrower ext4 reader profile than the existing writer. It
requires a clean revision-1 filesystem, 1/2/4 KiB blocks, 32-byte descriptors,
extents and ordinary flat directories. Only compatible bits `0x3c`, incompatible
bits `0x40`/`0x42`, and read-only-compatible bits `0x3` are admitted. Feature
definitions follow the [Linux kernel ext4 specification](https://docs.kernel.org/filesystems/ext4/super.html).
Journal recovery, metadata checksums, 64-bit addressing, flex block groups,
indexed/encrypted/inline data paths and unknown features are rejected. Extent
trees must be flat, initialized and hole-free; the firewall file needs a single
contiguous extent. Data mappings must not overlap each other or the metadata
read while resolving this path. Parsing is bounded to 8,192 reads and 16 MiB per
image, under a 600-second software deadline including input hashing. Blocking
filesystem I/O can exceed that deadline; no hard real-time guarantee is made.

This is not fsck: unreferenced metadata, allocation bitmaps, journal integrity,
other files/hard-link aliases and full block ownership are not validated.
`filesystemIntegrityVerified` remains false. The profile intentionally refuses
many legitimate ext4 filesystems; broaden it only after real layout evidence
and corresponding parser validation. Passing synthetic tests does not identify
a supported installed robot release.

For each slot, `/etc/init.d/S21firewall` must exactly equal the complete known
original or patched file. The preview changes only its fixed assignment. It
trims unchanged edge sectors and exports one or two sectors per changed slot;
every surrounding byte in those sectors is preserved. A slot already in the
requested state has `changeRequired: false` and no sector payload files.

## Review output and remaining gates

`preview.json` records raw/canonical input pins, code/profile hashes, image and
file hashes, observed inode/UUID, source and requested states, GPT geometry,
partition-relative and absolute proposed LBAs, sector counts, and every changed
byte's offset/before/after value. These fields expose the proposed operation for
review, not instructions admitted to a device writer.

Each changed slot has `<slot>.before.bin` and `<slot>.after.bin`. Before bytes
reverse the proposed local byte delta, but do not establish a complete recovery
backup or tested rollback. Adjacent sector bytes can contain private retained
data; keep these files local. Output uses a new private directory and exclusive
file creation. OS permissions still govern access on each platform.

Before any future apply, independently establish fresh physical/release
association, filesystem/block ownership, actual calibration/storage recovery,
the complete endpoint/certificate/conversion changes, owner confirmation,
bounded writer/readback acceptance and a verified rollback path. Neither this
preview nor a prior capture candidate opens a device test window. See
[preparation](conversion-preparation.md), [retained recovery checks](recovery-file-check.md)
and [primary GPT audit](primary-gpt-audit.md).
