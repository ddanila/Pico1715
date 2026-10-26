/* SPDX-License-Identifier: MIT. Storage core only; never called with image_lock held. */
#include "controller_usb.h"
#include "tusb.h"
static p1715_controller_usb usb;
static bool initialized,connected;
static void disconnect(void){
 p1715_controller_usb_disconnect(&usb);tud_cdc_read_flush();tud_cdc_write_clear();connected=false;
}
/* Observe every transition, including a drop/rise within one tud_task visit. */
void tud_cdc_line_state_cb(uint8_t itf,bool dtr,bool rts){
 (void)itf;(void)rts;if(!dtr)disconnect();
}
void tud_umount_cb(void){disconnect();}
void p1715_controller_usb_device(void){
 if(!initialized){p1715_controller_usb_init(&usb);tusb_init();initialized=true;}
 /* Own TinyUSB on this core; do not initialize the SDK stdio USB worker. */
 tud_task();
 p1715_controller_usb_poll(&usb);
 if(!tud_cdc_connected()){
  disconnect();return;
 }
 if(!connected){p1715_controller_usb_disconnect(&usb);connected=true;}
 /* At most one request and one 64-byte TX chunk per visit. Never wait for host. */
 for(unsigned i=0;i<16 && !usb.pending && !usb.waiting && tud_cdc_available();i++){
  uint8_t b;if(tud_cdc_read(&b,1)==1)p1715_controller_usb_receive(&usb,b);
 }
 size_t n;const uint8_t *data=p1715_controller_usb_output(&usb,&n);
 uint32_t available=tud_cdc_write_available();
 if(n>64)n=64;
 if(n>available)n=available;
 if(n)p1715_controller_usb_sent(&usb,tud_cdc_write(data,(uint32_t)n));
 tud_cdc_write_flush();
}
