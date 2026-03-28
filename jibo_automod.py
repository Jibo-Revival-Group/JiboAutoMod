#!/usr/bin/env python3
"""
Jibo Auto-Mod Tool
==================
Automatically mods a Jibo robot by:
1. Building the Shofel exploit (if needed)
2. Dumping the eMMC
3. Extracting and modifying the /var partition
4. Writing the modified partition back

Supports: Linux and Windows (with WSL or MinGW)
"""

import os
import sys
import json
import struct
import shutil
import hashlib
import platform
import subprocess
import argparse
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass


SCRIPT_DIR = Path(__file__).parent.resolve()
SHOFEL_DIR = SCRIPT_DIR / "Shofel"
WORK_DIR = SCRIPT_DIR / "jibo_work"

EMMC_TOTAL_SECTORS = 0x1D60000  # Total sectors to dump (~15GB)
EMMC_SECTOR_SIZE = 512

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

if platform.system() == "Windows" and "WT_SESSION" not in os.environ:
    for attr in dir(Colors):
        if not attr.startswith('_'):
            setattr(Colors, attr, '')


@dataclass
class PartitionInfo:
    """GPT partition information"""
    number: int
    start_sector: int
    end_sector: int
    size_sectors: int
    name: str



def print_banner():
    """Print the tool banner"""
    print(f"""
{Colors.CYAN}╔═══════════════════════════════════════════════════════════════════╗
║           {Colors.BOLD}JIBO AUTO-MOD TOOL{Colors.RESET}{Colors.CYAN}                                    ║
║      Automatic Developer Mode Enabler for Jibo Robots             ║
╚═══════════════════════════════════════════════════════════════════╝{Colors.RESET}
""")


def print_step(step: int, total: int, message: str):
    """Print a step indicator"""
    print(f"\n{Colors.BLUE}[{step}/{total}]{Colors.RESET} {Colors.BOLD}{message}{Colors.RESET}")


def print_success(message: str):
    """Print a success message"""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def print_warning(message: str):
    """Print a warning message"""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")


def print_error(message: str):
    """Print an error message"""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")


def print_info(message: str):
    """Print an info message"""
    print(f"{Colors.CYAN}ℹ {message}{Colors.RESET}")


def run_command(cmd: List[str], cwd: Optional[Path] = None, 
                capture_output: bool = False, check: bool = True,
                sudo: bool = False) -> subprocess.CompletedProcess:
    """Run a command and handle errors"""
    if sudo and platform.system() == "Linux":
        cmd = ["sudo"] + cmd
    
    try:
        result = subprocess.run(
            cmd, 
            cwd=cwd, 
            capture_output=capture_output, 
            text=True,
            check=check
        )
        return result
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed: {' '.join(cmd)}")
        if e.stderr:
            print(e.stderr)
        raise


def get_system_info() -> dict:
    """Get system information"""
    return {
        "os": platform.system(),
        "arch": platform.machine(),
        "python_version": platform.python_version(),
        "is_wsl": "microsoft" in platform.release().lower() if platform.system() == "Linux" else False
    }


def check_root_or_sudo() -> bool:
    """Check if running as root or with sudo capability"""
    if platform.system() == "Windows":
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    else:
        return os.geteuid() == 0 or shutil.which("sudo") is not None


def _check_payloads_exist() -> bool:
    """Quick check if critical payload binaries exist (for dependency checking)"""
    critical_payloads = ["emmc_server.bin"]
    return all((SHOFEL_DIR / p).exists() for p in critical_payloads)



def check_linux_dependencies() -> Tuple[bool, List[str], List[str]]:
    """Check for required Linux dependencies"""
    missing = []
    warnings = []
    
    required_tools = {
        "gcc": "build-essential or base-devel",
        "make": "build-essential or base-devel",
    }
    
    optional_tools = {
        "lsusb": "usbutils (optional, used for device detection)",
        "fdisk": "util-linux (optional, has Python fallback)",
    }
    
    for tool, package in required_tools.items():
        if not shutil.which(tool):
            missing.append(f"{tool} ({package})")
    
    for tool, package in optional_tools.items():
        if not shutil.which(tool):
            warnings.append(f"{tool} ({package})")
    
    if not _check_payloads_exist():
        if not shutil.which("arm-none-eabi-gcc"):
            missing.append("arm-none-eabi-gcc (arm-none-eabi-gcc or arm-none-eabi-toolchain)")
    
    try:
        result = subprocess.run(
            ["pkg-config", "--exists", "libusb-1.0"],
            capture_output=True
        )
        if result.returncode != 0:
            missing.append("libusb-1.0-dev or libusb1-devel")
    except FileNotFoundError:
        if not Path("/usr/include/libusb-1.0").exists() and \
           not Path("/usr/local/include/libusb-1.0").exists():
            missing.append("libusb-1.0-dev or libusb1-devel")
    
    return len(missing) == 0, missing, warnings


def check_windows_dependencies() -> Tuple[bool, List[str], List[str]]:
    """Check for required Windows dependencies"""
    missing = []
    warnings = []
    
    if not shutil.which("gcc") and not shutil.which("x86_64-w64-mingw32-gcc"):
        missing.append("MinGW-w64 or MSYS2")
    
    if not _check_payloads_exist():
        if not shutil.which("arm-none-eabi-gcc"):
            missing.append("ARM GNU Toolchain (arm-none-eabi-gcc)")
    
    if not shutil.which("make") and not shutil.which("mingw32-make"):
        missing.append("GNU Make")

    if not shutil.which("debugfs") and not shutil.which("debugfs.exe"):
        warnings.append("debugfs (e2fsprogs) - optional but recommended for reliable mode.json edits on Windows")
    
    return len(missing) == 0, missing, warnings


