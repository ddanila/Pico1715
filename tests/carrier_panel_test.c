/* SPDX-License-Identifier: MIT */
#include "../firmware/carrier_panel.h"
#include "../firmware/service.h"
#include <assert.h>
#include <stdio.h>
static bool busy,ready;
static unsigned submits,last,takes;
static p1715_control_status status;
static int result;
bool p1715_control_submit(unsigned cmd){if(busy)return false;busy=true;submits++;last=cmd;return true;}
bool p1715_control_take(p1715_control_status *s,int *r){assert(busy);takes++;if(!ready)return false;*s=status;*r=result;ready=busy=false;return true;}
static void complete(unsigned state){status.diagnostics.shutdown=state;ready=true;}
int main(void){
 p1715_carrier_panel p={0};
 /* A USB transaction cannot be consumed; a held button survives contention. */
 busy=true;complete(P1715_RUNNING);
 p1715_carrier_panel_step(&p,0,true,true);
 p1715_carrier_panel_step(&p,499999,true,true);assert(!p.eject_pending);
 p1715_carrier_panel_step(&p,500000,true,true);assert(p.eject_pending && takes==0 && submits==0);
 busy=ready=false;
 p1715_carrier_panel_step(&p,500001,true,false);assert(p.owns && last==P1715_CONTROL_EJECT && !p.safe);
 complete(P1715_DRAINING);p1715_carrier_panel_step(&p,500002,true,false);assert(!p.owns && !p.safe);
 p1715_carrier_panel_step(&p,600002,true,false);assert(last==P1715_CONTROL_STATUS && submits==2);
 complete(P1715_SAFE);p1715_carrier_panel_step(&p,600003,true,false);assert(p.safe);
 /* SAFE is never inferred from an eject acknowledgment or incomplete drain. */
 p1715_carrier_panel_step(&p,700003,false,false);complete(P1715_SAFE);status.diagnostics.storage_busy=1;
 p1715_carrier_panel_step(&p,700004,false,false);assert(!p.safe);status.diagnostics.storage_busy=0;
 p1715_carrier_panel_step(&p,800004,false,false);complete(P1715_SAFE);status.diagnostics.dirty_blocks=1;
 p1715_carrier_panel_step(&p,800005,false,false);assert(!p.safe);status.diagnostics.dirty_blocks=0;
 p1715_carrier_panel_step(&p,900005,false,false);complete(P1715_SAFE);result=1;
 p1715_carrier_panel_step(&p,900006,false,false);assert(!p.safe);result=0;
 /* Release and a short bounce do not eject; a second deliberate hold does. */
 p1715_carrier_panel_step(&p,900007,true,false);
 p1715_carrier_panel_step(&p,900100,false,false);
 p1715_carrier_panel_step(&p,900101,true,false);
 p1715_carrier_panel_step(&p,1400101,true,false);assert(last==P1715_CONTROL_EJECT);
 complete(P1715_UNSAFE);p1715_carrier_panel_step(&p,1400102,false,false);assert(!p.safe);
 puts("carrier panel PASS: hold/release, USB ownership, draining/SAFE/error status");
}
