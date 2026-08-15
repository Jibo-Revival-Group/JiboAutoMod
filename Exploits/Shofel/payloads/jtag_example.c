#include "t124.h"
#include "types.h"

static inline u32 read32(uintptr_t addr) {
    return *(vu32 *)addr;
}

static inline void write32(uintptr_t addr, u32 val) {
    *(vu32 *)addr = val;
}

static inline void or32(uintptr_t addr, u32 val) {
    write32(addr, read32(addr) | val);
}

__attribute__(( section(".init") ))
void main() {

    
    u32 pirom_start_0 = 0x00010000;
    write32( SECURE_BOOT_BASE + SB_PIROM_START_0, pirom_start_0 );

    u32 sb_csr_0 = 0x00000010;
    write32( SECURE_BOOT_BASE + SB_CSR_0, sb_csr_0 );

    u32 sb_pfcfg_0 = read32( SECURE_BOOT_BASE + SB_PFCFG_0 );
    sb_pfcfg_0 &= 0xfffffff0;
    sb_pfcfg_0 |= 0xf;
    write32( SECURE_BOOT_BASE + SB_PFCFG_0, sb_pfcfg_0 );

    or32( APB_BASE + APB_MISC_PP_CONFIG_CTL_0, APB_MISC_PP_CONFIG_CTL_0_JTAG |
                                               APB_MISC_PP_CONFIG_CTL_0_TBE );
    while(1) {
        // Halt COP and wait for JTAG
        or32( FLOW_CTLR_BASE + FLOW_CTLR_HALT_COP_EVENTS_0,
                FLOW_CTLR_HALT_COP_FLOW_MODE_WAITEVENT |
                FLOW_CTLR_HALT_COP_JTAG );
    }
}

