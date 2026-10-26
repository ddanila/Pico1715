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
static void finalize(p1715_analyzer *a);
void p1715_analyzer_stop(p1715_analyzer *a){
 if(a->state==P1715_LA_DONE || a->state==P1715_LA_ERROR)return;
 if(!a->stopping)a->progress=a->io.time_us(a->io.user);
 if(a->trigger.enabled && !a->stop_reason)a->stop_reason=2;
 a->stopping=true;a->controls&=~P1715_LA_RUN;controls(a);
 // Acquisition has not started during the initial clear hold: no terminal frame will arrive.
 if(a->state==P1715_LA_HOLD && (a->controls&P1715_LA_CLEAR)){
  finalize(a);a->io.fence(a->io.user);a->state=P1715_LA_DONE;
 }
}
size_t p1715_analyzer_header_size(const p1715_analyzer *a){return a->trigger.enabled?80:32;}
bool p1715_trigger_valid(const p1715_trigger_config *c,size_t size){
 if(!c || c->enabled>1)return false;
 if(!c->enabled)return !c->kinds && !c->address && !c->data && !c->pre && !c->post;
 return size>=96 && c->kinds && !(c->kinds&~0x170u) && !(c->data&0xffff0000u) &&
        (uint64_t)c->pre+1+c->post<=(size-80)/16;
}
int p1715_analyzer_start(p1715_analyzer *a,p1715_analyzer_io io,uint8_t *ram,size_t size,uint32_t clock_hz){
 const p1715_trigger_config c={0};return p1715_analyzer_start_trigger(a,io,ram,size,clock_hz,&c);
}
int p1715_analyzer_start_trigger(p1715_analyzer *a,p1715_analyzer_io io,uint8_t *ram,size_t size,uint32_t clock_hz,const p1715_trigger_config *config){
 if(!p1715_trigger_valid(config,size) || !a || !ram || size<48 || !clock_hz || !io.pins || !io.controls || !io.time_us || !io.fence)return -1;
 memset(a,0,sizeof(*a));a->io=io;a->ram=ram;a->size=size;a->clock_hz=clock_hz;
 a->trigger=*config;a->trigger_index=a->trigger_sequence=UINT32_MAX;
 memset(ram,0,p1715_analyzer_header_size(a));a->state=P1715_LA_HOLD;a->controls=P1715_LA_CLEAR;controls(a);
 a->release_at=io.time_us(io.user)+100;
 return 0;
}
static uint32_t window_capacity(const p1715_analyzer *a){return a->trigger.pre+1+a->trigger.post;}
void p1715_analyzer_trigger_info(const p1715_analyzer *a,uint8_t *p){
 uint32_t fields[]={a->trigger.enabled,a->trigger.kinds,a->trigger.address,a->trigger.data,
  a->trigger.pre,a->trigger.post,a->triggered,a->trigger_index,a->trigger_sequence,
  a->omitted,a->post_collected,a->stop_reason};
 for(unsigned i=0;i<12;i++)put32(p+4*i,fields[i]);
}
int p1715_analyzer_read(const p1715_analyzer *a,uint32_t offset,uint8_t *out,size_t n){
 size_t header=p1715_analyzer_header_size(a),total=header+(size_t)a->records*16;
 if(a->state!=P1715_LA_DONE || offset>total || n>total-offset)return -1;
 while(n){
  size_t physical,chunk;
  if(offset<header){physical=offset;chunk=header-offset;}
  else{
   size_t relative=offset-header;
   physical=a->trigger.enabled?header+((a->head+relative/16)%window_capacity(a))*16+relative%16:offset;
   chunk=16-relative%16;
  }
  if(chunk>n)chunk=n;
  memcpy(out,a->ram+physical,chunk);out+=chunk;offset+=(uint32_t)chunk;n-=chunk;
 }
 return 0;
}
static void append(p1715_analyzer *a,const uint8_t *r){
 uint32_t slot=(a->head+a->records)%window_capacity(a);
 memcpy(a->ram+80+(size_t)slot*16,r,16);a->records++;
}
static void store_record(p1715_analyzer *a,const uint8_t *r){
 if(!a->trigger.enabled){
  if(a->records<(a->size-32)/16){memcpy(a->ram+32+(size_t)a->records*16,r,16);a->records++;}
  else {a->local_dropped++;a->full=true;p1715_analyzer_stop(a);}
  return;
 }
 if(a->stopping){a->omitted++;return;}
 if(!a->triggered){
  uint32_t address=(uint32_t)r[2]|(uint32_t)r[3]<<8;
  bool match=((a->trigger.kinds>>(r[0]>>4))&1) &&
   !((address^a->trigger.address)&(a->trigger.address>>16)) &&
   !((r[1]^a->trigger.data)&(a->trigger.data>>8));
  if(match){
   a->triggered=true;a->trigger_index=a->records;a->trigger_sequence=get32(r+12);append(a,r);
  }else{
   if(!a->trigger.pre){a->omitted++;return;}
   if(a->records==a->trigger.pre){a->head=(a->head+1)%window_capacity(a);a->records--;a->omitted++;}
   append(a,r);return;
  }
 }else{append(a,r);a->post_collected++;}
 if(a->post_collected==a->trigger.post){a->stop_reason=1;p1715_analyzer_stop(a);}
}
static void finalize(p1715_analyzer *a){
  uint64_t loss=(uint64_t)a->fpga_dropped+a->local_dropped;
  memcpy(a->ram,"P1715CY\0",8);a->ram[8]=a->trigger.enabled?2:1;a->ram[9]=0;a->ram[10]=16;a->ram[11]=0;
  put32(a->ram+12,a->clock_hz);put32(a->ram+16,a->records);
  put32(a->ram+20,loss>UINT32_MAX?UINT32_MAX:(uint32_t)loss);
  uint64_t intentional=(uint64_t)a->filtered+a->omitted;
  put32(a->ram+24,intentional>UINT32_MAX?UINT32_MAX:(uint32_t)intentional);put32(a->ram+28,0x170);if(a->trigger.enabled)p1715_analyzer_trigger_info(a,a->ram+32);a->terminal=true;
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
  if(a->unique_records==UINT32_MAX)return false;
  store_record(a,r);
  memcpy(a->last_record,r,16);a->last_sequence=seq;a->have_last=true;a->unique_records++;
 }else if(f[0]==2 && (f[2]&1) && !(f[2]&~3)){
  if(!a->stopping || get32(r+8)!=a->unique_records || get32(r+12)!=0x170)return false;
  a->fpga_dropped=get32(r);a->filtered=get32(r+4);
  finalize(a);
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
