import importlib
import subprocess
import platform
import sys
from packaging.requirements import Requirement
from importlib.metadata import requires, version, PackageNotFoundError

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
            print(f"[  ] Missing packages: {', '.join(missing_packages)}")
            print("[  ] Installing pkgs...")
            
            cmd = [sys.executable, "-m", "pip", "install", "-r", requirements_file]
            
            # If on Linux/macOS and NOT in a virtual environment, append the bypass flag
            # (In Windows, or inside a venv, this isn't needed)
            in_venv = sys.prefix != sys.base_prefix
            if sys.platform != "win32" and not in_venv:
                cmd.append("--break-system-packages")
                
            subprocess.check_call(cmd)
            
            print("\n" + "="*50)
            print("[ 󱝎 ] All missing dependencies have been successfully installed!")
            print("[ 󱄌 ] Please RESTART the application now.")
            print("="*50 + "\n")
            sys.exit(0)
            
    except FileNotFoundError:
        print(f"[  ] Error: '{requirements_file}' not found.")
        sys.exit(1)





def rut_menu():
    print("===[ ROBOT UNLOCKING TOOLS ]===")
    print("If ou happen to want to contribute to this section make" + Color.BOLD + Color.UNDERLINE+ " sure you make a branch with the /exploits/ prefix" + Color.RESET)






# ============================================== START <<<<<<<<<<<<<<<<<<<
print("Jibo Modding tool v2 | RELEASE 0.1a")
print("Use nerdfont as a font if youre missing icons")
print("If your distro/os isnt supported you can contribute your own config to: ")
print("https://github.com/Jibo-Revival-Group/JiboAutoMod")
print("Initialising python dependencies...")
check_py_dependencies()

import questionary
toolMode = questionary.select("Select Tool", ["Robot Unlocking Tools","Robot Manager [WIP]","Jibo Package Manager [WIP]","Jibo Server Tools","Exit"],qmark="",pointer="").ask()




match toolMode:
    case "Robot Unlocking Tools":
       rut_menu() 
