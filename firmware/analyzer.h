/* SPDX-License-Identifier: MIT */
#ifndef P1715_ANALYZER_H
#define P1715_ANALYZER_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define P1715_LA_ACK (1u<<14)
#define P1715_LA_SYNC (1u<<16)
#define P1715_LA_CLEAR (1u<<17)
#define P1715_LA_RUN (1u<<21)
#define P1715_LA_CONTROLS (P1715_LA_ACK|P1715_LA_SYNC|P1715_LA_CLEAR|P1715_LA_RUN)
#define P1715_LA_RAM_OFFSET (1024u*1024u)
#define P1715_LA_RAM_SIZE (7u*1024u*1024u)
typedef struct {
 void *user;
 uint32_t (*pins)(void *);
 void (*controls)(void *,uint32_t);
 uint64_t (*time_us)(void *);
 void (*fence)(void *);
} p1715_analyzer_io;
enum {P1715_LA_HOLD=1,P1715_LA_REQUEST,P1715_LA_LOW,P1715_LA_DONE,P1715_LA_ERROR};
typedef struct {
 p1715_analyzer_io io;
 uint8_t *ram;
 size_t size;
 uint32_t state,controls,records,unique_records,local_dropped,fpga_dropped,filtered;
 uint32_t retries,duplicates,crc_errors,index_errors,clock_hz,last_sequence;
 bool stopping,full,have_last,terminal;
 unsigned received,consecutive_errors;
 uint64_t progress,release_at;
 uint8_t frame[22],last_record[16];
} p1715_analyzer;
int p1715_analyzer_start(p1715_analyzer *,p1715_analyzer_io,uint8_t *,size_t,uint32_t);
void p1715_analyzer_step(p1715_analyzer *);
void p1715_analyzer_stop(p1715_analyzer *);
#endif
