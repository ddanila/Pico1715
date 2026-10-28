/* SPDX-License-Identifier: MIT */
#ifndef P1715_COMBINED_H
#define P1715_COMBINED_H
#include "analyzer.h"
typedef struct {
 p1715_analyzer capture;
 uint8_t *ram;
 size_t size;
 uint8_t frame[22],received,command;
 bool arm_after_clear,active;
 uint64_t now;
 uint32_t framing_errors;
} p1715_combined;
void p1715_combined_init(p1715_combined *,uint8_t *,size_t);
int p1715_combined_start(p1715_combined *,uint64_t);
void p1715_combined_stop(p1715_combined *);
void p1715_combined_reset(p1715_combined *);
/* True means reserved mailbox register consumed. Core 0 only. */
bool p1715_combined_request(p1715_combined *,unsigned,bool,uint8_t,uint8_t *,uint64_t);
#endif
