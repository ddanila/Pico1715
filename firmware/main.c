/* SPDX-License-Identifier: MIT */
#include "platform.h"
#include "service.h"
#ifndef P1715_WRITEBACK
#define P1715_WRITEBACK 0
#endif
static pico1715_controller card;
void p1715_controller_usb_device(void);
static void diagnostic_worker(void){for(;;){p1715_controller_usb_device();sleep_us(100);}}
int main(void){
 p1715_background_hook(p1715_controller_usb_device);
#if P1715_PROTECTED_WRITEBACK
 int failed=p1715_service_init_protected(&card,P1715_WORST_BLOCK_US,P1715_RESERVE_MARGIN_US);
#else
 int failed=p1715_service_init(&card,P1715_WRITEBACK);
#endif
 if(failed){
  multicore_launch_core1(diagnostic_worker);
  for(;;){p1715_control_step();sleep_us(100);}
 }
 for(;;)p1715_service_step();
}
