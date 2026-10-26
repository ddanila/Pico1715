/* SPDX-License-Identifier: MIT */
#include "analyzer_usb.h"
#include <string.h>
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(i*8));}
static uint32_t crc(const uint8_t *p,size_t n,uint32_t c){
 while(n--){c^=*p++;for(unsigned i=0;i<8;i++)c=(c>>1)^((c&1)?0xedb88320u:0);}
 return c;
}
void p1715_usb_init(p1715_analyzer_usb *u,p1715_analyzer *a,p1715_analyzer_io io,uint8_t *ram,size_t size,uint32_t hz){
 memset(u,0,sizeof(*u));memset(a,0,sizeof(*a));u->capture=a;u->io=io;u->ram=ram;u->capacity=size;u->clock_hz=hz;
 if(!ram)a->state=P1715_LA_ERROR;
}
void p1715_usb_reset_backend(p1715_analyzer_usb *u,p1715_reset_io io){
 if(u->reset_io.cancel)u->reset_io.cancel(u->reset_io.user);
 u->reset_io=io;
 if(io.cancel)io.cancel(io.user);
 u->reset_state=0;
}
static void reset_cancel(p1715_analyzer_usb *u,uint32_t reason){
 if(u->reset_state!=1 && u->reset_state!=2)return;
 if(u->reset_io.cancel)u->reset_io.cancel(u->reset_io.user);
 u->reset_state=4;u->reset_reason=reason;
 u->reset_released=(uint32_t)u->io.time_us(u->io.user);
}
void p1715_usb_poll(p1715_analyzer_usb *u){
 if(u->reset_state!=1 && u->reset_state!=2)return;
 uint64_t now=u->io.time_us(u->io.user);
 p1715_analyzer *a=u->capture;
 if(u->reset_state==1){
  if(now>=u->reset_deadline || a->state==P1715_LA_ERROR || a->state==P1715_LA_DONE || a->stopping){reset_cancel(u,2);return;}
  if(!(a->controls&P1715_LA_RUN) || (a->controls&P1715_LA_CLEAR)){u->reset_ready_at=0;return;}
  if(!u->reset_ready_at){u->reset_ready_at=now+1000;return;}
  if(now<u->reset_ready_at)return;
  if(!u->reset_io.start(u->reset_io.user)){reset_cancel(u,3);return;}
  u->reset_state=2;u->reset_asserted=(uint32_t)now;
 }
 if(u->reset_state==2 && (uint32_t)(now-u->reset_asserted)>=10 && !u->reset_io.active(u->reset_io.user)){
  u->reset_state=3;u->reset_released=(uint32_t)now;
 }
}
void p1715_usb_disconnect(p1715_analyzer_usb *u){reset_cancel(u,1);u->received=u->pending=u->sent=0;}
static void dispatch(p1715_analyzer_usb *u){
 uint8_t *q=u->request,*r=u->response,*p=r+28;
 p1715_analyzer *a=u->capture;
 uint32_t gen=get32(q+12),offset=get32(q+16),length=get32(q+20),count=0;
 uint8_t error=0,command=q[5];
 bool active=a->state>=P1715_LA_HOLD && a->state<=P1715_LA_LOW;
 if(q[4]!=1 || q[6] || q[7] || command<1 || command>9)error=1;
 else if(command!=4 && command!=5 && command!=8 && command!=9 && (offset || length))error=1;
 else if(command==5 && (offset || length!=24))error=1;
 else if((command==8 || command==9) && length)error=1;
 else if(command!=1 && command!=7 && gen!=u->generation)error=3;
 else if((command==2 || command==5) && (u->reset_state==1 || u->reset_state==2))error=2;
 else if(command==2){
  if(active)error=2;
  else if(!u->ram || u->generation==UINT32_MAX)error=5;
  else if(p1715_analyzer_start_trigger(a,u->io,u->ram,u->capacity,u->clock_hz,&u->trigger))error=5;
  else u->generation++;
 }else if(command==3){
  reset_cancel(u,4);
  if(active)p1715_analyzer_stop(a);
  else if(a->state!=P1715_LA_DONE)error=2;
 }else if(command==4){
  uint32_t total=(uint32_t)p1715_analyzer_header_size(a)+a->records*16;
  if(a->state!=P1715_LA_DONE)error=2;
  else if(!length || length>P1715_USB_CHUNK || offset>total || length>total-offset)error=4;
  else if(p1715_analyzer_read(a,offset,p,length))error=4;
  else count=length;
 }
 if(!error && (command==8 || command==9)){
  if(!u->reset_io.start || !u->reset_io.cancel || !u->reset_io.active)error=6;
  else if(offset!=u->reset_id)error=7;
  else if(u->reset_id==UINT32_MAX)error=5;
  else if(u->reset_state==1 || u->reset_state==2 || (command==9 && active))error=2;
  else if(command==9 && (!u->ram || u->generation==UINT32_MAX))error=5;
  else {
   u->reset_id++;u->reset_generation=u->generation;
   u->reset_requested=(uint32_t)u->io.time_us(u->io.user);
   u->reset_asserted=u->reset_released=u->reset_reason=0;u->reset_ready_at=0;
   if(command==9){
    if(p1715_analyzer_start_trigger(a,u->io,u->ram,u->capacity,u->clock_hz,&u->trigger)){
     u->reset_state=4;u->reset_reason=3;error=5;
    }else {u->generation++;u->reset_generation=u->generation;u->reset_state=1;
     u->reset_deadline=u->io.time_us(u->io.user)+100000;}
   }else if(u->reset_io.start(u->reset_io.user)){
    u->reset_state=2;u->reset_asserted=(uint32_t)u->io.time_us(u->io.user);
   }else {u->reset_state=4;u->reset_reason=3;error=6;}
  }
 }
 if(!error && command>=7){
  uint32_t fields[]={u->reset_io.start && u->reset_io.cancel && u->reset_io.active,
   u->reset_state,u->reset_id,u->reset_generation,u->reset_requested,u->reset_asserted,u->reset_released,u->reset_reason};
  for(unsigned i=0;i<8;i++)put32(p+4*i,fields[i]);
  count=sizeof(fields);
 }
 if(!error && command==5){
  p1715_trigger_config c={get32(q+24),get32(q+28),get32(q+32),get32(q+36),get32(q+40),get32(q+44)};
  if(active)error=2;
  else if(!p1715_trigger_valid(&c,u->capacity))error=4;
  else {u->trigger=c;memcpy(p,q+24,24);memset(p+24,0,24);put32(p+28,UINT32_MAX);put32(p+32,UINT32_MAX);count=48;}
 }
 if(!error && command==6){p1715_analyzer_trigger_info(a,p);count=48;}
 if(!error && command<=3){
  uint32_t fields[]={a->state,u->generation,a->records,a->state==P1715_LA_DONE?(uint32_t)p1715_analyzer_header_size(a)+a->records*16:0,
   a->fpga_dropped,a->local_dropped,a->filtered,a->retries,a->full,a->stopping};
  for(unsigned i=0;i<10;i++)put32(p+4*i,fields[i]);
  count=sizeof(fields);
 }
 memcpy(r,"P17R",4);r[4]=1;r[5]=command;r[6]=error;r[7]=0;
 memcpy(r+8,q+8,4);put32(r+12,u->generation);put32(r+16,offset);put32(r+20,count);
 put32(r+24,~crc(p,count,crc(r,24,UINT32_MAX)));
 u->sent=0;u->pending=28+count;
}
void p1715_usb_receive(p1715_analyzer_usb *u,uint8_t byte){
 if(u->pending)return;
 u->request[u->received++]=byte;
 if(u->received<=4 && memcmp(u->request,"P17Q",u->received)){
  u->received=byte=='P'?1:0;u->request[0]=byte;return;
 }
 if(u->received==24 && u->request[5]==5 && get32(u->request+20)==24)return;
 if(u->received==24 || u->received==48){u->received=0;dispatch(u);}
}
const uint8_t *p1715_usb_output(p1715_analyzer_usb *u,size_t *size){*size=u->pending-u->sent;return u->response+u->sent;}
void p1715_usb_sent(p1715_analyzer_usb *u,size_t n){
 if(n>u->pending-u->sent)n=u->pending-u->sent;
 u->sent+=n;if(u->sent==u->pending)u->pending=u->sent=0;
}
