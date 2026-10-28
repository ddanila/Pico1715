/* SPDX-License-Identifier: MIT */
#include "../firmware/reserve.h"
#include "../firmware/service.h"
#include <assert.h>
#include <stdio.h>
static unsigned state,failures,updates;
static uint64_t budget,latched;
int p1715_backup_update(unsigned s,uint64_t b){state=s;budget=b;updates++;return 0;}
int p1715_shutdown_request(unsigned c){assert(c==P1715_POWER_FAIL);failures++;latched=budget;return 0;}
int main(void){
 p1715_reserve r;p1715_reserve_init(&r,0);
 p1715_reserve_step(&r,0,false,false,false);assert(state==P1715_BACKUP_ABSENT&&!failures);
 p1715_reserve_step(&r,1,true,true,true);
 p1715_reserve_step(&r,2000000,true,true,true);assert(state==P1715_BACKUP_CHARGING&&!budget);
 p1715_reserve_init(&r,3000000);
 p1715_reserve_step(&r,0,true,true,true);
 p1715_reserve_step(&r,999999,true,true,true);assert(state==P1715_BACKUP_CHARGING);
 p1715_reserve_step(&r,1000000,true,true,true);assert(state==P1715_BACKUP_READY&&budget==3000000);
 p1715_reserve_step(&r,1000001,true,false,false);assert(failures==1&&latched==3000000);
 unsigned n=updates;
 p1715_reserve_step(&r,9000000,true,true,true);
 p1715_reserve_step(&r,9000001,false,false,false);assert(failures==1&&updates==n);
 p1715_reserve_init(&r,3000000);
 p1715_reserve_step(&r,0,true,true,true);
 p1715_reserve_step(&r,1000000,true,true,true);
 p1715_reserve_step(&r,1000001,true,true,false);assert(state==P1715_BACKUP_CHARGING&&!budget);
 p1715_reserve_step(&r,1000002,true,true,true);
 p1715_reserve_step(&r,2000001,true,true,true);assert(state==P1715_BACKUP_CHARGING);
 p1715_reserve_step(&r,2000002,true,true,true);assert(state==P1715_BACKUP_READY);
 p1715_reserve_step(&r,2000003,false,true,true);assert(state==P1715_BACKUP_FAILED&&failures==2&&!latched);
 p1715_reserve_init(&r,3000000);
 p1715_reserve_step(&r,0,true,false,true);assert(failures==3&&!latched);
 puts("reserve PASS: absent, unqualified, stable charge, outage latch, reserve fall, removal");
}
