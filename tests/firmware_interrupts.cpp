// SPDX-License-Identifier: MIT
// ROM-free phase sweep: production firmware, storage and board-level RTL.
#include "Vfirmware_cosim_top.h"
extern "C" {
#include "firmware/service.h"
#include "firmware/store.h"
#include "tools/firmware_host/host_hal.h"
}
#include <cassert>
#include <cstdio>
#include <cstring>
#include <initializer_list>
static Vfirmware_cosim_top rtl;
static pico1715_controller card;
static uint8_t disk[P1715_IMAGE_BYTES];
static unsigned cases;
static void pins(){rtl.gpio_out=host_outputs;rtl.gpio_dir=host_directions;rtl.eval();host_inputs=rtl.gpio_in;}
static void us(unsigned count=1){
 for(unsigned i=0;i<count;i++){
  host_time_us++;pins();p1715_service_step();pins();
  for(unsigned n=0;n<100;n++){
   rtl.clk100=0;rtl.eval();rtl.clk100=1;rtl.eval();
   assert(!rtl.fault && !rtl.contention);
  }
 }
}
static void idle(){
 rtl.transaction=0;rtl.iorq_n=rtl.rd_n=rtl.wr_n=1;
 rtl.obs_m1_n=rtl.obs_iorq_n=rtl.obs_mreq_n=rtl.obs_rd_n=1;
}
static uint8_t io(unsigned port,bool write,uint8_t value=0){
 auto before=p1715_status.requests;
 rtl.host_addr=port;rtl.host_wdata=value;rtl.transaction=1;
 rtl.iorq_n=0;rtl.rd_n=write;rtl.wr_n=!write;rtl.eval();
 unsigned waited=0;
 do{us();assert(++waited<80);}while(rtl.wait_pull_low);
 assert(p1715_status.requests==before+1);
 if(!write)assert(rtl.host_data_enable);
 auto result=rtl.host_rdata;idle();us(3);return result;
}
static void out(unsigned p,uint8_t v){(void)io(p,true,v);}
static uint8_t ack(){
 rtl.obs_m1_n=rtl.obs_iorq_n=0;us();
 assert(rtl.host_data_enable);uint8_t vector=rtl.host_rdata;
 us();idle();us();
 assert(card.service);
 return vector;
}
static void fetch(uint8_t op){
 rtl.obs_data=op;rtl.obs_m1_n=rtl.obs_mreq_n=rtl.obs_rd_n=0;us();
 idle();us();
}
static void reti(){fetch(0xed);fetch(0x4d);us();assert(!card.service);}
static uint64_t ticks(unsigned microseconds){return (uint64_t)microseconds*PICO1715_CLOCK_HZ/1000000;}
static void run(unsigned depth,int phase,unsigned index_service_us,bool data_field,unsigned read_pause_us=0){
 idle();rtl.reset_n=0;rtl.power_good=1;
 host_storage_init(disk,false);pins();assert(!p1715_service_init(&card,false));
 us(3);rtl.reset_n=1;us(3);
 // The one-byte reference is a diagnostic counterfactual, not production config.
 if(depth)card.timing.fifo_depth=depth;
 unsigned capacity=card.timing.fifo_depth?card.timing.fifo_depth:1;
 out(0x20,0xef);out(6,4);
 out(5,0x10);out(5,0x83);
 out(7,0x12);out(7,0x37);out(7,0xfd);out(7,0x83);
 if(data_field){out(4,0xa5);out(4,0x85);out(4,0xa5);}
 else out(4,0xa5);
 // Move index to either side of first-byte/mark arrival. Only disk phase is
 // injected; mailbox, IRQ selection/ack, RETI and receive data use real paths.
 // Report the resulting tick offset, including mailbox acquisition latency.
 card.next_index=card.cycle+ticks((unsigned)(128+phase));
 card.timing.mark_delay=(unsigned)ticks(96);
 out(4,0x85);
 uint8_t expected[1030];unsigned length=card.length;
 assert(length==(data_field?1030u:10u));memcpy(expected,card.field,length);
 uint8_t received[1030];unsigned reads=0,index_acks=0,mark_acks=0;
 int64_t offset_ticks=(int64_t)card.next_index-(int64_t)((card.next_byte+PICO1715_BIT_RATE-1)/PICO1715_BIT_RATE);
 auto deadline=host_time_us+80000;
 while(host_time_us<deadline && (reads<length || rtl.int_pull_low)){
  if(rtl.int_pull_low){
   uint8_t vector=ack();
   if(vector==0x10){index_acks++;us(index_service_us);reti();}
   else{
    assert(vector==0x12 && !mark_acks);mark_acks++;
    // Bounded mark-handler entry cost, including the mailbox's polling cost.
    us(16);
    while(reads<length){received[reads++]=io(2,false);us(read_pause_us);}
    out(4,0xa5);reti();
   }
  }else us();
 }
 assert(reads==length && index_acks<=1 && mark_acks==1);
 bool equal=!memcmp(expected,received,length);
 assert(!card.underflows && !card.tx_early && !card.tx_late);
 assert(!memcmp(card.image,disk,sizeof(disk)) && !card.writes);
 printf("{\"capacity\":%u,\"production\":%s,\"phase_us\":%d,\"index_service_us\":%u,\"read_pause_us\":%u,\"index_minus_mark_ticks\":%lld,\"length\":%u,\"overruns\":%llu,\"equal\":%s,\"index_acks\":%u,\"mark_acks\":%u}\n",
  capacity,depth?"false":"true",phase,index_service_us,read_pause_us,(long long)offset_ticks,length,
  (unsigned long long)card.overruns,equal?"true":"false",index_acks,mark_acks);
 cases++;
}
int main(){
 for(int phase=-64;phase<=64;phase++){
  run(1,phase,28,false);run(0,phase,28,false);
 }
 for(int phase:{-32,0,32})run(0,phase,28,true);
 run(0,-64,28,true,40); // sustained consumer deficit must remain detectable
 run(0,-4,160,false); // finite buffering must still report excessive latency
 printf("firmware interrupt phase sweep: %u cases\n",cases);
}
