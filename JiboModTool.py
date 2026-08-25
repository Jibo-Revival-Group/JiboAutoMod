import importlib
import importlib.util
import os
import platform
import subprocess
import sys
import time
from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError, requires, version
from pathlib import Path

# Check if packaging library exists. It wasn't existing in my nixos so I wanted to add this check for the other users
if importlib.util.find_spec("packaging") is None:
    # Get the os
    if sys.platform.startswith("linux"):
        distro_id = None
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("ID="):
                        distro_id = line.strip().split("=", 1)[1].strip('"')
                        break
        except FileNotFoundError:
            pass

        if distro_id == "nixos":
            # NixOS users need to run the flake.nix file
            print(
                "The required libraries are not installed. If you are using nixos, "
                "please run `nix develop` in the root directory and run the modding tool "
                "in the created shell again. This will install the required dependencies "
                "needed for the modding tool"
            )
        elif distro_id in (
            "ubuntu",
            "debian",
            "linuxmint",
            "pop",
            "elementary",
            "zorin",
        ):
            # Debian -> apt
            print("Attempting to install python3-packaging via apt...")
            try:
                subprocess.run(
                    ["sudo", "apt", "install", "-y", "python3-packaging"], check=True
                )
            except subprocess.CalledProcessError:
                print(
                    "Automatic installation failed. Please install 'python3-packaging' manually."
                )
        elif distro_id in ("fedora", "centos", "rhel", "rocky", "almalinux"):
            # Red Hat -> dnf
            print("Attempting to install python3-packaging via dnf...")
            try:
                subprocess.run(
                    ["sudo", "dnf", "install", "-y", "python3-packaging"], check=True
                )
            except subprocess.CalledProcessError:
                print(
                    "Automatic installation failed. Please install 'python3-packaging' manually."
                )
        elif distro_id in ("arch", "manjaro", "endeavouros"):
            # Arch -> pacman
            print("Attempting to install python-packaging via pacman...")
            try:
                subprocess.run(
                    ["sudo", "pacman", "-S", "--noconfirm", "python-packaging"],
                    check=True,
                )
            except subprocess.CalledProcessError:
                print(
                    "Automatic installation failed. Please install 'python-packaging' manually."
                )
        elif distro_id in ("opensuse", "suse"):
            # openSUSE -> zypper
            print("Attempting to install python3-packaging via zypper...")
            try:
                subprocess.run(
                    ["sudo", "zypper", "install", "-y", "python3-packaging"], check=True
                )
            except subprocess.CalledProcessError:
                print(
                    "Automatic installation failed. Please install 'python3-packaging' manually."
                )
        else:
            # Unknown linux distro
            print(
                f"Unsupported Linux distribution detected (ID: {distro_id}). "
                "Please install the 'packaging' library manually using your package manager."
            )
    else:
        print(
            "The required 'packaging' library is not installed. "
            "Please install it using pip or your system's package manager."
        )

from packaging.requirements import Requirement

import config


@contextmanager
def execution_environment(run_dir: str):
    abs_run_dir = str(Path(run_dir).resolve())
    original_cwd = os.getcwd()

    # 1. Add run_dir to sys.path so importlib.import_module("Platform...") finds the package
    sys.path.insert(0, abs_run_dir)
    # 2. Change CWD for relative file checks (e.g. os.path.isdir("Platform/..."))
    os.chdir(abs_run_dir)

    try:
        yield
    finally:
        os.chdir(original_cwd)
        if abs_run_dir in sys.path:
            sys.path.remove(abs_run_dir)


class Color:
    # Styles
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Text Colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


