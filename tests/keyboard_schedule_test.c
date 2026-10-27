/* SPDX-License-Identifier: MIT */
#include "../tools/keyboard_schedule.h"
#include <assert.h>
static int received;
static int receive(void *u,uint8_t b){(void)u;assert(b==received++);return b==0?-EAGAIN:b==1?-ENOSPC:0;}
int main(int argc,char **argv){
 assert(argc==3);struct key_schedule s={0};
 assert(key_schedule_load(&s,argv[1])==0);
 key_schedule_step(&s,0,receive,NULL);assert(s.attempted==1);
 key_schedule_step(&s,10,receive,NULL);assert(s.attempted==2);
 key_schedule_step(&s,21,receive,NULL);assert(s.attempted==3 && s.late==1);
 key_schedule_step(&s,50,receive,NULL);assert(s.attempted==3);
 assert(s.accepted==1 && s.disabled==1 && s.full==1 && s.rejected==2);
 free(s.events);memset(&s,0,sizeof(s));assert(key_schedule_load(&s,argv[2])==-1);
 puts("keyboard schedule PASS: one-shot delivery, rejection, lateness and malformed input");
}
