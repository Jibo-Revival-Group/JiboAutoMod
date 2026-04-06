#include "types.h"
#include "t124.h"
#include "emmc.h"
#include "emmc_server.h"

typedef void (*ep1_x_imm_t)(void *buffer, u32 size, u32 *num_xfer);

static inline u32 read32(uintptr_t addr) {
    return *(vu32 *)addr;
}

static inline void write32(uintptr_t addr, u32 val) {
    *(vu32 *)addr = val;
}

static inline void or32(uintptr_t addr, u32 val) {
    write32(addr, read32(addr) | val);
}

static inline void and32(uintptr_t addr, u32 val) {
    write32(addr, read32(addr) & val);
}

void enter_rcm() {
    or32(PMC_BASE + PMC_SCRATCH0, PMC_SCRATCH0_MODE_RCM);
    or32(PMC_BASE + PMC_CNTRL, PMC_CNTRL_MAIN_RST);
}

static void delay(u32 count) {
    for (volatile u32 d = 0; d < count; d++) ;
}

/*
 * SDHCI register access: use native 16-bit/8-bit widths where the SDHCI
 * spec defines sub-word registers. The Linux kernel uses writew/readw for
 * Clock Control (0x2C) and writeb/readb for Software Reset (0x2F).
 * ARM7TDMI supports LDRH/STRH and LDRB/STRB natively.
 *
 * Register map at SDHCI offset 0x2C (32-bit word):
 *   [15:0]  = Clock Control  (16-bit at 0x2C)
 *   [23:16] = Timeout Control (8-bit at 0x2E)
 *   [31:24] = Software Reset  (8-bit at 0x2F)
 */

static inline u16 read16(uintptr_t addr) {
    return *(vu16 *)addr;
}

static inline void write16(uintptr_t addr, u16 val) {
    *(vu16 *)addr = val;
}

static inline u8 read8(uintptr_t addr) {
    return *(vu8 *)addr;
}

static inline void write8(uintptr_t addr, u8 val) {
    *(vu8 *)addr = val;
}

/* Clock Control: 16-bit register at offset 0x2C */
static u16 read_clkctl(void) {
    return read16(SDMMC4_BASE + 0x2C);
}

/* Software Reset: 8-bit register at offset 0x2F */
static void write_swrst(u8 bits) {
    write8(SDMMC4_BASE + 0x2F, bits);
}

static u8 read_swrst(void) {
    return read8(SDMMC4_BASE + 0x2F);
}

/* Host Control: 8-bit at offset 0x28 */
static u8 read_hostctl(void) {
    return read8(SDMMC4_BASE + SDHCI_HOST_CONTROL);
}

static void write_hostctl(u8 val) {
    write8(SDMMC4_BASE + SDHCI_HOST_CONTROL, val);
}

/* Timeout Control: 8-bit at offset 0x2E */
static void write_timeout(u8 val) {
    write8(SDMMC4_BASE + 0x2E, val);
}

static u32 last_cmd_int_status = 0;  /* INT_STATUS captured on last cmd error */
static u32 last_read_int_status = 0; /* INT_STATUS captured on last read error */

/*
 * Send a command to the eMMC card via SDHCI.
 * cmd_val: 16-bit command register value
 * argument: 32-bit command argument
 * Returns 0 on success, negative on error:
 *   -1 = CMD_INHIBIT timeout (command line busy)
 *   -2 = SDHCI_INT_ERROR (card/controller error)
 *   -3 = CMD_COMPLETE timeout (command sent but no response)
 *   -4 = DAT_INHIBIT timeout (R1b busy signal)
 */
static int send_cmd(u32 cmd_val, u32 argument) {
    u32 status;
    u32 timeout;

    /* Wait for CMD line free */
    timeout = 500000;
    while (read32(SDMMC4_BASE + SDHCI_PRESENT_STATE) & SDHCI_CMD_INHIBIT) {
        if (--timeout == 0) {
            last_cmd_int_status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
            return -1;
        }
    }

    /* Clear all pending interrupts */
    write32(SDMMC4_BASE + SDHCI_INT_STATUS, 0xFFFFFFFF);

    /* Set argument */
    write32(SDMMC4_BASE + SDHCI_ARGUMENT, argument);

    /* Issue command (32-bit write: command in upper 16, xfer mode=0 in lower 16) */
    write32(SDMMC4_BASE + SDHCI_TRANSFER_MODE, (cmd_val << 16));

    /* Wait for Command Complete (even for no-response commands like CMD0,
     * the SDHCI controller sets CMD_COMPLETE after sending the command) */
    timeout = 500000;
    do {
        status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
        if (status & SDHCI_INT_ERROR) {
            last_cmd_int_status = status;
            write32(SDMMC4_BASE + SDHCI_INT_STATUS, 0xFFFFFFFF);
            write_swrst(SDHCI_RESET_CMD);
            delay(1000);
            return -2;
        }
        if (status & SDHCI_INT_CMD_COMPLETE) break;
        if (--timeout == 0) {
            last_cmd_int_status = status;
            return -3;
        }
    } while (1);

    /* Clear Command Complete */
    write32(SDMMC4_BASE + SDHCI_INT_STATUS, SDHCI_INT_CMD_COMPLETE);

    /* For R1b responses, wait for DAT line to become free (busy signal) */
    if ((cmd_val & 0x03) == 0x03) {
        timeout = 1000000;
        while (read32(SDMMC4_BASE + SDHCI_PRESENT_STATE) & SDHCI_DAT_INHIBIT) {
            if (--timeout == 0) return -4;
        }
    }

    return 0;
}

