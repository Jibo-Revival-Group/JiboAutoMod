#ifndef _ENDIANNESS_H_
#define _ENDIANNESS_H_

#if defined(__BYTE_ORDER__) && defined(__ORDER_BIG_ENDIAN__) && defined(__ORDER_LITTLE_ENDIAN__)
    #if __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__

        #if defined(__APPLE__)
            #include <libkern/OSByteOrder.h>
            #define TO_LITTLE_ENDIAN(x) OSSwapHostToLittleInt32(x)
        #else
            #include <byteswap.h>
            #define TO_LITTLE_ENDIAN(x) bswap_32(x)
        #endif

    #elif __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__

        #define TO_LITTLE_ENDIAN(x) x

    #endif
#elif defined(__BYTE_ORDER) && defined(__BIG_ENDIAN) && defined(__LITTLE_ENDIAN)
    #if __BYTE_ORDER == __BIG_ENDIAN

        #include <byteswap.h>
        #define TO_LITTLE_ENDIAN(x) bswap_32(x)

    #elif __BYTE_ORDER == __LITTLE_ENDIAN

        #define TO_LITTLE_ENDIAN(x) x

    #endif
#endif

#ifndef TO_LITTLE_ENDIAN
    #error "Unable to determine host byte order"
#endif

#endif