def print_install_instructions(system: str, missing: List[str], warnings: List[str] = None):
    """Print installation instructions for missing dependencies"""
    if missing:
        print_error("Missing dependencies:")
        for dep in missing:
            print(f"  - {dep}")
    
    if warnings:
        print_warning("Optional dependencies (have fallbacks):")
        for warn in warnings:
            print(f"  - {warn}")
    
    if missing:
        print(f"\n{Colors.BOLD}Installation instructions:{Colors.RESET}")
    
        if system == "Linux":
            distro = "unknown"
            if Path("/etc/arch-release").exists():
                distro = "arch"
            elif Path("/etc/debian_version").exists():
                distro = "debian"
        elif Path("/etc/fedora-release").exists():
            distro = "fedora"
        
        if distro == "arch":
            print(f"""
  {Colors.CYAN}# Arch/CachyOS/Manjaro:{Colors.RESET}
  sudo pacman -S --needed base-devel libusb git arm-none-eabi-gcc arm-none-eabi-newlib
""")
        elif distro == "debian":
            print(f"""
  {Colors.CYAN}# Ubuntu/Debian:{Colors.RESET}
  sudo apt update
  sudo apt install build-essential libusb-1.0-0-dev git gcc-arm-none-eabi libnewlib-arm-none-eabi
""")
        elif distro == "fedora":
            print(f"""
  {Colors.CYAN}# Fedora:{Colors.RESET}
  sudo dnf groupinstall "Development Tools"
  sudo dnf install libusb1-devel arm-none-eabi-gcc-cs arm-none-eabi-newlib
""")
        else:
            print(f"""
  {Colors.CYAN}# Generic:{Colors.RESET}
  Install: build-essential, libusb-1.0-dev, git, arm-none-eabi-gcc
""")
    
    elif system == "Windows":
        print(f"""
  {Colors.CYAN}Option 1 - MSYS2 (Recommended):{Colors.RESET}
  1. Download MSYS2 from https://www.msys2.org/
  2. Open MSYS2 MINGW64 terminal and run:
     pacman -S mingw-w64-x86_64-gcc mingw-w64-x86_64-libusb make
     pacman -S mingw-w64-x86_64-arm-none-eabi-gcc

  {Colors.CYAN}Option 2 - WSL (Windows Subsystem for Linux):{Colors.RESET}
  1. Install WSL2: wsl --install
  2. Run this tool inside WSL with Linux dependencies
""")



def check_shofel_built() -> bool:
    """Check if shofel2_t124 is already built"""
    shofel_exe = SHOFEL_DIR / "shofel2_t124"
    if platform.system() == "Windows":
        shofel_exe = SHOFEL_DIR / "shofel2_t124.exe"
    return shofel_exe.exists()


def check_payloads_built() -> Tuple[bool, List[str]]:
    """Check if ARM payload binaries exist"""
    required_payloads = ["emmc_server.bin"]  # This is the critical one for EMMC operations
    optional_payloads = ["boot_bct.bin", "mem_dumper_usb_server.bin", "intermezzo.bin"]
    
    missing_required = []
    missing_optional = []
    
    for payload in required_payloads:
        if not (SHOFEL_DIR / payload).exists():
            missing_required.append(payload)
    
    for payload in optional_payloads:
        if not (SHOFEL_DIR / payload).exists():
            missing_optional.append(payload)
    
    return len(missing_required) == 0, missing_required + missing_optional


def build_shofel(force_rebuild: bool = False) -> bool:
    """Build the shofel2_t124 exploit tool"""
    print_step(1, 6, "Building Shofel exploit tool")
    
    payloads_ok, missing_payloads = check_payloads_built()
    
    if check_shofel_built() and payloads_ok and not force_rebuild:
        print_success("Shofel already built, skipping...")
        return True
    
    print_info("Compiling shofel2_t124...")
    
    try:
        if force_rebuild:
            run_command(["make", "clean"], cwd=SHOFEL_DIR, capture_output=True, check=False)
        
        result = run_command(["make"], cwd=SHOFEL_DIR, capture_output=True, check=False)
        
        if check_shofel_built():
            print_success("Host tool (shofel2_t124) built successfully!")
            
            payloads_ok, missing_payloads = check_payloads_built()
            if not payloads_ok:
                print_error("ARM payload binaries are missing!")
                print_info("Missing files: " + ", ".join(missing_payloads))
                print()
                print(f"{Colors.YELLOW}The ARM toolchain (arm-none-eabi-gcc) is required to build payloads.{Colors.RESET}")
                print()
                
                if Path("/etc/arch-release").exists():
                    print(f"  {Colors.CYAN}Arch/CachyOS:{Colors.RESET} sudo pacman -S arm-none-eabi-gcc arm-none-eabi-newlib")
                elif Path("/etc/debian_version").exists():
                    print(f"  {Colors.CYAN}Ubuntu/Debian:{Colors.RESET} sudo apt install gcc-arm-none-eabi libnewlib-arm-none-eabi")
                elif Path("/etc/fedora-release").exists():
                    print(f"  {Colors.CYAN}Fedora:{Colors.RESET} sudo dnf install arm-none-eabi-gcc-cs arm-none-eabi-newlib")
                else:
                    print(f"  Install arm-none-eabi-gcc for your distribution")
                
                print()
                print("After installing, run: make -C Shofel")
                return False
            else:
                print_success("All payload binaries present!")
            
            return True
        else:
            print_error("Shofel build failed")
            if result.stderr:
                print(result.stderr)
            return False
            
    except Exception as e:
        print_error(f"Build failed: {e}")
        return False



