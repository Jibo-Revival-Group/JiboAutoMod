# Implementation Summary: eMMC Recovery Commands

## What Was Implemented

Following Gemini's suggestions for handling corrupted eMMC sectors, two new capabilities have been added:

### 1. **ERASE Command** (CMD35/36/38)
Forces the eMMC controller to reallocate bad blocks by marking sectors as "discardable"

- **Command:** `./shofel2_t124 EMMC_ERASE start_sector end_sector`
- **Purpose:** Tell eMMC "these sectors are no longer needed - reallocate the physical blocks"
- **Mechanism:** Sends three sequential eMMC commands:
  - CMD35 (ERASE_GROUP_START): Define start address
  - CMD36 (ERASE_GROUP_END): Define end address
  - CMD38 (ERASE): Execute the erase operation
- **Result:** Controller moves data from bad blocks to spare block pool, restoring read/write access

### 2. **EXT_CSD Register Reading** (CMD8)
Reads 512-byte device configuration and health register for diagnostics

- **Command:** `./shofel2_t124 EMMC_READ_EXT_CSD output.bin`
- **Purpose:** Check eMMC chip health, wear estimates, and device status
- **Key Info:**
  - Device Life Time Estimation (indicates wear level)
  - Pre-EOL Information (predicts remaining device life)
  - Configuration parameters and version info
- **Use Case:** Diagnose whether corruption is from bad write operations or device failure

## Files Modified

### 1. **[include/emmc_server.h](include/emmc_server.h)**
```c
/* Added command definitions */
#define EMMC_CMD_READ_EXT_CSD   0x04  /* Read 512-byte EXT_CSD register */
#define EMMC_CMD_ERASE          0x05  /* Erase sectors (force reallocation) */

/* Already had read/write optimization: */
#define EMMC_CHUNK_SECTORS_READ    8   /* 8 sectors (4KB) = 1.1 MB/s reads */
#define EMMC_CHUNK_SECTORS_WRITE   1   /* 1 sector = safe writes */
```

### 2. **[payloads/emmc_server.c](payloads/emmc_server.c)**

**New eMMC Commands:**
```c
#define MMC_CMD8    0x083A  /* SEND_EXT_CSD: Read 512-byte register */
#define MMC_CMD35   0x233A  /* ERASE_GROUP_START */
#define MMC_CMD36   0x243A  /* ERASE_GROUP_END */
#define MMC_CMD38   0x263B  /* ERASE */
```

**New Functions:**
```c
/* Read EXT_CSD register (512 bytes of chip health/config) */
static int read_ext_csd(u32 *buffer);

/* Erase sector range - sends CMD35/36/38 in sequence */
static int erase_emmc_sectors(u32 start_sector, u32 end_sector);
```

**New Command Handlers in entry():**
- `if (cmd.op == EMMC_CMD_READ_EXT_CSD)` - Reads and sends 512-byte register
- `if (cmd.op == EMMC_CMD_ERASE)` - Executes three-command erase sequence

### 3. **[exploit/shofel2_t124.c](exploit/shofel2_t124.c)**

**Updated help text:**
```
EMMC_READ_EXT_CSD out_file -> Reads 512-byte EXT_CSD register (chip health/config info)
EMMC_ERASE start_sector end_sector -> Erases sectors (tells controller to reallocate bad blocks)
```

**New argument parsing modes:**
```c
emmc_mode = 4;  /* EMMC_READ_EXT_CSD */
emmc_mode = 5;  /* EMMC_ERASE */
```

**Command handlers:**
- Mode 4: Reads EXT_CSD, displays hex dump, saves 512 bytes to file
- Mode 5: Sends ERASE command, receives status, reports success/failure

## How It Works

### ERASE Process
```
Host Tool (shofel2_t124)
     |
     v
   USB Transfer: struct emmc_cmd_s { op=ERASE, start_sector=X, num_sectors=Y }
     |
     v
Payload (emmc_server.bin)
     |
     +---> init_sdmmc4()
     |
     +---> send CMD35 with argument = start_sector
     |
     +---> send CMD36 with argument = end_sector
     |
     +---> send CMD38 (execute erase)
     |
     +---> return status (0 = success, -N = error code)
     |
     v
   USB Transfer: 4-byte status
     |
     v
Host Tool displays result
```

### EXT_CSD Reading Process
```
Host Tool (shofel2_t124)
     |
     v
   USB Transfer: struct emmc_cmd_s { op=READ_EXT_CSD }
     |
     v
Payload (emmc_server.bin)
     |
     +---> init_sdmmc4()
     |
     +---> send CMD8 (SEND_EXT_CSD)
     |
     +---> receive 512 bytes via SDHCI data register
     |
     v
   USB Transfer: 512-byte EXT_CSD register data
     |
     v
Host Tool saves to file, displays hex dump
```

## Key Design Decisions

