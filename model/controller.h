/* SPDX-License-Identifier: MIT */
#ifndef PICO1715_CONTROLLER_H
#define PICO1715_CONTROLLER_H
#include <stddef.h>
#include <stdint.h>
/* Functional field model: read requests advance bytes, not a flux/timing model.
 * Raw media order is cylinder, head, sector; IDs start at one. */
typedef struct {
  uint8_t *image;
  size_t image_size;
  unsigned cylinders, heads, sectors, size_code;
  unsigned cylinder, sector, data_field, pos, length;
  uint8_t field[1032], control, format, select, irq_enabled, pending, service;
  uint8_t vector, direction_pending, direction;
  uint8_t mark_vector, mark_enabled, mark_pending, mask_pending, irq_mask;
  uint8_t writable, write_active, write_sync, write_mark;
  unsigned write_pos, field_head, field_sector;
  uint8_t write_buffer[1026];
  uint64_t writes, rejected_writes;
  uint64_t cycle, next_index, fields, bytes, interrupts, steps;
} pico1715_controller;
int pico1715_mount(pico1715_controller *, uint8_t *, size_t,
                   unsigned cylinders, unsigned heads, unsigned sectors,
                   unsigned size_code);
void pico1715_reset(void *);
int pico1715_read(void *, uint16_t, uint8_t *);
void pico1715_write(void *, uint16_t, uint8_t);
void pico1715_tick(void *, uint64_t);
int pico1715_irq(void *);
uint8_t pico1715_ack(void *);
void pico1715_reti(void *);
#endif