def detect_jibo_rcm() -> bool:
    """Detect if Jibo is connected in RCM mode"""
    print_info("Looking for Jibo in RCM mode (NVIDIA APX device)...")
    
    if platform.system() == "Linux":
        if shutil.which("lsusb"):
            try:
                result = run_command(["lsusb"], capture_output=True)
                if "0955:7740" in result.stdout:
                    print_success("Found Jibo in RCM mode!")
                    return True
                else:
                    print_warning("Jibo not found in RCM mode")
                    print_info("Make sure to:")
                    print("  1. Hold the RCM button (small button under the base)")
                    print("  2. Press the reset/power button")
                    print("  3. Release after seeing red LED (no boot animation)")
                    return False
            except Exception as e:
                print_error(f"lsusb failed: {e}")
        
        try:
            usb_devices = Path("/sys/bus/usb/devices")
            if usb_devices.exists():
                for device in usb_devices.iterdir():
                    vendor_file = device / "idVendor"
                    product_file = device / "idProduct"
                    if vendor_file.exists() and product_file.exists():
                        vendor = vendor_file.read_text().strip()
                        product = product_file.read_text().strip()
                        if vendor == "0955" and product == "7740":
                            print_success("Found Jibo in RCM mode! (via sysfs)")
                            return True
        except Exception:
            pass
        
        print_warning("Cannot detect USB devices. Please ensure Jibo is in RCM mode.")
        print_info("The tool will attempt to connect anyway.")
        return True  # Let shofel try
    
    elif platform.system() == "Windows":
        print_warning("Windows USB detection - please ensure Zadig drivers are installed")
        print_info("Run Zadig and install WinUSB driver for 'APX' device")
        return True
    
    return False


def wait_for_jibo_rcm(timeout: int = 60) -> bool:
    """Wait for Jibo to be connected in RCM mode"""
    import time
    
    print_info(f"Waiting for Jibo in RCM mode (timeout: {timeout}s)...")
    print_info("Hold RCM button + press reset/power to enter RCM mode")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        if detect_jibo_rcm():
            return True
        time.sleep(1)
        sys.stdout.write(".")
        sys.stdout.flush()
    
    print()
    print_error("Timeout waiting for Jibo")
    return False



def parse_gpt_partitions(dump_path: Path) -> List[PartitionInfo]:
    """Parse GPT partition table from dump file"""
    partitions = []
    
    with open(dump_path, "rb") as f:
        f.seek(512)
        
        gpt_header = f.read(512)
        
        signature = gpt_header[:8]
        if signature != b'EFI PART':
            print_warning("GPT signature not found, trying fdisk parsing...")
            return parse_partitions_fdisk(dump_path)
        
        partition_entries_lba = struct.unpack("<Q", gpt_header[72:80])[0]
        num_entries = struct.unpack("<I", gpt_header[80:84])[0]
        entry_size = struct.unpack("<I", gpt_header[84:88])[0]
        
        f.seek(partition_entries_lba * 512)
        
        for i in range(num_entries):
            entry = f.read(entry_size)
            if len(entry) < 128:
                break
            
            
            type_guid = entry[:16]
            if type_guid == b'\x00' * 16:
                continue  # Empty entry
            
            first_lba = struct.unpack("<Q", entry[32:40])[0]
            last_lba = struct.unpack("<Q", entry[40:48])[0]
            
            name_bytes = entry[56:128]
            try:
                name = name_bytes.decode('utf-16le').rstrip('\x00')
            except:
                name = f"partition{i+1}"
            
            partitions.append(PartitionInfo(
                number=i + 1,
                start_sector=first_lba,
                end_sector=last_lba,
                size_sectors=last_lba - first_lba + 1,
                name=name
            ))
    
    return partitions


def parse_partitions_fdisk(dump_path: Path) -> List[PartitionInfo]:
    """Parse partitions using fdisk (Linux fallback)"""
    partitions = []
    
    try:
        result = run_command(
            ["fdisk", "-l", str(dump_path)],
            capture_output=True,
            check=False
        )
        
        for line in result.stdout.split('\n'):
            if dump_path.name in line and not line.startswith("Disk"):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        part_name = parts[0]
                        part_num = int(''.join(c for c in part_name if c.isdigit()) or '0')
                        
                        start = int(parts[1])
                        end = int(parts[2])
                        
                        partitions.append(PartitionInfo(
                            number=part_num,
                            start_sector=start,
                            end_sector=end,
                            size_sectors=end - start + 1,
                            name=f"partition{part_num}"
                        ))
                    except (ValueError, IndexError):
                        continue
        
    except Exception as e:
        print_error(f"fdisk parsing failed: {e}")
    
    return partitions


def find_var_partition(partitions: List[PartitionInfo]) -> Optional[PartitionInfo]:
    """Find the /var partition (partition 5, ~500MB)"""
    for part in partitions:
        if part.number == 5:
            size_mb = (part.size_sectors * EMMC_SECTOR_SIZE) / (1024 * 1024)
            if 400 < size_mb < 600:
                return part
    
    for part in partitions:
        size_mb = (part.size_sectors * EMMC_SECTOR_SIZE) / (1024 * 1024)
        if 450 < size_mb < 550:
            print_warning(f"Using partition {part.number} as var (size matches)")
            return part
    
    return None