/*
 * MMC command register values (16-bit, for upper half of 0x0C write).
 * Format: (cmd_index << 8) | flags
 * Response: 00=none, 01=136-bit(R2), 02=48-bit(R1/R3), 03=48-bit+busy(R1b)
 */
#define MMC_CMD0    0x0000  /* GO_IDLE_STATE: no response */
#define MMC_CMD1    0x0102  /* SEND_OP_COND: R3, no CRC/index check */
#define MMC_CMD2    0x0209  /* ALL_SEND_CID: R2 (136-bit), CRC check */
#define MMC_CMD3    0x031A  /* SET_RELATIVE_ADDR: R1, CRC+index check */
#define MMC_CMD7    0x071B  /* SELECT_CARD: R1b, CRC+index check */
#define MMC_CMD8    0x083A  /* SEND_EXT_CSD: R1, 512-byte data, CRC+index check */
#define MMC_CMD12   0x0C1B  /* STOP_TRANSMISSION: R1b, no data, CRC+index check */
#define MMC_CMD16   0x101A  /* SET_BLOCKLEN: R1, CRC+index check */
#define MMC_CMD18   0x123A  /* READ_MULTIPLE_BLOCK: R1, data, CRC+index check */
#define MMC_CMD24   0x183A  /* WRITE_BLOCK: R1, data, CRC+index check */
#define MMC_CMD25   0x193A  /* WRITE_MULTIPLE_BLOCK: R1, data, CRC+index check */
#define MMC_CMD6    0x061B  /* SWITCH: R1b, no data, CRC+index check */
#define MMC_CMD35   0x233A  /* ERASE_GROUP_START: R1, CRC+index check */
#define MMC_CMD36   0x243A  /* ERASE_GROUP_END: R1, CRC+index check */
#define MMC_CMD38   0x263B  /* ERASE: R1b, CRC+index check */

/*
 * Boot partition encoding in start_sector for EMMC_CMD_READ / EMMC_CMD_WRITE:
 *   bits [31:30] == 00  → User Data Area (normal sectors)
 *   bits [31:30] == 10  → Boot Partition 1 (boot0), real sector in bits [29:0]
 *   bits [31:30] == 11  → Boot Partition 2 (boot1), real sector in bits [29:0]
 *
 * Example: sector 0x80000000 means "boot0, sector 0".
 *          sector 0xC0000005 means "boot1, sector 5".
 *
 * After the operation the partition is switched back to UDA (0).
 */
#define BOOT_PART_MASK   0xC0000000U
#define BOOT_PART_UDA    0x00000000U
#define BOOT_PART_BOOT0  0x80000000U
#define BOOT_PART_BOOT1  0xC0000000U
#define BOOT_PART_SECTOR(s) ((s) & 0x3FFFFFFFU)

static u32 sdmmc4_initialized = 0;
static u32 init_error = 0;

/* Diagnostic trace: stores CAR/SDHCI state at key init steps */
static u32 diag[40];

/*
 * Perform pad auto-calibration (from IROM reverse engineering at 0x10a788).
 * Calibrates I/O pad impedance for SDMMC4 interface.
 * Must be called after clock is enabled and reset deasserted.
 */
static void sdmmc4_auto_cal(void) {
    u32 timeout;

    /* Set COMP_PADCTRL_E_INPUT (bit 31) - force pads powered for calibration */
    or32(SDMMC4_BASE + SDMMC_SDMEMCOMP_PADCTRL, SDMMC_COMP_PADCTRL_E_INPUT);

    /* Start auto-calibration: set AUTO_CAL_START (bit 31) + AUTO_CAL_ENABLE (bit 29) */
    or32(SDMMC4_BASE + SDMMC_AUTO_CAL_CONFIG,
         SDMMC_AUTO_CAL_START | SDMMC_AUTO_CAL_ENABLE);

    /* Readback for memory fence */
    (void)read32(SDMMC4_BASE + SDMMC_AUTO_CAL_CONFIG);

    /* Poll AUTO_CAL_STATUS bit 31 until clear (calibration complete) */
    timeout = 100000;
    while ((read32(SDMMC4_BASE + SDMMC_AUTO_CAL_STATUS) & SDMMC_AUTO_CAL_ACTIVE)
           && --timeout) {
        delay(1);
    }

    if (!timeout) {
        /* Timeout - disable auto-cal enable */
        and32(SDMMC4_BASE + SDMMC_AUTO_CAL_CONFIG, ~SDMMC_AUTO_CAL_ENABLE);
    }

    /* Clear COMP_PADCTRL_E_INPUT (bit 31) - release forced pad power */
    and32(SDMMC4_BASE + SDMMC_SDMEMCOMP_PADCTRL, ~SDMMC_COMP_PADCTRL_E_INPUT);
}

