import subprocess
import sys


def install_build_dependencies(missing_packages):
    if not missing_packages:
        print("[   ] All pendencies installed!, proceeding")
        return True
    print(f"[󰥨  ] Missing system packages : {missing_packages}")
    print("[  ] Launching pacman to detch dependencies...     (root might be required)")

    cmd = ["sudo", "pacman" , "-S" , "--needed"] + missing_packages

    try:
        subprocess.check_call(cmd)
        print("[   ] Build dependencies installed!")
        return True
    except subprocess.CalledProcessError:
        print("[ 󱄌 ] Error : Pacman failed to install system dependencies")
        return False


def check_build_dependencies():
    required_packages = ["base-devel", "libusb" , "git" , "python" , "python-pip"]
    missing_packages = []

    print("[  󰥨 ] Checking enviroment build tools....")
    
    for pkg in required_packages:
        result = subprocess.run(
                ["pacman", "-Qq", pkg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
                )
        if result.returncode != 0:
            missing_packages.append(pkg)
            print(f"[󰥨  ] Found missing package : {pkg} , it will get installed automatically later!")

    return missing_packages


def load_msg():
    print("Cachy OS denfinitions!!")
    print(">>>   Arch btw based!   <<<")

def dummy():
    print("Do something")
