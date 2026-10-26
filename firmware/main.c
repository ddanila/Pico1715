/* SPDX-License-Identifier: MIT */
#include "platform.h"
#include "service.h"
#ifndef P1715_WRITEBACK
#define P1715_WRITEBACK 0
#endif
static pico1715_controller card;
int main(void){
#if P1715_PROTECTED_WRITEBACK
 int failed=p1715_service_init_protected(&card,P1715_WORST_BLOCK_US,P1715_RESERVE_MARGIN_US);
#else
 int failed=p1715_service_init(&card,P1715_WRITEBACK);
#endif
 if(failed)for(;;)tight_loop_contents();
 for(;;)p1715_service_step();
}
