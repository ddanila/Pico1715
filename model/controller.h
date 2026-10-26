/* SPDX-License-Identifier: MIT */
#ifndef PICO1715_CONTROLLER_H
#define PICO1715_CONTROLLER_H
#include <stddef.h>
#include <stdint.h>
#define PICO1715_CLOCK_HZ 2458000u
#define PICO1715_BIT_RATE 250000u
typedef struct {
  unsigned enabled, no_wait, read_delay, write_delay, mark_delay, irq_delay;
  unsigned fifo_depth, drop_byte, corrupt_crc;
} pico1715_timing;
/* Field model with optional scheduled bytes and transaction waits; not flux.
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
  pico1715_timing timing;
  uint8_t rx[16], rx_count, rx_head, rx_last, stream_active, mark_latched;
  uint64_t rx_at[16];
  uint8_t prepared, prepared_data;
  uint64_t prepared_at;
  uint64_t next_byte, read_request, tx_ready, write_request, irq_due;
  unsigned read_pending, write_pending, tx_full;
  uint8_t tx_data;
  uint64_t arrivals, overruns, underflows, drops, max_read_age, latch_cycle;
  uint64_t tx_early, tx_late, last_tx, max_tx_interval;
} pico1715_controller;
int pico1715_mount(pico1715_controller *, uint8_t *, size_t,
                   unsigned cylinders, unsigned heads, unsigned sectors,
                   unsigned size_code);
void pico1715_reset(void *);
int pico1715_read(void *, uint16_t, uint8_t *);
/* Stage one queued byte without acknowledging a guest read or enlarging capacity. */
void pico1715_prepare_read(pico1715_controller *);
void pico1715_write(void *, uint16_t, uint8_t);
void pico1715_tick(void *, uint64_t);
int pico1715_irq(void *);
uint8_t pico1715_ack(void *);
void pico1715_reti(void *);
int pico1715_wait(void *, uint16_t, int write);
#endif
