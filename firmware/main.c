/* SPDX-License-Identifier: MIT */
#include "platform.h"
#include "service.h"
#ifndef P1715_WRITEBACK
#define P1715_WRITEBACK 0
#endif
static pico1715_controller card;
int main(void){
 if(p1715_service_init(&card,P1715_WRITEBACK))for(;;)tight_loop_contents();
 for(;;)p1715_service_step();
}
