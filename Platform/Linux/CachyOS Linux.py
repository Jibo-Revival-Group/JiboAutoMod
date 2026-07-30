import os
import subprocess
import sys

# ========== PLATFROM VARS
SHOFEL_DIR = os.path.join(os.getcwd(), "Shofel")
SHOFEL_BINARY = os.path.join(SHOFEL_DIR, "shofel2_t124")

def extract_var_partition(image_path="./dump/jibo_dump.bin", output_path="./dump/jibo_var.bin", StartSector=8294434,EndSector=9318433,sector_size=512):
    sector_count = (EndSector - StartSector) + 1

    byte_skip = StartSector * sector_size
    byte_count = sector_count * sector_size

    print("[󰥨  ] Calculating offsets...")
    print(f"[󰥨  ] Skipping... {StartSector} sectors ({byte_skip} bytes)")
    print(f"[󰥨  ] Reading... {sector_count} sectors ({byte_count} bytes)")

    # Convert to absolute paths
    abs_image_path = os.path.abspath(image_path)
    abs_output_path = os.path.abspath(output_path)

    try:
        with open(abs_image_path, "rb") as in_file:
            in_file.seek(byte_skip)
            print(f"[  󰥥] Extracting partition to {output_path}")

            partition_data = in_file.read(byte_count)
        with open(abs_output_path, "wb") as out_file:
            out_file.write(partition_data)

        print("[ & ] Success! Partition extracted!")

    except FileNotFound:
        print(f"[ 󱄌 ] Error : dump wasnt found inside {image_path}, exiting...")
        sys.exit(1)
    except Exception as e:
        print(f"[  ] Critical error : Unhandled Exception by @extract_var_partition | {e} , quitting... ")


