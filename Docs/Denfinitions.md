 - - - 
 
    # DOCS FOR RELEASE 0.1a

 - - -

| Name       | Type       | Data     | Data1      | Descr                 |
| ---------- | ---------- | -------- | ---------- | --------------------- |
| OS_NAME    | str        | Linux    |            | fetch os name         |
| OS_VERSION | str        | Cachy OS |            | fetch os version name |
| PLATFORM   | str tuplet | OS_NAME  | OS_VERSION | name & version tuplet |


# Function Denfinitions
- - -

## `load_msg()`


| Arguments | Returns | Descr                                             |
| --------- | ------- | ------------------------------------------------- |
| 0         | 1       | Prints a message uppon load just to test it loads |
Implementation examples:

```python

def load_msg():
    print("Generic denfinitions (>>>  Debian based  <<<)")

```

## `check_build_dependencies()`


| Arguments | Returns   | Descr                                                                                                |
| --------- | --------- | ---------------------------------------------------------------------------------------------------- |
| 0         | str array | Checks for missing packages in the current environment , if any missing it must pack them in a array |
Implementation examples:

```python

def check_build_dependencies():
    required_packages = ["base-devel", "libusb" , "git" , "python" , "python-pip"]
    missing_packages = []
    missing_packages.append(pkg1)
    missing_packages.append("libusb") # <---- Grab missing pkgs in some way
    print(f"[󰥨  ] Missing packages : {missing_packages} , they will get installed automatically!")

    return missing_packages
```

Example return `["pkg1","libusb"]`



## `install_build_dependencies(strArray)`

This must take a array of dependencies and install them ... **it must also do a quick check in case the system already satisfies requirements!**, i was gonna make it optional , but different systems might behave differently , so we pass it on to whatever the maintainer wants to do!

| Arguments | Returns | Descr                                                      |
| --------- | ------- | ---------------------------------------------------------- |
| strArray  | bool    | Takes the mising dependencies and attempts to install them |
Implementation examples:

```python

def install_build_dependencies(missing_pacakges)
	# MANDATORY!!!! , check if already satisfied
	if not missing_packages:
        print("[   ] All pendencies installed!, proceeding")
        return True
    print(f"[󰥨  ] Missing system packages : {missing_packages}")
    
    try:
	    install_method()
	    return True # <--- Only if install succeded
	except error:
		handle_error(error)
		return False # <--- Only if install failed

```


## `check_shofel_built()`


| Arguments | Returns | Descr                                                                        |
| --------- | ------- | ---------------------------------------------------------------------------- |
| 0         | bool    | Checks the Shofel directory for a binary and returns true or false if exists |
|           |         |                                                                              |
Implementation examples:

```python

def check_shofel_built():
    
    print("[  󰥨 ] Checking if Shofel2 is build....")

    if os.path.isfile(SHOFEL_BINARY) and os.access(SHOFEL_BINARY, os.X_OK):
        print("[   ] Shofel2 installed!, proceeding")
        return True
    else:
        print("[ 󱈾 ] Shofel not built")
        return False

```


## `build_shofel()`

the command that builds shofel (You must specify how to fetch the shofel directories!!)


| Arguments | Returns | Descr                                                                        |
| --------- | ------- | ---------------------------------------------------------------------------- |
| 0         | bool    | Checks the Shofel directory for a binary and returns true or false if exists |
|           |         |                                                                              |
Implementation examples:

```python

def build_shofel():
    print("[  ] Building Shofel2 via Makefile...")
    try:
        subprocess.check_call(["make"], cwd=SHOFEL_DIR) # <-- Build the thing
        print("[   ] Shofel2 Built!, proceeding")
        return True
    except subprocess.CalledProcessError:  #<--- Handle errors
	    return False #<---- Return False or exit depending on the error!
    except FileNotFound:
        sys.exit(1)

```


## `is_jibo_present()`

the command that scans the USB devices and returns true when it detects the correct device


| Arguments | Returns | Descr                        |
| --------- | ------- | ---------------------------- |
| 0         | bool    | Checks if jibo is plugged in |
|           |         |                              |
Implementation examples:

```python

def is_jibo_present():
    target_id = "0955:7740"
    try:
        result = usb.get_jibo()

        if target_id in result.stdout:
            print("[   ] Jibo APX Detected!")
            return True #<-- return True when found!
        print("[   ] No device, Make sure youre connected to USB and in RCM mode!")
        return False

    except(subprocess.CalledProcessError, FileNotFound):
        sys.exit(1) #<--- handle errors



```

## `begin_dump(StartSector, EndSector)`

the command that executes shofel and places the dump in `dump/jibo_dump.bin`


| Arguments | Returns                  | Descr                      | StartSector  | EndSector          |
| --------- | ------------------------ | -------------------------- | ------------ | ------------------ |
| 2         | bool                     | Runs EMMC_READ With shofel | HexValue     | HexValue           |
|           | true when dump complete! |                            | default: 0x0 | default: 0x1D60000 |
Implementation examples:

```python

def begin_dump(StartSector=0x0, EndSector=0x1D60000 ):
    dump_dir = "dump"
    try:
        if not os.path.exists(dump_dir):
            os.makedirs(dump_dir) #<--- create a dump dir if not existing already
    except Exception as error:
        sys.exit(1)#<--- remember to catch exceptions!!!


    if not os.pth.isdir(SHOFEL_DIR):
         sys.exit(1)
    try:
        dumping_from_jibo(StartSector,EndSector) #<-- do the actuall dump
        return True
    except subprocess.CalledProcessError: #<--- Dont forget these exceptions!
        print("[ 󱄌 ] Error : Shofel read operation was interrupted.")
        return False
    except FileNotFound:
        return False



```


## `extract_var_partition(image_path, output_path, start_sector, end_sector, sector_size)`

the command that executes shofel and places the dump in `dump/jibo_dump.bin`


| Arguments | Returns                                           | StartSector  | EndSector          | image_path         | output_path       | sector_size |
| --------- | ------------------------------------------------- | ------------ | ------------------ | ------------------ | ----------------- | ----------- |
| 5         | bool                                              | HexValue     | HexValue           | String path        | String Path       | Int         |
|           | true when var partition split AND saved complete! | default: 0x0 | default: 0x1D60000 | dump/jibo_dump.bin | dump/jibo_var.bin | 512         |
Implementation examples:

```python
def extract_var_partition(image_path="../dump/jibo_dump.bin", output_path="../dump/jibo_var.bin", StartSector=8294434,EndSector=9318433,sector_size=512):
    sector_count = (EndSector - StartSector) +x1
    byte_skip = StartSector * sector_size
    byte_count = sector_count * sector_size
    try:
        with open(image_path, "rb") as in_file:
            in_file.seek(byte_skip)
            partition_data = in_file.read(byte_count) #extract to ram (not best approach btw)
        with open(output_path, "wb") as out_file:
            out_file.write(partition_data) #write from ram to file



    except FileNotFound:
        sys.exit(1) #handle exceptions
    except Exception as e:
        print(f"[  ] Critical error : Unhandled Exception by @extract_var_partition | {e} , quitting... ") #All of them !!!

```
