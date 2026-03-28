# Jibo Auto-Mod Tool

**Automatically enable developer mode on Jibo robots**

This tool automates the process of modding a Jibo robot to enable SSH access and developer mode. It works on both **Linux** and **Windows**.

## ⚠️ Warning

**USE AT YOUR OWN RISK!** This tool modifies your Jibo's internal storage. While the process is generally safe:

- **Always keep backups** - the tool creates them automatically
- **Don't disconnect during write operations** - this could brick your Jibo
- **Calibration data is unique** - your backup contains data specific to YOUR Jibo

## Quick Start

### Linux

```bash
# Make the script executable
chmod +x jibo_automod.sh

# Run the tool
./jibo_automod.sh
```

### Windows

1. Install [Python 3.8+](https://www.python.org/downloads/) (check "Add to PATH")
2. Install [MSYS2](https://www.msys2.org/) for build tools
3. Double-click `jibo_automod.bat`

Or use WSL (Windows Subsystem for Linux) and follow Linux instructions.

## Requirements

### Linux
- Python 3.8+
- build-essential (gcc, make)
- libusb-1.0-dev
- arm-none-eabi-gcc (ARM toolchain)
- ~20GB free disk space

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install build-essential libusb-1.0-0-dev git python3 \
                 gcc-arm-none-eabi libnewlib-arm-none-eabi
```

**Arch/CachyOS:**
```bash
sudo pacman -S --needed base-devel libusb git python \
                        arm-none-eabi-gcc arm-none-eabi-newlib
```

### Windows
- Python 3.8+
- MSYS2 with MinGW-w64 toolchain
- Zadig (for USB driver installation)
- e2fsprogs (provides `debugfs`, used to edit `mode.json` inside the ext filesystem image without mounting)
- ~20GB free disk space

## What Does It Do?

1. **Builds Shofel** - Compiles the exploit tool from source
2. **Dumps eMMC** - Reads the entire 15GB storage (~2-4 hours)
3. **Modifies Partition** - Changes `/var/jibo/mode.json` from "normal" to "int-developer"
4. **Writes Back** - Updates only the modified partition
5. **Verifies** - Reads back to confirm the write was successful

## Usage

### Full Automatic Mod
```bash
./jibo_automod.sh
```

## Optional GUI

The GUI is separate from the CLI tools. You can still run `jibo_automod.sh` / `jibo_updater.sh` directly.

Install GUI deps:

```bash
python3 -m pip install -r requirements-gui.txt
```

Launch main panel (Linux):

```bash
./jibo_gui.sh
```

Launch main panel (Windows):

```bat
jibo_gui.bat
```

### Just Dump (no modification)
```bash
./jibo_automod.sh --dump-only -o my_jibo_backup.bin
```

### Use Existing Dump
```bash
./jibo_automod.sh --dump-path /path/to/existing_dump.bin
```

### Write Pre-Modified Partition
```bash
./jibo_automod.sh --write-partition var_modified.bin --start-sector 0x7E9022
```

### Fast Mode (GPT + /var only)
This avoids the 15GB full dump by reading just the partition table + the ~500MB `/var` partition,
editing `/var/jibo/mode.json`, and writing back only the changed sectors.

```bash
./jibo_automod.sh --mode-json-only
```

If patch-writing is not desired (or your filesystem changes a lot of blocks), force a full `/var` write:

```bash
./jibo_automod.sh --mode-json-only --full-var-write
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `--dump-only` | Only dump eMMC, don't modify |
| `--dump-path FILE` | Use existing dump instead of dumping |
| `--output, -o FILE` | Output file for dump |
| `--start-sector HEX` | Sector for write operation (default: 0x7E9022) |
| `--force-dump` | Re-dump even if file exists |
| `--rebuild-shofel` | Force rebuild of exploit tool |
| `--skip-detection` | Skip USB device detection |
| `--no-verify` | Skip write verification |
| `--mode-json-only` | Fast mode: dump GPT + /var only, patch `mode.json`, write back minimal changes |
| `--full-var-write` | With `--mode-json-only`: write entire /var partition instead of patch-writing |

## Entering RCM Mode

To mod your Jibo, you need to put it in RCM (Recovery Mode):

1. **Locate the buttons:**
   - RCM button: Small button under the base
   - Reset/Power button: Standard power button

2. **Enter RCM:**
   - Hold the RCM button
   - Press the reset/power button
   - Release both when you see a red LED (no boot animation)

3. **Verify:**
   - On Linux: `lsusb` should show `NVIDIA Corp. APX`
   - On Windows: Device Manager shows "APX" device

## After Modding

Once the tool completes successfully:

1. Unplug Jibo from USB
2. Hold power button until red LED goes off
3. Power on Jibo normally
4. Wait for boot - you should see a **checkmark** instead of the eye animation
5. SSH into Jibo:
   ```bash
   ssh root@<jibo-ip-address>
   # Password: jibo
   ```

## Updating Jibo (JiboOs releases)

This repo also includes an updater that can pull the latest release from the JiboOs Gitea repo,
then upload the release `build/` overlay into Jibo’s `/` over SFTP.

### Install updater dependency

```bash
python3 -m pip install -r requirements.txt
```

### Run updater

```bash
./jibo_updater.sh --ip <jibo-ip-address>
```

Windows:

```bat
jibo_updater.bat --ip <jibo-ip-address>
```

Stable-only (ignore prereleases):

```bash
python3 jibo_updater.py --ip <jibo-ip-address> --stable
```

If the release archive layout changes and the tool can’t find the `build/` folder automatically,
pass it explicitly (path is relative to the extracted archive root):

```bash
python3 jibo_updater.py --ip <jibo-ip-address> --build-path V3.1/build
```

## Troubleshooting

### "Jibo not found in RCM mode"
- Make sure you're holding RCM button while pressing reset
- Try a different USB cable (data cables, not charge-only)
- On Windows, install WinUSB driver using Zadig

### "Permission denied" on Linux
- Run with sudo: `sudo ./jibo_automod.sh`
- Or add udev rules for the Nvidia APX device

### Windows: mode.json edit fails / raw patch warning
If you see messages about raw edits needing padding, install `debugfs` via MSYS2 so the tool can edit the ext filesystem image safely:

1. Install MSYS2: https://www.msys2.org/
2. In an MSYS2 terminal:
   - `pacman -S --needed e2fsprogs`

Then re-run with `--mode-json-only`.

### Build fails
- Make sure ARM toolchain is installed
- On Arch: `pacman -S arm-none-eabi-gcc arm-none-eabi-newlib`
- On Ubuntu: `apt install gcc-arm-none-eabi libnewlib-arm-none-eabi`

### Dump crashes near 99%
- This is often OK - the last partition may be empty space
- Check if your dump file is ~14-15GB, that's probably complete

### SSH connection refused
- Make sure Jibo shows checkmark on boot
- Verify you're using the correct IP address
- Try `ssh -v` for debug output

## File Structure

```
JiboAutoMod/
├── jibo_automod.py      # Main tool (Python)
├── jibo_automod.sh      # Linux launcher
├── jibo_automod.bat     # Windows launcher
├── README.md            # This file
├── guide.md             # Original manual guide
├── Shofel/              # Shofel exploit source
│   ├── Makefile
│   ├── shofel2_t124     # Built executable
│   └── ...
└── jibo_work/           # Working directory (created)
    ├── jibo_full_dump.bin
    ├── var_partition.bin
    └── var_partition_backup.bin
```

## Technical Details

### Partition Layout
| # | Size | Purpose |
|---|------|---------|
| 1 | 1GB | System A |
| 2 | 1GB | System B |
| 3 | 50MB | Boot config |
| 4 | 2GB | Root filesystem |
| 5 | 500MB | /var (we modify this) |
| 6 | ~10GB | Data |

### Mode Values
- `"normal"` - Standard Jibo operation
- `"int-developer"` - Developer mode (SSH enabled, services disabled)

## Credits

- Shofel exploit based on fail0verflow's Fusee Gelée
- Katherine Temkin's research on Tegra vulnerabilities
- devsparx for the T124 port
- The Jibo preservation community

CLI Arguments
This page documents the CLI flags for the two main tools:

../jibo_automod.py (installer/mod tool)
../jibo_updater.py (OS updater)
If you’re using launchers (.sh/.bat), they forward all arguments through.

jibo_automod.py
Modes (mutually exclusive)
(no mode flag)

Full mod workflow (full eMMC dump, extract/modify/write /var).
--dump-only

Only dump eMMC; don’t modify anything.
--write-partition FILE

Write an already-prepared partition image to eMMC.
You must tell it where to write using --start-sector.
--mode-json-only

Fast path:
read GPT (small)
read /var only (~500MB)
modify /var/jibo/mode.json
write back either a patch (default) or full /var
Common options
--dump-path FILE

Use an existing dump file instead of reading from the device.
--output FILE / -o FILE

Output file for dumps.
--start-sector HEX

Start sector for --write-partition.
Parsed with base autodetect (0x... works).
Default is 0x7E9022 (but the full/fast workflows usually compute the start sector from GPT).
--force-dump

Re-dump even if a dump exists.
--rebuild-shofel

Force rebuilding ShofEL (make clean then make).
--skip-detection

Skip USB “is Jibo connected” checks.
--no-verify

Skip verification read-back.
Fast mode options
--full-var-write
Only meaningful with --mode-json-only.
If set: write the full /var partition back (slower).
If not set: compute sector diffs and only write changed ranges (faster).
Examples
Full mod:

python3 jibo_automod.py
Dump only:

python3 jibo_automod.py --dump-only -o my_dump.bin
Use existing dump:

python3 jibo_automod.py --dump-path jibo_work/jibo_full_dump.bin
Fast mode:

python3 jibo_automod.py --mode-json-only
Write a prepared partition:

python3 jibo_automod.py --write-partition var_partition.bin --start-sector 0x7E9022
jibo_updater.py
The updater assumes you already have SSH access to the robot.

Required
--ip <host> (alias: --host)
IP or hostname of your Jibo.
Connection
--user <name> (default root)
--password <pass> (default jibo)
--ssh-timeout <seconds> (default 15)
Release selection
--releases-api <url>

API endpoint for Gitea releases.
--stable

Ignore prereleases.
--tag <tag>

Install a specific tag instead of “latest”.
Archive layout
--build-path <relative/path>
If the updater can’t find the build/ folder automatically, specify where it is inside the extracted archive.
Safety / UX
--state-file <path>

Where it remembers the last applied version per host.
--force

Re-download and re-install even if the local state says you’re already on that version.
--yes

Don’t prompt for confirmation.
--dry-run

Download/extract + connect, but don’t upload files and don’t touch mode.json.
Returning to normal mode
--return-normal

After update, set /var/jibo/mode.json back to normal (no prompt).
--no-return-normal

## Updater: Interactive TUI and GUI integration

The bundled `jibo_updater.py` now supports a simple interactive text UI and a small programmatic interface intended for later GUI integration.

- `--tui`: Launch a brief interactive text UI to pick a distribution host and release, or select a local archive under `jibo_work/updates/downloads/`.
- `--distributors <path>`: Use `Distributors.json` (default) to get a list of release hosts to probe for latency and releases.

Standalone TUI helper
---------------------

If you want a more polished terminal UI, use the new `jibo_updater_tui.py` curses-based helper. It provides
keyboard navigation and prints a JSON selection to stdout suitable for piping into other scripts.

Usage:

```bash
python3 jibo_updater_tui.py --distributors Distributors.json
```

The TUI outputs a JSON object describing the selected host and release, for example:

```json
{"host": "https://code.zane.org/..", "source":"remote", "tag":"v3.3.0", "tarball_url":"https://..."}
```

Behavior notes:
- The TUI will probe hosts listed in `Distributors.json` and present latency and available releases.
- Local archives found in `jibo_work/updates/downloads/` are shown as a "local" source and can be chosen without downloading.
- When updating, uploaded files and directories are set to permissive `0777` to avoid boot failures caused by missing execute/read permissions.

GUI integration:
- `jibo_updater.py` includes a simple programmatic surface (CLI flags and a small interactive mode) designed so a GUI can call it or be wired to a future HTTP/JSON control API. For now, use `--tui` to exercise the flow; GUI hooks will be documented in `CHECKLIST.md` for the next steps.

Dependencies: no additional Python packages were added for this change (uses standard library + `paramiko` already required). If you use the GUI in future, update `requirements-gui.txt` accordingly.

Never prompt and never change mode back.
Examples
Update to latest:

python3 jibo_updater.py --ip 192.168.1.50
Stable only:

python3 jibo_updater.py --ip 192.168.1.50 --stable
Specific tag:

python3 jibo_updater.py --ip 192.168.1.50 --tag v3.3.0
Dry run:

python3 jibo_updater.py --ip 192.168.1.50 --dry-run