/*
 * Initialize SDMMC4 controller and eMMC card.
 *
 * ATTEMPT 29: Call the IROM's device_init_generic() function directly
 * to perform the pad/pinmux/drive configuration from the IROM's internal
 * tables. This is the one step we've never done — the IROM calls it
 * BEFORE the CAR reset cycle, and it configures pad drive strength,
 * voltage, and pinmux from data-driven tables in the ROM.
 *
 * The IROM's device_init_generic is at 0x101EA8 (Thumb).
 * It reads a table pointer from IRAM at 0x400022FC.
 * Calling convention: r0 = device_index (0), r1 = voltage_mode (2 or 3).
 *
 * Diagnostic layout (diag[0..39] → regs[16..55]):
 *   [0]  CLK_OUT_ENB_L (residual)
 *   [1]  RST_DEVICES_L (residual)
 *   [2]  CLK_SOURCE_SDMMC4 (residual)
 *   [3]  IO_DPD2_STATUS (residual)
 *   [4]  IRAM[0x400022FC] (table pointer)
 *   [5]  table[0] (first word of table data)
 *   [6]  table[1] (second word)
 *   [7]  CAPABILITIES
 *   [8]  device_init_generic return value
 *   [9]  0x2C after stable poll
 *   [10] stable flag (0 or 1)
 *   [11] 0x2C final
 *   [12] 0x28 final (host+power)
 *   [13] PRESENT_STATE (before CMD0)
 *   [14] VENDOR_CLK_CTRL (after init)
 *   [15] VENDOR_MISC_CTRL (after init)
 *   [19] PLLP_BASE
 *   [20] PMC+0xE8 (before)
 *   [30] result: 0=fail, 1=stable, 2=CMD0 OK
 *   [33] CMD error code
 *   [34] CMD INT_STATUS
 *   [35] CMD PRESENT_STATE
 */
