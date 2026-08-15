#include "types.h"
#include "t124.h"
#include "mem_dumper_usb_server.h"

typedef void (*ep1_x_imm_t)(void *buffer, u32 size, u32 *num_xfer);

void memcpy( void *dst, const void *src, size_t len ) {

    for ( size_t i = 0; i < len; i++ ) {
        ( (u8 *)dst )[i] = ( (u8 *)src )[i];
    }

}

static inline u32 read32(uintptr_t addr) {
    return *(vu32 *)addr;
}

static inline void write32(uintptr_t addr, u32 val) {
    *(vu32 *)addr = val;
}

static inline void or32(uintptr_t addr, u32 val) {
    write32(addr, read32(addr) | val);
}

void enter_rcm() {
    or32(PMC_BASE + PMC_SCRATCH0, PMC_SCRATCH0_MODE_RCM);
    or32(PMC_BASE + PMC_CNTRL, PMC_CNTRL_MAIN_RST);
}

__attribute__((section(".init")))
void entry() {

    u32 num_xfer;
    u32 to_send;
    struct mem_dumper_args_s args;
    u8 *buffer = (u8*)0x40020000;

    ep1_x_imm_t ep1_out_read_imm = (ep1_x_imm_t) ( BOOTROM_EP1_OUT_READ_IMM | 1 );
    ep1_x_imm_t ep1_in_write_imm = (ep1_x_imm_t) ( BOOTROM_EP1_IN_WRITE_IMM | 1 );

    ep1_out_read_imm( &args, sizeof(args), &num_xfer );
    
    while ( args.len > 0 ) {

        to_send = args.len > 0x1000? 0x1000 : args.len;
        
        memcpy( buffer, (void*)args.start, to_send );
        ep1_in_write_imm( buffer, to_send, &num_xfer );

        args.start += to_send;
        args.len -= to_send;
    }
    enter_rcm();

}