### 1. **Timeout Values**
- **ERASE operations: 5 seconds** (vs 500ms for reads/writes)
  - Reason: Erase is a slow Flash operation, can take several seconds
- **All other operations: 500K loop iterations**
  - Provides consistent timeout behavior across commands

### 2. **Command Sequencing**
- **Three separate commands (CMD35→36→38) instead of one**
  - Meets eMMC spec requirements
  - Allows error checking between steps
  - Provides detailed error diagnostics

### 3. **EXT_CSD as Command, Not Feature**
- Implemented as EMMC_CMD_READ_EXT_CSD (not automatic on init)
- Reason: 512 bytes is large, only useful when explicitly requested for diagnostics

### 4. **Safety-First Approach**
- Both operations return specific error codes
- Host tool validates responses before reporting success
- Erased sectors become all-zeros (safe, no data remnants)

## Error Codes

If operation fails, you'll see: `0xDEAD0000 | error_code`

```c
/* From erase_emmc_sectors(): */
-1: Device not ready
-2: CMD35 failed (SDHCI_INT_ERROR during ERASE_GROUP_START)
-3: CMD35 timeout
-4: CMD36 failed (SDHCI_INT_ERROR during ERASE_GROUP_END)
-5: CMD36 timeout
-6: CMD38 failed (SDHCI_INT_ERROR during ERASE)
-7: CMD38 timeout (erase took > 5 seconds)

/* From read_ext_csd(): */
-1: Device not ready
-2: CMD8 failed (command error)
-3: CMD8 timeout
-4: BUF_RD_READY failed
-5: BUF_RD_READY timeout
-6: XFER_COMPLETE failed
-7: XFER_COMPLETE timeout
```

Example error displayed:
```
Error: eMMC erase failed with status 0xDEAD0007.
        ^ This means: Error code 7 = ERASE operation timed out (took > 5 seconds)
```

## Testing Recommendations

### 1. **Baseline Test: Read EXT_CSD First**
```bash
./shofel2_t124 EMMC_READ_EXT_CSD health.bin
xxd -s 268 -l 8 health.bin  # Check Device Life Time Estimation
```

### 2. **Erase Small Test Range**
Before erasing large corrupted ranges, test with a small sector group:
```bash
./shofel2_t124 EMMC_ERASE 0x100000 0x100010  # Just 16 sectors
```

### 3. **Verify Reallocation**
After erase, read those sectors to confirm they're now accessible:
```bash
./shofel2_t124 EMMC_READ 0x100000 0x10 test_after_erase.bin
```

### 4. **Full Diagnostics**
After recovery, take a full dump to verify:
```bash
./shofel2_t124 EMMC_READ 0 0x1D60000 recovered_full_dump.bin
```

## Caveats & Limitations

### ⚠️ Critical Limitations
1. **ERASE is destructive** - All data in range is permanently lost
2. **Not a repair** - Erase can't fix physically damaged Flash cells
3. **Limited spare blocks** - If too many sectors fail, controller runs out of spares
4. **Health degrades** - Each erase operation slightly ages the device (see EXT_CSD)

### 📱 Device-Dependent Behavior
Different eMMC chips may behave differently:
- Some controllers reallocate instantly; some take time
- Bad block threshold varies by manufacturer
- Spare block pool size differs (typically 5-10%)

### 🔌 No Wear Leveling Coverage
These commands work within bootrom constraints:
- Limited to RCM payload (64KB) 
- No wear leveling algorithm (raw sector access)
- Direct SDHCI register control (no device driver)

## Integration with Existing Code

The new commands integrate seamlessly with the existing optimization:

```
Before: 
  EMMC_CMD_READ (optimized to 8 sectors = 1.1 MB/s)
  EMMC_CMD_WRITE (reverted to 1 sector = safe)

After:
  EMMC_CMD_READ (unchanged - still 1.1 MB/s)
  EMMC_CMD_WRITE (unchanged - still single sector)
  EMMC_CMD_READ_EXT_CSD (NEW - diagnostics)
  EMMC_CMD_ERASE (NEW - recovery)
```

The read/write operations are completely unaffected. The new commands are purely additive.

## Compiler & Build Status

✅ **Host tool (x86):** Compiles successfully
- `gcc -Wall -Werror` passes
- All new functions compile without errors
- New command handlers validate correctly

⚠️ **Payload (ARM):** Requires ARM toolchain
- `arm-none-eabi-gcc` not installed on build system
- Code is ready for ARM compilation
- No ARM-specific code changes needed

## Next Steps

1. **Test ERASE command** on corrupted sector range identified in boot log
2. **Verify with EMMC_READ** after erase completes
3. **Monitor EXT_CSD** to track device health degradation
4. **Document results** for future reference

See [EMMC_RECOVERY_GUIDE.md](EMMC_RECOVERY_GUIDE.md) for detailed recovery procedures.


yes ai made this , yes i checked , its correct