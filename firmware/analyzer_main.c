/* SPDX-License-Identifier: MIT. Standalone analyzer firmware, SWD control for now. */
#include "pico/stdlib.h"
#include "hardware/sync.h"
#include "analyzer.h"
uint8_t *p1715_psram_region(uint32_t offset,uint32_t size);
p1715_analyzer p1715_analyzer_status;
volatile bool p1715_analyzer_request_stop;
static uint32_t pins(void *p){(void)p;return gpio_get_all();}
static void controls(void *p,uint32_t value){(void)p;gpio_put_masked(P1715_LA_CONTROLS,value);}
static uint64_t now(void *p){(void)p;return time_us_64();}
static void fence(void *p){(void)p;__dmb();}
int main(void){
 for(unsigned i=0;i<=21;i++){gpio_init(i);gpio_set_dir(i,GPIO_IN);gpio_pull_down(i);}
 gpio_put_masked(P1715_LA_CONTROLS,P1715_LA_CLEAR);
 gpio_set_dir_masked(P1715_LA_CONTROLS,P1715_LA_CONTROLS);
 uint8_t *ram=p1715_psram_region(P1715_LA_RAM_OFFSET,P1715_LA_RAM_SIZE);
 if(!ram || p1715_analyzer_start(&p1715_analyzer_status,
   (p1715_analyzer_io){NULL,pins,controls,now,fence},ram,P1715_LA_RAM_SIZE,50000000)){
  p1715_analyzer_status.state=P1715_LA_ERROR;for(;;)tight_loop_contents();
 }
 for(;;){
  if(p1715_analyzer_request_stop)p1715_analyzer_stop(&p1715_analyzer_status);
  p1715_analyzer_step(&p1715_analyzer_status);
 }
}
