/* SPDX-License-Identifier: MIT */
#include "../model/controller.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void out(pico1715_controller *c, unsigned port, unsigned value) {
  pico1715_write(c, (uint16_t)port, (uint8_t)value);
}
static unsigned in(pico1715_controller *c, unsigned port) {
  uint8_t value = 0; assert(pico1715_read(c, (uint16_t)port, &value)); return value;
}
static void arm(pico1715_controller *c) { out(c,4,0xa5); out(c,4,0x85); }
static uint64_t byte_time(unsigned n) {
  return ((uint64_t)n * PICO1715_CLOCK_HZ * 8 + PICO1715_BIT_RATE - 1) / PICO1715_BIT_RATE;
}
int main(void) {
  uint8_t disk[1024]; memset(disk, 0x62, sizeof(disk));
  pico1715_controller c, split;
  assert(!pico1715_mount(&c,disk,sizeof(disk),1,1,1,3));
  c.timing.enabled=1;
  out(&c,0x20,0xef); out(&c,6,4); arm(&c);
  assert(pico1715_wait(&c,2,0));
  pico1715_tick(&c,78); assert(!(in(&c,6)&2)); assert(c.pos==0);
  pico1715_tick(&c,79); assert(in(&c,6)&2);
  assert(!pico1715_wait(&c,2,0)); assert(in(&c,2)==0xa1);
  pico1715_tick(&c,157); assert(c.pos==1 && pico1715_wait(&c,2,0));
  pico1715_tick(&c,158); assert(!pico1715_wait(&c,2,0));
  pico1715_tick(&c,236); /* real byte clock continues despite no CPU read */
  assert(c.pos==3 && c.overruns==1 && c.rx_count==1);
  assert(in(&c,2)==0xa1);
  pico1715_tick(&c,315); assert(in(&c,2)==0xfe);
  assert(in(&c,2)==0xfe && c.underflows==1); /* no magical next byte */
  split=c;
  pico1715_tick(&c,1000);
  for (unsigned tick=316;tick<=1000;tick++) pico1715_tick(&split,tick);
  assert(c.pos==split.pos && c.overruns==split.overruns && c.rx_count==split.rx_count);
  pico1715_reset(&c); c.timing.irq_delay=100;
  out(&c,0x20,0xef);out(&c,6,4);out(&c,7,0xcf);out(&c,7,0xe3);
  out(&c,7,0x12);out(&c,7,0x37);out(&c,7,0xfd);out(&c,7,0x83);arm(&c);
  pico1715_tick(&c,79); assert(!pico1715_irq(&c));
  pico1715_tick(&c,178); assert(!pico1715_irq(&c));
  pico1715_tick(&c,179); assert(pico1715_irq(&c));
  assert(pico1715_ack(&c)==0x12);assert(!pico1715_irq(&c));pico1715_reti(&c);
  arm(&c);pico1715_tick(&c,258);pico1715_reset(&c);pico1715_tick(&c,500);
  assert(!pico1715_irq(&c) && !c.stream_active && !c.rx_count);
  /* Preserve a valid encoded data field, then feed it to a clocked transmitter. */
  c.timing.enabled=0;out(&c,0x20,0xef);out(&c,6,4);arm(&c);arm(&c);
  uint8_t field[1030];memcpy(field,c.field,sizeof(field));
  pico1715_reset(&c);c.timing.enabled=1;c.writable=1;
  out(&c,0x20,0xef);c.field_sector=1;out(&c,4,0xb4);
  for(unsigned i=0;i<sizeof(field);i++) {
    assert(!pico1715_wait(&c,0,1));out(&c,0,field[i]);
    assert(pico1715_wait(&c,0,1));
    pico1715_tick(&c,byte_time(i+1));
  }
  out(&c,4,0xbf);assert(c.writes==1 && !c.tx_late && !c.tx_early);
  /* A lost producer deadline repeats the output latch, never freezes time. */
  out(&c,4,0xb4);pico1715_tick(&c,c.cycle+160);assert(c.tx_late==2);
  pico1715_reset(&c);assert(!c.write_active && !c.tx_full && !c.write_pending);
  assert(disk[0]==0x62 && disk[1023]==0x62);
  /* Read-ahead reserves existing capacity and counts only accepted CPU reads. */
  pico1715_reset(&c); c.timing.fifo_depth=2;
  out(&c,0x20,0xef);out(&c,6,4);arm(&c);
  pico1715_tick(&c,79);pico1715_prepare_read(&c);
  assert(c.prepared && !c.rx_count && !c.bytes && !c.max_read_age);
  pico1715_prepare_read(&c);assert(c.prepared && !c.bytes);
  pico1715_tick(&c,158);assert(c.prepared && c.rx_count==1);
  pico1715_tick(&c,236);assert(c.overruns==1 && c.rx_count==1);
  assert(!pico1715_wait(&c,2,0) && in(&c,2)==0xa1);
  assert(!c.prepared && c.bytes==1 && c.max_read_age==157);
  pico1715_prepare_read(&c);assert(c.prepared);
  out(&c,4,0xa5);assert(!c.prepared && !c.rx_count && !c.stream_active);
  out(&c,4,0x85);pico1715_tick(&c,315);pico1715_prepare_read(&c);
  assert(c.prepared);pico1715_reset(&c);assert(!c.prepared && !c.rx_count);
  puts("timed arrivals, waits, overrun, IRQ delay, reset and write-clock tests passed");
}
