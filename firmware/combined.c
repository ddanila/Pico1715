/* SPDX-License-Identifier: MIT. Bounded combined mailbox endpoint; core 0 only. */
#include "combined.h"
#include <string.h>
#include <stdatomic.h>
static uint32_t pins(void *p){(void)p;return 0;}
static uint64_t now(void *p){return ((p1715_combined *)p)->now;}
static void fence(void *p){(void)p;atomic_thread_fence(memory_order_seq_cst);}
static void controls(void *p,uint32_t value){
 p1715_combined *c=p;
 if(!(value&(P1715_LA_RUN|P1715_LA_CLEAR))){c->command=2;c->arm_after_clear=false;}
}
void p1715_combined_init(p1715_combined *c,uint8_t *ram,size_t size){
 memset(c,0,sizeof(*c));c->ram=ram;c->size=size;
}
int p1715_combined_start(p1715_combined *c,uint64_t time){
 if(!c->ram || c->size<48 || (c->active && c->capture.state!=P1715_LA_DONE && c->capture.state!=P1715_LA_ERROR))return -1;
 c->now=time;
 if(p1715_analyzer_start(&c->capture,(p1715_analyzer_io){c,pins,controls,now,fence},c->ram,c->size,50000000))return -1;
 c->received=0;c->framing_errors=0;c->command=3;c->arm_after_clear=true;c->active=true;return 0;
}
void p1715_combined_stop(p1715_combined *c){
 if(!c->active)return;
 p1715_analyzer_stop(&c->capture);c->command=2;c->arm_after_clear=false;
}
void p1715_combined_reset(p1715_combined *c){
 /* Link restart retransmits the staged frame from byte zero. Full records are
    deduplicated by the analyzer; the capture itself survives host reset. */
 c->received=0;
}
static void failed(p1715_combined *c){
 c->framing_errors++;c->capture.state=P1715_LA_ERROR;c->command=2;c->arm_after_clear=false;c->received=0;
}
bool p1715_combined_request(p1715_combined *c,unsigned reg,bool write,uint8_t value,uint8_t *reply,uint64_t time){
 if(reg<12 || reg>15)return false;
 c->now=time;*reply=255;
 if(!write && reg==14){*reply=c->ram?0xa7:255;return true;}
 if(!write && reg==12){
  *reply=c->command;c->command=c->arm_after_clear?1:0;c->arm_after_clear=false;
  if(*reply==1){c->capture.state=P1715_LA_REQUEST;c->capture.controls=P1715_LA_RUN;}
  return true;
 }
 if(!write || (reg!=13 && reg!=15))return true;
 if(!c->active || c->capture.state==P1715_LA_HOLD || c->capture.state==P1715_LA_ERROR || c->capture.state==P1715_LA_DONE)return true;
 if(reg==13){
  // A new frame marker also safely restarts an interrupted partial frame.
  c->received=0;
 }else if(!c->received){failed(c);return true;}
 c->frame[c->received++]=value;
 if(c->received==22){
  c->received=0;
  if(!p1715_analyzer_frame(&c->capture,c->frame))failed(c);
 }
 return true;
}