def extract_partition(dump_path: Path, partition: PartitionInfo, output_path: Path) -> bool:
    """Extract a partition from the dump"""
    print_info(f"Extracting partition {partition.number} ({partition.size_sectors} sectors)...")
    
    try:
        with open(dump_path, "rb") as src:
            src.seek(partition.start_sector * EMMC_SECTOR_SIZE)
            data = src.read(partition.size_sectors * EMMC_SECTOR_SIZE)
        
        with open(output_path, "wb") as dst:
            dst.write(data)
        
        print_success(f"Partition extracted to {output_path}")
        return True
        
    except Exception as e:
        print_error(f"Extraction failed: {e}")
        return False


def modify_mode_json_direct(partition_path: Path) -> bool:
    """
    Modify mode.json directly in the partition image by searching for the pattern.
    This works on both Linux and Windows without mounting.
    """
    print_info("Searching for mode.json in partition (raw, no mount)...")

    def _is_safe_pad_byte(b: int) -> bool:
        return b in (0x00, 0x09, 0x0A, 0x0D, 0x20)

    try:
        with open(partition_path, "r+b") as f:
            data = bytearray(f.read())

            json_patterns = [
                (b'{"mode":"normal"}', b'{"mode":"int-developer"}'),
                (b'{"mode": "normal"}', b'{"mode": "int-developer"}'),
                (b'{ "mode": "normal" }', b'{"mode":"int-developer"}'),
            ]

            for old_json, new_json in json_patterns:
                offset = bytes(data).find(old_json)
                if offset == -1:
                    continue

                print_info(f"Found mode.json JSON at offset {offset} (0x{offset:x})")
                end_offset = offset + len(old_json)

                if len(new_json) <= len(old_json):
                    region_len = len(old_json)
                    replacement = new_json + b" " * (region_len - len(new_json))
                    data[offset:offset + region_len] = replacement
                else:
                    extra = len(new_json) - len(old_json)
                    following = data[end_offset:end_offset + extra]
                    if len(following) != extra or not all(_is_safe_pad_byte(b) for b in following):
                        print_warning("Raw edit would require growing the file and no safe padding was found")
                        return False

                    region_len = len(new_json)
                    data[offset:offset + region_len] = new_json

                f.seek(0)
                f.write(data)
                print_success("mode.json modified successfully (raw in-place overwrite)")
                return True

            print_warning("mode.json pattern not found (raw). Will try filesystem mount if available...")
            return False

    except Exception as e:
        print_error(f"Direct modification failed: {e}")
        return False


def modify_partition_mounted(partition_path: Path) -> bool:
    """Modify mode.json by mounting the partition (Linux only)"""
    if platform.system() != "Linux":
        print_error("Filesystem mounting only supported on Linux")
        return False
    
    mount_point = WORK_DIR / "jibo_var_mount"
    mount_point.mkdir(parents=True, exist_ok=True)
    
    try:
        print_info(f"Mounting partition at {mount_point}...")
        run_command(
            ["mount", "-o", "loop", str(partition_path), str(mount_point)],
            sudo=True
        )
        
        mode_json_path = mount_point / "jibo" / "mode.json"
        
        if not mode_json_path.exists():
            for alt_path in [
                mount_point / "mode.json",
                mount_point / "etc" / "jibo" / "mode.json",
            ]:
                if alt_path.exists():
                    mode_json_path = alt_path
                    break
        
        if mode_json_path.exists():
            print_info(f"Found mode.json at {mode_json_path}")

            perm = None
            uid = None
            gid = None
            try:
                stat_res = run_command(
                    ["stat", "-c", "%a %u %g", str(mode_json_path)],
                    sudo=True,
                    capture_output=True,
                    check=True,
                )
                parts = stat_res.stdout.strip().split()
                if len(parts) == 3:
                    perm, uid, gid = parts[0], parts[1], parts[2]
            except Exception:
                pass

            try:
                backup_text = run_command(
                    ["cat", str(mode_json_path)],
                    sudo=True,
                    capture_output=True,
                    check=True,
                ).stdout
                (WORK_DIR / "mode.json.original").write_text(backup_text)
            except Exception:
                pass

            try:
                mode_text = run_command(
                    ["cat", str(mode_json_path)],
                    sudo=True,
                    capture_output=True,
                    check=True,
                ).stdout
                content = json.loads(mode_text)
            except Exception:
                with open(mode_json_path, "r") as f:
                    content = json.load(f)
            
            print_info(f"Current mode: {content.get('mode', 'unknown')}")
            
            content["mode"] = "int-developer"
            
            temp_json = WORK_DIR / "mode_temp.json"
            with open(temp_json, "w") as f:
                json.dump(content, f)

            run_command(["cp", str(temp_json), str(mode_json_path)], sudo=True)

            if perm is not None:
                run_command(["chmod", perm, str(mode_json_path)], sudo=True, check=False)
            if uid is not None and gid is not None:
                run_command(["chown", f"{uid}:{gid}", str(mode_json_path)], sudo=True, check=False)

            try:
                (WORK_DIR / "mode.json.modified").write_text(json.dumps(content))
            except Exception:
                pass
            
            print_success("mode.json modified to 'int-developer'")
            
        else:
            print_error(f"mode.json not found in mounted partition")
            print_info("Listing mount contents:")
            run_command(["ls", "-la", str(mount_point)], sudo=True)
            return False
        
        return True
        
    except Exception as e:
        print_error(f"Mount/modify failed: {e}")
        return False
        
    finally:
        try:
            run_command(["umount", str(mount_point)], sudo=True, check=False)
        except:
            pass


