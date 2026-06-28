import os
import platform
import sys
import subprocess
import importlib
from packaging.requirements import Requirement
from importlib.metadata import requires, version, PackageNotFoundError

OS_NAME = "NOS"
OS_VERSION = "NOVER"
PLATFORM = (OS_NAME, OS_VERSION)





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
    os_name , os_version = PLATFORM


    os_dir = os.path.join("Platform",os_name)
    if not os.path.isdir(os_dir):
        print(f"[  ] (@load_platform_module) Critical Error: Operating System: {os_name} is not supported yet")
        print(f"[  ] You can be the first one to contribute for {os_name} {os_version}! , Create a PR over at: ")
        print("[  ] https://github.com/Jibo-Revival-Group/JiboAutoMod or Let us know by making a issue there! ")

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
                print(f"[  ] Found generic denfinitios for {os_name}, should work for {os_version}")
                return platform_module
            except ModuleNotFoundError:
                print(f"[  ] (@load_platform_module) Critical Error : Failed to find Default denfinitions for {os_name}, maybe re-pull source?")
                sys.exit(1)
        else:
            raise error


print("Jibo Modding tool v2")
print("Use nerdfont as a font if youre missing icons")
print("If your distro/os isnt supported you can contribute your own config to: ")
print("https://github.com/Jibo-Revival-Group/JiboAutoMod")
print("Initialising python dependencies...")



check_py_dependencies()
PLATFORM = get_os()



print("[  ] Detected os : ", PLATFORM[0])
print("[  ] Checking / Generating build enviroment")


tool = load_platform_module(PLATFORM)

tool.load_msg()
deps = tool.check_build_dependencies()
tool.install_build_dependencies(deps)









