// SPDX-License-Identifier: MIT
#include "Vfirmware_cosim_top.h"
#include "tools/cosim/bridge.h"
extern "C" {
#include "machines/robotron1715/pc1715.h"
#include "firmware/service.h"
#include "firmware/store.h"
#include "host_hal.h"
}
#include <cstdio>
#include <cstdlib>
#include <cstring>
static Vfirmware_cosim_top rtl;
static pc1715 *machine;
static pico1715_controller *card;
static uint8_t *output_image;
static bool active,launched,ready,last_ack,last_reti,last_response;
static uint16_t address;
static int writing;
static uint64_t phase,requests,acks,returns,last_poll,last_worker;
static unsigned settle;
static void pins() {rtl.gpio_out=host_outputs;rtl.gpio_dir=host_directions;rtl.eval();host_inputs=rtl.gpio_in;}
static void service(bool force=false) {
    pins();
    if(ready && (force || host_time_us!=last_poll)) {
        last_poll=host_time_us;p1715_service_step();pins();
    }
    if(host_worker && host_time_us-last_worker>=100) {
        last_worker=host_time_us;
        if(p1715_status.dirty_blocks && !p1715_status.storage_error)p1715_storage_step();
    }
}
static void clock_edge() {
    service();
    rtl.clk100=0;rtl.eval();rtl.clk100=1;rtl.eval();
    bool response=(host_outputs>>14)&1;
    if(response && !last_response) {
        if(!(rtl.gpio_in&(1u<<13)))std::abort();
        requests++;
    }
    last_response=response;
    bool ack=(rtl.gpio_in>>18)&1,reti=(rtl.gpio_in>>19)&1;
    if(ack!=last_ack){last_ack=ack;acks++;}
    if(reti!=last_reti){last_reti=reti;returns++;}
    if(rtl.fault || rtl.contention) {std::fprintf(stderr,"Firmware RTL fault=%u contention=%u time=%llu inputs=%08x outputs=%08x dir=%08x\n",rtl.fault,rtl.contention,(unsigned long long)host_time_us,host_inputs,host_outputs,host_directions);std::abort();}
}
extern "C" void cosim_init(void *m,void *c) {
    machine=(pc1715 *)m;card=(pico1715_controller *)c;
    requests=acks=returns=0;
    // The probe's original image is an output buffer only after initialization.
    output_image=card->image;
    // Absent-media probes retain their image separately (see export API).
    if(!output_image) {std::fputs("missing initial image buffer\n",stderr);std::abort();}
}
extern "C" void firmware_cosim_start(int absent) {
    bool writable=card->writable;
    host_storage_init(output_image,absent);
    ready=p1715_service_init(card,writable)==0;
    last_poll=UINT64_MAX;last_worker=0;
}
extern "C" void cosim_reset(void *) {
    active=launched=false;phase=0;settle=8;
    host_time_us=0;last_poll=UINT64_MAX;last_worker=0;
    rtl.transaction=0;rtl.iorq_n=rtl.rd_n=rtl.wr_n=1;
    rtl.obs_m1_n=rtl.obs_mreq_n=rtl.obs_iorq_n=rtl.obs_rd_n=1;
    rtl.power_good=1;rtl.reset_n=0;last_ack=last_reti=last_response=false;
    service(true);clock_edge();rtl.reset_n=1;service(true);
    for(unsigned i=0;i<12;i++)clock_edge();
}
extern "C" void cosim_tick(void *,uint64_t cycle) {
    host_time_us=cycle*1000000/PICO1715_CLOCK_HZ;
    if(active && !launched) {
        rtl.host_addr=address;rtl.host_wdata=Z80_GET_DATA(machine->cpu.pins);
        rtl.transaction=1;rtl.iorq_n=0;rtl.rd_n=writing;rtl.wr_n=!writing;
        launched=true;
    }
    phase+=100000000;
    unsigned count=(unsigned)(phase/PICO1715_CLOCK_HZ);phase%=PICO1715_CLOCK_HZ;
    if(active || settle || ((rtl.gpio_in>>13)&1) || ((host_outputs>>14)&1)) {
        for(unsigned i=2;i<count;i++)clock_edge();
        if(!active && settle)settle--;
    } else service();
}
static bool claimed(uint16_t a,int write) {unsigned p=a&255;return p<8 || (write && p>=0x20 && p<=0x23);}
extern "C" int cosim_wait(void *,uint16_t a,int write) {
    if(!claimed(a,write))return 0;
    if(!active){active=true;launched=false;address=a;writing=write;return 1;}
    return !launched || rtl.wait_pull_low;
}
static void finish(){active=launched=false;rtl.transaction=0;rtl.iorq_n=rtl.rd_n=rtl.wr_n=1;rtl.eval();settle=8;}
extern "C" int cosim_read(void *,uint16_t a,uint8_t *v){
    if(!claimed(a,0))return 0;
    if(!rtl.host_data_enable && ready)std::abort();
    *v=rtl.host_data_enable?rtl.host_rdata:0xff;finish();return 1;
}
extern "C" void cosim_write(void *,uint16_t a,uint8_t){if(claimed(a,1))finish();}
extern "C" int cosim_irq(void *){pins();return rtl.int_pull_low;}
extern "C" uint8_t cosim_ack(void *){
    rtl.obs_m1_n=rtl.obs_iorq_n=0;rtl.obs_mreq_n=rtl.obs_rd_n=1;
    clock_edge();clock_edge();
    if(!rtl.host_data_enable)std::abort();
    return rtl.host_rdata;
}
extern "C" void cosim_reti(void *){}
extern "C" void cosim_observe(void){
    uint64_t p=machine->cpu.pins;
    rtl.obs_m1_n=!(p&Z80_M1);rtl.obs_iorq_n=!(p&Z80_IORQ);
    rtl.obs_mreq_n=!(p&Z80_MREQ);rtl.obs_rd_n=!(p&Z80_RD);rtl.obs_data=Z80_GET_DATA(p);
    clock_edge();clock_edge();
}
extern "C" uint64_t cosim_requests(void){return requests;}
extern "C" uint64_t cosim_acks(void){return acks;}
extern "C" uint64_t cosim_returns(void){return returns;}
extern "C" void firmware_cosim_export(void){
    if(host_worker && !p1715_status.storage_error)p1715_storage_step();
    if(ready && std::memcmp(card->image,host_storage_image(),P1715_IMAGE_BYTES)) {
        std::fputs("PSRAM differs from persisted SD image\n",stderr);std::abort();
    }
    std::memcpy(output_image,host_storage_image(),P1715_IMAGE_BYTES);
    std::fprintf(stderr,"Firmware state=%u requests=%llu sd_reads=%llu sd_writes=%llu dirty=%u error=%u\n",
        p1715_status.state,(unsigned long long)p1715_status.requests,
        (unsigned long long)host_sd_reads,(unsigned long long)host_sd_writes,
        p1715_status.dirty_blocks,p1715_status.storage_error);
}
