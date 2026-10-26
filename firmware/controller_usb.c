/* SPDX-License-Identifier: MIT */
#include "controller_usb.h"
#include "service.h"
#include "store.h"
#include <string.h>
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
static void put64(uint8_t *p,uint64_t v){put32(p,(uint32_t)v);put32(p+4,(uint32_t)(v>>32));}
static void reply(p1715_controller_usb *u,unsigned error,const p1715_control_status *s){
 uint8_t *p=u->response;memcpy(p,"P1CR",4);p[4]=1;p[5]=u->request[5];p[6]=(uint8_t)error;p[7]=0;
 memcpy(p+8,u->request+8,4);put32(p+12,s?P1715_CONTROL_PAYLOAD:0);
 if(s){
  const p1715_diagnostics *d=&s->diagnostics;
  uint32_t fields[]={d->state,d->dirty_blocks,d->storage_error,d->max_service_us,
   d->shutdown,d->shutdown_reason,d->backup,d->write_policy,d->dirty_limit,d->storage_busy};
  for(unsigned i=0;i<10;i++)put32(p+16+4*i,fields[i]);
  uint64_t wide[]={d->requests,d->reserve_us,d->shutdown_deadline,s->writes,s->rejected_writes,
   s->overruns,s->underflows,s->tx_overruns,s->tx_underruns};
  for(unsigned i=0;i<9;i++)put64(p+56+8*i,wide[i]);
 }
 size_t n=16+(s?P1715_CONTROL_PAYLOAD:0);put32(p+n,p1715_crc32(p,n));
 u->pending=n+4;u->sent=0;u->received=0;
}
void p1715_controller_usb_init(p1715_controller_usb *u){memset(u,0,sizeof(*u));}
void p1715_controller_usb_disconnect(p1715_controller_usb *u){
 u->received=u->pending=u->sent=0;
 if(u->waiting)u->discard=true; /* Submitted eject is never undone on disconnect. */
}
void p1715_controller_usb_receive(p1715_controller_usb *u,uint8_t b){
 if(u->pending || u->waiting)return;
 u->request[u->received++]=b;
 if(u->received==4 && memcmp(u->request,"P1CQ",4)){
  memmove(u->request,u->request+1,3);u->received=3;return;
 }
 if(u->received!=sizeof(u->request))return;
 if(u->request[4]!=1 || u->request[6] || u->request[7] ||
    get32(u->request+12)!=p1715_crc32(u->request,12)){reply(u,1,NULL);return;}
 unsigned cmd=u->request[5];
 if(cmd!=P1715_CONTROL_STATUS && cmd!=P1715_CONTROL_EJECT){reply(u,2,NULL);return;}
 if(!p1715_control_submit(cmd)){reply(u,4,NULL);return;}
 u->waiting=true;u->discard=false;
}
void p1715_controller_usb_poll(p1715_controller_usb *u){
 p1715_control_status status;int result;
 if(!u->waiting || !p1715_control_take(&status,&result))return;
 u->waiting=false;
 if(u->discard){u->received=0;u->discard=false;return;}
 reply(u,result?3:0,&status);
}
const uint8_t *p1715_controller_usb_output(p1715_controller_usb *u,size_t *n){
 *n=u->pending-u->sent;return u->response+u->sent;
}
void p1715_controller_usb_sent(p1715_controller_usb *u,size_t n){
 if(n>u->pending-u->sent)n=u->pending-u->sent;
 u->sent+=n;if(u->sent==u->pending)u->pending=u->sent=0;
}
