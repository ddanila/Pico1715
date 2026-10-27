/* SPDX-License-Identifier: MIT */
#include "../session.h"
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#define CHIPS_UTIL_IMPL
#include "third_party/cpu/chips/z80dasm.h"
#ifdef P1715_FIRMWARE_COSIM
#include "../../firmware/service.h"
#include "../firmware_host/host_hal.h"
int firmware_cosim_snapshot(unsigned);
#endif
#ifdef P1715_CAPTURE
#include "../analyzer/session_capture.h"
#endif
static pc1715 machine;
static pico1715_controller controller;
static uint8_t image[819200], keys[4096];
static unsigned initialized,head,count,half,attempted,accepted,rejected,disabled,full;
static uint64_t ticks,due;
static int target=-1,hit,exporting;
static char text[128];
static int result;
int p1715_result(void){return result;}
int p1715_version(void){return 2;}
int p1715_init(const uint8_t *rom,unsigned rom_size,const uint8_t *disk,unsigned disk_size,int writable){
    if(initialized || rom_size!=2048 || disk_size!=sizeof(image) || !rom || !disk)return result=-EINVAL;
    if(p1715_board_init(&machine))return result=-EINVAL;
    memcpy(machine.rom,rom,2048);memcpy(image,disk,sizeof(image));
    if(pico1715_mount(&controller,image,sizeof(image),80,2,5,3))return result=-EINVAL;
    controller.writable=!!writable;
    controller.timing.enabled=1;
    if(p1715_board_attach(&machine,&controller,0))return result=-EINVAL;
    initialized=1;return result=0;
}
static void tick(void){
    if(count && ticks>=due){
        int r=pc1715_sio_receive(&machine,0,half?keys[head]:0xe0);
        attempted++;if(!r)accepted++;else{rejected++;if(r==-EAGAIN)disabled++;else full++;}
        if(!half){half=1;due=ticks+1000;}else{half=0;head=(head+1)%4096;count--;due=ticks+100000;}
    }
    p1715_board_tick(&machine);p1715_board_observe();ticks++;
#ifdef P1715_CAPTURE
    p1715_capture_observe(&machine);
#endif
}
unsigned p1715_run(unsigned budget){
    if(!initialized || exporting)return result=0;
    unsigned n=0;hit=0;
    while(n<budget){tick();n++;if(target>=0 && z80_opdone(&machine.cpu.cpu) && Z80_GET_ADDR(machine.cpu.pins)==target){hit=1;break;}}
    return result=n;
}
int p1715_key(unsigned ch){
    if(!initialized || ch>127 || ch==0)return -EINVAL;
    if(count==4096)return -ENOSPC;
    keys[(head+count)%4096]=(uint8_t)ch;count++;if(count==1 && due<ticks)due=ticks;return 0;
}
void p1715_cancel(void){count=half?1:0;}
void p1715_reset(void){if(initialized && !exporting){head=count=half=0;due=ticks;target=-1;hit=0;pc1715_reset(&machine);}}
int p1715_break(int address){if(address< -1 || address>65535)return -EINVAL;target=address;hit=0;return 0;}
int p1715_hit(void){return hit;}
unsigned p1715_step(void){
    if(!initialized || exporting)return result=0;
    unsigned n=0;do{tick();n++;}while(n<100000 && !z80_opdone(&machine.cpu.cpu));return result=n;
}
const uint8_t *p1715_screen(void){return machine.ram+0xf800;}
const uint8_t *p1715_ram(void){return machine.ram;}
const uint8_t *p1715_disk(void){return image;}
int p1715_peek(unsigned a){return a>65535?-EINVAL:(machine.rom_enabled && a<2048?machine.rom[a]:machine.ram[a]);}
unsigned p1715_map(unsigned a,int write){return ((machine.rom_enabled && a<2048 && !write?2u:1u)<<24)|(a&65535);}
unsigned p1715_reg(unsigned i){
    z80_t *r=&machine.cpu.cpu;
    unsigned v[]={r->pc,r->sp,r->af,r->bc,r->de,r->hl,r->ix,r->iy,r->af2,r->bc2,r->de2,r->hl2,r->im,r->iff1,r->iff2,r->i,r->r,(unsigned)ticks,(unsigned)(ticks>>32),0,!!(machine.cpu.pins&Z80_HALT),z80_opdone(r),Z80_GET_ADDR(machine.cpu.pins)};
    return i<sizeof(v)/sizeof(*v)?v[i]:0;
}
typedef struct{uint16_t pc;unsigned n,len;} disasm;
static uint8_t dis_read(void *p){disasm*d=p;return d->n++<16?(uint8_t)p1715_peek(d->pc++):0;}
static void dis_write(char c,void*p){disasm*d=p;if(d->len<127)text[d->len++]=c;}
unsigned p1715_disassemble(unsigned pc){disasm d={(uint16_t)pc,0,0};unsigned end=z80dasm_op(d.pc,dis_read,dis_write,&d);text[d.len]=0;return end;}
const char *p1715_text(void){return text;}
/* Copy is returned only when all accepted firmware writes are committed. Each
 * call is bounded. Callers keep pumping until 1 or a negative error. */
int p1715_export(void){
    if(!initialized)return result=-EINVAL;
    if(!exporting){
        if(machine.io_active || !z80_opdone(&machine.cpu.cpu)){
            unsigned n=0;do{tick();n++;}while(n<1024 && (machine.io_active || !z80_opdone(&machine.cpu.cpu)));
            if(machine.io_active || !z80_opdone(&machine.cpu.cpu))return result=0;
        }
        exporting=1;
    }
#ifdef P1715_FIRMWARE_COSIM
    int r=firmware_cosim_snapshot(100);
#else
    int r=1;
#endif
    if(r)exporting=0;
    return result=r;
}
double p1715_stat(unsigned i){
    double v[]={ticks,controller.cylinder,controller.sector,controller.fields,controller.writes,
      controller.rejected_writes,machine.wait_ticks,controller.overruns,controller.underflows,
      controller.tx_early,controller.tx_late,count,attempted,accepted,rejected,disabled,full,
      machine.rom_enabled,controller.write_active,controller.stream_active};
    if(i<sizeof(v)/sizeof(*v))return v[i];
#ifdef P1715_FIRMWARE_COSIM
    switch(i){case 20:return p1715_status.state;case 21:return p1715_status.dirty_blocks;
      case 22:return p1715_status.storage_error;case 23:return cosim_requests();case 24:return host_sd_writes;}
#endif
    return -1;
}
