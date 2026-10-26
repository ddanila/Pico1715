/* SPDX-License-Identifier: MIT. Standalone analyzer firmware with bounded USB CDC servicing. */
#include "pico/stdlib.h"
#include "hardware/sync.h"
#include "analyzer_usb.h"
#include "tusb.h"
uint8_t *p1715_psram_region(uint32_t offset,uint32_t size);
p1715_analyzer p1715_analyzer_status;
static p1715_analyzer_usb usb;
static bool connected;
static void service_usb(void){
 tud_task();
 bool current=tud_cdc_connected();
 if(!current){
  p1715_usb_disconnect(&usb);tud_cdc_read_flush();tud_cdc_write_clear();connected=false;return;
 }
 if(!connected){p1715_usb_disconnect(&usb);connected=true;}
 /* One request/one TX packet per visit; never wait for host availability. */
 for(unsigned i=0;i<24 && !usb.pending && tud_cdc_available();i++){
  uint8_t b;if(tud_cdc_read(&b,1)==1)p1715_usb_receive(&usb,b);
 }
 size_t n;const uint8_t *data=p1715_usb_output(&usb,&n);
 uint32_t available=tud_cdc_write_available();
 if(n>64)n=64;
 if(n>available)n=available;
 if(n)p1715_usb_sent(&usb,tud_cdc_write(data,(uint32_t)n));
 tud_cdc_write_flush();
}
static uint32_t pins(void *p){(void)p;return gpio_get_all();}
static void controls(void *p,uint32_t value){(void)p;gpio_put_masked(P1715_LA_CONTROLS,value);}
static uint64_t now(void *p){(void)p;return time_us_64();}
static void fence(void *p){(void)p;__dmb();}
int main(void){
 for(unsigned i=0;i<=21;i++){gpio_init(i);gpio_set_dir(i,GPIO_IN);gpio_pull_down(i);}
 gpio_put_masked(P1715_LA_CONTROLS,P1715_LA_CLEAR);
 gpio_set_dir_masked(P1715_LA_CONTROLS,P1715_LA_CONTROLS);
 uint8_t *ram=p1715_psram_region(P1715_LA_RAM_OFFSET,P1715_LA_RAM_SIZE);
 p1715_usb_init(&usb,&p1715_analyzer_status,
   (p1715_analyzer_io){NULL,pins,controls,now,fence},ram,P1715_LA_RAM_SIZE,50000000);
 /* Use SDK CDC descriptors, but own tud_task: do not start stdio USB's worker. */
 tusb_init();
 unsigned iterations=0;
 for(;;){
  if(p1715_analyzer_status.state>=P1715_LA_HOLD && p1715_analyzer_status.state<=P1715_LA_LOW)
   p1715_analyzer_step(&p1715_analyzer_status);
  if(++iterations==256){iterations=0;service_usb();}
 }
}
