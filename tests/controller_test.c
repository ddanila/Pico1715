/* SPDX-License-Identifier: MIT */
#include "../model/controller.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void out(pico1715_controller *c, unsigned p, unsigned d) {
  pico1715_write(c, (uint16_t)(0xa500 | p), (uint8_t)d);
}
static unsigned in(pico1715_controller *c, unsigned p) {
  uint8_t d = 0;
  assert(pico1715_read(c, (uint16_t)(0x5a00 | p), &d));
  return d;
}
static void arm(pico1715_controller *c, unsigned head) {
  out(c, 4, 0xa5); out(c, 4, 0xbb); (void)in(c, 2);
  out(c, 4, head ? 0x81 : 0x85);
}
int main(void) {
  uint8_t disk[2 * 2 * 1024], before[sizeof(disk)];
  memset(disk, 0x31, sizeof(disk)); memset(disk + 1024, 0x72, 1024);
  pico1715_controller c;
  assert(pico1715_mount(&c, disk, sizeof(disk)-1, 2, 2, 1, 3) < 0);
  assert(!pico1715_mount(&c, disk, sizeof(disk), 2, 2, 1, 3));
  out(&c, 0x20, 0xef); out(&c, 6, 4);
  assert(!(in(&c, 6) & 0xa1)); /* ready, track zero, protected */
  out(&c, 7, 0xcf); out(&c, 7, 0xe3);
  out(&c, 7, 0x12); out(&c, 7, 0x37); out(&c, 7, 0xfd);
  out(&c, 7, 0x83); arm(&c, 0);
  assert(pico1715_irq(&c)); assert(pico1715_ack(&c) == 0x12);
  assert(!pico1715_irq(&c)); pico1715_reti(&c);
  const uint8_t id[] = {0xa1,0xa1,0xa1,0xfe,0,0,1,3,0xda,0x4e};
  for (unsigned i = 0; i < sizeof(id); i++) assert(in(&c, 2) == id[i]);
  assert(in(&c, 2) == 0x4e); /* gap */
  arm(&c, 0);
  for (unsigned i = 0; i < 3; i++) assert(in(&c, 2) == 0xa1);
  assert(in(&c, 2) == 0xfb);
  for (unsigned i = 0; i < 1024; i++) assert(in(&c, 2) == 0x31);
  arm(&c, 1); for (unsigned i = 0; i < 5; i++) (void)in(&c, 2);
  assert(in(&c, 2) == 1); /* actual head in ID */
  arm(&c, 1); for (unsigned i = 0; i < 4; i++) (void)in(&c, 2);
  assert(in(&c, 2) == 0x72);
  out(&c, 5, 0x10); out(&c, 5, 0x83); out(&c, 7, 3);
  pico1715_tick(&c, 491600); assert(pico1715_irq(&c));
  assert(pico1715_ack(&c) == 0x10); pico1715_reti(&c);
  out(&c, 5, 3); pico1715_tick(&c, 983200); assert(!pico1715_irq(&c));
  out(&c, 4, 0xbf); out(&c, 4, 0x3f); out(&c, 4, 0xbf);
  assert(in(&c, 6) & 0x80); assert(c.cylinder == 1);
  out(&c, 4, 0x3f); out(&c, 4, 0xbf); assert(c.cylinder == 1);
  out(&c, 4, 0x1f); out(&c, 4, 0x9f); assert(c.cylinder == 0);
  memcpy(before, disk, sizeof(disk));
  out(&c, 4, 0xb4); out(&c, 0, 0xa1); out(&c, 0, 0xfb); out(&c, 4, 0xbf);
  assert(c.rejected_writes == 1 && !memcmp(disk, before, sizeof(disk)));
  /* A complete captured field can be replayed; protection still blocks it. */
  c.data_field = 0; arm(&c, 0); arm(&c, 0);
  uint8_t data[1030]; memcpy(data, c.field, sizeof(data));
  out(&c, 4, 0xb4);
  for (unsigned i = 0; i < sizeof(data); i++) out(&c, 0, data[i]);
  out(&c, 4, 0xbf); assert(c.writes == 0 && c.rejected_writes == 2);
  c.writable = 1; data[100] ^= 1;
  out(&c, 4, 0xb4);
  for (unsigned i = 0; i < sizeof(data); i++) out(&c, 0, data[i]);
  out(&c, 4, 0xbf); assert(c.writes == 0 && c.rejected_writes == 3);
  assert(!memcmp(disk, before, sizeof(disk)));
  out(&c, 0x20, 0xff); arm(&c, 0); assert(!(in(&c, 6) & 2));
  out(&c, 0x20, 0xef); out(&c, 6, 0); arm(&c, 0);
  assert(!(in(&c, 6) & 2)); /* unsupported density never supplies fields */
  pico1715_reset(&c); assert(c.image == disk && c.writable && !c.writes);
  assert(!pico1715_irq(&c) && c.control == 255 && c.select == 255);
  out(&c, 0x20, 0xef); out(&c, 4, 0xb4);
  for (unsigned i = 0; i < 50; i++) out(&c, 0, data[i]);
  pico1715_reset(&c); out(&c, 4, 0xbf);
  assert(!c.write_active && !memcmp(disk, before, sizeof(disk)));
  puts("controller contract tests passed");
}
