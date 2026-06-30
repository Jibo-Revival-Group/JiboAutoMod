import platform
import os
import shutil
import sys

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
                print(f"[  ] Found generic denfinitios for {os_name}, should work for {os_version}")
                return platform_module
            except ModuleNotFoundError:
                print(f"[  ] (@load_platform_module) Critical Error : Failed to find Default denfinitions for {os_name}, maybe re-pull source?")
                sys.exit(1)
        else:
            raise error




def ensure_platform_environment(PLATFORM):
    
    if isinstance(PLATFORM, str):
        os_name, os_version = PLATFORM, "Unknown"
    else:
        os_name, os_version = PLATFORM

    os_dir = os_name
    template_src = "template.temp"
    
    if not os.path.exists(template_src):
        print(f"[  ] Status: Cannot scaffold profiles. Template source '{template_src}' is missing!")
        return False

    config_already_existed = True

    if not os.path.isdir(os_dir):
        print(f"[ 󰏖 ] Status: Configuration directory for '{os_name}' does not exist. Creating it...")
        os.makedirs(os_dir, exist_ok=True)
        config_already_existed = False
        
        # Create package init file
        with open(os.path.join(os_dir, "__init__.py"), "w") as f:
            f.write("# Auto-generated package file\n")
            
        # Scaffold Default.py
        default_py_path = os.path.join(os_dir, "Default.py")
        shutil.copy(template_src, default_py_path)
        print(f"[ 󰏖 ] Status: Scaffolded generic fallback at '{default_py_path}'.")
    else:
        print(f"[ 󰴊 ] Status: Found existing OS directory for '{os_name}'.")

    specific_file_name = f"{os_version}.py"
    specific_py_path = os.path.join(os_dir, specific_file_name)
    
    if not os.path.exists(specific_py_path):
        print(f"[  ] Status: Specific profile for '{os_version}' is missing.")
        shutil.copy(template_src, specific_py_path)
        print(f"[ 󰴊 ] Status: Created a fresh customized profile template at '{specific_py_path}'.")
        config_already_existed = False
    else:
        print(f"[ 󰴊 ] Status: Specific profile for '{os_version}' already exists and is ready.")
        
    return config_already_existed



print(">>>> VERSION IS 0.1a")
current_platform = get_os()



ensure_platform_environment(current_platform)







