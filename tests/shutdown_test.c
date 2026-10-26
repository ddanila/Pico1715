/* SPDX-License-Identifier: MIT. Production service/store with deterministic SD interleaving. */
#include "../firmware/service.h"
#include "../firmware/store.h"
#include "../tools/firmware_host/host_hal.h"
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include <string.h>
static uint8_t original[P1715_IMAGE_BYTES];
static pico1715_controller card;
static unsigned cut,action,probes;
static jmp_buf outage;
static void step(void){host_time_us++;p1715_service_step();}
static void out(unsigned port,uint8_t data){
 unsigned reg=port<8?port:8+(port&3);
 host_inputs=(1u<<15)|(1u<<13)|(1u<<12)|(reg<<8)|data;step();
 host_inputs=1u<<15;step();
}
static void fresh(bool writable){
 host_storage_init(original,false);assert(!p1715_service_init(&card,writable));
 host_inputs=1u<<15;card.timing.enabled=0;cut=action=probes=0;
}
static uint16_t crc(uint16_t c,uint8_t b){
 c^=(uint16_t)b<<8;for(unsigned i=0;i<8;i++)c=(uint16_t)((c<<1)^((c&0x8000)?0x1021:0));return c;
}
static void sector(uint8_t value){
 out(0x20,0xef);out(6,4);out(4,0xa5);out(4,0x85);
 /* Observe the ID through the controller to establish the write destination. */
 uint8_t byte;for(unsigned i=0;i<10;i++)assert(pico1715_read(&card,2,&byte));
 out(4,0xb4);
 uint16_t sum=0xffff;
 for(unsigned i=0;i<1028;i++){
  uint8_t b=i<3?0xa1:i==3?0xfb:value;sum=crc(sum,b);out(0,b);
 }
 out(0,sum>>8);out(0,(uint8_t)sum);out(4,0xbf);
}
static void isolated(void){
 assert(!(host_outputs&((1u<<21)|(1u<<14)|(1u<<16)|(1u<<17))));
 assert(!(host_directions&255));assert(!card.writable);
}
static void hook(bool write,uint32_t lba){
 (void)lba;if(!write)return;probes++;
 assert(p1715_status.storage_busy);
 assert(p1715_status.shutdown!=P1715_SAFE);
 if(action==1){assert(!p1715_shutdown_request(P1715_EJECT));isolated();}
 if(action==2){host_time_us+=100;step();}
 if(action==3 || action==4){assert(!p1715_backup_update(action==3?P1715_BACKUP_EXHAUSTED:P1715_BACKUP_FAILED,0));}
 if(cut && host_sd_writes==cut)longjmp(outage,1);
}
static void unchanged(void){assert(!memcmp(card.image,original,sizeof(original)));}
int main(void){
 memset(original,0x31,sizeof(original));
 fresh(false);assert(p1715_write_policy(P1715_WRITE_PROTECTED,100,100)==-1);
 p1715_shutdown_command=P1715_EJECT;step();assert(p1715_status.shutdown==P1715_SAFE);isolated();
 /* Backup absent: explicit eject drains normally while external power is present. */
 fresh(true);sector(0x72);assert(p1715_status.dirty_blocks==2);
 host_io_hook=hook;action=1;p1715_storage_step();
 assert(probes==8 && p1715_status.shutdown==P1715_SAFE && !p1715_status.dirty_blocks);isolated();
 for(unsigned i=0;i<1024;i++)assert(host_storage_image()[i]==0x72);
 uint64_t requests=p1715_status.requests;out(4,0xff);
 assert(p1715_status.requests==requests);host_inputs=0;step();host_inputs=1u<<15;step();isolated();
 assert(p1715_status.shutdown==P1715_SAFE); /* host reset cannot reopen ejected media */
 /* An incomplete sector has not committed: eject cancels it without dirtying media. */
 fresh(true);out(4,0xb4);out(0,0xa1);assert(card.write_active);
 assert(!p1715_shutdown_request(P1715_EJECT));assert(!card.write_active);
 assert(p1715_status.shutdown==P1715_SAFE);unchanged();isolated();
 /* Power fail with no reserve must not claim safe with acknowledged RAM writes. */
 fresh(true);sector(0x72);assert(!p1715_shutdown_request(P1715_POWER_FAIL));
 assert(p1715_status.shutdown==P1715_UNSAFE && p1715_status.shutdown_reason==P1715_SHUTDOWN_RESERVE);
 p1715_storage_step();assert(!host_sd_writes);isolated();
 /* Protected policy gates writes until charged; no invented default flush budget. */
 fresh(true);assert(p1715_write_policy(P1715_WRITE_PROTECTED,0,0)==-1);
 assert(!p1715_write_policy(P1715_WRITE_PROTECTED,100,100));
 sector(0x72);unchanged();assert(!p1715_status.dirty_blocks);
 assert(!p1715_backup_update(P1715_BACKUP_CHARGING,9999));sector(0x72);unchanged();
 assert(!p1715_backup_update(P1715_BACKUP_READY,299));sector(0x72);unchanged();
 assert(!p1715_backup_update(P1715_BACKUP_READY,300));sector(0x72);assert(p1715_status.dirty_blocks==2);
 uint64_t writes=card.writes;sector(0x93);assert(card.writes==writes); /* budget full */
 assert(!p1715_shutdown_request(P1715_POWER_FAIL));uint64_t deadline=p1715_status.shutdown_deadline;
 assert(!p1715_backup_update(P1715_BACKUP_READY,99999));
 assert(!p1715_shutdown_request(P1715_POWER_FAIL));assert(p1715_status.shutdown_deadline==deadline);
 assert(!p1715_backup_update(P1715_BACKUP_READY,100));
 assert(p1715_status.shutdown_deadline<deadline);deadline=p1715_status.shutdown_deadline;
 assert(!p1715_shutdown_request(P1715_POWER_FAIL));assert(p1715_status.shutdown_deadline==deadline);
 p1715_storage_step();assert(p1715_status.shutdown==P1715_SAFE);
 /* Reserve loss before outage freezes writes and drains under live power. */
 fresh(true);assert(!p1715_write_policy(P1715_WRITE_PROTECTED,100,100));
 assert(!p1715_backup_update(P1715_BACKUP_READY,500));sector(0x72);
 assert(!p1715_backup_update(P1715_BACKUP_CHARGING,0));isolated();
 assert(p1715_status.shutdown==P1715_DRAINING);p1715_storage_step();assert(p1715_status.shutdown==P1715_SAFE);
 /* Deadline and reserve exhaustion during an SD operation cannot turn SAFE later. */
 for(unsigned mode=2;mode<=4;mode++){
  fresh(true);sector(0x72);assert(!p1715_backup_update(P1715_BACKUP_READY,300));
  assert(!p1715_shutdown_request(P1715_POWER_FAIL));host_io_hook=hook;action=mode;
  p1715_storage_step();assert(p1715_status.shutdown==P1715_UNSAFE);isolated();
  assert(!p1715_backup_update(P1715_BACKUP_READY,99999));
  assert(!p1715_shutdown_request(P1715_EJECT));assert(p1715_status.shutdown==P1715_UNSAFE);
 }
 /* Every write/journal phase fails closed, including clear after target completion. */
 for(unsigned torn=0;torn<=259;torn+=259)for(unsigned phase=1;phase<=8;phase++){
  fresh(true);sector(0x72);assert(!p1715_shutdown_request(P1715_EJECT));
  host_torn_bytes=torn;host_fail_write=phase;host_io_hook=hook;p1715_storage_step();
  assert(p1715_status.shutdown==P1715_UNSAFE && p1715_status.storage_error);
  assert(p1715_status.dirty_blocks && !p1715_status.storage_busy);isolated();
 }
 /* Abrupt power loss at every phase: cold recovery is block-atomic, not sector-atomic. */
 for(unsigned phase=1;phase<=8;phase++){
  fresh(true);sector(0x72);assert(!p1715_shutdown_request(P1715_EJECT));
  cut=phase;host_io_hook=hook;
  if(!setjmp(outage)){p1715_storage_step();assert(0);}
  host_storage_power_cycle();assert(!p1715_service_init_protected(&card,100,100));
  assert(!card.writable && p1715_status.write_policy==P1715_WRITE_PROTECTED);
  for(unsigned i=0;i<1024;i++)assert(card.image[i]==(i<512?(phase>=3?0x72:0x31):(phase>=7?0x72:0x31)));
  assert(p1715_status.backup==P1715_BACKUP_ABSENT);
  assert(!p1715_write_policy(P1715_WRITE_PROTECTED,100,100));
  host_inputs=1u<<15;card.timing.enabled=0;sector(0x93);assert(!p1715_status.dirty_blocks);
 }
 puts("shutdown PASS: eject, isolation, in-flight journal, reserve gating/budget, repeated outages, deadline, 16 SD failures/torn writes and 8 power cuts");
}
