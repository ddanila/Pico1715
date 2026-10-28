/* SPDX-License-Identifier: MIT */
#include "platform.h"
#include "service.h"
#if P1715_RESERVE_SUPERVISOR
#include "reserve.h"
static p1715_reserve reserve;
#endif
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
#if P1715_RESERVE_SUPERVISOR
 p1715_reserve_init(&reserve,P1715_QUALIFIED_RESERVE_US);
 const unsigned pins[]={P1715_SUPPLY_OK_GPIO,P1715_RESERVE_OK_GPIO,P1715_RESERVE_PRESENT_GPIO};
 for(unsigned i=0;i<3;i++){gpio_init(pins[i]);gpio_set_dir(pins[i],GPIO_IN);}
 gpio_pull_up(P1715_RESERVE_PRESENT_GPIO);
 /* External open-drain pullups are on the daughter; disconnected status must
    not qualify READY. Presence is sampled independently. */
 gpio_pull_down(P1715_SUPPLY_OK_GPIO);gpio_pull_down(P1715_RESERVE_OK_GPIO);
#endif
 for(;;){
#if P1715_RESERVE_SUPERVISOR
  p1715_reserve_step(&reserve,time_us_64(),!gpio_get(P1715_RESERVE_PRESENT_GPIO),
                    gpio_get(P1715_SUPPLY_OK_GPIO),gpio_get(P1715_RESERVE_OK_GPIO));
#endif
  p1715_service_step();
 }

}
