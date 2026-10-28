// SPDX-License-Identifier: MIT
// Cooperative core-0/core-1 scheduling with wall-clock RTL while firmware waits.
#include "Vfirmware_cosim_top.h"
extern "C" {
#include "firmware/service.h"
#include "firmware/controller_usb.h"
#include "firmware/store.h"
#include "tools/firmware_host/host_hal.h"
}
#include <cassert>
#include <cstdio>
#include <cstring>
#include <ucontext.h>
#include <initializer_list>
static Vfirmware_cosim_top rtl;
static pico1715_controller card;
static uint8_t disk[P1715_IMAGE_BYTES];
static ucontext_t caller,cores[2];
static uint8_t stacks[2][128*1024];
static uint64_t due[2],calls[P1715_COST_COUNT],lock_waits,sd_waits;
static unsigned cost[P1715_COST_COUNT],sd_cost,current,owner=2,cases;
static bool worker_enabled,control_traffic;
static p1715_controller_usb control_usb;
static unsigned control_responses,control_worker_us,control_next_command=1;
static bool control_busy_seen;
static void control_visit();
static uint64_t max_latency,fault_at,fault_latency,late_replies,reset_replies;
static bool previous_ack;
static void pause(unsigned delay){
 due[current]=host_time_us+delay;
 assert(!swapcontext(&cores[current],&caller));
}
static void work(unsigned kind){assert(kind<P1715_COST_COUNT);calls[kind]++;if(cost[kind])pause(cost[kind]);}
static void lock(critical_section_t *,bool enter){
 if(enter){
  assert(owner!=current);
  while(owner!=2){lock_waits++;pause(1);}
  owner=current;
 }else{assert(owner==current);owner=2;}
}
static void sd(bool writing,uint32_t){if(writing && sd_cost){sd_waits++;pause(sd_cost);}}
static void core0(){for(;;){p1715_service_step();pause(1);}}
static void core1(){for(;;){if(control_traffic)control_visit();p1715_storage_step();pause(100);}}
static uint32_t control_get32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void control_visit(){
 assert(owner!=1); // USB work must never extend the image critical section.
 if(control_worker_us)pause(control_worker_us);
 p1715_controller_usb_poll(&control_usb);
 size_t n;const uint8_t *p=p1715_controller_usb_output(&control_usb,&n);
 if(n){
  if(!control_usb.sent){
   assert(n==132 && !p[6] && control_get32(p+128)==p1715_crc32(p,128));
   if(control_get32(p+52))control_busy_seen=true;
   if(control_get32(p+32)==P1715_SAFE)assert(!control_get32(p+20)&&!control_get32(p+52));
  }
  size_t sent=n>64?64:n;p1715_controller_usb_sent(&control_usb,sent);
  if(sent==n)control_responses++;
 }
 if(!control_usb.pending && !control_usb.waiting){
  uint8_t request[16]={'P','1','C','Q',1,(uint8_t)control_next_command};
  control_next_command=1;
  uint32_t crc=p1715_crc32(request,12);for(unsigned i=0;i<4;i++)request[12+i]=(uint8_t)(crc>>(8*i));
  for(uint8_t b:request)p1715_controller_usb_receive(&control_usb,b);
 }
}
static void pins(){
 bool ack=(host_outputs&(1u<<14))!=0;
 if(ack && !previous_ack){if(rtl.fault)late_replies++;if(!rtl.reset_n)reset_replies++;}
 previous_ack=ack;
 rtl.gpio_out=host_outputs;rtl.gpio_dir=host_directions;rtl.eval();host_inputs=rtl.gpio_in;
}
static void us(unsigned n=1){
 for(unsigned i=0;i<n;i++){
  host_time_us++;pins();
  for(unsigned c=0;c<2;c++)if((!c || worker_enabled) && host_time_us>=due[c]){
   current=c;assert(!swapcontext(&caller,&cores[c]));pins();
  }
  current=2;
  for(unsigned edge=0;edge<100;edge++){
   rtl.clk100=0;rtl.eval();rtl.clk100=1;rtl.eval();
   assert(!rtl.contention);
   if(rtl.fault && !fault_at)fault_at=host_time_us;
   if(rtl.fault)assert(!rtl.wait_pull_low && !rtl.host_data_enable);
  }
 }
}
static void idle(){
 rtl.transaction=0;rtl.iorq_n=rtl.rd_n=rtl.wr_n=1;
 rtl.obs_m1_n=rtl.obs_iorq_n=rtl.obs_mreq_n=rtl.obs_rd_n=1;
}
static void begin(unsigned port,bool write,uint8_t value){
 rtl.host_addr=port;rtl.host_wdata=value;rtl.transaction=1;
 rtl.iorq_n=0;rtl.rd_n=write;rtl.wr_n=!write;rtl.eval();
}
static bool io(unsigned port,bool write,uint8_t &value){
 uint64_t before=p1715_status.requests,start=host_time_us;
 begin(port,write,value);unsigned waited=0;
 do{us();assert(++waited<200);}while(rtl.wait_pull_low);
 bool ok=!rtl.fault;
 if(ok){
  assert(p1715_status.requests==before+1);
  if(!write){assert(rtl.host_data_enable);value=rtl.host_rdata;}
  if(host_time_us-start>max_latency)max_latency=host_time_us-start;
 }else{assert(!rtl.host_data_enable);if(!fault_latency)fault_latency=host_time_us-start;}
 idle();us(3);return ok;
}
static bool out(unsigned port,uint8_t value){return io(port,true,value);}
static bool in(unsigned port,uint8_t &value){return io(port,false,value);}
static void fresh(){
 host_cost_hook=nullptr;host_lock_hook=nullptr;p1715_background_hook(nullptr);control_traffic=false;
 p1715_controller_usb_init(&control_usb);control_responses=control_worker_us=0;control_next_command=1;control_busy_seen=false;idle();rtl.reset_n=0;rtl.power_good=1;
 host_storage_init(disk,false);pins();assert(!p1715_service_init(&card,true));
 memset(cost,0,sizeof(cost));memset(calls,0,sizeof(calls));sd_cost=0;
 owner=current=2;worker_enabled=false;late_replies=reset_replies=0;previous_ack=false;lock_waits=sd_waits=max_latency=fault_at=fault_latency=0;
 for(unsigned c=0;c<2;c++){
  assert(!getcontext(&cores[c]));cores[c].uc_stack.ss_sp=stacks[c];
  cores[c].uc_stack.ss_size=sizeof(stacks[c]);cores[c].uc_link=nullptr;
  makecontext(&cores[c],c?core1:core0,0);due[c]=host_time_us;
 }
 host_cost_hook=work;host_lock_hook=lock;host_io_hook=sd;
 us(3);rtl.reset_n=1;us(3);
 assert(out(0x20,0xef));assert(out(6,4));
}
static bool arm(){return out(4,0xa5) && out(4,0x85);}
static bool read_field(bool &equal){
 uint8_t expected[1030],actual[1030];unsigned length=card.length;
 assert(length==10 || length==sizeof(expected));memcpy(expected,card.field,length);
 for(unsigned i=0;i<length;i++)if(!in(2,actual[i])){equal=false;return false;}
 equal=!memcmp(expected,actual,length);return out(4,0xa5);
}
static uint16_t crc(uint16_t c,uint8_t b){
 c^=(uint16_t)b<<8;for(unsigned i=0;i<8;i++)c=(uint16_t)((c<<1)^((c&0x8000)?0x1021:0));return c;
}
static bool write_sector(uint8_t value=0x62){
 uint8_t field[1030]={0xa1,0xa1,0xa1,0xfb};memset(field+4,value,1024);
 uint16_t sum=0xffff;for(unsigned i=0;i<1028;i++)sum=crc(sum,field[i]);
 field[1028]=sum>>8;field[1029]=(uint8_t)sum;
 if(!out(4,0xb4))return false;
 for(uint8_t b:field)if(!out(0,b))return false;
 us(32);return out(4,0xbf);
}
static void seed_writeback(){
 assert(arm());bool equal;assert(read_field(equal) && equal);
 assert(write_sector());assert(card.writes==1 && p1715_status.dirty_blocks==2);
 // Let subsequent measurements isolate the stressed operation, not setup.
 card.overruns=card.underflows=card.tx_early=card.tx_late=0;max_latency=0;
 memset(calls,0,sizeof(calls));
}
static void record(const char *name,unsigned delay,bool complete,bool equal){
 printf("{\"case\":\"%s\",\"delay_us\":%u,\"complete\":%s,\"equal\":%s,\"fault\":%s,\"max_request_us\":%llu,\"fault_release_us\":%llu,\"overruns\":%llu,\"underflows\":%llu,\"tx_underruns\":%llu,\"tx_overruns\":%llu,\"lock_wait_us\":%llu,\"sd_waits\":%llu,\"shutdown\":%u,\"dirty\":%u,\"storage_error\":%u,\"late_replies\":%llu,\"reset_replies\":%llu,\"cost_calls\":[",
  name,delay,complete?"true":"false",equal?"true":"false",rtl.fault?"true":"false",
  (unsigned long long)max_latency,(unsigned long long)fault_latency,(unsigned long long)card.overruns,(unsigned long long)card.underflows,
  (unsigned long long)card.tx_late,(unsigned long long)card.tx_early,
  (unsigned long long)lock_waits,(unsigned long long)sd_waits,
  p1715_status.shutdown,p1715_status.dirty_blocks,p1715_status.storage_error,
  (unsigned long long)late_replies,(unsigned long long)reset_replies);
 for(unsigned i=0;i<P1715_COST_COUNT;i++)printf("%s%llu",i?",":"",(unsigned long long)calls[i]);
 puts("]}");cases++;
}
static void sweep(const char *name,unsigned kind,unsigned delay){
 fresh();seed_writeback();cost[kind]=delay;sd_cost=5000;worker_enabled=true;
 bool equal=false,complete=arm();
 // Consume the ID then the following data field to exercise full-length load.
 if(complete)complete=read_field(equal);
 if(complete && equal){complete=arm();if(complete)complete=read_field(equal);}
 record(name,delay,complete,equal);
}
static void write_sweep(const char *name,unsigned kind,unsigned delay){
 fresh();seed_writeback();worker_enabled=true;sd_cost=5000;cost[kind]=delay;
 bool complete=write_sector(0x96),equal=card.writes==2;
 for(unsigned i=0;i<1024;i++)equal=equal && card.image[i]==0x96;
 record(name,delay,complete,equal);
}
static void reset_held(){
 fresh();seed_writeback();worker_enabled=true;sd_cost=5000;cost[P1715_COST_READ]=100;
 assert(arm());begin(2,false,0);
 unsigned waited=0;while(!calls[P1715_COST_READ]){us();assert(++waited<60);}
 assert(rtl.wait_pull_low);
 rtl.reset_n=0;rtl.eval();assert(!rtl.wait_pull_low && !rtl.host_data_enable);
 us(120);assert(reset_replies==0);assert(!(host_outputs&(1u<<14)) && !(host_directions&255));
 idle();memset(cost,0,sizeof(cost));rtl.reset_n=1;us(5);
 uint8_t value=0;assert(in(4,value) && value==0xff);
 assert(!card.stream_active && !card.rx_count && p1715_status.dirty_blocks);
 assert(out(0x20,0xef));assert(out(6,4));
 assert(arm());bool equal;assert(read_field(equal) && equal);
 record("reset-during-read",100,true,true);
}
static void watchdog(){
 fresh();seed_writeback();worker_enabled=true;sd_cost=5000;cost[P1715_COST_READ]=100;
 assert(arm());uint8_t value=0;uint64_t start=host_time_us;
 assert(!in(2,value));assert(fault_at-start>=81 && fault_at-start<=84);
 us(120);assert(late_replies==0);assert(rtl.fault && !rtl.wait_pull_low && !rtl.host_data_enable);
 // A reply to an expired request must not be left driving the mailbox.
 assert(!(host_outputs&(1u<<14)) && !(host_directions&255));
 record("watchdog-held-read",100,false,false);
 rtl.reset_n=0;us(5);idle();memset(cost,0,sizeof(cost));rtl.reset_n=1;us(5);
 assert(!rtl.fault);assert(in(4,value) && value==0xff);
 assert(out(0x20,0xef));assert(out(6,4));assert(arm());
 bool equal;assert(read_field(equal) && equal);
 record("watchdog-reset-recovery",0,true,true);
}
static void watchdog_write(){
 fresh();seed_writeback();worker_enabled=true;sd_cost=5000;cost[P1715_COST_COMMIT]=100;
 assert(!write_sector(0x96));us(120);
 assert(rtl.fault && !late_replies && card.writes==1);
 for(unsigned i=0;i<1024;i++)assert(card.image[i]==0x62);
 record("watchdog-late-commit",100,false,false);
}
static void watchdog_lock(){
 fresh();seed_writeback();worker_enabled=true;sd_cost=5000;cost[P1715_COST_SNAPSHOT]=128;
 us(5);assert(owner==1);
 uint8_t value=0;assert(!in(4,value));us(150);
 assert(rtl.fault && !late_replies && lock_waits);
 record("watchdog-lock-contention",128,false,false);
}
static void shutdown(){
 fresh();seed_writeback();worker_enabled=true;sd_cost=5000;
 cost[P1715_COST_SNAPSHOT]=40;us(5);
 p1715_shutdown_command=P1715_EJECT;
 unsigned elapsed=0;while(p1715_status.shutdown==P1715_RUNNING){us();assert(++elapsed<100);}
 assert(p1715_status.shutdown==P1715_DRAINING);
 assert(!rtl.wait_pull_low && !rtl.host_data_enable && !rtl.int_pull_low);
 while(p1715_status.shutdown==P1715_DRAINING){us(100);assert((elapsed+=100)<100000);}
 assert(p1715_status.shutdown==P1715_SAFE && !p1715_status.dirty_blocks && !p1715_status.storage_busy);
 assert(!memcmp(card.image,host_storage_image(),sizeof(disk)));
 for(unsigned i=0;i<1024;i++)assert(host_storage_image()[i]==0x62);
 assert(!memcmp(host_storage_image()+1024,disk+1024,sizeof(disk)-1024));
 record("eject-during-contended-writeback",40,true,true);
}
static void control_stress(unsigned snapshot,unsigned usb_delay,bool eject){
 fresh();seed_writeback();worker_enabled=true;sd_cost=5000;
 control_traffic=true;control_worker_us=usb_delay;control_next_command=eject?2:1;
 p1715_background_hook(control_visit);cost[P1715_COST_SNAPSHOT]=snapshot;
 bool equal=false,complete=true;
 if(eject){
  unsigned elapsed=0;while(p1715_status.shutdown!=P1715_SAFE){us(100);assert((elapsed+=100)<200000);}
  assert(!p1715_status.storage_busy && !p1715_status.dirty_blocks);
  assert(!rtl.wait_pull_low && !rtl.host_data_enable && !rtl.int_pull_low);
  equal=!memcmp(card.image,host_storage_image(),sizeof(disk));assert(equal);
 }else{
  for(unsigned i=0;i<8 && complete;i++){
   complete=arm();if(complete)complete=read_field(equal);
   if(!equal)break;
  }
 }
 unsigned elapsed=0;while(!control_responses){us(100);assert((elapsed+=100)<200000);}
 if(snapshot<=8 && !eject)assert(control_responses>10 && control_busy_seen);
 if(eject)assert(control_busy_seen);
 if(snapshot<=8)assert(complete && equal && !rtl.fault && !card.overruns && !card.tx_late);
 else assert(rtl.fault || card.overruns || !equal); // Deliberate scheduling overload remains observable.
 printf("control responses=%u worker_delay=%u eject=%u\n",control_responses,usb_delay,eject);
 record(eject?"usb-eject":"usb-status-flood",snapshot,complete,equal);
}
#if P1715_COMBINED
static p1715_control_status trace_command(unsigned cmd){
 assert(p1715_control_submit(cmd));p1715_control_status status;int result;
 unsigned waited=0;while(!p1715_control_take(&status,&result)){us(10);assert((waited+=10)<100000);}
 assert(!result);return status;
}
static void combined_capture(bool delayed){
 fresh();
 if(delayed){cost[P1715_COST_POLL]=1;cost[P1715_COST_READ]=1;cost[P1715_COST_WRITE]=2;cost[P1715_COST_FIELD]=4;cost[P1715_COST_COMMIT]=4;cost[P1715_COST_SNAPSHOT]=4;}
 trace_command(P1715_CONTROL_TRACE_START);us(1000);
 assert(arm());bool equal=false;assert(read_field(equal) && equal);
 assert(write_sector(0x96));worker_enabled=true;sd_cost=1000;
 for(unsigned i=0;i<4;i++){assert(arm());assert(read_field(equal) && equal);}
 trace_command(P1715_CONTROL_TRACE_STOP);
 p1715_control_status status;unsigned waited=0;
 do{us(100);status=trace_command(P1715_CONTROL_TRACE_STATUS);assert((waited+=100)<1000000);}while(status.trace[1]!=4 && status.trace[1]!=5);
 assert(status.trace[1]==4 && status.trace[2]>0 && !status.trace[8] && !status.trace[9]);
 trace_command(P1715_CONTROL_EJECT);
 while(p1715_status.shutdown==P1715_DRAINING){us(100);assert((waited+=100)<1000000);}
 assert(p1715_status.shutdown==P1715_SAFE && !p1715_status.dirty_blocks);
 assert(!memcmp(card.image,host_storage_image(),P1715_IMAGE_BYTES));
 trace_command(P1715_CONTROL_TRACE_REWIND);
 unsigned downloaded=0,total=status.trace[5];
 FILE *output=std::fopen("build/combined-capture.p1715","wb");assert(output);
 do{status=trace_command(P1715_CONTROL_TRACE_READ);unsigned n=status.trace[7];assert(n && n<=64);
  if(!downloaded)assert(!memcmp(status.trace_data,"P1715CY\0",8));
  assert(std::fwrite(status.trace_data,1,n,output)==n);downloaded+=n;assert(status.trace[6]==downloaded);
 }while(downloaded<total);
 std::fclose(output);
 assert(downloaded==total && !late_replies && !reset_replies && !p1715_status.storage_error);
 printf("combined firmware/RTL PASS: records=%u fpga_dropped=%u bytes=%u persisted writes=%llu\n",status.trace[2],status.trace[3],downloaded,(unsigned long long)card.writes);
}
#endif
int main(int argc,char **argv){
#if P1715_COMBINED
 if(argc==2 && !strcmp(argv[1],"--combined")){combined_capture(false);combined_capture(true);return 0;}
#endif
 if(argc==2 && !strcmp(argv[1],"--control")){
  control_stress(0,0,false);control_stress(8,1000,false);
  control_stress(128,0,false);control_stress(8,1000,true);return 0;
 }
 if(argc==2 && !strcmp(argv[1],"--recovery")){watchdog();watchdog_write();watchdog_lock();reset_held();shutdown();return 0;}
 assert(argc==1);
 for(unsigned delay=0;delay<=40;delay++){
  sweep("read-cost",P1715_COST_READ,delay);
  sweep("poll-cost",P1715_COST_POLL,delay);
  write_sweep("write-cost",P1715_COST_WRITE,delay);
 }
 for(unsigned delay:{0u,16u,32u,48u,64u,80u,96u,128u}){
  sweep("field-build-cost",P1715_COST_FIELD,delay);
  sweep("snapshot-lock-cost",P1715_COST_SNAPSHOT,delay);
  write_sweep("commit-cost",P1715_COST_COMMIT,delay);
 }
 watchdog();watchdog_write();watchdog_lock();reset_held();shutdown();
 printf("firmware timing cases: %u\n",cases);
}
