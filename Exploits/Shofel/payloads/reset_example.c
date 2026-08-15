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

__attribute__((section(".init")))
void main() {
    or32(PMC_BASE + PMC_CNTRL, PMC_CNTRL_MAIN_RST);
}

