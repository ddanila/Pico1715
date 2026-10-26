/* SPDX-License-Identifier: MIT. Bring-up firmware; not electrically qualified. */
#include "platform.h"
#include "service.h"
#include "store.h"
#include "sd_spi.h"
#include "../model/controller.h"
#include <string.h>
#define LINK_WRITE 12
#define LINK_REQ 13
#define LINK_ACK 14
#define HOST_RESET 15
#define INDEX_PENDING 16
#define MARK_PENDING 17
#define IRQ_ACK 18
#define IRQ_RETI 19
#define ACK_INDEX 20
#define BACKEND_READY 21
uint8_t *p1715_psram(void);
static pico1715_controller *controller;
#define card (*controller)
static p1715_store store={NULL,p1715_sd_read,p1715_sd_write,0};
static critical_section_t image_lock;
static uint32_t dirty[P1715_IMAGE_BLOCKS],generation;
static uint8_t *image;
/* SWD-visible diagnostics. No printf/USB ISR on the bus-serving core. */
volatile p1715_diagnostics p1715_status;
volatile uint32_t p1715_shutdown_command;
static uint32_t block_budget_us,reserve_margin_us;
static bool write_capable,tx_pending;
static uint8_t tx_staged;
static bool writes_allowed(void){
 return !p1715_status.storage_error && p1715_status.shutdown==P1715_RUNNING &&
   (p1715_status.write_policy==P1715_WRITE_EXPERIMENTAL ||
    (p1715_status.write_policy==P1715_WRITE_PROTECTED && p1715_status.backup==P1715_BACKUP_READY &&
     p1715_status.dirty_blocks+2<=p1715_status.dirty_limit));
}
static void isolate(void){
 tx_pending=false;
 card.writable=0;card.write_active=0;card.stream_active=0;
 gpio_put(BACKEND_READY,0);gpio_put(LINK_ACK,0);gpio_set_dir_masked(255,0);
 gpio_put(INDEX_PENDING,0);gpio_put(MARK_PENDING,0);
}
/* Called with image_lock held. Never report SAFE while a journal operation is in flight. */
static void shutdown_progress(void){
 if(p1715_status.shutdown!=P1715_DRAINING)return;
 if(p1715_status.storage_error){
  p1715_status.shutdown=P1715_UNSAFE;p1715_status.shutdown_reason=P1715_SHUTDOWN_STORAGE;
 }else if(p1715_status.shutdown_deadline && time_us_64()>=p1715_status.shutdown_deadline){
  p1715_status.shutdown=P1715_UNSAFE;p1715_status.shutdown_reason=P1715_SHUTDOWN_DEADLINE;
 }else if(!p1715_status.dirty_blocks && !p1715_status.storage_busy)p1715_status.shutdown=P1715_SAFE;
}
static void dirty_limit(void){
 uint64_t budget=p1715_status.reserve_us;
 p1715_status.dirty_limit=0;
 if(p1715_status.backup==P1715_BACKUP_READY && block_budget_us && budget>reserve_margin_us){
  budget=(budget-reserve_margin_us)/block_budget_us;
  p1715_status.dirty_limit=budget>P1715_IMAGE_BLOCKS?P1715_IMAGE_BLOCKS:(uint32_t)budget;
 }
}
int p1715_shutdown_request(unsigned command){
 if(p1715_status.state!=2 || (command!=P1715_EJECT && command!=P1715_POWER_FAIL))return -1;
 isolate();
 critical_section_enter_blocking(&image_lock);
 if(p1715_status.shutdown==P1715_RUNNING)p1715_status.shutdown=P1715_DRAINING;
 if(command==P1715_POWER_FAIL && p1715_status.shutdown==P1715_DRAINING){
  uint64_t now=time_us_64(),budget=p1715_status.reserve_us;
  if(p1715_status.backup!=P1715_BACKUP_READY || !budget){
   if(p1715_status.dirty_blocks || p1715_status.storage_busy){
    p1715_status.shutdown=P1715_UNSAFE;p1715_status.shutdown_reason=P1715_SHUTDOWN_RESERVE;
   }
  }else {
   uint64_t deadline=UINT64_MAX-now<budget?UINT64_MAX:now+budget;
   /* Repeated outages or ready updates cannot extend an existing deadline. */
   if(!p1715_status.shutdown_deadline || deadline<p1715_status.shutdown_deadline)p1715_status.shutdown_deadline=deadline;
  }
 }
 shutdown_progress();critical_section_exit(&image_lock);return 0;
}
int p1715_write_policy(unsigned policy,uint32_t worst_block_us,uint32_t margin_us){
 if(policy>P1715_WRITE_PROTECTED || p1715_status.state!=2 ||
    (policy!=P1715_READ_ONLY && !write_capable) ||
    (policy==P1715_WRITE_PROTECTED && !worst_block_us))return -1;
 critical_section_enter_blocking(&image_lock);
 if(p1715_status.shutdown!=P1715_RUNNING || p1715_status.dirty_blocks || p1715_status.storage_busy || card.write_active){
  critical_section_exit(&image_lock);return -1;
 }
 p1715_status.write_policy=policy;block_budget_us=worst_block_us;reserve_margin_us=margin_us;dirty_limit();
 card.writable=policy==P1715_WRITE_EXPERIMENTAL || (policy==P1715_WRITE_PROTECTED && p1715_status.dirty_limit>=2);
 critical_section_exit(&image_lock);return 0;
}
int p1715_backup_update(unsigned state,uint64_t reserve_us){
 if(state>P1715_BACKUP_FAILED || p1715_status.state!=2)return -1;
 critical_section_enter_blocking(&image_lock);
 p1715_status.backup=state;p1715_status.reserve_us=state==P1715_BACKUP_READY?reserve_us:0;dirty_limit();
 bool lost=p1715_status.write_policy==P1715_WRITE_PROTECTED &&
  (state!=P1715_BACKUP_READY || p1715_status.dirty_limit<p1715_status.dirty_blocks);
 bool draining=p1715_status.shutdown==P1715_DRAINING && p1715_status.shutdown_deadline;
 critical_section_exit(&image_lock);
 /* Reserve loss while mains remains present still drains under live power. */
 if(lost && (p1715_status.dirty_blocks || card.write_active))p1715_shutdown_request(P1715_EJECT);
 if(draining)p1715_shutdown_request(P1715_POWER_FAIL);
 return 0;
}
void p1715_storage_step(void){
 uint8_t block[512];
 for(unsigned i=0;i<P1715_IMAGE_BLOCKS;i++){
  critical_section_enter_blocking(&image_lock);
  shutdown_progress();
  if(p1715_status.storage_error || p1715_status.shutdown==P1715_UNSAFE || p1715_status.shutdown==P1715_SAFE){
   critical_section_exit(&image_lock);return;
  }
  uint32_t version=dirty[i];
  if(version){P1715_WORK(P1715_COST_SNAPSHOT);memcpy(block,image+i*512,512);p1715_status.storage_busy=1;}
  critical_section_exit(&image_lock);
  if(!version)continue;
  int failed=p1715_store_write(&store,i,block);
  critical_section_enter_blocking(&image_lock);
  p1715_status.storage_busy=0;
  if(failed)p1715_status.storage_error=1;
  else if(dirty[i]==version){dirty[i]=0;p1715_status.dirty_blocks--;}
  shutdown_progress();
  critical_section_exit(&image_lock);
  if(failed)return;
 }
}
static void worker(void){for(;;){p1715_storage_step();sleep_us(100);}}
static void outputs(void){
 gpio_put(INDEX_PENDING,card.irq_enabled&&card.pending&&!card.service);
 gpio_put(MARK_PENDING,card.mark_enabled&&card.mark_pending&&!card.service);
}
static bool ack_seen,reti_seen,responded,reset_seen,prefetch_allowed;
static uint64_t start;
static bool request_live(void){return gpio_get(HOST_RESET) && gpio_get(LINK_REQ);}
static void abandon_response(void){
 tx_pending=false;prefetch_allowed=false;
 gpio_set_dir_masked(255,0);gpio_put(LINK_ACK,0);responded=false;
}
static int service_init(pico1715_controller *c,bool writable,bool protect,uint32_t worst,uint32_t margin){
 controller=c;
 memset((void *)&p1715_status,0,sizeof(p1715_status));
 generation=0;store.failed=0;p1715_shutdown_command=0;tx_pending=false;
 block_budget_us=worst;reserve_margin_us=margin;write_capable=writable;
 p1715_status.write_policy=protect?P1715_WRITE_PROTECTED:writable?P1715_WRITE_EXPERIMENTAL:P1715_READ_ONLY;
 for(unsigned pin=0;pin<=21;pin++){gpio_init(pin);gpio_set_dir(pin,GPIO_IN);gpio_pull_down(pin);}
 for(unsigned pin=LINK_ACK;pin<=INDEX_PENDING;pin++)if(pin!=HOST_RESET)gpio_set_dir(pin,GPIO_OUT);
 gpio_set_dir(MARK_PENDING,GPIO_OUT);gpio_set_dir(BACKEND_READY,GPIO_OUT);
 gpio_put(BACKEND_READY,0);gpio_put(LINK_ACK,0);gpio_pull_up(HOST_RESET);
 critical_section_init(&image_lock);p1715_status.state=1;
 if(protect && !worst){p1715_status.state=0xe4;return -1;}
 image=p1715_psram();if(!image){p1715_status.state=0xe1;return -1;}
 if(p1715_sd_init()||p1715_store_open(&store)){p1715_status.state=0xe2;return -1;}
 for(unsigned i=0;i<P1715_IMAGE_BLOCKS;i++)if(p1715_store_read(&store,i,image+i*512)){
  p1715_status.state=0xe3;return -1;}
 pico1715_mount(&card,image,P1715_IMAGE_BYTES,80,2,5,3);card.writable=writable&&!protect;
 card.timing.enabled=1;card.timing.fifo_depth=P1715_RX_FIFO_DEPTH;
 critical_section_enter_blocking(&image_lock);memset(dirty,0,sizeof(dirty));critical_section_exit(&image_lock);
 if(writable)multicore_launch_core1(worker);
 ack_seen=reti_seen=responded=reset_seen=false;prefetch_allowed=true;
 start=time_us_64();gpio_put(BACKEND_READY,1);p1715_status.state=2;
 return 0;
}
int p1715_service_init(pico1715_controller *c,bool writable){return service_init(c,writable,false,0,0);}
int p1715_service_init_protected(pico1715_controller *c,uint32_t worst,uint32_t margin){return service_init(c,true,true,worst,margin);}
void p1715_service_step(void){
  P1715_WORK(P1715_COST_POLL);
  uint32_t command=p1715_shutdown_command;
  if(command){p1715_shutdown_command=0;(void)p1715_shutdown_request(command);}
  critical_section_enter_blocking(&image_lock);
  shutdown_progress();
  card.writable=writes_allowed();
  bool shut=p1715_status.shutdown!=P1715_RUNNING;
  critical_section_exit(&image_lock);
  if(shut){isolate();return;}
  if(!gpio_get(HOST_RESET)){
   tx_pending=false;
   gpio_put(BACKEND_READY,0);gpio_put(LINK_ACK,0);gpio_set_dir_masked(255,0);
   if(!reset_seen){pico1715_reset(&card);start=time_us_64();reset_seen=true;}
   ack_seen=reti_seen=responded=false;prefetch_allowed=true;outputs();return;
  }
  if(reset_seen){reset_seen=false;gpio_put(BACKEND_READY,1);}
  uint64_t cycle=(time_us_64()-start)*PICO1715_CLOCK_HZ/1000000;
  pico1715_tick(&card,cycle);
  bool ack=gpio_get(IRQ_ACK),reti=gpio_get(IRQ_RETI);
  if(ack!=ack_seen){ack_seen=ack;card.service=1;
   if(gpio_get(ACK_INDEX)){card.pending=0;card.interrupts++;}else card.mark_pending=0;}
  if(reti!=reti_seen){reti_seen=reti;pico1715_reti(&card);}
  if(p1715_status.storage_error)card.writable=0;
  outputs();
  if(!gpio_get(LINK_REQ)){
   // Release shared data BEFORE lowering ACK; FPGA must see an idle bus first.
   gpio_set_dir_masked(255,0);gpio_put(LINK_ACK,0);responded=false;
   /* Prepare while the CPU executes between I/O requests. The staged byte
      still occupies one slot of the same bounded receive capacity. */
   if(prefetch_allowed && card.stream_active && card.rx_count && !card.prepared){
    P1715_WORK(P1715_COST_READ);
    if(gpio_get(HOST_RESET))pico1715_prepare_read(&card);
   }
   return;
  }
  if(responded)return;
  uint32_t pins=gpio_get_all();unsigned reg=(pins>>8)&15;bool write=(pins>>LINK_WRITE)&1;
  uint16_t port=reg<8?reg:0x20+(reg&3);
  if(pico1715_wait(&card,port,write))return;
  uint64_t begun=time_us_64();uint8_t data=255;
  if(write && port==0 && card.write_active){
   if(!request_live()){abandon_response();return;}
   tx_staged=(uint8_t)pins;tx_pending=true;
  }else if(write){
   critical_section_enter_blocking(&image_lock);
   if(!request_live()){critical_section_exit(&image_lock);abandon_response();return;}
   card.writable=writes_allowed(); /* Recheck after any intervening worker failure. */
   if(port==4 && card.write_active && (pins&1))P1715_WORK(P1715_COST_COMMIT);
   else if(port==4 && ((uint8_t)pins&0x3b)==1 && card.control!=(uint8_t)pins)P1715_WORK(P1715_COST_FIELD);
   if(!request_live()){critical_section_exit(&image_lock);abandon_response();return;}
   uint64_t before=card.writes;pico1715_write(&card,port,(uint8_t)pins);
   if(card.writes!=before){
    unsigned block=((card.cylinder*card.heads+card.field_head)*card.sectors+card.field_sector-1)*2;
    if(++generation==0)generation=1;
    for(unsigned i=block;i<block+2;i++){if(!dirty[i])p1715_status.dirty_blocks++;dirty[i]=generation;}
   }
   critical_section_exit(&image_lock);
  }else{
   if(port==2 && !card.prepared)P1715_WORK(P1715_COST_READ);
   if(!request_live()){abandon_response();return;}
   pico1715_read(&card,port,&data);
  }
  /* Lock waits or controller work may outlive the FPGA watchdog or host reset.
     A withdrawn request must never receive a new ACK/data-drive pulse. */
  if(!request_live()){abandon_response();return;}
  if(!write){gpio_put_masked(255,data);gpio_set_dir_masked(255,255);}
  __dmb();gpio_put(LINK_ACK,1);responded=true;p1715_status.requests++;
  uint32_t duration=(uint32_t)(time_us_64()-begun);
  if(duration>p1715_status.max_service_us)p1715_status.max_service_us=duration;
  /* Acknowledgement admits one byte to a bounded local slot. Finish its
     processing before accepting another request (including gate close). */
  if(tx_pending){
   P1715_WORK(P1715_COST_WRITE);
   tx_pending=false;
   if(!gpio_get(HOST_RESET)){abandon_response();return;}
   if(p1715_shutdown_command || p1715_status.storage_error)return;
   /* Keep the serializer clock honest: deadlines elapsed during processing
      count as underruns before the new byte reaches the output latch. */
   pico1715_tick(&card,(time_us_64()-start)*PICO1715_CLOCK_HZ/1000000);
   pico1715_write(&card,0,tx_staged);
  }
}
