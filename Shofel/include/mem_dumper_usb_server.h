#ifndef _MEM_DUMP_USB_SERVER_H_
#define _MEM_DUMP_USB_SERVER_H_

#if __arm__    
    typedef u32 uint32_t;
#else
    #include <stdint.h>
#endif

    struct mem_dumper_args_s {
        uint32_t start;
        uint32_t len;
    };

#endif

