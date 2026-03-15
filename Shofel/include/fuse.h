#ifndef _FUSE_H_
#define _FUSE_H_

#include <stdio.h>
#include <stdint.h>

// Based on https://github.com/moriczgergo/moonflower/blob/933ab9ef66b76aa49ad2c29ca88d78173a81eff2/src/fuse.h

typedef struct {
    uint32_t FUSE_PRODUCTION_MODE; //0x000
    uint32_t FUSE_JTAG_SECUREID_VALID; //0x004
    uint32_t FUSE_ODM_LOCK; //0x008
    uint32_t FUSE_OPT_OPENGL_EN; //0x00c
    uint32_t FUSE_SKU_INFO; //0x010
    uint32_t FUSE_CPU_SPEEDO_0_CALIB; //0x014
    uint32_t FUSE_CPU_IDDQ_CALIB; //0x018
    uint32_t RESERVED_0x01C;
    uint32_t RESERVED_0x020;
    uint32_t RESERVED_0x024;
    uint32_t FUSE_OPT_FT_REV; //0x028
    uint32_t FUSE_CPU_SPEEDO_1_CALIB; //0x02c
    uint32_t FUSE_CPU_SPEEDO_2_CALIB; //0x030
    uint32_t FUSE_SOC_SPEEDO_0_CALIB; //0x034
    uint32_t FUSE_SOC_SPEEDO_1_CALIB; //0x038
    uint32_t FUSE_SOC_SPEEDO_2_CALIB; //0x03c
    uint32_t FUSE_SOC_IDDQ_CALIB; //0x040
    uint32_t RESERVED_0x044;
    uint32_t FUSE_FA; //0x048
    uint32_t FUSE_RESERVED_PRODUCTION; //0x04c
    uint32_t FUSE_HDMI_LANE0_CALIB; //0x050
    uint32_t FUSE_HDMI_LANE1_CALIB; //0x054
    uint32_t FUSE_HDMI_LANE2_CALIB; //0x058
    uint32_t FUSE_HDMI_LANE3_CALIB; //0x05c
    uint32_t FUSE_ENCRYPTION_RATE; //0x060
    uint32_t FUSE_PUBLIC_KEY[0x8]; //0x064 - 0x080
    uint32_t FUSE_TSENSOR1_CALIB; //0x084
    uint32_t FUSE_TSENSOR2_CALIB; //0x088
    uint32_t RESERVED_0x08C;
    uint32_t FUSE_OPT_CP_REV; //0x090
    uint32_t FUSE_OPT_PFG; //0x094
    uint32_t FUSE_TSENSOR0_CALIB; //0x098
    uint32_t FUSE_BOOTROM_PATCH_SIZE; //0x09c
    uint32_t FUSE_SECURITY_MODE; //0x0a0
    uint32_t FUSE_PRIVATE_KEY[0x4]; //0x0a4 - 0x0b0
    uint32_t FUSE_DEVICE_KEY; //0x0b4
    uint32_t FUSE_ARM_DEBUG_DIS; //0x0b8
    uint32_t FUSE_BOOT_DEVICE_INFO; //0x0bc
    uint32_t FUSE_RESERVED_SW; //0x0c0
    uint32_t FUSE_VP8_ENABLE; //0x0c4
    uint32_t FUSE_RESERVED_ODM[0x8]; //0x0c8-0x0e4
    uint32_t FUSE_OBS_DIS; //0x0e8
    uint32_t RESERVED_0x0EC;
    uint32_t FUSE_USB_CALIB; //0x0f0
    uint32_t FUSE_SKU_DIRECT_CONFIG; //0x0f4
    uint32_t FUSE_KFUSE_PRIVKEY_CTRL; //0x0f8
    uint32_t FUSE_PACKAGE_INFO; //0x0fc
    uint32_t FUSE_OPT_VENDOR_CODE; //0x100
    uint32_t FUSE_OPT_FAB_CODE; //0x104
    uint32_t FUSE_OPT_LOT_CODE_0; //0x108
    uint32_t FUSE_OPT_LOT_CODE_1; //0x10c
    uint32_t FUSE_OPT_WAFER_ID; //0x110
    uint32_t FUSE_OPT_X_COORDINATE; //0x114
    uint32_t FUSE_OPT_Y_COORDINATE; //0x118
    uint32_t FUSE_OPT_SEC_DEBUG_EN; //0x11c
    uint32_t FUSE_OPT_OPS_RESERVED; //0x120
    uint32_t FUSE_SATA_CALIB; //0x124
    uint32_t FUSE_GPU_IDDQ_CALIB; //0x128
    uint32_t FUSE_TSENSOR3_CALIB; //0x12c
    uint32_t FUSE_SKU_BOND_OUT_L; //0x130
    uint32_t FUSE_SKU_BOND_OUT_H; //0x134
    uint32_t FUSE_SKU_BOND_OUT_U; //0x138
    uint32_t FUSE_SKU_BOND_OUT_V; //0x13c
    uint32_t FUSE_SKU_BOND_OUT_W; //0x140
    uint32_t RESERVED_0x144;
    uint32_t FUSE_OPT_SUBREVISION; //0x148
    uint32_t FUSE_OPT_SW_RESERVED_0; //0x14c
    uint32_t FUSE_OPT_SW_RESERVED_1; //0x150
    uint32_t FUSE_TSENSOR4_CALIB; //0x154
    uint32_t FUSE_TSENSOR5_CALIB; //0x158
    uint32_t FUSE_TSENSOR6_CALIB; //0x15c
    uint32_t FUSE_TSENSOR7_CALIB; //0x160
    uint32_t FUSE_OPT_PRIV_SEC_EN; //0x164
    uint32_t FUSE_PKC_DISABLE; //0x168
    uint32_t RESERVED_0x16C;
    uint32_t RESERVED_0x170;
    uint32_t RESERVED_0x174;
    uint32_t RESERVED_0x178;
    uint32_t FUSE_FUSE2TSEC_DEBUG_DISABLE; //0x17c
    uint32_t FUSE_TSENSOR8_CALIB; //0x180 // <--WTF
    uint32_t FUSE_OPT_CP_BIN; //0x184
    uint32_t FUSE_OPT_GPU_FS; //0x188
    uint32_t FUSE_OPT_FT_BIN; //0x18c
    uint32_t RESERVED_0x190;
    uint32_t FUSE_SKU_BOND_OUT_X; //0x194
    uint32_t FUSE_APB2JTAG_DISABLE; //0x198
    uint32_t RESERVED_0x19C;
    uint32_t FUSE_PHY_FLOORSWEEP; //0x1a0
    uint32_t FUSE_PHY_FLOOR_ENABLE; //0x1a4
    uint32_t FUSE_ARM_CRYPT_DE_FEATURE; //0x1a8
    uint32_t FUSE_DENVER_MTS_DE_FEATURE; //0x1ac
    uint32_t FUSE_DIE_VERSION_OVERRIDE; //0x1b0
    uint32_t FUSE_TRIMMERS; //0x1b4
    uint32_t FUSE_DENVER_BOOT_SEC; //0x1b8
    uint32_t FUSE_DENVER_DFD_ACCESS; //0x1bc
    uint32_t FUSE_WOA_SKU_FLAG; //0x1c0
    uint32_t FUSE_ECO_RESERVE_1; //0x1c4
    uint32_t FUSE_GCPLEX_CONFIG_FUSE; //0x1c8
    uint32_t RESERVED_0x1CC;
    uint32_t RESERVED_0x1D0;
    uint32_t RESERVED_0x1D4;
    uint32_t RESERVED_0x1D8;
    uint32_t RESERVED_0x1DC;
    uint32_t RESERVED_0x1E0;
    uint32_t RESERVED_0x1E4;
    uint32_t RESERVED_0x1E8;
    uint32_t RESERVED_0x1EC;
    uint32_t RESERVED_0x1F0;
    uint32_t RESERVED_0x1F4;
    uint32_t RESERVED_0x1F8;
    uint32_t FUSE_SPARE_REALIGNMENT_REG; //0x1fc
    uint32_t FUSE_SPARE_BITS[0X40]; //0x200 - 0X2fc
} fuse_chip_registers_t;

void print_fuses( fuse_chip_registers_t *fuse_chip_registers );

#endif

