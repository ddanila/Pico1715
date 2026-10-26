/* SPDX-License-Identifier: MIT */
#ifndef P1715_CARRIER_PANEL_H
#define P1715_CARRIER_PANEL_H
#include <stdbool.h>
#include <stdint.h>
typedef struct {
 bool pressed,latched,eject_pending,owns,safe;
 uint64_t pressed_at,next_status;
} p1715_carrier_panel;
/* Core 1 only. USB and panel serialize ownership of the control mailbox. */
void p1715_carrier_panel_step(p1715_carrier_panel *,uint64_t now,bool pressed,bool usb_owns);
#endif