static void init_sdmmc4(void) {
    u32 timeout;
    int cmd_ret;

    if (sdmmc4_initialized) return;

    init_error = 0;

    /* ============================================================
     * PHASE 0: RESIDUAL STATE + IRAM TABLE CHECK
     * ============================================================ */

    /* CAR state */
    diag[0] = read32(CAR_BASE + 0x10);    /* CLK_OUT_ENB_L */
    diag[1] = read32(CAR_BASE + 0x04);    /* RST_DEVICES_L */
    diag[2] = read32(CAR_BASE + 0x164);   /* CLK_SOURCE_SDMMC4 */
    diag[19] = read32(CAR_BASE + 0xA0);   /* PLLP_BASE */

    /* PMC state */
    diag[3] = read32(PMC_BASE + 0x1C4);   /* IO_DPD2_STATUS */
    diag[20] = read32(PMC_BASE + 0xE8);   /* PMC+0xE8 */

    /* Read IROM's IRAM table pointer for device_init_generic */
    diag[4] = read32(0x400022FC);  /* table pointer array base */
    {
        u32 tbl = diag[4];
        if ((tbl >= 0x100000 && tbl < 0x110000) ||
            (tbl >= 0x40000000 && tbl < 0x40040000)) {
            diag[5] = read32(tbl);      /* table[0] */
            diag[6] = read32(tbl + 4);  /* table[1] */
        } else {
            diag[5] = 0xBAD00BAD;
            diag[6] = 0xBAD00BAD;
        }
    }

    /* Ensure SDMMC4 clock on for register reads */
    if (!(diag[0] & CAR_SDMMC4_BIT))
        write32(CAR_BASE + CAR_CLK_ENB_L_SET, CAR_SDMMC4_BIT);
    if (diag[1] & CAR_SDMMC4_BIT)
        write32(CAR_BASE + CAR_RST_DEV_L_CLR, CAR_SDMMC4_BIT);
    (void)read32(CAR_BASE + 0x04);
    delay(5000);

    diag[7] = read32(SDMMC4_BASE + 0x40);  /* CAPABILITIES */

    /* ============================================================
     * PHASE 1: CALL IROM's device_init_generic
     * ============================================================
     * This is the missing step! The IROM calls this function at
     * 0x101EA8 BEFORE the CAR reset cycle. It configures:
     *   - Pinmux (with tristate sequencing)
     *   - Pad drive strength / voltage mode
     *   - Possibly pad group registers
     *
     * The function reads its table from IRAM at 0x400022FC.
     * This IRAM area (offset 0x22FC) is below the stack area
     * and should survive our exploit.
     */

    /* Release DPD first (IROM does this earlier in boot) */
    write32(PMC_BASE + 0x1B8, 0x7FFFFFFF);
    delay(2000);
    write32(PMC_BASE + 0x1C0, 0x7FFFFFFF);
    delay(5000);

    /* Clear PMC+0xE8 bit 1 (IROM does this before device_init_generic) */
    and32(PMC_BASE + 0xE8, ~0x2u);
    delay(1000);

    /* Call IROM's device_init_generic(0, 3)
     * Args: r0=0 (device index for SDMMC4), r1=3 (3.3V voltage mode)
     * Address 0x101EA8 | 1 = 0x101EA9 for Thumb mode call */
    {
        typedef int (*dev_init_fn_t)(int device, int voltage);
        dev_init_fn_t irom_dev_init = (dev_init_fn_t)(0x101EA9);
        diag[8] = (u32)irom_dev_init(0, 3);
    }

    /* ============================================================
     * PHASE 2: CAR RESET + SDHCI INIT (same as IROM does AFTER
     * device_init_generic)
     * ============================================================ */

    /* CAR: assert reset */
    or32(CAR_BASE + 0x04, CAR_SDMMC4_BIT);
    (void)read32(CAR_BASE + 0x04);
    delay(2000);

    /* Set clock source: PLLP, N=0x20 → 24 MHz */
    write32(CAR_BASE + 0x164, 0x00000020);
    (void)read32(CAR_BASE + 0x164);
    delay(2000);

    /* Enable SDMMC4 clock */
    or32(CAR_BASE + 0x10, CAR_SDMMC4_BIT);
    (void)read32(CAR_BASE + 0x10);
    delay(2000);

    /* Deassert SDMMC4 reset */
    and32(CAR_BASE + 0x04, ~CAR_SDMMC4_BIT);
    (void)read32(CAR_BASE + 0x04);
    delay(2000);

    /* Auto-calibration */
    sdmmc4_auto_cal();

    /* Clock Control: IntClkEn + div=0x01 (proven 160KB/s speed) */
    write32(SDMMC4_BASE + SDHCI_CLOCK_CONTROL, 0x00000101);
    (void)read32(SDMMC4_BASE + SDHCI_CLOCK_CONTROL);

    /* Poll stable with shorter timeout, accept if not stable */
    {
        u32 start = read32(0x60005010);
        diag[10] = 0;
        while ((read32(0x60005010) - start) < 50000) {  /* reduced from 100ms to 50ms */
            if (read32(SDMMC4_BASE + 0x2C) & 0x0002) {
                diag[10] = 1;
                break;
            }
        }
        diag[9] = read32(SDMMC4_BASE + 0x2C);
    }

    /*power ON (host control + power) */
    write32(SDMMC4_BASE + 0x28, 0x00000D00);
    (void)read32(SDMMC4_BASE + 0x28);
    delay(5000);

    /* turn on SDHCI 3.0 mode*/
    write32(SDMMC4_BASE + SDMMC_VENDOR_MISC_CTRL, SDMMC_MISC_CTRL_SPEC_300);

    /* Set data timeout to maximum (TMCLK * 2^27) */
    write_timeout(0x0E);

    /* Enable interrupts (0x00FB = IROM's 0x00CB + BUF_WR_READY + BUF_RD_READY for PIO) */
    write32(SDMMC4_BASE + 0x34, 0x007F00FB);

    /* Enable SD Clock (only works if stable is set) */
    {
        u32 clk = read32(SDMMC4_BASE + 0x2C);
        clk |= 0x0004;
        write32(SDMMC4_BASE + 0x2C, clk);
    }
    (void)read32(SDMMC4_BASE + 0x2C);
    delay(5000);

    /* Capture final state */
    diag[11] = read32(SDMMC4_BASE + 0x2C);  /* clock control */
    diag[12] = read32(SDMMC4_BASE + 0x28);  /* host+power */
    diag[13] = read32(SDMMC4_BASE + 0x24);  /* PRESENT_STATE */
    diag[14] = read32(SDMMC4_BASE + 0x100); /* VENDOR_CLK_CTRL */
    diag[15] = read32(SDMMC4_BASE + 0x120); /* VENDOR_MISC_CTRL */

    diag[30] = diag[10] ? 1 : 0;

    /* === Try CMD0 === */
    cmd_ret = send_cmd(MMC_CMD0, 0);
    if (cmd_ret < 0) {
        init_error = 0xE0000001;
        diag[33] = (u32)(-cmd_ret);
        diag[34] = last_cmd_int_status;
        diag[35] = read32(SDMMC4_BASE + SDHCI_PRESENT_STATE);
        return;
    }

    diag[30] = 2;  /* CMD0 succeeded! */

    /* Delay after CMD0 before starting CMD1 */
    delay(100000);

    /* CMD1: SEND_OP_COND - poll until card ready (bit 31 set)
     * eMMC spec allows up to 1 second for power-up.
     * delay(50000) ≈ 12ms on ARM7TDMI @ 12MHz, 2000 retries = ~24 seconds max */
    diag[16] = 0;  /* first OCR */
    diag[17] = 0;  /* last OCR */
    diag[18] = 0;  /* retry count */
    timeout = 2000;
    while (1) {
        cmd_ret = send_cmd(MMC_CMD1, 0x40FF8080);
        if (cmd_ret < 0) {
            init_error = 0xE0000002;
            diag[33] = (u32)(-cmd_ret);
            diag[34] = last_cmd_int_status;
            diag[35] = read32(SDMMC4_BASE + SDHCI_PRESENT_STATE);
            return;
        }
        u32 ocr = read32(SDMMC4_BASE + SDHCI_RESPONSE);
        diag[18]++;
        if (diag[16] == 0) diag[16] = ocr;  /* capture first response */
        diag[17] = ocr;  /* always update last response */
        if (ocr & (1u << 31)) break;
        if (--timeout == 0) { init_error = 0xE0000003; return; }
        delay(50000);
    }

    diag[30] = 3;  /* CMD1 succeeded! */

    cmd_ret = send_cmd(MMC_CMD2, 0);
    if (cmd_ret < 0) { init_error = 0xE0000004; diag[33] = (u32)(-cmd_ret); diag[34] = last_cmd_int_status; return; }

    diag[30] = 4;  /* CMD2 succeeded! */

    cmd_ret = send_cmd(MMC_CMD3, 0x00010000);
    if (cmd_ret < 0) { init_error = 0xE0000005; diag[33] = (u32)(-cmd_ret); diag[34] = last_cmd_int_status; return; }

    cmd_ret = send_cmd(MMC_CMD7, 0x00010000);
    if (cmd_ret < 0) { init_error = 0xE0000006; diag[33] = (u32)(-cmd_ret); diag[34] = last_cmd_int_status; return; }

    cmd_ret = send_cmd(MMC_CMD16, 512);
    if (cmd_ret < 0) { init_error = 0xE0000007; diag[33] = (u32)(-cmd_ret); diag[34] = last_cmd_int_status; return; }

    diag[30] = 5;  /* All CMDs succeeded! */
    sdmmc4_initialized = 1;
}

