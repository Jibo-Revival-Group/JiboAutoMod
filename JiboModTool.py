import questionary















# ============================================== START <<<<<<<<<<<<<<<<<<<
print("Jibo Modding tool v2 | RELEASE 0.1a")
print("Use nerdfont as a font if youre missing icons")
print("If your distro/os isnt supported you can contribute your own config to: ")
print("https://github.com/Jibo-Revival-Group/JiboAutoMod")
print("Initialising python dependencies...")



toolMode = questionary.select("Select Tool", ["Robot Unlocking Tools","Robot Manager [WIP]","Jibo Package Manager [WIP]","Jibo Server Tools","Exit"],qmark="",pointer="").ask()


