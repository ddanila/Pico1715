/* SPDX-License-Identifier: MIT */
#ifndef P1715_CONTROLLER_USB_H
#define P1715_CONTROLLER_USB_H
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#define P1715_CONTROL_PAYLOAD 112u
/* One fixed request and response. Owned exclusively by the storage/USB core. */
typedef struct {
 uint8_t request[16],response[20+P1715_CONTROL_PAYLOAD];
 size_t received,pending,sent;
 bool waiting,discard;
} p1715_controller_usb;
void p1715_controller_usb_init(p1715_controller_usb *);
void p1715_controller_usb_poll(p1715_controller_usb *);
void p1715_controller_usb_receive(p1715_controller_usb *,uint8_t);
const uint8_t *p1715_controller_usb_output(p1715_controller_usb *,size_t *);
void p1715_controller_usb_sent(p1715_controller_usb *,size_t);
void p1715_controller_usb_disconnect(p1715_controller_usb *);
#endif
