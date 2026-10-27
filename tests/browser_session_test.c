/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
int p1715_init(const uint8_t*,unsigned,const uint8_t*,unsigned,int);
int p1715_key(unsigned);void p1715_cancel(void);void p1715_reset(void);
int p1715_break(int);int p1715_hit(void);unsigned p1715_run(unsigned);unsigned p1715_step(void);
int p1715_peek(unsigned);unsigned p1715_map(unsigned,int);unsigned p1715_reg(unsigned);
double p1715_stat(unsigned);const uint8_t*p1715_ram(void);int p1715_export(void);
int main(void){
 uint8_t rom[2048]={0x31,0,0xfe,0x3e,3,0xd3,0x0e,0x3e,0xc1,0xd3,0x0e,0xc3,11,0};
 static uint8_t disk[819200];
 assert(p1715_init(rom,1,disk,sizeof(disk),0)<0);
 assert(p1715_init(rom,sizeof(rom),disk,sizeof(disk),0)==0);
 assert(p1715_init(rom,sizeof(rom),disk,sizeof(disk),0)<0);
 assert(p1715_peek(0)==0x31 && p1715_ram()[0]==0);
 assert(p1715_map(0,0)==0x2000000 && p1715_map(0,1)==0x1000000);
 unsigned before=p1715_reg(17);for(unsigned i=0;i<100;i++)p1715_peek(i);assert(before==p1715_reg(17));
 assert(p1715_break(11)==0);assert(p1715_run(1000)<1000 && p1715_hit());assert(p1715_reg(22)==11);
 p1715_break(-1);assert(p1715_step()>0 && p1715_reg(21));
 assert(p1715_key(0)<0 && p1715_key(128)<0);
 for(unsigned i=0;i<4096;i++){assert(p1715_key('A')==0);}
 assert(p1715_key('B')<0);
 p1715_run(1);p1715_cancel();assert(p1715_stat(11)==1);p1715_run(1001);assert(p1715_stat(11)==0);
 assert(p1715_stat(12)==2 && p1715_stat(13)==2);
 assert(p1715_key('C')==0);before=p1715_reg(17);p1715_reset();assert(p1715_stat(11)==0 && p1715_reg(17)==before);
 p1715_run(1000);int r;do{r=p1715_export();}while(!r);assert(r==1);
 before=p1715_reg(17);assert(p1715_run(1000)==1000 && p1715_reg(17)==before+1000);
 do{r=p1715_export();}while(!r);assert(r==1);puts("interactive session PASS");
}
