import importlib
import subprocess
import sys
import os
import importlib.util
from pathlib import Path
from packaging.requirements import Requirement
from importlib.metadata import requires, version, PackageNotFoundError
from contextlib import contextmanager

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







def run_script(script_path: str):
    path = Path(script_path).resolve()
    # Automatically get the parent directory (e.g., /home/eva/Documents/JiboAutoMod/Exploits)
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
    print("If you happen to want to contribute to this section make " + Color.BOLD + Color.UNDERLINE+ "sure you make a branch with the /exploits/ prefix" + Color.RESET)
    print("Also pls RTFM over at ./Docs/AddExploit.md")
    
    from Exploits.ExploitDictionary import EXPLOITS

    exploits = [
            Choice(title=f"{exploit['name']} - {exploit['description']}", value=exploit) for exploit in EXPLOITS
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
toolMode = questionary.select("Select Tool", ["Robot Unlocking Tools","Robot Manager [WIP]","Jibo Package Manager [WIP]","Jibo Server Tools","Exit"],qmark="",pointer="").ask()




match toolMode:
    case "Robot Unlocking Tools":
       rut_menu() 
