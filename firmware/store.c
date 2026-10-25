/* SPDX-License-Identifier: MIT */
#include "store.h"
#include <string.h>
static uint32_t get32(const uint8_t *b){return b[0]|((uint32_t)b[1]<<8)|((uint32_t)b[2]<<16)|((uint32_t)b[3]<<24);}
static void put32(uint8_t *b,uint32_t n){for(unsigned i=0;i<4;i++)b[i]=(uint8_t)(n>>(8*i));}
uint32_t p1715_crc32(const uint8_t *b,unsigned n){
 uint32_t crc=~0u;
 while(n--){crc^=*b++;for(unsigned bit=0;bit<8;bit++)crc=(crc>>1)^((crc&1)?0xedb88320u:0);}
 return ~crc;
}
static int fail(p1715_store *s){s->failed=1;return -1;}
static int clear(p1715_store *s){uint8_t zero[512]={0};return s->write(s->user,1,zero)?fail(s):0;}
int p1715_store_open(p1715_store *s){
 uint8_t h[512],data[512],zero[512]={0};s->failed=0;
 if(s->read(s->user,0,h)||memcmp(h,"P1715SD1",8)||get32(h+8)!=P1715_IMAGE_LBA||
    get32(h+12)!=P1715_IMAGE_BLOCKS||get32(h+508)!=p1715_crc32(h,508))return fail(s);
 if(s->read(s->user,1,h))return fail(s);
 if(!memcmp(h,zero,512))return 0;
 if(memcmp(h,"P1715J01",8)||get32(h+508)!=p1715_crc32(h,508)||get32(h+8)>=P1715_IMAGE_BLOCKS)
  return fail(s); /* A torn/unknown record fails closed, never guesses. */
 if(s->read(s->user,2,data)||get32(h+12)!=p1715_crc32(data,512))return fail(s);
 if(s->write(s->user,P1715_IMAGE_LBA+get32(h+8),data))return fail(s);
 return clear(s);
}
int p1715_store_read(p1715_store *s,uint32_t block,uint8_t *data){
 if(s->failed||block>=P1715_IMAGE_BLOCKS)return fail(s);
 return s->read(s->user,P1715_IMAGE_LBA+block,data)?fail(s):0;
}
int p1715_store_write(p1715_store *s,uint32_t block,const uint8_t *data){
 uint8_t h[512]={0};
 if(s->failed||block>=P1715_IMAGE_BLOCKS)return fail(s);
 memcpy(h,"P1715J01",8);put32(h+8,block);put32(h+12,p1715_crc32(data,512));
 put32(h+508,p1715_crc32(h,508));
 // One outstanding redo record; do not reuse its data after any write failure.
 if(s->write(s->user,2,data)||s->write(s->user,1,h)||
    s->write(s->user,P1715_IMAGE_LBA+block,data))return fail(s);
 return clear(s);
}
