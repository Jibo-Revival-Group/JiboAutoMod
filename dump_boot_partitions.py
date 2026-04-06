#!/usr/bin/env python3
"""
dump_boot_partitions.py — dump eMMC boot0 and boot1 hardware partitions

These partitions are NOT in the main NAND dump (jibo_full_dump.bin).
They hold the Tegra T124 BCT (Boot Configuration Table) and the
low-level bootloader, which the SoC ROM reads before any GPT exists.

Output files (written to jibo_work/):
    emmc_boot0.bin   — Boot Partition 1 (~4–8 MB)
    emmc_boot1.bin   — Boot Partition 2 (~4–8 MB)

Requires:
    - Jibo in RCM mode (NVIDIA APX, USB 0955:7740)
    - Shofel/shofel2_t124 built
    - emmc_server.bin rebuilt with boot-partition support (make -C Shofel)

Usage:
    python3 dump_boot_partitions.py
"""

import os
import sys
import subprocess
import platform
import struct
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
SHOFEL_DIR = SCRIPT_DIR / "Shofel"
WORK_DIR   = SCRIPT_DIR / "jibo_work"

SECTOR_SIZE = 512

# Magic sector bases that tell the payload which partition to access
BOOT0_BASE = 0x80000000
BOOT1_BASE = 0xC0000000


def shofel_exe() -> Path:
    if platform.system() == "Windows":
        return SHOFEL_DIR / "shofel2_t124.exe"
    return SHOFEL_DIR / "shofel2_t124"


def run_shofel(args: list, capture: bool = True, timeout: int = 300):
    exe = shofel_exe()
    cmd = [str(exe)] + args
    if platform.system() == "Linux":
        cmd = ["sudo"] + cmd
    result = subprocess.run(cmd, cwd=SHOFEL_DIR, capture_output=capture, timeout=timeout)
    return result.returncode, result.stdout, result.stderr


def device_present() -> bool:
    try:
        r = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
        return "0955:7740" in r.stdout or "NVIDIA Corp. APX" in r.stdout
    except Exception:
        return False


def get_boot_partition_size() -> int:
    """Read EXT_CSD to determine the boot partition size in sectors.
    EXT_CSD byte 226 (BOOT_SIZE_MULT): boot partition size = BOOT_SIZE_MULT * 128 KB.
    Returns sector count, or a safe default of 8192 (4 MB) on failure."""
    tmp = WORK_DIR / "_ext_csd_tmp.bin"
    try:
        rc, _, _ = run_shofel(["EMMC_READ_EXT_CSD", str(tmp)])
        if rc != 0 or not tmp.exists():
            print("[!] EXT_CSD read failed — using default boot partition size (4 MB)")
            return 4 * 1024 * 1024 // SECTOR_SIZE  # 8192 sectors

        data = tmp.read_bytes()
        if len(data) < 227:
            print("[!] EXT_CSD too short — using default boot partition size (4 MB)")
            return 4 * 1024 * 1024 // SECTOR_SIZE

        boot_size_mult = data[226]  # BOOT_SIZE_MULT
        if boot_size_mult == 0:
            print("[!] BOOT_SIZE_MULT is 0 — using default boot partition size (4 MB)")
            return 4 * 1024 * 1024 // SECTOR_SIZE

        size_bytes = boot_size_mult * 128 * 1024
        size_sectors = size_bytes // SECTOR_SIZE
        print(f"[+] EXT_CSD BOOT_SIZE_MULT={boot_size_mult} → boot partition = {size_bytes//1024} KB ({size_sectors} sectors)")
        return size_sectors
    finally:
        tmp.unlink(missing_ok=True)


def dump_partition(label: str, base: int, num_sectors: int, out_path: Path) -> bool:
    """Dump one boot partition by passing the encoded base sector to EMMC_READ."""
    size_kb = num_sectors * SECTOR_SIZE // 1024
    encoded_start = f"0x{base:08x}"  # e.g. 0x80000000 for boot0

    print(f"\n[*] Dumping {label} ({size_kb} KB, {num_sectors} sectors)...")
    print(f"    encoded start sector: {encoded_start}")
    print(f"    output: {out_path}")

    rc, _, stderr = run_shofel(
        ["EMMC_READ", encoded_start, f"0x{num_sectors:x}", str(out_path)],
        capture=False,
        timeout=120,
    )

    if rc != 0:
        print(f"[!] {label} dump FAILED (rc={rc})")
        if stderr:
            print(f"    stderr: {stderr.decode(errors='replace')}")
        return False

    if not out_path.exists():
        print(f"[!] {label}: output file not created")
        return False

    actual = out_path.stat().st_size
    expected = num_sectors * SECTOR_SIZE
    print(f"[+] {label} written: {actual:,} bytes (expected {expected:,})")

    if actual != expected:
        print(f"[!] Size mismatch — dump may be incomplete")
        return False

    # Quick sanity: check if it's all zeros
    data = out_path.read_bytes()
    nz = sum(1 for b in data if b != 0)
    if nz == 0:
        print(f"[!] WARNING: {label} is entirely zeros — partition may be empty or switch failed")
    else:
        print(f"[+] {label} contains data ({nz:,} non-zero bytes)")

    return True


def main():
    print("=" * 60)
    print("Jibo eMMC Boot Partition Dumper")
    print("=" * 60)

    # Prerequisites
    exe = shofel_exe()
    if not exe.exists():
        print(f"[!] shofel2_t124 not found: {exe}")
        print("    Build first: make -C Shofel")
        sys.exit(1)

    WORK_DIR.mkdir(exist_ok=True)

    print("\n[*] Checking for Jibo in RCM mode...")
    if not device_present():
        print("[!] Device not detected!")
        print("    Hold RCM button, press reset, then check: lsusb | grep NVIDIA")
        sys.exit(1)
    print("[+] Device detected")

    # Get boot partition size from EXT_CSD
    boot_sectors = get_boot_partition_size()

    # Dump boot0 and boot1
    boot0_path = WORK_DIR / "emmc_boot0.bin"
    boot1_path = WORK_DIR / "emmc_boot1.bin"

    ok0 = dump_partition("boot0", BOOT0_BASE, boot_sectors, boot0_path)
    ok1 = dump_partition("boot1", BOOT1_BASE, boot_sectors, boot1_path)

    print("\n" + "=" * 60)
    if ok0 and ok1:
        print("[+] Both boot partitions dumped successfully.")
        print(f"    {boot0_path}")
        print(f"    {boot1_path}")
        print("\nThese files, combined with jibo_full_dump.bin, give you a")
        print("complete backup of all eMMC data including the bootloader.")
    else:
        print("[!] One or more dumps failed.")
    print("=" * 60)

    sys.exit(0 if (ok0 and ok1) else 1)


if __name__ == "__main__":
    main()