/* Wait for CMD and DAT lines to be free */
static int wait_ready(void) {
    u32 timeout = 500000;
    while (read32(SDMMC4_BASE + SDHCI_PRESENT_STATE) & (SDHCI_CMD_INHIBIT | SDHCI_DAT_INHIBIT)) {
        if (--timeout == 0) return -1;
    }
    return 0;
}

/* Reset CMD and DAT lines after error */
static void reset_cmd_dat(void) {
    write_swrst(SDHCI_RESET_CMD | SDHCI_RESET_DAT);
    u32 timeout = 10000;
    while ((read_swrst() & (SDHCI_RESET_CMD | SDHCI_RESET_DAT)) && --timeout) ;
}

/* Read N sectors directly into a target address (for DMA) */
static int read_emmc_sectors_addr(u32 sector, u32 count, u32 addr) {
    u32 status;
    u32 timeout;

    if (count == 0) return 0;
    if (wait_ready() < 0) return -1;

    /* Set SDMA address register to target address */
    write32(SDMMC4_BASE + 0x00, addr);  /* SDMA System Address */

    /* Block count is written in the upper half of BLOCK_SIZE register */
    write32(SDMMC4_BASE + SDHCI_INT_STATUS, 0xFFFFFFFF);
    write32(SDMMC4_BASE + SDHCI_BLOCK_SIZE, (count << 16) | 0x200);
    write32(SDMMC4_BASE + SDHCI_ARGUMENT, sector);
    write32(SDMMC4_BASE + SDHCI_TRANSFER_MODE,
                    ((u32)MMC_CMD18 << 16) | XFER_MODE_READ_MULTI);
    timeout = 1000000;  /* increased timeout */
    do {
        status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
        if (status & SDHCI_INT_ERROR) { last_read_int_status = status; reset_cmd_dat(); return -2; }
        if (--timeout == 0) { last_read_int_status = status; return -3; }
    } while (!(status & SDHCI_INT_CMD_COMPLETE));

    write32(SDMMC4_BASE + SDHCI_INT_STATUS, SDHCI_INT_CMD_COMPLETE);

    timeout = 2000000;
    do {
        status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
        if (status & SDHCI_INT_ERROR) { last_read_int_status = status; reset_cmd_dat(); return -6; }
        if (--timeout == 0) { last_read_int_status = status; return -7; }
    } while (!(status & SDHCI_INT_XFER_COMPLETE));

    write32(SDMMC4_BASE + SDHCI_INT_STATUS, 0xFFFFFFFF);
    return 0;
}

static int read_emmc_sectors(u32 sector, u32 count, u32 *buffer) {
    u32 status;
    u32 timeout;

    if (count == 0) return 0;
    if (wait_ready() < 0) return -1;

    /* note AGAIN > Block count is written in the upper half of BLOCK_SIZE register */
    write32(SDMMC4_BASE + SDHCI_INT_STATUS, 0xFFFFFFFF);
    write32(SDMMC4_BASE + SDHCI_BLOCK_SIZE, (count << 16) | 0x200);  /* back to 512B */
    write32(SDMMC4_BASE + SDHCI_ARGUMENT, sector);
    write32(SDMMC4_BASE + SDHCI_TRANSFER_MODE,
                    ((u32)MMC_CMD18 << 16) | XFER_MODE_READ_MULTI);
    timeout = 1000000;  /* increased timeout for multi-block */
    do {
        status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
        if (status & SDHCI_INT_ERROR) { last_read_int_status = status; reset_cmd_dat(); return -2; }
        if (--timeout == 0) { last_read_int_status = status; return -3; }
    } while (!(status & SDHCI_INT_CMD_COMPLETE));

    write32(SDMMC4_BASE + SDHCI_INT_STATUS, SDHCI_INT_CMD_COMPLETE);

    for (u32 blk = 0; blk < count; blk++) {
        timeout = 2000000;  /* timeout */
        do {
            status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
            if (status & SDHCI_INT_ERROR) { last_read_int_status = status; reset_cmd_dat(); return -4; }
            if (--timeout == 0) { last_read_int_status = status; return -5; }
        } while (!(status & SDHCI_INT_BUF_RD_READY));

        for (u32 i = 0; i < 128; i++) {
            buffer[blk * 128 + i] = read32(SDMMC4_BASE + SDHCI_BUFFER);
        }

        /* Clear buffer ready so we can wait for the next block */
        write32(SDMMC4_BASE + SDHCI_INT_STATUS, SDHCI_INT_BUF_RD_READY);
    }

    timeout = 2000000;  /* timeout for transfer complete */
    do {
        status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
        if (status & SDHCI_INT_ERROR) { last_read_int_status = status; reset_cmd_dat(); return -6; }
        if (--timeout == 0) { last_read_int_status = status; return -7; }
    } while (!(status & SDHCI_INT_XFER_COMPLETE));

    write32(SDMMC4_BASE + SDHCI_INT_STATUS, 0xFFFFFFFF);
    return 0;
}

