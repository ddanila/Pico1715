/* SPDX-License-Identifier: MIT */
#ifndef P1715_SAMPLE_H
#define P1715_SAMPLE_H
#include "machines/robotron1715/pc1715.h"
/* Four illustrative samples per T state, not physical half-cycle WAIT timing. */
static inline uint64_t p1715_bus_sample(const pc1715 *m) {
 uint64_t p=m->cpu.pins,s=0x3fbf000000ULL|Z80_GET_ADDR(p)|((uint64_t)Z80_GET_DATA(p)<<16);
 const uint64_t pins[]={Z80_MREQ,Z80_IORQ,Z80_RD,Z80_WR,Z80_M1,Z80_RFSH};
 for(unsigned i=0;i<6;i++)if(p&pins[i])s&=~(1ULL<<(24+i));
 if(m->io_waiting)s&=~(1ULL<<32);
 if(p&Z80_INT)s&=~(1ULL<<33);
 return s;
}
#endif
