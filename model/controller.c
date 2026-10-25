/* SPDX-License-Identifier: MIT
 * Independent functional model derived from the 1715 schematic and ROM I/O.
 * No firmware patches or guest-memory access. See docs/classic-controller.md.
 */
#include "controller.h"
#include <string.h>

static uint16_t crc_byte(uint16_t crc, uint8_t b) {
  crc ^= (uint16_t)b << 8;
  for (unsigned i = 0; i < 8; i++)
    crc = (uint16_t)((crc << 1) ^ ((crc & 0x8000) ? 0x1021 : 0));
  return crc;
}
static int selected(const pico1715_controller *c) {
  /* One mounted drive: latch input D4 routes to /SE0. Low nibble is /LCK. */
  return c->image && !(c->select & 0x10);
}
void pico1715_reset(void *p) {
  pico1715_controller *c = p;
  c->cylinder = 0; c->sector = 1; c->data_field = 0;
  c->pos = c->length = 0; c->control = c->select = 0xff;
  c->format = c->irq_enabled = c->pending = c->service = 0;
  c->vector = c->direction_pending = c->direction = 0;
  c->mark_vector = c->mark_enabled = c->mark_pending = c->mask_pending = 0;
  c->irq_mask = 255;
  c->cycle = 0; c->next_index = 491600; /* 300 rpm at 2.458 MHz */
  c->fields = c->bytes = c->interrupts = c->steps = 0;
  c->write_active = c->write_sync = c->write_mark = 0;
  c->write_pos = c->field_head = c->field_sector = 0;
  c->writes = c->rejected_writes = 0;
}
int pico1715_mount(pico1715_controller *c, uint8_t *data, size_t n,
                   unsigned tracks, unsigned heads, unsigned sectors,
                   unsigned code) {
  if (!c || !data || !tracks || tracks > 255 || !heads || heads > 2 ||
      !sectors || sectors > 255 || code > 3 ||
      n != (size_t)tracks * heads * sectors * (128u << code)) return -1;
  memset(c, 0, sizeof(*c));
  c->image = data; c->image_size = n; c->cylinders = tracks;
  c->heads = heads; c->sectors = sectors; c->size_code = code;
  pico1715_reset(c);
  return 0;
}
static void field(pico1715_controller *c) {
  unsigned head = !(c->control & 4), n = 128u << c->size_code;
  c->pos = c->length = 0;
  /* This first model supports MFM 250 kbit/s only. Wrong format times out. */
  if (!selected(c) || (c->format & 0x14) != 4 || head >= c->heads) return;
  uint8_t *b = c->field;
  b[0] = b[1] = b[2] = 0xa1;
  b[3] = c->data_field ? 0xfb : 0xfe;
  unsigned end;
  if (c->data_field) {
    size_t offset = (((size_t)c->cylinder * c->heads + head) * c->sectors +
                     c->sector - 1) * n;
    memcpy(b + 4, c->image + offset, n);
    end = n + 4;
  } else {
    b[4] = c->cylinder; b[5] = head; b[6] = c->sector; b[7] = c->size_code;
    c->field_head = head; c->field_sector = c->sector;
    end = 8;
  }
  uint16_t crc = 0xffff;
  for (unsigned i = 0; i < end; i++) crc = crc_byte(crc, b[i]);
  b[end++] = crc >> 8; b[end++] = crc & 255;
  c->length = end;
  c->fields++;
  if (c->mark_enabled && !(c->irq_mask & 2)) c->mark_pending = 1;
  if (c->data_field) c->sector = c->sector % c->sectors + 1;
  c->data_field ^= 1;
}
int pico1715_read(void *p, uint16_t address, uint8_t *data) {
  pico1715_controller *c = p;
  switch (address & 255) {
  case 4: *data = c->control; return 1;
  case 2:
    *data = c->pos < c->length ? c->field[c->pos++] : 0x4e;
    c->bytes++;
    return 1;
  case 6:
    /* PIO1B direction E3: inputs 0,1,5,6,7; outputs 2,3,4.
     * /RDY, /WP, /FW, /T0 active low, MKE is inverted by board logic. */
    *data = (c->format & 0x1c) | 0x40 | (c->writable ? 0x20 : 0) |
            (c->cylinder ? 0x80 : 0) |
            (selected(c) ? 0 : 1) | (c->pos < c->length ? 2 : 0);
    return 1;
  default: return 0;
  }
}
static void write_byte(pico1715_controller *c, uint8_t data) {
  if (!c->write_mark) {
    if (data == 0xa1) c->write_sync++;
    else if (data == 0xfb && c->write_sync >= 3) c->write_mark = 1;
    else c->write_sync = 0;
  } else if (c->write_pos < sizeof(c->write_buffer))
    c->write_buffer[c->write_pos++] = data;
}
static void finish_write(pico1715_controller *c) {
  unsigned n = 128u << c->size_code;
  uint16_t crc = 0xffff;
  for (unsigned i = 0; i < 3; i++) crc = crc_byte(crc, 0xa1);
  crc = crc_byte(crc, 0xfb);
  if (c->write_pos >= n + 2)
    for (unsigned i = 0; i < n + 2; i++) crc = crc_byte(crc, c->write_buffer[i]);
  if (c->writable && selected(c) && c->write_mark && c->write_pos >= n + 2 &&
      !crc && c->field_sector && c->field_head < c->heads) {
    size_t offset = (((size_t)c->cylinder * c->heads + c->field_head) *
                      c->sectors + c->field_sector - 1) * n;
    memcpy(c->image + offset, c->write_buffer, n);
    c->writes++;
  } else c->rejected_writes++;
  c->data_field = 0; c->sector = c->sector % c->sectors + 1;
  c->write_active = 0;
}
void pico1715_write(void *p, uint16_t address, uint8_t data) {
  pico1715_controller *c = p;
  unsigned port = address & 255;
  if (port >= 0x20 && port <= 0x23) { c->select = data; return; }
  if (port == 0 && c->write_active) write_byte(c, data);
  else if (port == 5) {
    if (!(data & 1)) c->vector = data;
    else if ((data & 15) == 3 || (data & 15) == 7) {
      c->irq_enabled = data >> 7;
      if (!c->irq_enabled) c->pending = 0;
    }
  } else if (port == 7) {
    if (c->direction_pending) { c->direction = data; c->direction_pending = 0; }
    else if (c->mask_pending) { c->irq_mask = data; c->mask_pending = 0; }
    else if (data == 0xcf) c->direction_pending = 1;
    else if (!(data & 1)) c->mark_vector = data;
    else if ((data & 15) == 7 || (data & 15) == 3) {
      c->mark_enabled = data >> 7;
      if (!c->mark_enabled) c->mark_pending = 0;
      if ((data & 15) == 7 && (data & 16)) c->mask_pending = 1;
    }
  } else if (port == 6) c->format = data;
  else if (port == 4) {
    if ((c->control & 1) && !(data & 1)) {
      c->write_active = 1; c->write_pos = 0;
      c->write_sync = c->write_mark = 0;
    } else if (!(c->control & 1) && (data & 1) && c->write_active)
      finish_write(c);
    if ((c->control & 0x80) && !(data & 0x80) && selected(c)) {
      if (data & 0x20) { if (c->cylinder + 1 < c->cylinders) c->cylinder++; }
      else if (c->cylinder) c->cylinder--;
      c->steps++; c->sector = 1; c->data_field = 0;
    }
    uint8_t old = c->control;
    c->control = data;
    /* MK low arms mark acquisition; BB/A5 housekeeping doesn't consume fields. */
    if ((data & 0x39) == 1 && !(data & 2) && old != data) field(c);
  }
}
void pico1715_tick(void *p, uint64_t cycle) {
  pico1715_controller *c = p;
  c->cycle = cycle;
  if (cycle >= c->next_index) {
    c->next_index = cycle + 491600;
    if (selected(c) && c->irq_enabled && !c->service) c->pending = 1;
  }
}
int pico1715_irq(void *p) {
  pico1715_controller *c = p;
  return ((c->irq_enabled && c->pending) ||
          (c->mark_enabled && c->mark_pending)) && !c->service;
}
uint8_t pico1715_ack(void *p) {
  pico1715_controller *c = p;
  c->service = 1;
  if (c->irq_enabled && c->pending) {
    c->pending = 0; c->interrupts++; return c->vector;
  }
  c->mark_pending = 0;
  return c->mark_vector;
}
void pico1715_reti(void *p) { ((pico1715_controller *)p)->service = 0; }
