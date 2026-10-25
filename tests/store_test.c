/* SPDX-License-Identifier: MIT */
#include "../firmware/store.h"
#include "../firmware/sd_crc.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint8_t media[(P1715_IMAGE_LBA+P1715_IMAGE_BLOCKS)*512];
static unsigned writes,fail_at,torn;
static int rd(void *p,uint32_t b,uint8_t *d){(void)p;memcpy(d,media+b*512,512);return 0;}
static int wr(void *p,uint32_t b,const uint8_t *d){(void)p;writes++;
 if(writes==fail_at){if(torn)memcpy(media+b*512,d,19);return -1;}
 memcpy(media+b*512,d,512);return 0;}
static void word(uint8_t *b,uint32_t n){for(unsigned i=0;i<4;i++)b[i]=(uint8_t)(n>>(i*8));}
static void fresh(void){memset(media,0,sizeof(media));memcpy(media,"P1715SD1",8);
 word(media+8,P1715_IMAGE_LBA);word(media+12,P1715_IMAGE_BLOCKS);word(media+508,p1715_crc32(media,508));
 writes=fail_at=torn=0;}
int main(void){
 assert(p1715_sd_crc7(0,0)==0x95);assert(p1715_sd_crc7(8,0x1aa)==0x87);
 assert(p1715_sd_crc16((const uint8_t *)"123456789",9)==0x31c3);
 assert(p1715_crc32((const uint8_t *)"123456789",9)==0xcbf43926u);
 p1715_store s={NULL,rd,wr,0};uint8_t data[512],readback[512];
 for(unsigned i=0;i<512;i++)data[i]=(uint8_t)(i^0x69);
 fresh();assert(!p1715_store_open(&s));assert(!p1715_store_write(&s,1599,data));
 assert(!p1715_store_read(&s,1599,readback)&&!memcmp(data,readback,512));
 assert(!p1715_store_open(&s));assert(p1715_store_write(&s,1600,data));
 for(unsigned cut=1;cut<=4;cut++){
  fresh();assert(!p1715_store_open(&s));fail_at=cut;
  assert(p1715_store_write(&s,3,data)&&s.failed);
  unsigned n=writes;assert(p1715_store_write(&s,4,data)&&writes==n);
  fail_at=0;assert(!p1715_store_open(&s));assert(!p1715_store_read(&s,3,readback));
  if(cut<3){uint8_t zero[512]={0};assert(!memcmp(readback,zero,512));}
  else assert(!memcmp(readback,data,512));
 }
 fresh();assert(!p1715_store_open(&s));fail_at=2;torn=1;
 assert(p1715_store_write(&s,4,data));fail_at=0;assert(p1715_store_open(&s));
 fresh();assert(!p1715_store_open(&s));fail_at=3;assert(p1715_store_write(&s,4,data));
 fail_at=0;media[2*512+17]^=1;assert(p1715_store_open(&s));
 fresh();media[508]^=1;assert(p1715_store_open(&s));
 puts("storage PASS: CRC, bounds, cold-open, all four write cuts, torn header and corrupt journal");
}