def dump_var_partition_direct(output_path="./dump/jibo_var.bin", StartSector=8294434, EndSector=9318433):
    sector_count = (EndSector - StartSector) + 1
    
    print(f"[󰥨  ] Dumping var partition directly (sectors {StartSector} to {EndSector})")
    print(f"[󰥨  ] Total sectors: {sector_count}")
    

    abs_output_path = os.path.abspath(output_path)
    
    cmd = ["sudo", "./shofel2_t124", "EMMC_READ", hex(StartSector), hex(sector_count), abs_output_path]
    print(f"[󰥨  ] Command: {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd, cwd=SHOFEL_DIR)
        print("\n" + "="*50)
        print(f"[   ] Var partition dump complete!")
        print(f"[   ] Saved to: {output_path}")
        print("\n" + "="*50)
        return True
    except subprocess.CalledProcessError:
        print("[ 󱄌 ] Error: Var partition dump failed.")
        return False


def compute_binary_diff(original_path, modified_path, diff_output_path):
    print(f"[󰥨  ] Computing binary diff between original and modified...")
    
    # Convert to absolute paths
    abs_original_path = os.path.abspath(original_path)
    abs_modified_path = os.path.abspath(modified_path)
    abs_diff_output_path = os.path.abspath(diff_output_path)
    
    try:
        with open(abs_original_path, "rb") as orig_file, open(abs_modified_path, "rb") as mod_file:
            orig_data = orig_file.read()
            mod_data = mod_file.read()
        
        if len(orig_data) != len(mod_data):
            print(f"[ 󱄌 ] Warning: File sizes differ (original: {len(orig_data)}, modified: {len(mod_data)})")
            min_len = min(len(orig_data), len(mod_data))
        else:
            min_len = len(orig_data)
        
        # Find differing regions
        diff_regions = []
        in_diff = False
        diff_start = 0
        diff_data = bytearray()
        
        for i in range(min_len):
            if orig_data[i] != mod_data[i]:
                if not in_diff:
                    in_diff = True
                    diff_start = i
                    diff_data = bytearray()
                diff_data.append(mod_data[i])
            else:
                if in_diff:
                    in_diff = False
                    diff_regions.append((diff_start, bytes(diff_data)))
        
        # Handle trailing diff
        if in_diff:
            diff_regions.append((diff_start, bytes(diff_data)))
        
        # Calculate total diff size
        total_diff_bytes = sum(len(data) for _, data in diff_regions)
        
        print(f"[   ] Found {len(diff_regions)} differing region(s)")
        print(f"[   ] Total bytes to write: {total_diff_bytes} (vs {min_len} total)")
        
        with open(abs_diff_output_path, "wb") as diff_file:
            for offset, data in diff_regions:
                diff_file.write(offset.to_bytes(4, 'little'))
                diff_file.write(len(data).to_bytes(4, 'little'))
                diff_file.write(data)
        
        print(f"[   ] Diff saved to: {diff_output_path}")
        return diff_regions, total_diff_bytes
        
    except Exception as e:
        print(f"[  ] Critical error computing diff: {e}")
        return None, 0


def write_var_partition_to_device(partition_path, StartSector=8294434, EndSector=9318433):
    """Write entire var partition back to device in one operation"""
    sector_count = (EndSector - StartSector) + 1
    
    print(f"[󰥨  ] Writing var partition back to device (sectors {StartSector} to {EndSector})")
    print(f"[󰥨  ] Total sectors: {sector_count}")
    
    # Convert to absolute path
    abs_partition_path = os.path.abspath(partition_path)
    
    cmd = ["sudo", "./shofel2_t124", "EMMC_WRITE", hex(StartSector), abs_partition_path]
    
    try:
        subprocess.check_call(cmd, cwd=SHOFEL_DIR)
        print("\n" + "="*50)
        print(f"[   ] Var partition write complete!")
        print("\n" + "="*50)
        return True
    except subprocess.CalledProcessError:
        print("[ 󱄌 ] Error: Var partition write failed.")
        return False 


def begin_dump(StartSector=0x0, EndSector=0x1D60000 ):
    dump_dir = "dump"
    try:
        if not os.path.exists(dump_dir):
            os.makedirs(dump_dir)
            print(f"[   ] Created directory {dump_dir}!")
        else:
            print(f"[   ] Directory {dump_dir} already exists!")
    except Exception as error:
        print(f"[  ] Could not create {dump_dir}!, exiting...")
        sys.exit(1)


    if not os.path.isdir(SHOFEL_DIR):
         print(f"[ 󱄌 ] Error : Shofel directory wasnt found inside {SHOFEL_DIR}, exiting...")
         sys.exit(1)
    print(f"[  󰥥] Starting Dump using Shofel2")
    
    cmd = [ "sudo" , "./shofel2_t124" , "EMMC_READ" , str(StartSector) , str(EndSector) , "../dump/jibo_dump.bin"]

    try:
        subprocess.check_call(cmd, cwd=SHOFEL_DIR)
        print("\n" + "="*50)
        print(f"[   ] EMMC Dump complete!")
        print(f"[   ] EMMC Dump saved under: dump/jibo_dump.bin")
        print("\n" + "="*50)
        return True
    except subprocess.CalledProcessError:
        print("[ 󱄌 ] Error : Shofel read operation was interrupted.")
        return False
    except FileNotFound:
        print("[ 󱄌 ] Error : Shofel2 wasnt found in the Shofel directory, did you build?.")
        return False



        





def is_jibo_present():
    target_id = "0955:7740"
    try:
        result = subprocess.run(["lsusb"], capture_output=True, text=True, check=True)

        if target_id in result.stdout:
            print("[   ] Jibo APX Detected!")
            return True
        print("[   ] No device, Make sure youre connected to USB and in RCM mode!")
        return False

    except(subprocess.CalledProcessError, FileNotFound):
        print(f"[  ] (@Linux/Cachy:mH*jd) Critical Error: Failed to run lsusb, check usbutils are installed exiting...")
        sys.exit(1)








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

def patchDevMode(partition_path, target_json='{"mode":"int-developer"}'):
   temp_file = os.path.abspath("temp_mode.json")
   abs_partition_path = os.path.abspath(partition_path)
   internal_path = "/jibo/mode.json"
    
    # create the JSON locally
   with open(temp_file, "w") as f:
       f.write(target_json)
       
   try:
       print(f"[+] Removing old {internal_path} inside partition...")
       # debugfs -w (write-mode) -R (run command)
       subprocess.run([
           "debugfs", "-w", 
           "-R", f"rm {internal_path}", 
           abs_partition_path
       ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
       
       print(f"[+] Writing new {internal_path} and updating metadata...")
       result = subprocess.run([
           "debugfs", "-w", 
           "-R", f"write {temp_file} {internal_path}", 
           abs_partition_path
       ], capture_output=True, text=True)
       
       if result.returncode == 0:
           print("[+] Success! mode.json updated successfully.")
           return True 
       else:
           print(f"[-] Error writing file: {result.stderr}")
           return False
           
   finally:
       #delete the local temp file
       if os.path.exists(temp_file):
           os.remove(temp_file)



def dummy():
    print("Do so:mething")
