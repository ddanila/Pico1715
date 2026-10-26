/* SPDX-License-Identifier: MIT */
#include "../firmware/service.h"
#include "../firmware/store.h"
#include "../tools/firmware_host/host_hal.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint8_t original[P1715_IMAGE_BYTES];
static pico1715_controller card;
static unsigned read_work,write_work,write_mode;
static void process_write(unsigned kind){
 if(kind!=P1715_COST_WRITE)return;
 write_work++;
 assert(host_outputs&(1u<<14)); /* the byte was admitted before processing */
 if(write_mode==1)host_inputs &= ~(1u<<15);
 if(write_mode==2)p1715_shutdown_command=P1715_POWER_FAIL;
 if(write_mode==3)host_time_us+=80;
}
static void tx_fixture(void){
 host_storage_init(original,false);assert(!p1715_service_init(&card,true));
 card.write_active=1;card.write_mark=1;card.tx_ready=UINT64_MAX;
 host_cost_hook=process_write;write_work=write_mode=0;
}
static uint8_t tail_fixture(void){
 tx_fixture();card.write_active=0;card.timing.enabled=0;
 pico1715_write(&card,0x20,0xef);pico1715_write(&card,6,4);
 pico1715_write(&card,4,0xa5);pico1715_write(&card,4,0x85);
 pico1715_write(&card,4,0xa5);pico1715_write(&card,4,0x85);
 assert(card.length==1030);
 memcpy(card.write_buffer,card.field+4,1025);
 card.write_pos=1025;card.write_active=card.write_mark=1;card.control=0xb4;
 card.timing.enabled=1;card.tx_ready=UINT64_MAX;card.stream_active=0;
 return card.field[1029];
}
static void withdraw_read(unsigned kind){
 if(kind==P1715_COST_READ){read_work++;host_inputs &= ~(1u<<13);}
}
static void step(uint32_t inputs){host_inputs=inputs;host_time_us++;p1715_service_step();}
int main(void){
 for(unsigned i=0;i<sizeof(original);i++)original[i]=(uint8_t)(i^(i>>9));
 host_storage_init(original,true);
 assert(p1715_service_init(&card,false)==-1 && p1715_status.state==0xe2);
 assert(!(host_outputs&(1u<<21)));
 host_storage_init(original,false);host_fail_read=3;
 assert(p1715_service_init(&card,false)==-1 && p1715_status.state==0xe3);
 assert(!(host_outputs&(1u<<21)));
 host_storage_init(original,false);
 assert(!p1715_service_init(&card,false));
 assert(!host_worker && !card.writable && host_sd_reads==1602);
 assert(card.timing.fifo_depth==P1715_RX_FIFO_DEPTH && P1715_RX_FIFO_DEPTH==2);
 assert(!memcmp(card.image,original,sizeof(original)));
 // Write a vector once; a held request must never repeat the side effect.
 const uint32_t reset=1u<<15,req=1u<<13,write=1u<<12;
 step(reset|req|write|(5u<<8)|0x80);
 assert(card.vector==0x80 && p1715_status.requests==1 && (host_outputs&(1u<<14)));
 step(reset|req|write|(5u<<8)|0x82);
 assert(card.vector==0x80 && p1715_status.requests==1);
 step(reset);assert(!(host_outputs&(1u<<14)) && !(host_directions&255));
 step(reset|req|(4u<<8));
 assert(p1715_status.requests==2 && (host_directions&255)==255);
 // Host reset during an answered read releases both ACK and the data bus.
 step(0);assert(!(host_outputs&((1u<<21)|(1u<<14))) && !(host_directions&255));
 step(reset);assert(host_outputs&(1u<<21));
 assert(card.timing.fifo_depth==P1715_RX_FIFO_DEPTH && !card.rx_count);
 step(reset|req|(4u<<8));assert(p1715_status.requests==3);
 step(reset);
 // Toggle notifications are consumed once, even when held across many polls.
 card.pending=1;card.irq_enabled=1;card.service=0;
 step(reset);assert(host_outputs&(1u<<16));
 uint64_t interrupts=card.interrupts;
 step(reset|(1u<<18)|(1u<<20));
 assert(card.service && !card.pending && card.interrupts==interrupts+1);
 step(reset|(1u<<18)|(1u<<20));assert(card.interrupts==interrupts+1);
 step(reset|(1u<<18)|(1u<<19)|(1u<<20));assert(!card.service);
 assert(host_sd_writes==0 && !memcmp(host_storage_image(),original,sizeof(original)));
 host_storage_init(original,false);assert(!p1715_service_init(&card,true));
 assert(host_worker && card.writable);
 // A timed-out read disables speculative preparation until host reset, so
 // an idle, faulted mailbox cannot keep launching background receive work.
 card.stream_active=1;card.rx_count=1;card.rx_head=0;card.rx[0]=0x63;
 card.next_byte=UINT64_MAX;
 host_cost_hook=withdraw_read;
 step(reset|req|(2u<<8));assert(read_work==1 && !card.prepared && !card.bytes);
 step(reset);assert(read_work==1 && !card.prepared);
 step(0);step(reset);host_cost_hook=NULL;
 assert(!card.prepared && !card.rx_count);
 // Admission copies data once; a held request cannot overwrite or duplicate it.
 tx_fixture();
 step(reset|req|write|0x63);
 assert(p1715_status.requests==1 && write_work==1 && card.tx_full);
 step(reset|req|write|0x96);
 assert(write_work==1 && card.tx_full && card.tx_data==0x63 && p1715_status.requests==1);
 step(reset);step(reset|req|write|0x96);
 assert(!(host_outputs&(1u<<14)) && p1715_status.requests==1); /* backpressure */
 step(reset);card.tx_full=0;
 step(reset|req|write|0x96);step(0);step(reset);
 assert(write_work==2 && !card.tx_full && !card.write_active && !card.writes);
 // Reset while processing discards the captured byte and releases ACK.
 tx_fixture();write_mode=1;
 step(reset|req|write|0x63);
 assert(write_work==1 && !card.tx_full && !(host_outputs&(1u<<14)));
 step(0);step(reset);assert(!card.write_active);
 // Power-fail arriving during processing cannot publish the staged byte.
 tx_fixture();write_mode=2;
 step(reset|req|write|0x63);step(reset);step(reset);
 assert(write_work==1 && !card.tx_full && !card.write_active && !card.writes);
 assert(p1715_status.shutdown==P1715_SAFE && !p1715_status.dirty_blocks);
 // Processing time cannot be hidden from the serializer's clock.
 tx_fixture();write_mode=3;card.tx_ready=100*PICO1715_BIT_RATE;
 step(reset|req|write|0x63);step(reset);
 assert(write_work==1 && card.tx_late && card.tx_data==0x63);
 assert(!memcmp(host_storage_image(),original,sizeof(original)));
 // Closing the write gate must not magically serialize a captured CRC tail.
 uint8_t tail=tail_fixture();
 step(reset|req|write|tail);assert(card.tx_full && card.write_pos==1025);
 step(reset);step(reset|req|write|(4u<<8)|0xbf);
 assert(!card.writes && card.rejected_writes==1 && !p1715_status.dirty_blocks);
 assert(!memcmp(card.image,original,sizeof(original)));
 // Once the last CRC byte really crosses the serializer, the same close commits.
 tail=tail_fixture();step(reset|req|write|tail);
 card.tx_ready=card.cycle*PICO1715_BIT_RATE;pico1715_tick(&card,card.cycle);
 assert(card.write_pos==1026 && !card.tx_full);
 step(reset);step(reset|req|write|(4u<<8)|0xbf);
 assert(card.writes==1 && !card.rejected_writes && p1715_status.dirty_blocks==2);
 host_cost_hook=NULL;
 puts("firmware service PASS: startup failures, image load, held request, GPIO release, reset, IRQ/RETI, read-only storage");
}