/* Read a single 512-byte sector from eMMC */
static int read_emmc_sector(u32 sector, u32 *buffer) {
    return read_emmc_sectors(sector, 1, buffer);
}

/* Write N sectors to eMMC using multi-block CMD25 */
static int write_emmc_sectors(u32 sector, u32 count, u32 *buffer) {
    u32 status;
    u32 timeout;

    if (count == 0) return 0;
    if (wait_ready() < 0) return -1;

    write32(SDMMC4_BASE + SDHCI_INT_STATUS, 0xFFFFFFFF);
    write32(SDMMC4_BASE + SDHCI_BLOCK_SIZE, (count << 16) | 0x200);
    write32(SDMMC4_BASE + SDHCI_ARGUMENT, sector);
    write32(SDMMC4_BASE + SDHCI_TRANSFER_MODE,
                    ((u32)MMC_CMD25 << 16) | XFER_MODE_WRITE_MULTI);

    timeout = 1000000;
    do {
        status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
        if (status & SDHCI_INT_ERROR) { reset_cmd_dat(); return -2; }
        if (--timeout == 0) return -3;
    } while (!(status & SDHCI_INT_CMD_COMPLETE));

    write32(SDMMC4_BASE + SDHCI_INT_STATUS, SDHCI_INT_CMD_COMPLETE);

    for (u32 blk = 0; blk < count; blk++) {
        timeout = 2000000;
        do {
            status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
            if (status & SDHCI_INT_ERROR) { reset_cmd_dat(); return -4; }
            if (--timeout == 0) return -5;
        } while (!(status & SDHCI_INT_BUF_WR_READY));

        for (u32 i = 0; i < 128; i++) {
            write32(SDMMC4_BASE + SDHCI_BUFFER, buffer[blk * 128 + i]);
        }

        write32(SDMMC4_BASE + SDHCI_INT_STATUS, SDHCI_INT_BUF_WR_READY);
    }

    timeout = 2000000;
    do {
        status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
        if (status & SDHCI_INT_ERROR) { reset_cmd_dat(); return -6; }
        if (--timeout == 0) return -7;
    } while (!(status & SDHCI_INT_XFER_COMPLETE));

    write32(SDMMC4_BASE + SDHCI_INT_STATUS, 0xFFFFFFFF);
    return 0;
}

/* Write a single 512-byte sector to eMMC */
static int write_emmc_sector(u32 sector, u32 *buffer) {
    u32 status;
    u32 timeout;

    if (wait_ready() < 0) return -1;

    write32(SDMMC4_BASE + SDHCI_INT_STATUS, 0xFFFFFFFF);
    write32(SDMMC4_BASE + SDHCI_BLOCK_SIZE, (1 << 16) | 0x200);
    write32(SDMMC4_BASE + SDHCI_ARGUMENT, sector);
    write32(SDMMC4_BASE + SDHCI_TRANSFER_MODE, ((u32)MMC_CMD24 << 16) | XFER_MODE_WRITE);

    timeout = 500000;
    do {
        status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
        if (status & SDHCI_INT_ERROR) { reset_cmd_dat(); return -2; }
        if (--timeout == 0) return -3;
    } while (!(status & SDHCI_INT_CMD_COMPLETE));

    write32(SDMMC4_BASE + SDHCI_INT_STATUS, SDHCI_INT_CMD_COMPLETE);

    timeout = 500000;
    do {
        status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
        if (status & SDHCI_INT_ERROR) { reset_cmd_dat(); return -4; }
        if (--timeout == 0) return -5;
    } while (!(status & SDHCI_INT_BUF_WR_READY));

    for (u32 i = 0; i < 128; i++) {
        write32(SDMMC4_BASE + SDHCI_BUFFER, buffer[i]);
    }

    timeout = 500000;
    do {
        status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
        if (status & SDHCI_INT_ERROR) { reset_cmd_dat(); return -6; }
        if (--timeout == 0) return -7;
    } while (!(status & SDHCI_INT_XFER_COMPLETE));

    write32(SDMMC4_BASE + SDHCI_INT_STATUS, 0xFFFFFFFF);
    return 0;
}

/* Read EXT_CSD register (512 bytes of chip health/configuration data) */
static int read_ext_csd(u32 *buffer) {
    u32 status;
    u32 timeout;

    if (wait_ready() < 0) return -1;

    write32(SDMMC4_BASE + SDHCI_INT_STATUS, 0xFFFFFFFF);
    write32(SDMMC4_BASE + SDHCI_BLOCK_SIZE, (1 << 16) | 0x200);  /* 1 block, 512 bytes */
    write32(SDMMC4_BASE + SDHCI_ARGUMENT, 0);  /* EXT_CSD addressed by sector 0 */
    write32(SDMMC4_BASE + SDHCI_TRANSFER_MODE,
                    ((u32)MMC_CMD8 << 16) | XFER_MODE_READ);

    timeout = 500000;
    do {
        status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
        if (status & SDHCI_INT_ERROR) { reset_cmd_dat(); return -2; }
        if (--timeout == 0) return -3;
    } while (!(status & SDHCI_INT_CMD_COMPLETE));

    write32(SDMMC4_BASE + SDHCI_INT_STATUS, SDHCI_INT_CMD_COMPLETE);

    timeout = 500000;
    do {
        status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
        if (status & SDHCI_INT_ERROR) { reset_cmd_dat(); return -4; }
        if (--timeout == 0) return -5;
    } while (!(status & SDHCI_INT_BUF_RD_READY));

    /* Read 512 bytes (128 words) of EXT_CSD data */
    for (u32 i = 0; i < 128; i++) {
        buffer[i] = read32(SDMMC4_BASE + SDHCI_BUFFER);
    }

    timeout = 500000;
    do {
        status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
        if (status & SDHCI_INT_ERROR) { reset_cmd_dat(); return -6; }
        if (--timeout == 0) return -7;
    } while (!(status & SDHCI_INT_XFER_COMPLETE));

    write32(SDMMC4_BASE + SDHCI_INT_STATUS, 0xFFFFFFFF);
    return 0;
}

