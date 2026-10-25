/* SPDX-License-Identifier: MIT */
#ifndef PICO1715_COSIM_BRIDGE_H
#define PICO1715_COSIM_BRIDGE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
void cosim_init(void *machine, void *controller);
void cosim_reset(void *);
void cosim_tick(void *, uint64_t);
int cosim_wait(void *, uint16_t, int);
int cosim_read(void *, uint16_t, uint8_t *);
void cosim_write(void *, uint16_t, uint8_t);
int cosim_irq(void *);
uint8_t cosim_ack(void *);
void cosim_reti(void *);
void cosim_observe(void);
uint64_t cosim_requests(void);
uint64_t cosim_acks(void);
uint64_t cosim_returns(void);
#ifdef __cplusplus
}
#endif
#endif
