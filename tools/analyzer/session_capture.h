/* SPDX-License-Identifier: MIT */
#ifndef P1715_SESSION_CAPTURE_H
#define P1715_SESSION_CAPTURE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
int p1715_capture_start(unsigned bytes,unsigned mask,unsigned clocks);
void p1715_capture_stop(void);
void p1715_capture_release(void);
/* state: 0 empty, 1 acquiring, 2 complete, 3 failed. reason: 1 manual,2 size,3 time,4 fault */
unsigned p1715_capture_status(unsigned field);
const uint8_t *p1715_capture_data(void);
void p1715_capture_observe(void *machine);
#ifdef __cplusplus
}
#endif
#endif
