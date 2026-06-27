import platform
import sys
import subprocess
from importlib.metadata import requires, version, PackageNotFoundError
from packaging.requirements import Requirement


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



print("Jibo Modding tool v2")
print("Use nerdfont as a font if youre missing icons")
print("If your distro/os isnt supported you can contribute your own config to: ")
print("https://github.com/Jibo-Revival-Group/JiboAutoMod")
print("Initialising python dependencies...")



check_py_dependencies()
PLATFORM = get_os()



print("Detected os : ", PLATFORM[0])
print("")
