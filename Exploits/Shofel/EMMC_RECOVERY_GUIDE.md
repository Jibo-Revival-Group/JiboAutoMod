# eMMC Recovery Guide: Using ERASE and EXT_CSD Commands

## Problem
The previous write optimization attempts corrupted certain eMMC sectors, making them inaccessible for reads. The eMMC controller has marked these sectors as "bad" and won't reallocate them unless explicitly told the data is no longer needed.

## Solution: Force Block Reallocation
The eMMC specification includes **ERASE** commands that tell the controller "you can discard/reallocate this data." This forces the controller to:
1. Mark the bad blocks for reclamation
2. Reallocate replacements from the spare block pool
3. Allow read/write operations on those sectors again

## New Commands

### 1. Read EXT_CSD Register (Chip Health Check)
```bash
./shofel2_t124 EMMC_READ_EXT_CSD ext_csd.bin
```

**What it does:**
- Reads the 512-byte Extended CSD register
- Contains device health info, life time estimates, and configuration
- Helps diagnose eMMC issues

**Key fields to inspect (byte positions):**
- **Bytes 268-269:** Device Life Time Estimation (A / B) - indicates wear/degradation
- **Bytes 271-274:** Pre-EOL Information - predicts remaining device life
- **Bytes 160-161:** Number of correctly programmed sectors
- **Bytes 2-4:** CSD structure version and device type info

**Example output:**
```
EXT_CSD saved to: ext_csd.bin
```

You can then examine specific bytes using:
```bash
xxd -g 4 ext_csd.bin | head -20   # View first 512 bytes
hexdump -C ext_csd.bin | grep "000" | head -20
```

### 2. Erase Corrupted Sector Range (Force Reallocation)
```bash
./shofel2_t124 EMMC_ERASE start_sector end_sector
```

**What it does:**
- Sends eMMC ERASE_GROUP_START (CMD35)
- Sends eMMC ERASE_GROUP_END (CMD36)
- Sends eMMC ERASE (CMD38) - actual erase operation
- Tells controller those sectors are expendable and can be reallocated

**Example: Erase sectors 0x10000 to 0x20000**
```bash
./shofel2_t124 EMMC_ERASE 0x10000 0x20000
```

Expected output:
```
Erasing sectors 65536 (0x10000) to 131072 (0x20000) - forcing reallocation...
Erase complete. Sectors have been marked as reallocatable.
```

## Recovery Workflow

### Step 1: Check Device Health
First, read the EXT_CSD register to understand the device state:
```bash
./shofel2_t124 EMMC_READ_EXT_CSD health_check.bin
```

### Step 2: Identify Corrupted Range
From your test boot log, determine which sectors are problematic:
- Try reading from sectors in steps (each 4KB or 1 sector)
- Note where reads start failing
- Find the exact corruption boundary

**Example: Binary search for corruption boundary**
```bash
./shofel2_t124 EMMC_READ 0x10000 0x1000 test1.bin  # Try reading 1MB from 0x10000
./shofel2_t124 EMMC_READ 0x10000 0x100 test2.bin   # Try reading 512KB (smaller batch)
./shofel2_t124 EMMC_READ 0x10000 0x10 test3.bin    # Try reading 32KB
```

If any read fails, narrow down further.

### Step 3: Erase Corrupted Sectors
Once you've identified the corrupted range (e.g., sectors 0x10000-0x20000):
```bash
./shofel2_t124 EMMC_ERASE 0x10000 0x20000
```

This tells the eMMC controller:
- "I'm done with these sectors"
- "You can reallocate the physical blocks"
- "Bad sectors can be replaced from spare pool"

### Step 4: Verify Recovery
After erasing, try reading those sectors again:
```bash
./shofel2_t124 EMMC_READ 0x10000 0x1000 verify.bin
```

If successful:
- Sectors are now readable
- Data will be zeros (sector was erased)
- Device has reallocated replacement blocks internally

## Important Notes

### ⚠️ ERASE IS DESTRUCTIVE
- **All data in the specified range will be lost**
- The erase operation cannot be undone
- Only erase sectors you've confirmed are corrupted
- Always back up critical data first

