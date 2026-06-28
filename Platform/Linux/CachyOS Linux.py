import os
import subprocess
import sys

# ========== PLATFROM VARS
SHOFEL_DIR = os.path.join(os.getcwd(), "Shofel")
SHOFEL_BINARY = os.path.join(SHOFEL_DIR, "shofel2_t124")



def build_shofel():
    if not os.path.isdir(SHOFEL_DIR):
        print(f"[ 󱄌 ] Error : Shofel directory wasnt found inside {SHOFEL_DIR}")
        return False
    
    print("[  ] Building Shofel2 via Makefile...")
    try:
        subprocess.check_call(["make"], cwd=SHOFEL_DIR)
        print("[   ] Shofel2 Built!, proceeding")
        return True
    except subprocess.CalledProcessError:
        print(f"[  ] (@Linux/Cachy:dH*jd) Critical Error: 'Make' failed without trying to compile Shofel, exiting..")
        sys.exit(1)
    except FileNotFound:
        print(f"[  ] (@Linux/Cachy:eH*jd) Critical Error: 'Make' wasnt found check 'base-devel' packages are installed, exiting..")
        sys.exit(1)

       




def check_shofel_built():
    
    print("[  󰥨 ] Checking if Shofel2 is build....")

    if os.path.isfile(SHOFEL_BINARY) and os.access(SHOFEL_BINARY, os.X_OK):
        print("[   ] Shofel2 installed!, proceeding")
        return True
    else:
        print("[ 󱈾 ] Shofel not built")
        return False

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
