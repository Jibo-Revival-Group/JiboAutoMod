# Function Denfinitions!

Below is a list of the functions needed to be implemented for a platform script to function correctly
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