/* Erase a range of sectors - tells eMMC controller data can be discarded/reallocated */
static int erase_emmc_sectors(u32 start_sector, u32 end_sector) {
    u32 status;
    u32 timeout;

    if (wait_ready() < 0) return -1;

    /* CMD35: ERASE_GROUP_START - set start address */
    write32(SDMMC4_BASE + SDHCI_INT_STATUS, 0xFFFFFFFF);
    write32(SDMMC4_BASE + SDHCI_BLOCK_SIZE, (1 << 16) | 0x200);
    write32(SDMMC4_BASE + SDHCI_ARGUMENT, start_sector);
    write32(SDMMC4_BASE + SDHCI_TRANSFER_MODE, ((u32)MMC_CMD35 << 16) | 0);

    timeout = 500000;
    do {
        status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
        if (status & SDHCI_INT_ERROR) { reset_cmd_dat(); return -2; }
        if (--timeout == 0) return -3;
    } while (!(status & SDHCI_INT_CMD_COMPLETE));

    write32(SDMMC4_BASE + SDHCI_INT_STATUS, SDHCI_INT_CMD_COMPLETE);

    /* CMD36: ERASE_GROUP_END - set end address */
    write32(SDMMC4_BASE + SDHCI_INT_STATUS, 0xFFFFFFFF);
    write32(SDMMC4_BASE + SDHCI_ARGUMENT, end_sector);
    write32(SDMMC4_BASE + SDHCI_TRANSFER_MODE, ((u32)MMC_CMD36 << 16) | 0);

    timeout = 500000;
    do {
        status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
        if (status & SDHCI_INT_ERROR) { reset_cmd_dat(); return -4; }
        if (--timeout == 0) return -5;
    } while (!(status & SDHCI_INT_CMD_COMPLETE));

    write32(SDMMC4_BASE + SDHCI_INT_STATUS, SDHCI_INT_CMD_COMPLETE);

    /* CMD38: ERASE - actually perform the erase operation */
    write32(SDMMC4_BASE + SDHCI_INT_STATUS, 0xFFFFFFFF);
    write32(SDMMC4_BASE + SDHCI_ARGUMENT, 0);
    write32(SDMMC4_BASE + SDHCI_TRANSFER_MODE, ((u32)MMC_CMD38 << 16) | 0);

    timeout = 5000000;  /* Erase can take longer than reads/writes */
    do {
        status = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
        if (status & SDHCI_INT_ERROR) { reset_cmd_dat(); return -6; }
        if (--timeout == 0) return -7;
    } while (!(status & SDHCI_INT_CMD_COMPLETE));

    write32(SDMMC4_BASE + SDHCI_INT_STATUS, 0xFFFFFFFF);
    return 0;
}

/*
 * Switch eMMC partition access via CMD6 SWITCH (EXT_CSD[179] PARTITION_CONFIG).
 *   part 0 = User Data Area
 *   part 1 = Boot Partition 1 (boot0)
 *   part 2 = Boot Partition 2 (boot1)
 * Returns 0 on success, negative on send_cmd error.
 */
static int switch_partition_access(u32 part) {
    /* CMD6 argument: [25:24]=3(WriteByte), [23:16]=179(PARTITION_CONFIG), [15:8]=value, [2:0]=0 */
    u32 arg = (3U << 24) | (179U << 16) | ((part & 0x7U) << 8);
    return send_cmd(MMC_CMD6, arg);
}

