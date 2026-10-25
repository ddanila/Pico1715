// SPDX-License-Identifier: MIT
// Scripted host bus, production firmware + storage, unmodified board RTL.
#include "Vfirmware_cosim_top.h"
extern "C" {
#include "firmware/service.h"
#include "firmware/store.h"
#include "tools/firmware_host/host_hal.h"
}
#include <cassert>
#include <cstdio>
#include <cstring>
#include <csetjmp>
#include <initializer_list>
static Vfirmware_cosim_top rtl;
static pico1715_controller card;
static uint8_t original[P1715_IMAGE_BYTES];
static bool running;
static unsigned cases,delay_us,reset_at_write,rewrite_at_write,hook_calls,probes;
static uint64_t replies,case_start;
static unsigned power_cut;
static std::jmp_buf power_loss;
static void pins(){rtl.gpio_out=host_outputs;rtl.gpio_dir=host_directions;rtl.eval();host_inputs=rtl.gpio_in;}
static void us(unsigned count=1){
 for(unsigned i=0;i<count;i++){
  host_time_us++;pins();
  uint64_t before=p1715_status.requests;
  if(running)p1715_service_step();
  replies+=p1715_status.requests-before;pins();
  for(unsigned edge=0;edge<100;edge++){
   rtl.clk100=0;rtl.eval();rtl.clk100=1;rtl.eval();
   assert(!rtl.fault && !rtl.contention);
  }
 }
}
static void idle_bus(){
 rtl.transaction=0;rtl.iorq_n=rtl.rd_n=rtl.wr_n=1;
 rtl.obs_m1_n=rtl.obs_iorq_n=rtl.obs_mreq_n=rtl.obs_rd_n=1;
}
static void begin(unsigned port,bool write,uint8_t value=0){
 rtl.host_addr=port;rtl.host_wdata=value;rtl.transaction=1;
 rtl.iorq_n=0;rtl.rd_n=write;rtl.wr_n=!write;rtl.eval();
}
static uint8_t io(unsigned port,bool write,uint8_t value=0){
 uint64_t before=p1715_status.requests;begin(port,write,value);
 unsigned waited=0;
 do{us();assert(++waited<80);}while(rtl.wait_pull_low);
 assert(p1715_status.requests==before+1);
 if(!write)assert(rtl.host_data_enable);
 uint8_t result=rtl.host_rdata;
 idle_bus();us(3);
 assert(!(host_outputs&(1u<<14)) && !(host_directions&255));
 return result;
}
static void out(unsigned port,uint8_t value){(void)io(port,true,value);}
static uint8_t in(unsigned port){return io(port,false);}
static void reset(){
 rtl.reset_n=0;rtl.eval();
 assert(!rtl.host_data_enable && !rtl.wait_pull_low && !rtl.int_pull_low);
 us(3);
 assert(!(host_outputs&((1u<<21)|(1u<<14))) && !(host_directions&255));
 assert(!card.stream_active && !card.write_active);
 idle_bus();rtl.reset_n=1;us(3);
 assert(host_outputs&(1u<<21));
}
static int boot(bool cold){
 running=false;idle_bus();rtl.reset_n=0;rtl.power_good=1;
 if(cold)host_storage_power_cycle();
 pins();us(2);
 int result=p1715_service_init(&card,true);
 running=result==0;pins();
 if(running)reset();
 else {assert(!(host_outputs&(1u<<21)));assert(!rtl.host_data_enable && !rtl.wait_pull_low);}
 return result;
}
static void fresh(){
 case_start=replies;
 host_storage_init(original,false);hook_calls=probes=0;
 delay_us=reset_at_write=rewrite_at_write=power_cut=0;
 assert(!boot(false));
}
static void arm(){out(4,0xa5);out(4,0x85);}
static void prepare(){
 out(0x20,0xef);out(6,4);arm();
 const uint8_t id[]={0xa1,0xa1,0xa1,0xfe,0,0,1,3};
 for(uint8_t b:id)assert(in(2)==b);
 (void)in(2);(void)in(2);
}
static uint16_t crc(uint16_t c,uint8_t b){
 c^=(uint16_t)b<<8;
 for(unsigned i=0;i<8;i++)c=(uint16_t)((c<<1)^((c&0x8000)?0x1021:0));
 return c;
}
static void write_sector(uint8_t value,unsigned bytes=1030){
 uint8_t field[1030]={0xa1,0xa1,0xa1,0xfb};
 memset(field+4,value,1024);uint16_t sum=0xffff;
 for(unsigned i=0;i<1028;i++)sum=crc(sum,field[i]);
 field[1028]=sum>>8;field[1029]=(uint8_t)sum;
 out(4,0xb4);
 for(unsigned i=0;i<bytes;i++)out(0,field[i]);
 if(bytes==1030){us(28);out(4,0xbf);}
}
static void filled(const uint8_t *p,uint8_t value,unsigned count){
 for(unsigned i=0;i<count;i++)assert(p[i]==value);
}
static void untouched_tail(){assert(!memcmp(host_storage_image()+1024,original+1024,sizeof(original)-1024));}
static void record(const char *name,unsigned parameter){
 printf("{\"case\":\"%s\",\"parameter\":%u,\"requests\":%llu,\"sd_writes\":%llu,\"state\":%u,\"dirty\":%u,\"error\":%u,\"probes\":%u}\n",
 name,parameter,(unsigned long long)(replies-case_start),(unsigned long long)host_sd_writes,
 p1715_status.state,p1715_status.dirty_blocks,p1715_status.storage_error,probes);cases++;
}
static void startup_stall(bool writing,uint32_t){
 assert(!writing && !(host_outputs&(1u<<21)));
 us(100);assert(!rtl.host_data_enable && !rtl.wait_pull_low);hook_calls++;
}
static void stall(bool writing,uint32_t){
 if(!writing)return;
 hook_calls++;
 if(host_sd_writes==power_cut)std::longjmp(power_loss,1);
 if(host_sd_writes==reset_at_write){reset();assert(p1715_status.dirty_blocks>0);}
 if(host_sd_writes==rewrite_at_write){write_sector(0x96);assert(p1715_status.dirty_blocks==2);}
 for(unsigned elapsed=0;elapsed<delay_us;){
  // Real host requests keep completing while the worker is inside SD I/O.
  assert(in(4)==card.control);probes++;
  unsigned n=delay_us-elapsed<100?delay_us-elapsed:100;
  us(n);elapsed+=n;
 }
}
int main(){
 memset(original,0x31,sizeof(original));
 // Delays must not block the bus-serving core or lose persisted bytes.
 for(unsigned latency:{0u,100u,5000u,50000u}){
  fresh();prepare();write_sector(0x62);assert(card.writes==1 && !card.rejected_writes);
  delay_us=latency;host_io_hook=stall;p1715_storage_step();host_io_hook=nullptr;
  assert(!p1715_status.dirty_blocks && !p1715_status.storage_error && hook_calls==8);
  assert(!card.tx_late && !card.tx_early);filled(host_storage_image(),0x62,1024);untouched_tail();
  if(latency)assert(probes>0);record("sd-delay-us",latency);
  assert(!boot(true));filled(card.image,0x62,1024);
 }
 // Reset an active read mailbox and a partially transmitted sector.
 fresh();prepare();arm();begin(2,false);us(2);
 assert(rtl.wait_pull_low && (rtl.gpio_in&(1u<<13)));reset();
 assert(p1715_status.dirty_blocks==0);prepare();assert(in(4)==0x85);
 assert(!memcmp(host_storage_image(),original,sizeof(original)));record("reset-held-read",0);
 fresh();prepare();write_sector(0x62,100);assert(card.write_active);reset();
 p1715_storage_step();assert(!memcmp(card.image,original,sizeof(original)));
 assert(!memcmp(host_storage_image(),original,sizeof(original)));record("reset-partial-sector",100);
 // Warm resets at each of the eight SD operations retain pending dirty RAM.
 for(unsigned phase=1;phase<=8;phase++){
  fresh();prepare();write_sector(0x62);reset_at_write=phase;delay_us=100;
  host_io_hook=stall;p1715_storage_step();host_io_hook=nullptr;
  assert(!p1715_status.dirty_blocks && !p1715_status.storage_error);
  filled(host_storage_image(),0x62,1024);untouched_tail();record("host-reset-during-writeback",phase);
  assert(!boot(true));filled(card.image,0x62,1024);
 }
 // A newer sector arrives while an older block snapshot is being flushed.
 fresh();prepare();write_sector(0x62);rewrite_at_write=1;host_io_hook=stall;
 p1715_storage_step();host_io_hook=nullptr;
 assert(p1715_status.dirty_blocks==1);filled(card.image,0x96,1024);
 filled(host_storage_image(),0x62,512);filled(host_storage_image()+512,0x96,512);
 p1715_storage_step();assert(!p1715_status.dirty_blocks);
 filled(host_storage_image(),0x96,1024);untouched_tail();record("newer-write-during-snapshot",1);
 // Fail each journal operation; worker must stop, disable writes, and replay on reboot.
 for(unsigned phase=1;phase<=8;phase++){
  fresh();prepare();write_sector(0x62);host_fail_write=phase;delay_us=100;
  host_io_hook=stall;p1715_storage_step();host_io_hook=nullptr;us(2);
  assert(p1715_status.storage_error && p1715_status.dirty_blocks && !card.writable);
  uint64_t writes=host_sd_writes;assert(writes==phase);
  p1715_storage_step();assert(host_sd_writes==writes);
  uint64_t accepted=card.writes,rejected=card.rejected_writes;
  write_sector(0x96);assert(card.writes==accepted && card.rejected_writes==rejected+1);
  filled(card.image,0x62,1024);assert(host_sd_writes==writes);
  reset();assert(!card.writable);assert(in(6)&1); // protected after reset
  record("sd-write-failure",phase);
  assert(!boot(true));
  filled(card.image,phase>=3?0x62:0x31,512);
  filled(card.image+512,phase>=7?0x62:0x31,512);untouched_tail();
  uint8_t zero[512]={0};assert(!memcmp(host_storage_block(1),zero,512));
 }
 // Abrupt loss abandons the worker stack BEFORE a selected SD operation.
 // Only trivial automatic objects occur between setjmp and this C callback.
 for(unsigned phase=1;phase<=8;phase++){
  fresh();prepare();write_sector(0x62);power_cut=phase;host_io_hook=stall;
  if(!setjmp(power_loss)){p1715_storage_step();assert(false);}
  assert(!p1715_status.storage_error); // no graceful error return happened
  assert(!boot(true));
  filled(card.image,phase>=3?0x62:0x31,512);
  filled(card.image+512,phase>=7?0x62:0x31,512);untouched_tail();
  record("power-loss-before-sd-operation",phase);
 }
 // A recovery operation can fail too; retain the journal for a later retry.
 for(unsigned fault=0;fault<2;fault++){
  fresh();prepare();write_sector(0x62);host_fail_write=3;p1715_storage_step();
  uint8_t journal[512];memcpy(journal,host_storage_block(1),512);
  host_storage_power_cycle();
  if(fault)host_fail_write=1;else host_fail_read=3;
  assert(boot(false)==-1 && p1715_status.state==0xe2);
  assert(!memcmp(journal,host_storage_block(1),512));
  record("recovery-io-failure",fault);
  assert(!boot(true));filled(card.image,0x62,512);filled(card.image+512,0x31,512);
 }
 // Torn payload/target writes recover; torn journal metadata fails closed.
 for(unsigned phase=1;phase<=4;phase++){
  fresh();prepare();write_sector(0x62);host_fail_write=phase;host_torn_bytes=19;
  p1715_storage_step();assert(p1715_status.storage_error);
  uint8_t journal[512],before[1024];
  memcpy(journal,host_storage_block(1),512);memcpy(before,host_storage_image(),1024);
  int result=boot(true);
  if(phase==2 || phase==4){
   assert(result==-1 && p1715_status.state==0xe2 && host_sd_writes==0);
   assert(!memcmp(journal,host_storage_block(1),512));
   assert(!memcmp(before,host_storage_image(),1024));
  }
  else {assert(!result);filled(card.image,phase==3?0x62:0x31,512);filled(card.image+512,0x31,512);}
  untouched_tail();record("torn-sd-write",phase);
 }
 // Slow startup reads keep the FPGA disabled until the whole cache is loaded.
 fresh();host_storage_power_cycle();host_io_hook=startup_stall;
 assert(!boot(false));host_io_hook=nullptr;
 assert(hook_calls==1602 && !memcmp(card.image,original,sizeof(original)));
 record("startup-read-delay-us",100);
 // Startup failures never expose a half-loaded disk to the host.
 for(unsigned read:{1u,2u,3u,1602u}){
  fresh();host_storage_power_cycle();host_fail_read=read;
  assert(boot(false)==-1);assert(p1715_status.state==(read<=2?0xe2u:0xe3u));
  assert(host_sd_writes==0 && !memcmp(host_storage_image(),original,sizeof(original)));
  record("startup-read-failure",read);
 }
 printf("firmware fault suite PASS: %u cases, %llu mailbox replies\n",cases,(unsigned long long)replies);
}
