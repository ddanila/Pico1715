/* SPDX-License-Identifier: MIT */
#include "Vcycle_capture_top.h"
#include "session_capture.h"
extern "C" {
#include "sample.h"
}
#include <memory>
#include <vector>
#include <cstring>
static std::unique_ptr<VerilatedContext> context;
static std::unique_ptr<Vcycle_capture_top> rtl;
static std::vector<uint8_t> bytes;
static unsigned state,reason,capacity,limit,ticks,mask,used;
static void word(unsigned offset,uint32_t v){for(unsigned i=0;i<4;i++)bytes[offset+i]=(v>>(i*8))&255;}
static void edge(){
 rtl->clk=0;rtl->eval();rtl->clk=1;rtl->eval();
 if(rtl->read_valid){
  if(used+16>capacity){state=3;reason=4;return;}
  for(unsigned i=0;i<4;i++)word(used+i*4,rtl->read_record[i]);
  used+=16;
 }
 if(rtl->overflow||rtl->dropped||rtl->host_oe||rtl->wait_pull_low||rtl->int_pull_low||rtl->busrq_pull_low||rtl->nmi_pull_low||rtl->memdi_pull_low||rtl->reset_pull_low||rtl->ieo!=rtl->iei){state=3;reason=4;}
}
static void finish(unsigned why){
 if(state!=1)return;
 reason=why;rtl->enable=0;
 unsigned n=0;
 do{edge();n++;}while(state==1 && n<1024 && !(rtl->idle&&!rtl->queued&&!rtl->read_valid));
 if(n==1024){state=3;reason=4;}
 word(16,(used-32)/16);word(20,rtl->dropped);word(24,rtl->filtered);
 if(state==1)state=2;
}
extern "C" int p1715_capture_start(unsigned size,unsigned selected,unsigned clocks){
 if(state==1 || size<8192 || size>64*1024*1024 || (selected!=0x170 && selected!=0x3fe))return -1;
 try{bytes.assign(size,0);rtl.reset();if(!context)context=std::make_unique<VerilatedContext>();rtl=std::make_unique<Vcycle_capture_top>(context.get());}catch(...){state=3;return -2;}
 capacity=size;limit=clocks;ticks=0;mask=selected;used=32;reason=0;
 std::memcpy(bytes.data(),"P1715CY\0",8);word(8,1|(16<<16));word(12,PC1715_CLOCK_HZ*4);word(28,mask);
 rtl->card_reset_n=0;rtl->iei=1;rtl->enable=0;rtl->read_enable=0;rtl->sample=0x3fbf000000ULL;rtl->capture_mask=mask;
 rtl->clk=0;rtl->eval();rtl->clk=1;rtl->eval();
 rtl->card_reset_n=1;rtl->read_enable=1;rtl->enable=1;state=1;return 0;
}
extern "C" void p1715_capture_observe(void *ptr){
 if(state!=1)return;
 const uint64_t s=p1715_bus_sample((pc1715*)ptr);
 for(unsigned i=0;i<4 && state==1;i++){rtl->sample=s|((uint64_t)(i>=2)<<30);edge();}
 ticks++;
 /* Reserve the entire FIFO plus encoder pipeline before disabling acquisition. */
 if(state==1 && used+4096+128>=capacity)finish(2);
 else if(state==1 && limit && ticks>=limit)finish(3);
}
extern "C" void p1715_capture_stop(void){finish(1);}
extern "C" void p1715_capture_release(void){if(state==1)finish(1);rtl.reset();std::vector<uint8_t>().swap(bytes);state=reason=used=0;}
extern "C" unsigned p1715_capture_status(unsigned field){
 const unsigned values[]={state,reason,used,(used>=32?(used-32)/16:0),ticks,mask,capacity};
 return field<7?values[field]:0;
}
extern "C" const uint8_t *p1715_capture_data(void){return state==2?bytes.data():nullptr;}
