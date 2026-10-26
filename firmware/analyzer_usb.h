/* SPDX-License-Identifier: MIT */
#ifndef P1715_ANALYZER_USB_H
#define P1715_ANALYZER_USB_H
#include "analyzer.h"
#define P1715_USB_CHUNK 1024u
/* Wire commands: STATUS=1 ARM=2 STOP=3 READ=4 CONFIGURE=5 TRIGGER_STATUS=6 RESET_STATUS=7 RESET=8 ARM_RESET=9. State 0 means idle. */
/* Backend must autonomously release after a bounded pulse, even if polling stops.
   active reports the accessory command output, NOT the motherboard CPU reset. */
typedef struct {
 void *user;
 bool (*start)(void *);
 void (*cancel)(void *);
 bool (*active)(void *);
} p1715_reset_io;
typedef struct {
 p1715_reset_io reset_io;
 uint32_t reset_state,reset_id,reset_generation,reset_requested,reset_asserted,reset_released,reset_reason;
 uint64_t reset_deadline,reset_ready_at;
 p1715_analyzer *capture;
 p1715_analyzer_io io;
 uint8_t *ram;
 size_t capacity;
 uint32_t clock_hz,generation;
 p1715_trigger_config trigger;
 uint8_t request[48],response[28+P1715_USB_CHUNK];
 size_t received,pending,sent;
} p1715_analyzer_usb;
void p1715_usb_init(p1715_analyzer_usb *,p1715_analyzer *,p1715_analyzer_io,uint8_t *,size_t,uint32_t);
void p1715_usb_reset_backend(p1715_analyzer_usb *,p1715_reset_io);
void p1715_usb_poll(p1715_analyzer_usb *);
void p1715_usb_disconnect(p1715_analyzer_usb *);
/* Feed only when no response is pending. Bounded, nonblocking transport seam. */
void p1715_usb_receive(p1715_analyzer_usb *,uint8_t);
const uint8_t *p1715_usb_output(p1715_analyzer_usb *,size_t *);
void p1715_usb_sent(p1715_analyzer_usb *,size_t);
#endif
