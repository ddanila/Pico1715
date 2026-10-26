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
void p1715_usb_disconnect(p1715_analyzer_usb *u){u->received=u->pending=u->sent=0;}
static void dispatch(p1715_analyzer_usb *u){
 uint8_t *q=u->request,*r=u->response,*p=r+28;
 p1715_analyzer *a=u->capture;
 uint32_t gen=get32(q+12),offset=get32(q+16),length=get32(q+20),count=0;
 uint8_t error=0,command=q[5];
 bool active=a->state>=P1715_LA_HOLD && a->state<=P1715_LA_LOW;
 if(q[4]!=1 || q[6] || q[7] || command<1 || command>4)error=1;
 else if(command!=4 && (offset || length))error=1;
 else if(command!=1 && gen!=u->generation)error=3;
 else if(command==2){
  if(active)error=2;
  else if(!u->ram || u->generation==UINT32_MAX)error=5;
  else if(p1715_analyzer_start(a,u->io,u->ram,u->capacity,u->clock_hz))error=5;
  else u->generation++;
 }else if(command==3){
  if(active)p1715_analyzer_stop(a);
  else if(a->state!=P1715_LA_DONE)error=2;
 }else if(command==4){
  uint32_t total=32+a->records*16;
  if(a->state!=P1715_LA_DONE)error=2;
  else if(!length || length>P1715_USB_CHUNK || offset>total || length>total-offset)error=4;
  else {memcpy(p,u->ram+offset,length);count=length;}
 }
 if(!error && command!=4){
  uint32_t fields[]={a->state,u->generation,a->records,a->state==P1715_LA_DONE?32+a->records*16:0,
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
 if(u->received==sizeof(u->request)){u->received=0;dispatch(u);}
}
const uint8_t *p1715_usb_output(p1715_analyzer_usb *u,size_t *size){*size=u->pending-u->sent;return u->response+u->sent;}
void p1715_usb_sent(p1715_analyzer_usb *u,size_t n){
 if(n>u->pending-u->sent)n=u->pending-u->sent;
 u->sent+=n;if(u->sent==u->pending)u->pending=u->sent=0;
}
