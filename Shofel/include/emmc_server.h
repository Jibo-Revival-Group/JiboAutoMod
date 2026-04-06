#ifndef _EMMC_SERVER_H_
#define _EMMC_SERVER_H_

#if __arm__
    typedef u32 uint32_t;
#else
    #include <stdint.h>
#endif

/* eMMC server protocol commands */
#define EMMC_CMD_READ           0x01
#define EMMC_CMD_WRITE          0x02
#define EMMC_CMD_STATUS         0x03
#define EMMC_CMD_READ_EXT_CSD   0x04  /* Read 512-byte EXT_CSD register for chip health */
#define EMMC_CMD_ERASE          0x05  /* Erase a range of sectors (forces reallocation) */
#define EMMC_CMD_EXIT           0xFF

/* Boot partition encoding for EMMC_CMD_READ / EMMC_CMD_WRITE start_sector:
 *   0x00000000 | sector  -> User Data Area  (normal)
 *   0x80000000 | sector  -> Boot Partition 1 (boot0)
 *   0xC0000000 | sector  -> Boot Partition 2 (boot1)
 * The payload switches the eMMC partition, performs the I/O, then restores UDA.
 * Use sector=0 and num_sectors=boot_size_sectors to dump an entire boot partition.
 */
#define EMMC_BOOT0_BASE  0x80000000U
#define EMMC_BOOT1_BASE  0xC0000000U

/* Transfer chunk sizes: sectors per USB transfer.
 * Both read and write now use 8-sector (4 KB) chunks via CMD18/CMD25.
 */
#define EMMC_CHUNK_SECTORS_READ    8
#define EMMC_CHUNK_SECTORS_WRITE   8
#define EMMC_CHUNK_SECTORS         8
#define EMMC_SECTOR_SIZE           512
#define EMMC_CHUNK_BYTES           (EMMC_CHUNK_SECTORS * EMMC_SECTOR_SIZE)

/* Command structure sent from PC to payload */
struct emmc_cmd_s {
    uint32_t op;
    uint32_t start_sector;
    uint32_t num_sectors;
};

#endif
