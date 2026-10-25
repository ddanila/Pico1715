/* SPDX-License-Identifier: MIT */
#ifndef PICO1715_SD_SPI_H
#define PICO1715_SD_SPI_H
#include <stdint.h>
int p1715_sd_init(void);
int p1715_sd_read(void *,uint32_t,uint8_t *);
int p1715_sd_write(void *,uint32_t,const uint8_t *);
#endif
