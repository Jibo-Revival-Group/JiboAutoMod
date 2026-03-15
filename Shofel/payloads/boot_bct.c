#include "types.h"
#include "t124.h"

typedef void (*do_bct_boot_t)( void );

void memcpy( void *dst, const void *src, size_t len ) {

    for ( size_t i = 0; i < len; i++ ) {
        ( (u8 *)dst )[i] = ( (u8 *)src )[i];
    }

}

__attribute__((section(".init")))
void entry() {

    memcpy( (void*) ( IRAM_END - IROM_LEN + 1 ), (void*) IROM_BEGIN, IROM_LEN );

    register do_bct_boot_t do_bct_boot = (do_bct_boot_t) ( BOOTROM_DO_BCT_BOOT | 1 );
    do_bct_boot();
    while(1);

}

