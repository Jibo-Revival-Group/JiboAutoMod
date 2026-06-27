# Jibo Auto-Mod Tool

**Automatically enable developer mode on Jibo robots**

This tool automates the process of modding a Jibo robot to enable SSH access and developer mode. It works on **Linux**, **macOS**, and **Windows**.

## ⚠️ Warning

**USE AT YOUR OWN RISK!** This tool modifies your Jibo's internal storage. While the process is generally safe:

- **Always keep backups** - the tool creates them automatically
- **Don't disconnect during write operations** - this could brick your Jibo
- **Calibration data is unique** - your backup contains data specific to YOUR Jibo

## Quick Start

### Linux
### macOS

¯\_(ツ)_/¯

### Windows

Comming soon

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