__attribute__((section(".init")))
void entry() {

    u32 num_xfer;
    struct emmc_cmd_s cmd;
    u8 *buffer = (u8*)0x40020000;

    ep1_x_imm_t ep1_out_read_imm = (ep1_x_imm_t)(BOOTROM_EP1_OUT_READ_IMM | 1);
    ep1_x_imm_t ep1_in_write_imm = (ep1_x_imm_t)(BOOTROM_EP1_IN_WRITE_IMM | 1);

    while (1) {
        ep1_out_read_imm(&cmd, sizeof(cmd), &num_xfer);

        if (cmd.op == EMMC_CMD_EXIT) {
            break;
        }

        if (cmd.op == EMMC_CMD_STATUS) {
            u32 regs[128];

            init_sdmmc4();

            regs[0] = 0xCAFE0000;
            regs[1] = init_error;
            regs[2] = sdmmc4_initialized;
            regs[3] = read32(SDMMC4_BASE + SDHCI_PRESENT_STATE);
            regs[4] = read_clkctl();
            regs[5] = read32(SDMMC4_BASE + SDHCI_INT_STATUS);
            regs[6] = read32(SDMMC4_BASE + SDHCI_INT_ENABLE);
            regs[7] = read32(SDMMC4_BASE + SDHCI_CAPABILITIES);
            regs[8] = read32(SDMMC4_BASE + SDHCI_HOST_CONTROL);
            regs[9] = read32(SDMMC4_BASE + SDHCI_RESPONSE);
            regs[10] = read32(SDMMC4_BASE + SDHCI_RESPONSE + 4);
            regs[11] = read32(SDMMC4_BASE + SDHCI_RESPONSE + 8);
            regs[12] = read32(SDMMC4_BASE + SDHCI_RESPONSE + 12);

            /* Init diagnostic trace (diag[0..39]) at regs[16..55] */
            for (u32 d = 0; d < 40; d++) regs[16 + d] = diag[d];

            /* Try reading sector 0 if init succeeded */
            regs[13] = 0xCAFE0001;
            regs[14] = 0;  /* read error INT_STATUS (if read fails) */
            regs[15] = 0;  /* first word of sector 0 (if read succeeds) */
            if (sdmmc4_initialized) {
                u32 sec_buf[128];
                last_read_int_status = 0;
                int r = read_emmc_sector(0, sec_buf);
                regs[13] = (u32)r;
                if (r < 0) {
                    regs[14] = last_read_int_status;
                } else {
                    regs[15] = sec_buf[0];  /* first 4 bytes of MBR */
                }
            }

            ep1_in_write_imm(regs, SDMMC4_REG_SIZE, &num_xfer);
            continue;
        }

        if (cmd.op == EMMC_CMD_READ) {
            init_sdmmc4();

            /* Decode boot partition encoding from high 2 bits of start_sector */
            u32 part_sel = cmd.start_sector & BOOT_PART_MASK;
            u32 sector   = BOOT_PART_SECTOR(cmd.start_sector);
            u32 remaining = cmd.num_sectors;

            if (part_sel != BOOT_PART_UDA)
                switch_partition_access((part_sel == BOOT_PART_BOOT0) ? 1 : 2);

            while (remaining > 0) {
                u32 batch = remaining > EMMC_CHUNK_SECTORS_READ ? EMMC_CHUNK_SECTORS_READ : remaining;
                u32 batch_bytes = batch * EMMC_SECTOR_SIZE;

                int result = read_emmc_sectors(sector, batch, (u32*)buffer);
                if (result < 0) {
                    u32 *err = (u32*)buffer;
                    err[0] = 0xDEAD0000 | (u32)((-result) & 0xFFFF);
                    for (u32 j = 1; j < batch * 128; j++) err[j] = 0xDEADDEAD;
                }

                ep1_in_write_imm(buffer, batch_bytes, &num_xfer);

                sector += batch;
                remaining -= batch;
            }

            if (part_sel != BOOT_PART_UDA)
                switch_partition_access(0);  /* restore UDA access */

            continue;
        }

        if (cmd.op == EMMC_CMD_WRITE) {
            init_sdmmc4();

            /* Decode boot partition encoding from high 2 bits of start_sector */
            u32 part_sel = cmd.start_sector & BOOT_PART_MASK;
            u32 sector   = BOOT_PART_SECTOR(cmd.start_sector);
            u32 remaining = cmd.num_sectors;
            u32 write_result = 0;

            if (part_sel != BOOT_PART_UDA)
                switch_partition_access((part_sel == BOOT_PART_BOOT0) ? 1 : 2);

            while (remaining > 0) {
                u32 batch = remaining > EMMC_CHUNK_SECTORS_WRITE ? EMMC_CHUNK_SECTORS_WRITE : remaining;
                u32 batch_bytes = batch * EMMC_SECTOR_SIZE;

                ep1_out_read_imm(buffer, batch_bytes, &num_xfer);

                if (write_result == 0) {
                    for (u32 i = 0; i < batch; i++) {
                        int result = write_emmc_sector(sector + i, (u32*)(buffer + i * EMMC_SECTOR_SIZE));
                        if (result < 0) {
                            write_result = 0xDEAD0000 | (u32)((-result) & 0xFFFF);
                            break;
                        }
                    }
                }

                sector += batch;
                remaining -= batch;
            }

            if (part_sel != BOOT_PART_UDA)
                switch_partition_access(0);  /* restore UDA access */

            ep1_in_write_imm(&write_result, 4, &num_xfer);
            continue;
        }

        if (cmd.op == EMMC_CMD_READ_EXT_CSD) {
            init_sdmmc4();

            int result = read_ext_csd((u32*)buffer);
            if (result < 0) {
                /* On error, clear the buffer and return zeros */
                for (u32 i = 0; i < 128; i++) {
                    ((u32*)buffer)[i] = 0;
                }
            }

            /* Send the 512-byte EXT_CSD register back to host */
            ep1_in_write_imm(buffer, 512, &num_xfer);
            continue;
        }

        if (cmd.op == EMMC_CMD_ERASE) {
            init_sdmmc4();
            u32 erase_result = 0;

            int result = erase_emmc_sectors(cmd.start_sector, cmd.num_sectors);
            if (result < 0) {
                erase_result = 0xDEAD0000 | (u32)((-result) & 0xFFFF);
            }

            ep1_in_write_imm(&erase_result, 4, &num_xfer);
            continue;
        }
    }

    enter_rcm();
}