def _find_debugfs_executable() -> Optional[str]:
    """Find a usable debugfs executable (e2fsprogs)."""
    for candidate in ("debugfs", "debugfs.exe"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def modify_partition_debugfs(partition_path: Path) -> bool:
    """Modify mode.json using debugfs (e2fsprogs) without mounting.

    This can work on Windows if the user has MSYS2 e2fsprogs installed (debugfs.exe on PATH).
    """
    debugfs = _find_debugfs_executable()
    if not debugfs:
        return False

    print_info("Attempting mode.json edit via debugfs (no mount)...")

    candidate_paths = [
        "/jibo/mode.json",
        "/mode.json",
        "/etc/jibo/mode.json",
    ]

    existing_path: Optional[str] = None
    original_text: Optional[str] = None
    for p in candidate_paths:
        try:
            res = run_command(
                [debugfs, "-R", f"cat {p}", str(partition_path)],
                capture_output=True,
                check=True,
            )
            if res.stdout and "File not found" not in res.stdout:
                existing_path = p
                original_text = res.stdout
                break
        except Exception:
            continue

    if not existing_path or original_text is None:
        print_warning("debugfs could not locate mode.json inside the image")
        return False

    try:
        (WORK_DIR / "mode.json.original").write_text(original_text)
    except Exception:
        pass

    try:
        content = json.loads(original_text)
    except Exception:
        print_warning("mode.json content is not valid JSON; refusing to edit")
        return False

    content["mode"] = "int-developer"
    new_text = json.dumps(content)

    temp_json = WORK_DIR / "mode_temp.json"
    temp_json.write_text(new_text)

    try:
        run_command([debugfs, "-w", "-R", f"rm {existing_path}", str(partition_path)], check=False, capture_output=True)
        run_command([debugfs, "-w", "-R", f"write {str(temp_json)} {existing_path}", str(partition_path)], capture_output=True)
    except Exception as e:
        print_warning(f"debugfs write failed: {e}")
        return False

    try:
        (WORK_DIR / "mode.json.modified").write_text(new_text)
    except Exception:
        pass

    print_success("mode.json modified to 'int-developer' (debugfs)")
    return True


def modify_var_partition(partition_path: Path) -> bool:
    """Modify the var partition to enable developer mode"""
    print_step(4, 6, "Modifying var partition")

    if platform.system() == "Linux":
        if modify_partition_mounted(partition_path):
            return True
        print_warning("Mount-based edit failed; falling back to raw in-place patch")

    if modify_partition_debugfs(partition_path):
        return True

    if modify_mode_json_direct(partition_path):
        return True
    
    print_error("Could not modify partition")
    return False


def emmc_read_to_file(output_path: Path, start_sector: int, num_sectors: int) -> bool:
    """Read a range of sectors from eMMC into a file."""
    shofel = get_shofel_path()
    if not shofel.exists():
        print_error("shofel2_t124 not found. Please build it first.")
        return False

    try:
        cmd = [
            str(shofel),
            "EMMC_READ",
            f"0x{start_sector:x}",
            f"0x{num_sectors:x}",
            str(output_path),
        ]
        if platform.system() == "Linux":
            cmd = ["sudo"] + cmd
        subprocess.run(cmd, cwd=SHOFEL_DIR, check=True)
        return output_path.exists()
    except subprocess.CalledProcessError as e:
        print_error(f"EMMC_READ failed: {e}")
        return False


def emmc_write_file(input_path: Path, start_sector: int) -> bool:
    """Write a file to eMMC starting at a given sector."""
    shofel = get_shofel_path()
    if not shofel.exists():
        print_error("shofel2_t124 not found. Please build it first.")
        return False

    try:
        cmd = [
            str(shofel),
            "EMMC_WRITE",
            f"0x{start_sector:x}",
            str(input_path),
        ]
        if platform.system() == "Linux":
            cmd = ["sudo"] + cmd
        subprocess.run(cmd, cwd=SHOFEL_DIR, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"EMMC_WRITE failed: {e}")
        return False


def compute_changed_sector_ranges(original_path: Path, modified_path: Path, sector_size: int = 512,
                                 scan_chunk_bytes: int = 4 * 1024 * 1024) -> Tuple[int, List[Tuple[int, int]]]:
    """Return (changed_sector_count, ranges) where ranges are (start_sector_offset, num_sectors)."""
    if original_path.stat().st_size != modified_path.stat().st_size:
        raise ValueError("Files differ in size; cannot compute sector diffs")
    total_bytes = original_path.stat().st_size
    if total_bytes % sector_size != 0:
        raise ValueError("Partition image size is not a multiple of sector size")

    changed_sectors: List[int] = []
    scan_chunk_bytes = max(sector_size, (scan_chunk_bytes // sector_size) * sector_size)

    with open(original_path, "rb") as f1, open(modified_path, "rb") as f2:
        base_sector = 0
        while True:
            b1 = f1.read(scan_chunk_bytes)
            b2 = f2.read(scan_chunk_bytes)
            if not b1 and not b2:
                break
            if b1 == b2:
                base_sector += len(b1) // sector_size
                continue

            sectors_in_chunk = min(len(b1), len(b2)) // sector_size
            for i in range(sectors_in_chunk):
                s1 = b1[i * sector_size:(i + 1) * sector_size]
                s2 = b2[i * sector_size:(i + 1) * sector_size]
                if s1 != s2:
                    changed_sectors.append(base_sector + i)
            base_sector += sectors_in_chunk

    if not changed_sectors:
        return 0, []

    changed_sectors.sort()
    ranges: List[Tuple[int, int]] = []
    start = prev = changed_sectors[0]
    for s in changed_sectors[1:]:
        if s == prev + 1:
            prev = s
            continue
        ranges.append((start, prev - start + 1))
        start = prev = s
    ranges.append((start, prev - start + 1))
    return len(changed_sectors), ranges


def write_partition_patch_to_emmc(original_path: Path, modified_path: Path, base_start_sector: int,
                                 max_ranges: int = 128, max_changed_sectors: int = 131072) -> bool:
    """Write only the changed sectors between two partition images."""
    try:
        changed_count, ranges = compute_changed_sector_ranges(original_path, modified_path)
    except Exception as e:
        print_warning(f"Patch write unavailable ({e}); falling back to full partition write")
        return write_partition_to_emmc(modified_path, base_start_sector)

    if changed_count == 0:
        print_success("No changes detected in /var partition; nothing to write")
        return True

    if len(ranges) > max_ranges or changed_count > max_changed_sectors:
        print_warning(f"Too many changes for patch write (ranges={len(ranges)}, sectors={changed_count}); using full /var write")
        return write_partition_to_emmc(modified_path, base_start_sector)

    print_info(f"Writing patch: {changed_count} sectors across {len(ranges)} ranges")

    sector_size = EMMC_SECTOR_SIZE
    with open(modified_path, "rb") as src:
        for idx, (start_off, count) in enumerate(ranges, start=1):
            patch_path = WORK_DIR / f"var_patch_{idx:03d}.bin"
            src.seek(start_off * sector_size)
            payload = src.read(count * sector_size)
            patch_path.write_bytes(payload)
            if not emmc_write_file(patch_path, base_start_sector + start_off):
                return False
    return True



def get_shofel_path() -> Path:
    """Get the path to shofel2_t124 executable"""
    if platform.system() == "Windows":
        return SHOFEL_DIR / "shofel2_t124.exe"
    return SHOFEL_DIR / "shofel2_t124"


def dump_emmc(output_path: Path, start_sector: int = 0, num_sectors: int = EMMC_TOTAL_SECTORS) -> bool:
    """Dump the Jibo eMMC to a file"""
    print_step(2, 6, "Dumping Jibo eMMC")
    
    shofel = get_shofel_path()
    if not shofel.exists():
        print_error("shofel2_t124 not found. Please build it first.")
        return False
    
    print_info(f"Dumping {num_sectors} sectors ({num_sectors * 512 / 1024 / 1024 / 1024:.1f} GB)...")
    print_info("This will take approximately 2-4 hours. Please be patient.")
    print_warning("DO NOT disconnect Jibo during this process!")
    
    try:
        cmd = [
            str(shofel),
            "EMMC_READ",
            f"0x{start_sector:x}",
            f"0x{num_sectors:x}",
            str(output_path)
        ]
        
        if platform.system() == "Linux":
            cmd = ["sudo"] + cmd
        
        subprocess.run(cmd, cwd=SHOFEL_DIR, check=True)
        
        if output_path.exists():
            size_gb = output_path.stat().st_size / (1024 * 1024 * 1024)
            print_success(f"eMMC dump complete: {output_path} ({size_gb:.2f} GB)")
            return True
        else:
            print_error("Dump file not created")
            return False
            
    except subprocess.CalledProcessError as e:
        print_error(f"eMMC dump failed: {e}")
        return False
    except KeyboardInterrupt:
        print_warning("Dump interrupted by user")
        return False


def write_partition_to_emmc(partition_path: Path, start_sector: int) -> bool:
    """Write a partition back to the Jibo eMMC"""
    print_step(5, 6, "Writing modified partition to Jibo")
    
    shofel = get_shofel_path()
    if not shofel.exists():
        print_error("shofel2_t124 not found")
        return False
    
    print_info(f"Writing to sector 0x{start_sector:x}...")
    print_warning("DO NOT disconnect Jibo during this process!")
    
    try:
        cmd = [
            str(shofel),
            "EMMC_WRITE",
            f"0x{start_sector:x}",
            str(partition_path)
        ]
        
        if platform.system() == "Linux":
            cmd = ["sudo"] + cmd
        
        subprocess.run(cmd, cwd=SHOFEL_DIR, check=True)
        
        print_success("Partition written successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print_error(f"Write failed: {e}")
        return False


def verify_write(partition_path: Path, start_sector: int, num_sectors: int) -> bool:
    """Verify the write by reading back and comparing hashes"""
    print_step(6, 6, "Verifying write")
    
    shofel = get_shofel_path()
    verify_path = WORK_DIR / "verify_partition.bin"
    
    print_info("Reading back partition for verification...")
    
    try:
        cmd = [
            str(shofel),
            "EMMC_READ",
            f"0x{start_sector:x}",
            f"0x{num_sectors:x}",
            str(verify_path)
        ]
        
        if platform.system() == "Linux":
            cmd = ["sudo"] + cmd
        
        subprocess.run(cmd, cwd=SHOFEL_DIR, check=True)
        
        with open(partition_path, "rb") as f:
            original_hash = hashlib.md5(f.read()).hexdigest()
        
        with open(verify_path, "rb") as f:
            verify_hash = hashlib.md5(f.read()).hexdigest()
        
        if original_hash == verify_hash:
            print_success(f"Verification passed! Hash: {original_hash}")
            return True
        else:
            print_error("Verification FAILED - hashes don't match!")
            print(f"  Original: {original_hash}")
            print(f"  Readback: {verify_hash}")
            return False
            
    except Exception as e:
        print_error(f"Verification failed: {e}")
        return False



def run_full_mod(args) -> bool:
    """Run the complete modding workflow"""
    print_banner()
    
    sys_info = get_system_info()
    print_info(f"System: {sys_info['os']} ({sys_info['arch']})")
    
    if sys_info['is_wsl']:
        print_info("Running in WSL - USB passthrough may require additional setup")
    
    print_step(0, 6, "Checking dependencies")
    
    if sys_info['os'] == "Linux":
        deps_ok, missing, warnings = check_linux_dependencies()
    else:
        deps_ok, missing, warnings = check_windows_dependencies()
    
    if not deps_ok:
        print_install_instructions(sys_info['os'], missing, warnings)
        return False
    
    if warnings:
        for warn in warnings:
            print_warning(f"Optional: {warn}")
    
    print_success("All required dependencies found!")
    
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    
    if not build_shofel(force_rebuild=args.rebuild_shofel):
        return False
    
    if not args.skip_detection:
        if not detect_jibo_rcm():
            if not wait_for_jibo_rcm(timeout=120):
                return False
    
    dump_path = WORK_DIR / "jibo_full_dump.bin"
    var_partition_path = WORK_DIR / "var_partition.bin"
    backup_var_path = WORK_DIR / "var_partition_backup.bin"
    
    if args.dump_path:
        dump_path = Path(args.dump_path)
        if not dump_path.exists():
            print_error(f"Specified dump file not found: {dump_path}")
            return False
        print_info(f"Using existing dump: {dump_path}")
    elif dump_path.exists() and not args.force_dump:
        print_info(f"Using existing dump: {dump_path}")
        print_info("Use --force-dump to re-dump")
    else:
        if not dump_emmc(dump_path):
            return False
    
    print_step(3, 6, "Analyzing partition table")
    
    partitions = parse_gpt_partitions(dump_path)
    if not partitions:
        print_error("No partitions found in dump")
        return False
    
    print_info("Partitions found:")
    for part in partitions:
        size_mb = (part.size_sectors * EMMC_SECTOR_SIZE) / (1024 * 1024)
        print(f"  {part.number}: sectors {part.start_sector}-{part.end_sector} ({size_mb:.1f} MB) - {part.name}")
    
    var_partition = find_var_partition(partitions)
    if not var_partition:
        print_error("Could not identify /var partition")
        return False
    
    print_success(f"Identified /var partition: partition {var_partition.number}")
    
    if not extract_partition(dump_path, var_partition, var_partition_path):
        return False
    
    shutil.copy(var_partition_path, backup_var_path)
    print_info(f"Backup created: {backup_var_path}")
    
    if not modify_var_partition(var_partition_path):
        return False
    
    if not args.skip_detection:
        print_info("Please ensure Jibo is still in RCM mode")
        print_info("If Jibo rebooted, re-enter RCM mode now")
        if not wait_for_jibo_rcm(timeout=60):
            print_warning("Continuing anyway...")
    
    if not write_partition_to_emmc(var_partition_path, var_partition.start_sector):
        return False
    
    if args.verify:
        if not verify_write(var_partition_path, var_partition.start_sector, var_partition.size_sectors):
            print_warning("Verification failed, but write may still be successful")
    
    print(f"""
{Colors.GREEN}╔═══════════════════════════════════════════════════════════════════╗
║                     {Colors.BOLD}MODDING COMPLETE!{Colors.RESET}{Colors.GREEN}                             ║
╚═══════════════════════════════════════════════════════════════════╝{Colors.RESET}

{Colors.BOLD}Next steps:{Colors.RESET}
1. Unplug Jibo from USB
2. Hold power button until red LED goes off
3. Power on Jibo normally
4. Wait for boot - you should see a checkmark instead of the eye
5. SSH into Jibo:
   {Colors.CYAN}ssh root@<jibo-ip>{Colors.RESET}
   Password: {Colors.YELLOW}jibo{Colors.RESET}

{Colors.BOLD}Your backup is saved at:{Colors.RESET}
{backup_var_path}

{Colors.YELLOW}Keep this backup safe - it contains your Jibo's calibration data!{Colors.RESET}
""")
    
    return True


def run_dump_only(args) -> bool:
    """Only dump the eMMC without modding"""
    print_banner()
    print_info("Running in dump-only mode")
    
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    
    if not build_shofel(force_rebuild=args.rebuild_shofel):
        return False
    
    if not args.skip_detection:
        if not wait_for_jibo_rcm(timeout=120):
            return False
    
    output_path = Path(args.output) if args.output else WORK_DIR / "jibo_full_dump.bin"
    return dump_emmc(output_path)


def run_write_only(args) -> bool:
    """Write a pre-modified partition to Jibo"""
    print_banner()
    print_info("Running in write-only mode")
    
    partition_path = Path(args.partition)
    if not partition_path.exists():
        print_error(f"Partition file not found: {partition_path}")
        return False
    
    if not build_shofel():
        return False
    
    if not args.skip_detection:
        if not wait_for_jibo_rcm(timeout=120):
            return False
    
    return write_partition_to_emmc(partition_path, args.start_sector)


def run_mode_json_only(args) -> bool:
    """Fast path: dump only GPT + /var, modify /var/jibo/mode.json, and write back minimal changes."""
    print_banner()
    print_info("Running in mode-json-only mode (GPT + /var only)")

    WORK_DIR.mkdir(parents=True, exist_ok=True)

    if not build_shofel(force_rebuild=args.rebuild_shofel):
        return False

    if not args.skip_detection:
        if not wait_for_jibo_rcm(timeout=120):
            return False

    gpt_path = WORK_DIR / "gpt_dump.bin"
    gpt_sectors = 4096  # 2MB; safely covers typical GPT entry area
    print_info(f"Dumping GPT header/table ({gpt_sectors} sectors)...")
    if not emmc_read_to_file(gpt_path, 0, gpt_sectors):
        return False

    partitions = parse_gpt_partitions(gpt_path)
    if not partitions:
        print_error("No partitions found in GPT dump")
        return False

    var_partition = find_var_partition(partitions)
    if not var_partition:
        print_error("Could not identify /var partition from GPT")
        return False

    print_success(
        f"Identified /var partition: {var_partition.number} "
        f"(start=0x{var_partition.start_sector:x}, sectors={var_partition.size_sectors})"
    )

    original_var_path = WORK_DIR / "var_partition_original.bin"
    var_partition_path = WORK_DIR / "var_partition.bin"
    backup_var_path = WORK_DIR / "var_partition_backup.bin"

    print_info("Dumping /var partition only (this is much smaller than a full eMMC dump)...")
    if not emmc_read_to_file(original_var_path, var_partition.start_sector, var_partition.size_sectors):
        return False

    shutil.copy(original_var_path, var_partition_path)
    shutil.copy(original_var_path, backup_var_path)
    print_info(f"Backup created: {backup_var_path}")

    if not modify_var_partition(var_partition_path):
        return False

    if not args.skip_detection:
        print_info("Please ensure Jibo is still in RCM mode")
        if not wait_for_jibo_rcm(timeout=60):
            print_warning("Continuing anyway...")

    if args.full_var_write:
        print_info("Writing full /var partition back to device...")
        if not write_partition_to_emmc(var_partition_path, var_partition.start_sector):
            return False
    else:
        print_info("Writing only changed sectors back to device (patch write)...")
        if not write_partition_patch_to_emmc(original_var_path, var_partition_path, var_partition.start_sector):
            return False

    if args.verify:
        if not verify_write(var_partition_path, var_partition.start_sector, var_partition.size_sectors):
            print_warning("Verification failed, but write may still be successful")

    print(f"\n{Colors.GREEN}{Colors.BOLD}Mode.json update complete!{Colors.RESET}")
    print_info(f"Saved originals in: {WORK_DIR}")
    print_info("If Jibo boots to a checkmark, SSH should work.")
    return True



def main():
    parser = argparse.ArgumentParser(
        description="Jibo Auto-Mod Tool - Automatically enable developer mode on Jibo robots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                      # Run full modding workflow
  %(prog)s --dump-only          # Only dump eMMC
  %(prog)s --write-partition var.bin --start-sector 0x7E9022
  %(prog)s --dump-path existing_dump.bin   # Use existing dump
        """
    )
    
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--dump-only", action="store_true",
                           help="Only dump the eMMC without modifying")
    mode_group.add_argument("--write-partition", metavar="FILE",
                           help="Write a partition file to Jibo (requires --start-sector)")
    mode_group.add_argument("--mode-json-only", action="store_true",
                           help="Fast mode: dump GPT + /var only, patch /var/jibo/mode.json, write back minimal changes")
    
    parser.add_argument("--dump-path", metavar="FILE",
                       help="Use existing dump file instead of dumping")
    parser.add_argument("--output", "-o", metavar="FILE",
                       help="Output file for dump (default: jibo_work/jibo_full_dump.bin)")
    parser.add_argument("--start-sector", type=lambda x: int(x, 0), default=0x7E9022,
                       help="Start sector for write operation (hex, default: 0x7E9022)")
    parser.add_argument("--force-dump", action="store_true",
                       help="Force re-dump even if dump file exists")
    parser.add_argument("--rebuild-shofel", action="store_true",
                       help="Force rebuild of Shofel exploit")
    parser.add_argument("--skip-detection", action="store_true",
                       help="Skip USB device detection (useful for debugging)")
    parser.add_argument("--verify", action="store_true", default=True,
                       help="Verify write by reading back (default: True)")
    parser.add_argument("--no-verify", action="store_false", dest="verify",
                       help="Skip write verification")
    parser.add_argument("--full-var-write", action="store_true", default=False,
                       help="With --mode-json-only: write entire /var partition instead of patch-writing changed sectors")
    
    args = parser.parse_args()
    
    if args.write_partition and not args.start_sector:
        parser.error("--write-partition requires --start-sector")
    
    try:
        if args.dump_only:
            success = run_dump_only(args)
        elif args.write_partition:
            args.partition = args.write_partition
            success = run_write_only(args)
        elif args.mode_json_only:
            success = run_mode_json_only(args)
        else:
            success = run_full_mod(args)
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n")
        print_warning("Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
