/* SPDX-License-Identifier: MIT */
#include "host_hal.h"
#include "../../firmware/store.h"
#include <string.h>
#include <assert.h>
uint32_t host_inputs,host_outputs,host_directions;
uint64_t host_time_us,host_sd_reads,host_sd_writes,host_fail_read,host_fail_write;
bool host_worker;
unsigned host_torn_bytes;
void (*host_io_hook)(bool,uint32_t);
void (*host_cost_hook)(unsigned);
void (*host_lock_hook)(critical_section_t *,bool);
static uint8_t sd[(P1715_IMAGE_LBA+P1715_IMAGE_BLOCKS)*512];
static uint8_t psram[P1715_IMAGE_BYTES];
static bool missing;
static void put32(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
void host_storage_init(const uint8_t *image,bool absent){
 memset(sd,0,sizeof(sd));memset(psram,0,sizeof(psram));missing=absent;
 memcpy(sd,"P1715SD1",8);put32(sd+8,P1715_IMAGE_LBA);put32(sd+12,P1715_IMAGE_BLOCKS);
 put32(sd+508,p1715_crc32(sd,508));
 memcpy(sd+P1715_IMAGE_LBA*512,image,P1715_IMAGE_BYTES);
 host_storage_power_cycle();
}
void host_storage_power_cycle(void){
 memset(psram,0,sizeof(psram));
 host_sd_reads=host_sd_writes=host_fail_read=host_fail_write=0;host_worker=false;
 host_torn_bytes=0;host_io_hook=NULL;host_cost_hook=NULL;host_lock_hook=NULL;
 host_inputs=host_outputs=host_directions=0;host_time_us=0;
}
uint8_t *p1715_psram(void){return psram;}
int p1715_sd_init(void){return missing?-1:0;}
int p1715_sd_read(void *u,uint32_t lba,uint8_t *data){
 (void)u;if(missing||lba>=sizeof(sd)/512)return -1;
 host_sd_reads++;if(host_io_hook)host_io_hook(false,lba);
 if(host_fail_read && host_sd_reads==host_fail_read)return -1;
 memcpy(data,sd+lba*512,512);return 0;
}
int p1715_sd_write(void *u,uint32_t lba,const uint8_t *data){
 (void)u;if(missing||lba>=sizeof(sd)/512)return -1;
 host_sd_writes++;if(host_io_hook)host_io_hook(true,lba);
 if(host_fail_write && host_sd_writes==host_fail_write){
  assert(host_torn_bytes<=512);memcpy(sd+lba*512,data,host_torn_bytes);return -1;
 }
 memcpy(sd+lba*512,data,512);return 0;
}
const uint8_t *host_storage_image(void){return sd+P1715_IMAGE_LBA*512;}
const uint8_t *host_storage_block(uint32_t lba){
 assert(lba<sizeof(sd)/512);return sd+lba*512;
}
