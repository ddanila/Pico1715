/* SPDX-License-Identifier: MIT. Shared by RP2350 firmware and RTL co-simulation. */
#include "analyzer.h"
#include <string.h>
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static void put32(uint8_t *p,uint32_t x){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(x>>(8*i));}
static uint16_t crc16(const uint8_t *p,unsigned n){
 uint16_t c=0xffff;
 while(n--){c^=(uint16_t)*p++<<8;for(unsigned i=0;i<8;i++)c=(uint16_t)((c&0x8000)?(c<<1)^0x1021:c<<1);}
 return c;
}
static void controls(p1715_analyzer *a){a->io.controls(a->io.user,a->controls);}
static void fail(p1715_analyzer *a){a->state=P1715_LA_ERROR;a->controls=0;controls(a);}
static void retry(p1715_analyzer *a,uint64_t now){
 a->retries++;
 if(++a->consecutive_errors>3){fail(a);return;}
 a->controls&=~(P1715_LA_ACK|P1715_LA_SYNC);controls(a);
 a->received=0;a->terminal=false;a->release_at=now+100;a->state=P1715_LA_HOLD;
}
void p1715_analyzer_stop(p1715_analyzer *a){
 if(a->state==P1715_LA_DONE || a->state==P1715_LA_ERROR)return;
 if(!a->stopping)a->progress=a->io.time_us(a->io.user);
 a->stopping=true;a->controls&=~P1715_LA_RUN;controls(a);
}
int p1715_analyzer_start(p1715_analyzer *a,p1715_analyzer_io io,uint8_t *ram,size_t size,uint32_t clock_hz){
 if(!a || !ram || size<48 || !clock_hz || !io.pins || !io.controls || !io.time_us || !io.fence)return -1;
 memset(a,0,sizeof(*a));a->io=io;a->ram=ram;a->size=size;a->clock_hz=clock_hz;
 memset(ram,0,32);a->state=P1715_LA_HOLD;a->controls=P1715_LA_CLEAR;controls(a);
 a->release_at=io.time_us(io.user)+100;
 return 0;
}
static bool commit(p1715_analyzer *a){
 uint8_t *f=a->frame,*r=f+4;
 uint16_t crc=crc16(f,20);
 if(f[20]!=(uint8_t)crc || f[21]!=(uint8_t)(crc>>8)){a->crc_errors++;return false;}
 if(f[1]!=1 || f[3]!=0)return false;
 if(f[0]==1 && f[2]==0){
  uint32_t seq=get32(r+12);
  if(a->have_last && seq==a->last_sequence){
   if(memcmp(r,a->last_record,16))return false;
   a->duplicates++;return true;
  }
  if(a->have_last && (int32_t)(seq-a->last_sequence)<=0)return false;
  if(a->records<(a->size-32)/16){memcpy(a->ram+32+(size_t)a->records*16,r,16);a->records++;}
  else {a->local_dropped++;a->full=true;p1715_analyzer_stop(a);}
  memcpy(a->last_record,r,16);a->last_sequence=seq;a->have_last=true;a->unique_records++;
 }else if(f[0]==2 && (f[2]&1) && !(f[2]&~3)){
  if(!a->stopping || get32(r+8)!=a->unique_records || get32(r+12)!=0x170)return false;
  a->fpga_dropped=get32(r);a->filtered=get32(r+4);
  uint64_t loss=(uint64_t)a->fpga_dropped+a->local_dropped;
  memcpy(a->ram,"P1715CY\0",8);a->ram[8]=1;a->ram[9]=0;a->ram[10]=16;a->ram[11]=0;
  put32(a->ram+12,a->clock_hz);put32(a->ram+16,a->records);
  put32(a->ram+20,loss>UINT32_MAX?UINT32_MAX:(uint32_t)loss);
  put32(a->ram+24,a->filtered);put32(a->ram+28,0x170);a->terminal=true;
 }else return false;
 a->io.fence(a->io.user); /* PSRAM contents must be visible before final ACK. */
 return true;
}
void p1715_analyzer_step(p1715_analyzer *a){
 if(a->state==P1715_LA_DONE || a->state==P1715_LA_ERROR)return;
 uint64_t now=a->io.time_us(a->io.user);
 if(a->state==P1715_LA_HOLD){
  if(now<a->release_at)return;
  bool initial=(a->controls&P1715_LA_CLEAR)!=0;
  a->controls&=~P1715_LA_CLEAR;a->controls|=P1715_LA_SYNC;
  if(initial && !a->stopping)a->controls|=P1715_LA_RUN;
  controls(a);a->state=P1715_LA_REQUEST;a->progress=now;return;
 }
 uint32_t pins=a->io.pins(a->io.user);bool req=(pins>>13)&1;
 if(a->state==P1715_LA_REQUEST && req){
  unsigned index=(pins>>8)&31;
  if(index!=a->received){a->index_errors++;retry(a,now);return;}
  a->frame[a->received++]=(uint8_t)pins;
  if(a->received==22){
   if(!commit(a)){retry(a,now);return;}
   a->consecutive_errors=0;
  }
  a->controls|=P1715_LA_ACK;controls(a);a->state=P1715_LA_LOW;a->progress=now;
 }else if(a->state==P1715_LA_LOW && !req){
  a->controls&=~P1715_LA_ACK;controls(a);a->progress=now;
  if(a->received==22){a->received=0;if(a->terminal){a->state=P1715_LA_DONE;return;}}
  a->state=P1715_LA_REQUEST;
 }else if((a->received || a->state==P1715_LA_LOW || a->stopping) && now-a->progress>10000){retry(a,now);}
}
