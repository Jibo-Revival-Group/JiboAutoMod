#ifndef _EMMC_H_
#define _EMMC_H_

/* SDMMC4 base address (eMMC) on Tegra T124 - at 0x700B0600, NOT 0x78000600 */
#define SDMMC4_BASE         0x700B0600
#define SDMMC4_VENDOR_CLK   0x700B0700
#define SDMMC4_VENDOR_MISC  0x700B07C0
#define SDMMC4_REG_SIZE     0x200

/* SDHCI register offsets (from SDMMC4_BASE) */
#define SDHCI_BLOCK_SIZE        0x04
#define SDHCI_ARGUMENT          0x08
#define SDHCI_TRANSFER_MODE     0x0C
#define SDHCI_RESPONSE          0x10
#define SDHCI_BUFFER            0x20
#define SDHCI_PRESENT_STATE     0x24
#define SDHCI_HOST_CONTROL      0x28
#define SDHCI_POWER_CONTROL     0x29
#define SDHCI_CLOCK_CONTROL     0x2C
#define SDHCI_SOFTWARE_RESET    0x2F
#define SDHCI_INT_STATUS        0x30
#define SDHCI_INT_ENABLE        0x34
#define SDHCI_CAPABILITIES      0x40
#define SDHCI_HOST_VERSION      0xFE

/* Vendor register offsets (from SDMMC4_BASE) */
#define SDMMC_VENDOR_CLK_CTRL   0x100   /* 0x700B0700 - Vendor Clock Control */
#define SDMMC_VENDOR_MISC_CTRL  0x120   /* 0x700B0720 - Vendor Misc Control */

/* VENDOR_CLK_CTRL bits */
#define SDMMC_CLK_CTRL_PADPIPE      0x08    /* PADPIPE_CLKEN_OVERRIDE */
#define SDMMC_CLK_CTRL_SPI_MODE     0x04    /* SPI_MODE_CLKEN_OVERRIDE */

/* VENDOR_MISC_CTRL bits */
#define SDMMC_MISC_CTRL_SPEC_300    0x20    /* Enable SDHCI Spec 3.0 mode */

/* Auto-calibration registers (from SDMMC4_BASE) */
#define SDMMC_SDMEMCOMP_PADCTRL 0x1E0   /* 0x700B07E0 - SDMEM comp pad control */
#define SDMMC_AUTO_CAL_CONFIG   0x1E4   /* 0x700B07E4 - Auto-cal configuration */
#define SDMMC_AUTO_CAL_STATUS   0x1EC   /* 0x700B07EC - Auto-cal status */

/* SDMEM_COMP_PADCTRL bits */
#define SDMMC_COMP_PADCTRL_E_INPUT  (1u << 31)  /* Force E_INPUT for calibration */

/* AUTO_CAL_CONFIG bits */
#define SDMMC_AUTO_CAL_START    (1u << 31)  /* Start auto-calibration */
#define SDMMC_AUTO_CAL_ENABLE   (1u << 29)  /* Enable auto-calibration */

/* AUTO_CAL_STATUS bits */
#define SDMMC_AUTO_CAL_ACTIVE   (1u << 31)  /* Auto-calibration in progress */

/* Software Reset bits */
#define SDHCI_RESET_ALL         0x01
#define SDHCI_RESET_CMD         0x02
#define SDHCI_RESET_DAT         0x04

/* PRESENT_STATE bits */
#define SDHCI_CMD_INHIBIT       0x00000001
#define SDHCI_DAT_INHIBIT       0x00000002
#define SDHCI_CARD_INSERTED     0x00010000

/* INT_STATUS bits */
#define SDHCI_INT_CMD_COMPLETE  0x0001
#define SDHCI_INT_XFER_COMPLETE 0x0002
#define SDHCI_INT_BUF_WR_READY  0x0010
#define SDHCI_INT_BUF_RD_READY  0x0020
#define SDHCI_INT_ERROR         0x8000

/*
 * MMC Command register values (16-bit, placed in upper half of 0x0C write).
 * Format: (cmd_index << 8) | (type << 6) | (data_present << 5) |
 *         (idx_check << 4) | (crc_check << 3) | response_type
 * Response types: 0x00=none, 0x01=136-bit(R2), 0x02=48-bit(R1), 0x03=48-bit+busy(R1b)
 */
#define MMC_CMD17_READ      0x113A  /* READ_SINGLE_BLOCK: R1, data, CRC+index check */
#define MMC_CMD24_WRITE     0x183A  /* WRITE_BLOCK: R1, data, CRC+index check */
#define MMC_CMD13_STATUS    0x0D1A  /* SEND_STATUS: R1, no data, CRC+index check */

/* Transfer Mode values (16-bit, lower half of 0x0C write) */
#define XFER_MODE_READ      0x0010  /* Data direction = read, single block, PIO */
#define XFER_MODE_WRITE     0x0000  /* Data direction = write, single block, PIO */

/* Additional transfer mode bits */
#define XFER_MODE_BLOCK_COUNT_ENABLE 0x0002  /* enable block count register */
#define XFER_MODE_AUTO_CMD12         0x0004  /* autostop after multiblock transfer */
#define XFER_MODE_MULTI_BLOCK        0x0020  /* the actuall multiblock transfer */

#define XFER_MODE_READ_MULTI  (XFER_MODE_READ  | XFER_MODE_BLOCK_COUNT_ENABLE | XFER_MODE_AUTO_CMD12 | XFER_MODE_MULTI_BLOCK)
#define XFER_MODE_WRITE_MULTI (XFER_MODE_WRITE | XFER_MODE_BLOCK_COUNT_ENABLE | XFER_MODE_AUTO_CMD12 | XFER_MODE_MULTI_BLOCK)

/* CAR (Clock and Reset Controller) registers for SDMMC4 */
#define CAR_BASE            0x60006000 
#define CAR_CLK_ENB_L_SET   0x320
#define CAR_RST_DEV_L_CLR   0x304
#define CAR_RST_DEV_L_SET   0x300
#define CAR_SDMMC4_BIT      (1 << 15)

/* PMC I/O deep power down (PMC_BASE defined in t124.h) */
#define PMC_IO_DPD2_REQ     0xC0
#define PMC_IO_DPD2_STATUS  0xC4

#endif
