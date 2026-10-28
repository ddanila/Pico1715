/* SPDX-License-Identifier: MIT */
#include "reserve.h"
#include "service.h"
#include <string.h>
void p1715_reserve_init(p1715_reserve *r,uint64_t qualified_us){
 memset(r,0,sizeof(*r));r->qualified_us=qualified_us;
}
static void report(p1715_reserve *r,unsigned state){
 if(!r->initialized || r->reported!=state){
  (void)p1715_backup_update(state,state==P1715_BACKUP_READY?r->qualified_us:0);
  r->reported=state;r->initialized=true;
 }
}
void p1715_reserve_step(p1715_reserve *r,uint64_t now,bool present,bool supply_ok,bool reserve_ok){
 if(r->terminated)return;
 if(!present){
  r->stable=false;
  if(r->seen){
   /* Removal invalidates the energy budget even if USB holds VSYS up. */
   report(r,P1715_BACKUP_FAILED);
   (void)p1715_shutdown_request(P1715_POWER_FAIL);r->terminated=true;
  }else report(r,P1715_BACKUP_ABSENT);
  return;
 }
 r->seen=true;
 if(!supply_ok){
  /* Latch the qualified budget BEFORE reserve voltage can fall. Do not call
     backup_update during discharge: RESERVE_OK is a charging threshold. */
  (void)p1715_shutdown_request(P1715_POWER_FAIL);r->terminated=true;return;
 }
 if(!reserve_ok){r->stable=false;report(r,P1715_BACKUP_CHARGING);return;}
 if(!r->stable){r->stable=true;r->stable_since=now;}
 report(r,r->qualified_us && now-r->stable_since>=1000000?
        P1715_BACKUP_READY:P1715_BACKUP_CHARGING);
}
