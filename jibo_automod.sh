#!/bin/bash
# Jibo Auto-Mod Tool - Linux/macOS Launcher
# This script checks dependencies and runs the auto-mod tool

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo ""
echo "============================================================"
echo "         JIBO AUTO-MOD TOOL - Linux Launcher"
echo "============================================================"
echo ""

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 not found!"
    echo "        Install with: sudo apt install python3"
    exit 1
fi

PYVER=$(python3 --version)
echo "[INFO] Found $PYVER"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "[INFO] Not running as root. sudo will be used when needed."
    # Check if we can sudo
    if ! sudo -v &> /dev/null; then
        echo "[WARNING] Cannot use sudo. USB operations may fail."
    fi
fi

# Check for required tools
check_tool() {
    if ! command -v "$1" &> /dev/null; then
        echo "[WARNING] $1 not found. Install: $2"
        return 1
    fi
    return 0
}

MISSING=0
check_tool "lsusb" "sudo apt install usbutils" || MISSING=1
check_tool "make" "sudo apt install build-essential" || MISSING=1
check_tool "gcc" "sudo apt install build-essential" || MISSING=1
check_tool "arm-none-eabi-gcc" "sudo apt install gcc-arm-none-eabi" || MISSING=1

if [ $MISSING -eq 1 ]; then
    echo ""
    echo "[WARNING] Some dependencies are missing. The tool will try to continue"
    echo "          but some features may not work."
    echo ""
fi

# Run the tool
echo "[INFO] Starting Jibo Auto-Mod Tool..."
echo ""

python3 jibo_automod.py "$@"
