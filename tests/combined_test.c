/* SPDX-License-Identifier: MIT */
#include "../firmware/combined.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void crc(uint8_t *f){
 uint16_t c=0xffff;for(unsigned i=0;i<20;i++){c^=(uint16_t)f[i]<<8;for(unsigned b=0;b<8;b++)c=(c&0x8000)?(uint16_t)((c<<1)^0x1021):(uint16_t)(c<<1);}
 f[20]=(uint8_t)c;f[21]=(uint8_t)(c>>8);
}
static uint8_t request(p1715_combined *c,unsigned reg,bool write,uint8_t value){uint8_t r;assert(p1715_combined_request(c,reg,write,value,&r,100));return r;}
static void frame(p1715_combined *c,uint8_t *f){crc(f);for(unsigned i=0;i<22;i++)request(c,i?15:13,true,f[i]);}
int main(void){
 uint8_t ram[64],f[22]={1,1},out[64];p1715_combined c;
 p1715_combined_init(&c,ram,sizeof(ram));assert(request(&c,14,false,0)==0xa7);
 uint8_t r;assert(!p1715_combined_request(&c,2,false,0,&r,0));
 assert(!p1715_combined_start(&c,0));assert(p1715_combined_start(&c,0)<0);
 assert(request(&c,12,false,0)==3);assert(request(&c,12,false,0)==1);assert(!request(&c,12,false,0));
 f[4]=0x40;f[5]=0xa5;frame(&c,f);assert(c.capture.records==1);
 frame(&c,f);assert(c.capture.records==1 && c.capture.duplicates==1);
 request(&c,13,true,1);request(&c,15,true,1);p1715_combined_reset(&c);frame(&c,f);assert(c.capture.duplicates==2);
 f[16]=1;frame(&c,f);assert(c.capture.records==2);
 f[16]=2;frame(&c,f);assert(c.capture.full && c.capture.local_dropped==1 && c.capture.stopping);
 assert(request(&c,12,false,0)==2);
 memset(f,0,sizeof(f));f[0]=2;f[1]=1;f[2]=1;f[12]=3;f[16]=0x70;f[17]=1;frame(&c,f);
 assert(c.capture.state==P1715_LA_DONE);assert(!p1715_analyzer_read(&c.capture,0,out,sizeof(out)));
 assert(!memcmp(out,"P1715CY",7) && out[20]==1);
 assert(!p1715_combined_start(&c,0));request(&c,12,false,0);request(&c,12,false,0);request(&c,15,true,0);assert(c.capture.state==P1715_LA_ERROR);
 assert(!p1715_combined_start(&c,0));request(&c,12,false,0);request(&c,12,false,0);memset(f,0,sizeof(f));f[0]=1;f[1]=1;crc(f);f[21]^=1;
 for(unsigned i=0;i<22;i++)request(&c,i?15:13,true,f[i]);
 assert(c.capture.state==P1715_LA_ERROR && c.capture.crc_errors==1);
 p1715_combined_init(&c,NULL,0);assert(request(&c,14,false,0)==255 && p1715_combined_start(&c,0)<0);
 puts("combined endpoint PASS: negotiation, bounded storage, replay deduplication, terminal accounting, framing/CRC refusal");
}
