# Jibo Auto-Mod - Shofel2 Makefile
# Supports: Linux, macOS, Windows (MSYS2/MinGW)

# --------- Platform Detection ---------

UNAME_S := $(shell uname -s 2>/dev/null || echo Windows)
UNAME_M := $(shell uname -m 2>/dev/null || echo x86_64)

ifeq ($(UNAME_S),Linux)
    PLATFORM := linux
    EXE_EXT :=
    LIBUSB_CFLAGS := $(shell pkg-config --cflags libusb-1.0 2>/dev/null || echo -I/usr/include/libusb-1.0)
    LIBUSB_LIBS := $(shell pkg-config --libs libusb-1.0 2>/dev/null || echo -lusb-1.0)
else ifeq ($(UNAME_S),Darwin)
    PLATFORM := macos
    EXE_EXT :=
    LIBUSB_CFLAGS := $(shell pkg-config --cflags libusb-1.0 2>/dev/null || echo -I/usr/local/include/libusb-1.0)
    LIBUSB_LIBS := $(shell pkg-config --libs libusb-1.0 2>/dev/null || echo -L/usr/local/lib -lusb-1.0)
else ifneq (,$(findstring MINGW,$(UNAME_S)))
    PLATFORM := windows
    EXE_EXT := .exe
    LIBUSB_CFLAGS := $(shell pkg-config --cflags libusb-1.0 2>/dev/null || echo -I/mingw64/include/libusb-1.0)
    LIBUSB_LIBS := $(shell pkg-config --libs libusb-1.0 2>/dev/null || echo -L/mingw64/lib -lusb-1.0)
else ifneq (,$(findstring MSYS,$(UNAME_S)))
    PLATFORM := windows
    EXE_EXT := .exe
    LIBUSB_CFLAGS := $(shell pkg-config --cflags libusb-1.0 2>/dev/null || echo -I/mingw64/include/libusb-1.0)
    LIBUSB_LIBS := $(shell pkg-config --libs libusb-1.0 2>/dev/null || echo -L/mingw64/lib -lusb-1.0)
else
    # Assume Windows if detection fails
    PLATFORM := windows
    EXE_EXT := .exe
    LIBUSB_CFLAGS := -I/mingw64/include/libusb-1.0
    LIBUSB_LIBS := -L/mingw64/lib -lusb-1.0
endif

$(info Building for: $(PLATFORM) ($(UNAME_S)/$(UNAME_M)))

# --------- Common Flags ---------

CFLAGS := -Wall -Werror -I include -MMD

BIN_FILES = reset_example.bin jtag_example.bin intermezzo.bin boot_bct.bin mem_dumper_usb_server.bin emmc_server.bin

# Check which payloads need to be built (skip existing ones)
EXISTING_BINS := $(wildcard $(BIN_FILES))
MISSING_BINS := $(filter-out $(EXISTING_BINS),$(BIN_FILES))

# Default target: build host tool + any missing payloads
# If all .bin files exist, only build the host tool
ifeq ($(MISSING_BINS),)
all: shofel2_t124$(EXE_EXT)
	@echo "All payload binaries already present, skipping ARM build."
else
all: shofel2_t124$(EXE_EXT) $(MISSING_BINS)
	@echo "Build complete."
endif

# --------- x86/x64 Host Compiler ---------

CC_x86 = gcc
CFLAGS_x86 := $(CFLAGS) $(LIBUSB_CFLAGS)
LDFLAGS_x86 := $(LIBUSB_LIBS)

# shameless copypasta from https://stackoverflow.com/a/2908351/375416
C_FILES_x86:= $(wildcard exploit/*.c)
OBJ_FILES_x86 := $(addprefix build/obj_x86/,$(notdir $(C_FILES_x86:.c=.o)))
-include $(OBJ_FILES_x86:.o=.d)

build/obj_x86/%.o: exploit/%.c
	@mkdir -p build/obj_x86
	$(CC_x86) $(CFLAGS_x86) -c -o $@ $<

shofel2_t124$(EXE_EXT): $(OBJ_FILES_x86)
	$(CC_x86) $(CFLAGS_x86) -o $@ $^ $(LDFLAGS_x86)

# ------------------------


# --------- ARMv4t Thumb (Payload Compiler) ---------

TOOLCHAIN_ARM ?= arm-none-eabi-
CC_ARM = $(TOOLCHAIN_ARM)gcc
AS_ARM = $(TOOLCHAIN_ARM)as
OBJCOPY_ARM = $(TOOLCHAIN_ARM)objcopy

CFLAGS_ARM := -Wall -I include -MMD -march=armv4t -mthumb -Os -ffreestanding \
	-fno-common -fomit-frame-pointer -nostdlib -fno-builtin-printf \
	-fno-asynchronous-unwind-tables -fPIE -fno-builtin -fno-exceptions \
	-Wno-array-bounds -Wno-error \
	-Wl,--no-dynamic-linker,--build-id=none,-T,payloads/payload.ld

# shameless copypasta from https://stackoverflow.com/a/2908351/375416
C_FILES_ARM := $(wildcard payloads/*.c)
OBJ_FILES_ARM := $(addprefix build/obj_arm/,$(notdir $(C_FILES_ARM:.c=.o)))
-include $(OBJ_FILES_ARM:.o=.d)

build/obj_arm/%.o: payloads/%.c
	@mkdir -p build/obj_arm
	$(CC_ARM) $(CFLAGS_ARM) -c -o $@ $<

build/reset_example.elf: build/obj_arm/reset_example.o
	$(CC_ARM) $(CFLAGS_ARM) -o $@ $^ -lgcc

build/jtag_example.elf: build/obj_arm/jtag_example.o
	$(CC_ARM) $(CFLAGS_ARM) -o $@ $^ -lgcc

build/boot_bct.elf: build/obj_arm/boot_bct.o
	$(CC_ARM) $(CFLAGS_ARM) -o $@ $^ -lgcc

build/mem_dumper_usb_server.elf: build/obj_arm/mem_dumper_usb_server.o
	$(CC_ARM) $(CFLAGS_ARM) -o $@ $^ -lgcc

build/emmc_server.elf: build/obj_arm/emmc_server.o
	$(CC_ARM) $(CFLAGS_ARM) -o $@ $^ -lgcc

build/intermezzo.elf: build/obj_arm/intermezzo.o
	$(CC_ARM) $(CFLAGS_ARM) -o $@ $^ -lgcc

%.bin: build/%.elf
	$(OBJCOPY_ARM) -O binary $< $@

# --------- Utility Targets ---------

# Clean host build only (preserves payload .bin files)
clean:
	rm -f $(OBJ_FILES_x86)
	rm -f shofel2_t124 shofel2_t124.exe

# Clean ARM build objects (preserves .bin files)
clean-arm:
	rm -f $(OBJ_FILES_ARM) build/*.elf

# Full clean including all binaries
cleanall: clean clean-arm
	rm -f build/obj_arm/*.d build/obj_x86/*.d
	rm -f $(BIN_FILES)

# Build only the host tool (no ARM payloads)
host-only: shofel2_t124$(EXE_EXT)

# Build only the ARM payloads
payloads-only: $(BIN_FILES)

# Show build info
info:
	@echo "Platform:     $(PLATFORM)"
	@echo "Executable:   shofel2_t124$(EXE_EXT)"
	@echo "LIBUSB_CFLAGS: $(LIBUSB_CFLAGS)"
	@echo "LIBUSB_LIBS:   $(LIBUSB_LIBS)"
	@echo "ARM Toolchain: $(TOOLCHAIN_ARM)"

.PHONY: all clean cleanall host-only payloads-only info

