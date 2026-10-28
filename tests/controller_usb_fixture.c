/* SPDX-License-Identifier: MIT */
#include "../firmware/controller_usb.h"
#include "../firmware/service.h"
#include "../firmware/store.h"
#include "../firmware/sd_crc.h"
#include "../tools/firmware_host/host_hal.h"
#include <assert.h>
#include <string.h>
static p1715_controller_usb usb;
static pico1715_controller card;
static uint8_t original[P1715_IMAGE_BYTES];
static void steps(unsigned count){for(unsigned i=0;i<count;i++){host_time_us++;p1715_service_step();}}
void fixture_init(unsigned mode){
 host_storage_init(original,mode==2);p1715_background_hook(NULL);
 int failed=p1715_service_init(&card,mode!=0);assert(failed==(mode==2?-1:0));
 host_inputs=1u<<15;p1715_controller_usb_init(&usb);
}
void fixture_feed(uint8_t b){p1715_controller_usb_receive(&usb,b);}
void fixture_poll(void){
 if(p1715_status.state==2)steps(256);else p1715_control_step();
 p1715_controller_usb_poll(&usb);
}
size_t fixture_read(uint8_t *out,size_t n){
 size_t available;const uint8_t *p=p1715_controller_usb_output(&usb,&available);
 if(n>available)n=available;
 memcpy(out,p,n);p1715_controller_usb_sent(&usb,n);return n;
}
void fixture_disconnect(void){p1715_controller_usb_disconnect(&usb);}
void fixture_core(void){p1715_control_step();}
void fixture_poll_usb(void){p1715_controller_usb_poll(&usb);}
void fixture_fail(void){host_fail_write=host_sd_writes+1;}
void fixture_storage(void){p1715_storage_step();}
unsigned fixture_shutdown(void){return p1715_status.shutdown;}
unsigned fixture_dirty_count(void){return p1715_status.dirty_blocks;}
static void out(unsigned reg,uint8_t value){
 host_inputs=(1u<<15)|(1u<<13)|(1u<<12)|(reg<<8)|value;steps(1);
 assert(host_outputs&(1u<<14));host_inputs=1u<<15;steps(1);
}
void fixture_dirty(void){
 card.timing.enabled=0;
 out(8,0xef);out(6,4);out(4,0xa5);out(4,0x85);out(4,0xa5);out(4,0x85);
 uint8_t field[1030]={0xa1,0xa1,0xa1,0xfb};memset(field+4,0x63,1024);
 uint16_t crc=0xffff;for(unsigned i=0;i<1028;i++){crc^=(uint16_t)field[i]<<8;for(unsigned j=0;j<8;j++)crc=(uint16_t)((crc<<1)^((crc&0x8000)?0x1021:0));}field[1028]=crc>>8;field[1029]=(uint8_t)crc;
 out(4,0xb4);for(unsigned i=0;i<sizeof(field);i++)out(0,field[i]);out(4,0xbf);
 assert(card.writes==1 && p1715_status.dirty_blocks==2);
}
unsigned fixture_persisted(void){
 const uint8_t *p=host_storage_image();
 for(unsigned i=0;i<P1715_IMAGE_BYTES;i++)if(p[i]!=(i<1024?0x63:0))return 0;
 return 1;
}
void fixture_big_counters(void){p1715_status.requests=0x123456789abcdef0ULL;card.overruns=0xfedcba9876543210ULL;}

void fixture_clear_counters(void){p1715_status.requests=0;card.overruns=0;}
static void during_write(bool writing,uint32_t lba){
 (void)lba;if(!writing)return;
 p1715_control_step();p1715_controller_usb_poll(&usb);
}
void fixture_io_control(void){host_io_hook=during_write;}
#if P1715_COMBINED
unsigned fixture_extension_read(unsigned reg){
 host_inputs=(1u<<15)|(1u<<13)|(reg<<8);steps(1);
 assert(host_outputs&(1u<<14));unsigned value=host_outputs&255;
 host_inputs=1u<<15;steps(1);return value;
}
void fixture_extension_write(unsigned reg,uint8_t value){out(reg,value);}
#endif
