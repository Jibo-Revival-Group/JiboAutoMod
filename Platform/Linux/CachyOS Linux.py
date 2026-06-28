import subprocess
import sys



def check_build_dependencies():
    required_packages = ["base-devel", "libusb" , "git" , "python" , "python-pip"]
    missing_packages = []

    print("[  󰥨 ] Checking enciroment build tools....")
    
    for pkg in required_packages:
        result = subprocess.run(
                ["pacman", "-Qq", pkg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
                )
        if result.returncode != 0:
            missing_packages.append(pkg)
    print(f"[󰥨  ] Missing packages : {missing_packages} , they will get installed automatically!")

    return missing_packages


def load_msg():
    print("Cachy OS denfinitions!!")
    print(">>>   Arch btw based!   <<<")

def dummy():
    print("Do something")
