/* SPDX-License-Identifier: MIT */
#ifndef P1715_RESERVE_H
#define P1715_RESERVE_H
#include <stdbool.h>
#include <stdint.h>
/* PIM724 SP/CE, NOT the main 40-pin header or Qw/ST. */
enum {P1715_SUPPLY_OK_GPIO=32,P1715_RESERVE_OK_GPIO=33,P1715_RESERVE_PRESENT_GPIO=36};
typedef struct {
 uint64_t qualified_us,stable_since;
 unsigned reported;
 bool stable,seen,terminated,initialized;
} p1715_reserve;
/* qualified_us=0 disables READY. Nonzero requires a separate measured load-test
   qualification for this assembly, SD card, temperature and firmware build. */
void p1715_reserve_init(p1715_reserve *,uint64_t qualified_us);
void p1715_reserve_step(p1715_reserve *,uint64_t now,bool present,bool supply_ok,bool reserve_ok);
#endif
