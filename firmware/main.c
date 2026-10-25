/* SPDX-License-Identifier: MIT. Bring-up firmware; not electrically qualified. */
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "pico/critical_section.h"
#include "hardware/sync.h"
#include "store.h"
#include "sd_spi.h"
#include "../model/controller.h"
#include <string.h>
#ifndef P1715_WRITEBACK
#define P1715_WRITEBACK 0
#endif
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
static pico1715_controller card;
static p1715_store store={NULL,p1715_sd_read,p1715_sd_write,0};
static critical_section_t image_lock;
static uint32_t dirty[P1715_IMAGE_BLOCKS],generation;
static uint8_t *image;
/* SWD-visible diagnostics. No printf/USB ISR on the bus-serving core. */
volatile struct {uint32_t state,dirty_blocks,storage_error,max_service_us;uint64_t requests;} p1715_status;
static void worker(void){
 uint8_t block[512];
 for(;;){
  for(unsigned i=0;i<P1715_IMAGE_BLOCKS;i++){
   critical_section_enter_blocking(&image_lock);
   uint32_t version=dirty[i];if(version)memcpy(block,image+i*512,512);
   critical_section_exit(&image_lock);
   if(!version)continue;
   if(p1715_store_write(&store,i,block)){p1715_status.storage_error=1;for(;;)tight_loop_contents();}
   critical_section_enter_blocking(&image_lock);
   if(dirty[i]==version){dirty[i]=0;p1715_status.dirty_blocks--;}
   critical_section_exit(&image_lock);
  }
  sleep_us(100);
 }
}
static void outputs(void){
 gpio_put(INDEX_PENDING,card.irq_enabled&&card.pending&&!card.service);
 gpio_put(MARK_PENDING,card.mark_enabled&&card.mark_pending&&!card.service);
}
int main(void){
 for(unsigned pin=0;pin<=21;pin++){gpio_init(pin);gpio_set_dir(pin,GPIO_IN);gpio_pull_down(pin);}
 for(unsigned pin=LINK_ACK;pin<=INDEX_PENDING;pin++)if(pin!=HOST_RESET)gpio_set_dir(pin,GPIO_OUT);
 gpio_set_dir(MARK_PENDING,GPIO_OUT);gpio_set_dir(BACKEND_READY,GPIO_OUT);
 gpio_put(BACKEND_READY,0);gpio_put(LINK_ACK,0);gpio_pull_up(HOST_RESET);
 critical_section_init(&image_lock);p1715_status.state=1;
 image=p1715_psram();if(!image){p1715_status.state=0xe1;for(;;)tight_loop_contents();}
 if(p1715_sd_init()||p1715_store_open(&store)){p1715_status.state=0xe2;for(;;)tight_loop_contents();}
 for(unsigned i=0;i<P1715_IMAGE_BLOCKS;i++)if(p1715_store_read(&store,i,image+i*512)){
  p1715_status.state=0xe3;for(;;)tight_loop_contents();}
 pico1715_mount(&card,image,P1715_IMAGE_BYTES,80,2,5,3);card.writable=P1715_WRITEBACK;
 card.timing.enabled=1;critical_section_enter_blocking(&image_lock);memset(dirty,0,sizeof(dirty));critical_section_exit(&image_lock);
 if(P1715_WRITEBACK)multicore_launch_core1(worker);
 bool ack_seen=false,reti_seen=false,responded=false,reset_seen=false;
 uint64_t start=time_us_64();gpio_put(BACKEND_READY,1);p1715_status.state=2;
 for(;;){
  if(!gpio_get(HOST_RESET)){
   gpio_put(BACKEND_READY,0);gpio_put(LINK_ACK,0);gpio_set_dir_masked(255,0);
   if(!reset_seen){pico1715_reset(&card);start=time_us_64();reset_seen=true;}
   ack_seen=reti_seen=responded=false;outputs();continue;
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
   gpio_set_dir_masked(255,0);gpio_put(LINK_ACK,0);responded=false;continue;
  }
  if(responded)continue;
  uint32_t pins=gpio_get_all();unsigned reg=(pins>>8)&15;bool write=(pins>>LINK_WRITE)&1;
  uint16_t port=reg<8?reg:0x20+(reg&3);
  if(pico1715_wait(&card,port,write))continue;
  uint64_t begun=time_us_64();uint8_t data=255;
  if(write){
   critical_section_enter_blocking(&image_lock);
   uint64_t before=card.writes;pico1715_write(&card,port,(uint8_t)pins);
   if(card.writes!=before){
    unsigned block=((card.cylinder*card.heads+card.field_head)*card.sectors+card.field_sector-1)*2;
    if(++generation==0)generation=1;
    for(unsigned i=block;i<block+2;i++){if(!dirty[i])p1715_status.dirty_blocks++;dirty[i]=generation;}
   }
   critical_section_exit(&image_lock);
  }else{pico1715_read(&card,port,&data);gpio_put_masked(255,data);gpio_set_dir_masked(255,255);}
  __dmb();gpio_put(LINK_ACK,1);responded=true;p1715_status.requests++;
  uint32_t duration=(uint32_t)(time_us_64()-begun);
  if(duration>p1715_status.max_service_us)p1715_status.max_service_us=duration;
 }
}
