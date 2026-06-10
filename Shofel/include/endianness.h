#ifndef _ENDIANNESS_H_
#define _ENDIANNESS_H_

#if defined(__APPLE__)
    #include <machine/endian.h>
#elif defined(__linux__) || defined(__FreeBSD__)
    #include <endian.h>
#endif

#ifndef BSWAP32
    #define BSWAP32(x) __builtin_bswap32(x)
#endif

#if defined(__BYTE_ORDER__) && defined(__ORDER_BIG_ENDIAN__) && (__BYTE_ORDER__ == __ORDER_BIG_ENDIAN__)
    #define TO_LITTLE_ENDIAN(x) BSWAP32(x)
#elif defined(__BYTE_ORDER__) && defined(__ORDER_LITTLE_ENDIAN__) && (__BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__)
    #define TO_LITTLE_ENDIAN(x) (x)
#elif defined(BYTE_ORDER) && defined(BIG_ENDIAN) && (BYTE_ORDER == BIG_ENDIAN)
    #define TO_LITTLE_ENDIAN(x) BSWAP32(x)
#elif defined(BYTE_ORDER) && defined(LITTLE_ENDIAN) && (BYTE_ORDER == LITTLE_ENDIAN)
    #define TO_LITTLE_ENDIAN(x) (x)
#elif defined(_WIN32)
    #define TO_LITTLE_ENDIAN(x) (x)
#else
    #error "Unsupported byte order"
#endif


#endif