### 📊 eMMC Specifications from Gemini
The ERASE approach works because:
1. **Modern eMMC includes bad block management**: Devices have spare blocks reserved for reallocation
2. **ERASE signals intent to discard**: CMD38 tells the controller "this data is disposable"
3. **Controller reallocates on next write**: Once freed, sectors can be reassigned to spare blocks
4. **Health tracking improves**: EXT_CSD Device Life Time Estimation decreases appropriately

### 🔍 EXT_CSD Register Health Fields
| Byte Offset | Field | Meaning |
|-------------|-------|---------|
| 268-269 | Device Life Time Estimation Type A | 0x00=normal, 0x01=warning, 0x02=critical |
| 269-270 | Device Life Time Estimation Type B | Similar to Type A |
| 271 | Pre-EOL Information | 0x00=normal, 0x01=warning, 0x02=urgent |
| 272-275 | Number of Correctly Programmed Sectors | Tracks write reliability |

### 💾 Data Preservation
After ERASE operation:
- Erased sectors become all-zeros
- You can write new data afterward
- Physical blocks are reallocated internally by controller
- Read operations will show 0x00 bytes in erased sectors

## Troubleshooting

### If ERASE fails (status 0xDEAD0000 | error_code)
Common error codes:
- **-1**: Device not ready (try again)
- **-2 to -7**: Command execution errors

**Retry with:**
1. Fresh device power cycle
2. Smaller erase range (try 256 sectors at a time)
3. Check that sectors are actually accessible first

### If reads still fail after ERASE
This indicates:
1. Sectors were physically damaged (controller couldn't reallocate)
2. eMMC device is failing (see EXT_CSD health status)
3. Multiple failed blocks (beyond spare pool size)

**Next steps:**
- Read full EXT_CSD register to check Device Life Time Estimation
- Attempt partial reads from adjacent sectors
- Consider device hardware failure

### If eMMC is permanently failing
Signs:
- EXT_CSD Device Life Time shows "critical" (0x02)
- Pre-EOL Information shows "urgent" (0x02)
- ERASE commands timeout
- Multiple random sectors becoming unreadable

**Action:** The eMMC device is reaching end-of-life. Plan for device replacement.

## Examples

### Example 1: Recover Sectors 0x100000-0x200000
```bash
# 1. Check health first
./shofel2_t124 EMMC_READ_EXT_CSD health.bin

# 2. Erase the corrupted range
./shofel2_t124 EMMC_ERASE 0x100000 0x200000

# 3. Verify recovery
./shofel2_t124 EMMC_READ 0x100000 0x1000 verify.bin
```

### Example 2: Gradual Corruption Discovery
```bash
# Start with small read to confirm the sector is accessible
./shofel2_t124 EMMC_READ 0x50000 0x1 test_1sector.bin

# Try larger range
./shofel2_t124 EMMC_READ 0x50000 0x100 test_256sectors.bin

# If failure, binary search...
./shofel2_t124 EMMC_READ 0x50000 0x80 test_half.bin
```

## Implementation Details

### CMD35: ERASE_GROUP_START
- Sets the starting address for the erase operation
- Argument: start_sector (32-bit address)
- Response: R1 (standard response)

### CMD36: ERASE_GROUP_END
- Sets the ending address for the erase operation
- Argument: end_sector (32-bit address)
- Response: R1 (standard response)

### CMD38: ERASE
- Performs the actual erase on all sectors from START to END
- Argument: ignored (0x00)
- Response: R1b (with busy signal - can take several seconds)
- Timeout: 5 seconds (extended, as erase is slow operation)

The implementation in [emmc_server.c](payloads/emmc_server.c) sends all three commands in sequence, with proper error checking and timeouts at each step.

## References
- eMMC Specification v4.5+ (commands 35, 36, 38)
- Gemini suggestions: "Force Erase Trick" and EXT_CSD health monitoring
- Related: Block reallocation is standard practice in SSDs, eMMC devices, and SD cards with wear leveling

## Quick Reference
```bash
# Diagnostics
./shofel2_t124 EMMC_STATUS                    # Check controller state
./shofel2_t124 EMMC_READ_EXT_CSD ext_csd.bin  # Check chip health

# Recovery
./shofel2_t124 EMMC_ERASE start end            # Force reallocation
./shofel2_t124 EMMC_READ start count out.bin   # Verify sectors

# Full dump (after recovery)
./shofel2_t124 EMMC_READ 0 0x1D60000 full_dump_recovered.bin

```

yes ai made this , yes i checked , its correct
