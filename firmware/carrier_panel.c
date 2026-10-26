/* SPDX-License-Identifier: MIT */
#include "carrier_panel.h"
#include "service.h"
void p1715_carrier_panel_step(p1715_carrier_panel *p,uint64_t now,bool pressed,bool usb_owns){
 if(pressed && !p->pressed)p->pressed_at=now;
 if(!pressed)p->latched=false;
 if(pressed && !p->latched && now-p->pressed_at>=500000){
  p->eject_pending=true;p->latched=true;p->safe=false;
 }
 p->pressed=pressed;
 if(usb_owns)return; /* Never consume a USB client's response. */
 if(p->owns){
  p1715_control_status s;int result;
  if(!p1715_control_take(&s,&result))return;
  p->owns=false;
  p->safe=!result && s.diagnostics.shutdown==P1715_SAFE &&
          !s.diagnostics.dirty_blocks && !s.diagnostics.storage_busy && !s.diagnostics.storage_error;
  p->next_status=now+100000;
 }
 if(p->eject_pending || now>=p->next_status){
  unsigned cmd=p->eject_pending?P1715_CONTROL_EJECT:P1715_CONTROL_STATUS;
  if(p1715_control_submit(cmd)){
   p->owns=true;
   if(p->eject_pending){p->eject_pending=false;p->safe=false;}
  }
 }
}