def check_py_dependencies(requirements_file="requirements.txt"):
    try:
        missing_packages = []

        with open(requirements_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                req = Requirement(line)
                try:
                    installed_version = version(req.name)
                    if not req.specifier.contains(installed_version, prereleases=True):
                        missing_packages.append(line)
                except PackageNotFoundError:
                    missing_packages.append(line)

        if missing_packages:
            print(f"[  ] Missing packages: {', '.join(missing_packages)}")
            print("[  ] Installing pkgs...")

            cmd = [sys.executable, "-m", "pip", "install", "-r", requirements_file]

            # If on Linux/macOS and NOT in a virtual environment, append the bypass flag
            # (In Windows, or inside a venv, this isn't needed)
            in_venv = sys.prefix != sys.base_prefix
            if sys.platform != "win32" and not in_venv:
                cmd.append("--break-system-packages")

            subprocess.check_call(cmd)

            print("\n" + "=" * 50)
            print("[ 󱝎 ] All missing dependencies have been successfully installed!")
            print("[ 󱄌 ] Please RESTART the application now.")
            print("=" * 50 + "\n")
            sys.exit(0)

    except FileNotFoundError:
        print(f"[  ] Error: '{requirements_file}' not found.")
        sys.exit(1)


def get_os():
    os_name = platform.system()

    if os_name == "Linux":
        try:
            info = platform.freedesktop_os_release()
            distro = info.get("NAME", "Unknown Linux")
            return ("Linux", str(distro))
        except (AttributeError, KeyError, FileNotFoundError):
            return ("Linux", "Unknown Linux")
    elif os_name == "Windows":
        return ("Windows", str(platform.release()))
    else:
        return os_name


def load_platform_module(PLATFORM):
    os_name, os_version = PLATFORM

    os_dir = os.path.join("Platform", os_name)
    if not os.path.isdir(os_dir):
        print(
            f"[  ] (@load_platform_module) Critical Error: Operating System: {os_name} is not supported yet"
        )
        print(
            f"[  ] You can be the first one to contribute for {os_name} {os_version}! , Create a PR over at: "
        )
        print(
            "[  ] https://github.com/Jibo-Revival-Group/JiboAutoMod or Let us know by making a issue there! "
        )

    specific_module_path = f"Platform.{os_name}.{os_version}"
    try:
        platform_module = importlib.import_module(specific_module_path)
        print(f"[ 󰏖 ] Loaded denfinitions for {os_name} thats build for {os_version}!")
        return platform_module
    except ModuleNotFoundError as error:
        if error.name == specific_module_path:
            default_module_path = f"Platform.{os_name}.Default"
            try:
                platform_module = importlib.import_module(default_module_path)
                print(
                    f"[  ] Found generic denfinitios for {os_name}, should work for {os_version}"
                )
                return platform_module
            except ModuleNotFoundError:
                print(
                    f"[  ] (@load_platform_module) Critical Error : Failed to find Default denfinitions for {os_name}, maybe re-pull source?"
                )
                sys.exit(1)
        else:
            raise error


def run_script(script_path: str):
    path = Path(script_path).resolve()
    # Automatically get the parent directory
    run_dir = path.parent
    module_name = path.stem

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {script_path}")

    module = importlib.util.module_from_spec(spec)

    # CRITICAL: exec_module must be wrapped INSIDE the context manager
    # because ShofelExploit.py calls load_platform_module() at top-level load time!
    with execution_environment(run_dir):
        spec.loader.exec_module(module)

        # If ShofelExploit.py also has a main() function:
        if hasattr(module, "main"):
            return module.main()


def rut_menu():
    print("===[ ROBOT UNLOCKING TOOLS ]===")
    print(
        "If ou happen to want to contribute to this section make "
        + Color.BOLD
        + Color.UNDERLINE
        + "sure you make a branch with the /exploits/ prefix"
        + Color.RESET
    )
    print("Also pls RTFM over at ./Docs/AddExploit.md")

    from Exploits.ExploitDictionary import EXPLOITS

    exploits = [
        Choice(title=exploit["name"], value=exploit, description=exploit["description"])
        for exploit in EXPLOITS
    ]

    selected_exploit = questionary.select("Choose an exploit", choices=exploits).ask()

    run_script(selected_exploit["path"])


# ============================================== START <<<<<<<<<<<<<<<<<<<
print("Jibo Modding tool v2 | RELEASE 0.1a")
print("Use nerdfont as a font if youre missing icons")
print("If your distro/os isnt supported you can contribute your own config to: ")
print("https://github.com/Jibo-Revival-Group/JiboAutoMod")
print("Initialising python dependencies...")
check_py_dependencies()

import questionary
from questionary import Choice

toolMode = questionary.select(
    "Select Tool",
    [
        "Robot Unlocking Tools",
        "Robot Manager [WIP]",
        "Jibo Package Manager [WIP]",
        "Jibo Server Tools",
        "Exit",
    ],
).ask()


match toolMode:
    case "Robot Unlocking Tools":
        rut_menu()
    case "Exit":
        sys.exit(0)
    case _:
        print(f"'{toolMode}' is not implemented yet cooming soon!")
