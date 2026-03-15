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

## Troubleshooting

### "Jibo not found in RCM mode"
- Make sure you're holding RCM button while pressing reset
- Try a different USB cable (data cables, not charge-only)
- On Windows, install WinUSB driver using Zadig

### "Permission denied" on Linux
- Run with sudo: `sudo ./jibo_automod.sh`
- Or add udev rules for the Nvidia APX device

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

## License

This tool is provided as-is for educational and preservation purposes. See individual component licenses in the Shofel directory.
