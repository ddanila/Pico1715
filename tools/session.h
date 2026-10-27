/* SPDX-License-Identifier: MIT
 * Shared classic motherboard/card lifecycle, used by probes and interactive hosts.
 * The host owns memory and clocks. No UI scheduling or guest patches live here. */
#ifndef P1715_SESSION_H
#define P1715_SESSION_H
#include "machines/robotron1715/pc1715.h"
#include "../model/controller.h"
#ifdef PICO1715_COSIM
#include "cosim/bridge.h"
#ifdef P1715_FIRMWARE_COSIM
void firmware_cosim_start(int absent);
#endif
#endif
static inline int p1715_board_init(pc1715 *m) {
    pc1715_init(m);return pc1715_onboard_enable(m);
}
static inline int p1715_board_attach(pc1715 *m,pico1715_controller *c,int absent) {
#ifdef PICO1715_COSIM
    cosim_init(m,c);
#ifdef P1715_FIRMWARE_COSIM
    firmware_cosim_start(absent);
#else
    (void)absent;
#endif
    pc1715_card card={c,cosim_read,cosim_write,cosim_tick,cosim_irq,
        cosim_ack,cosim_reti,cosim_reset,cosim_wait};
#else
    (void)absent;
    pc1715_card card={c,pico1715_read,pico1715_write,pico1715_tick,pico1715_irq,
        pico1715_ack,pico1715_reti,pico1715_reset,pico1715_wait};
#endif
    return pc1715_attach(m,&card);
}
static inline void p1715_board_tick(pc1715 *m){pc1715_run(m,1);}
static inline void p1715_board_observe(void){
#ifdef PICO1715_COSIM
    cosim_observe();
#endif
}
#endif
