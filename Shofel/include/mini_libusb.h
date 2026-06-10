#ifndef _MINI_LIBUSB_H_
#define _MINI_LIBUSB_H_

#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <limits.h>

#include <libusb.h>

#define USB_CTRL_DEVICE_ENDPOINT_TO_HOST 0x82
#define USB_CTRL_GET_STATUS 0x00

#ifndef USB_BULK_TIMEOUT
#define USB_BULK_TIMEOUT 5000
#endif

typedef struct mini_usb_handle mini_usb_handle;

#if DEBUG
    #define DEBUG_MSG(fmt, ...) do { fprintf( stderr, "%s:%d:%s(): " fmt, \
                                __FILE__, __LINE__, __func__, ##__VA_ARGS__ ); } while(0)
#else
    #define DEBUG_MSG(fmt, ...) 
#endif

mini_usb_handle *usb_open_by_vid_pid( uint16_t vid, uint16_t pid, uint8_t wait );
int usb_close( mini_usb_handle *usb );
int usb_send_bulk_txn( mini_usb_handle *usb, uint32_t ep, uint32_t len, void *data );
int usb_send_control_txn( mini_usb_handle *usb, uint8_t bRequestType, uint8_t bRequest, uint16_t wValue, uint16_t wIndex, uint16_t len, uint8_t *data, int32_t timeout );

#endif
