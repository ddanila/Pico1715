/* SPDX-License-Identifier: MIT */
#ifndef PICO1715_STORE_H
#define PICO1715_STORE_H
#include <stdint.h>
#define P1715_IMAGE_LBA 2048u
#define P1715_IMAGE_BLOCKS 1600u
#define P1715_IMAGE_BYTES (P1715_IMAGE_BLOCKS * 512u)
typedef struct {
 void *user;
 int (*read)(void *,uint32_t,uint8_t *);
 int (*write)(void *,uint32_t,const uint8_t *);
 int failed;
} p1715_store;
uint32_t p1715_crc32(const uint8_t *,unsigned);
int p1715_store_open(p1715_store *);
int p1715_store_read(p1715_store *,uint32_t,uint8_t *);
int p1715_store_write(p1715_store *,uint32_t,const uint8_t *);
#endif
