// SPDX-License-Identifier: MIT
#include "Vcosim_top.h"
#include "bridge.h"
extern "C" {
#include "machines/robotron1715/pc1715.h"
#include "model/controller.h"
}
#include <cstdio>
#include <cstdlib>
static Vcosim_top rtl;
static pc1715 *machine;
static pico1715_controller *card;
static bool active, launched;
static uint16_t address;
static int writing;
static uint64_t phase, requests, acks, returns;
static unsigned settle;
static void irq_inputs() {
    rtl.irq_pending=pico1715_irq(card);
    rtl.irq_vector=(card->irq_enabled && card->pending) ? card->vector : card->mark_vector;
}
static void clock_edge() {
    irq_inputs();
    if (!rtl.request) rtl.response_ack=0;
    else if (!rtl.response_ack) {
        uint16_t port=rtl.request_reg<8 ? rtl.request_reg : 0x20+(rtl.request_reg&3);
        if (!pico1715_wait(card,port,rtl.request_write)) {
            uint8_t data=0xff;
            if (rtl.request_write) pico1715_write(card,port,rtl.request_data);
            else pico1715_read(card,port,&data);
            rtl.response_data=data;rtl.response_ack=1;requests++;
        }
    }
    rtl.clk=0;rtl.eval();rtl.clk=1;rtl.eval();
    if (rtl.ack_pulse) {
        uint8_t vector=pico1715_ack(card);acks++;
        if(vector!=rtl.vector_data) {std::fputs("IRQ vector mismatch\n",stderr);std::abort();}
    }
    if (rtl.reti_pulse) {pico1715_reti(card);returns++;}
    if(rtl.fault) {std::fputs("RTL frontend fault\n",stderr);std::abort();}
}
extern "C" void cosim_init(void *m,void *c) {machine=(pc1715 *)m;card=(pico1715_controller *)c;}
extern "C" void cosim_reset(void *) {
    pico1715_reset(card);active=launched=false;phase=requests=acks=returns=0;settle=8;
    rtl.iorq_n=rtl.m1_n=rtl.rd_n=rtl.wr_n=1;
    rtl.obs_m1_n=rtl.obs_mreq_n=rtl.obs_iorq_n=rtl.obs_rd_n=1;
    rtl.power_good=1;rtl.reset_n=0;rtl.response_ack=0;
    clock_edge();rtl.reset_n=1;
    for(unsigned i=0;i<5;i++)clock_edge();
}
extern "C" void cosim_tick(void *,uint64_t cycle) {
    pico1715_tick(card,cycle);
    if(active && !launched) {
        rtl.host_addr=address;rtl.host_wdata=Z80_GET_DATA(machine->cpu.pins);
        rtl.iorq_n=0;rtl.m1_n=1;rtl.rd_n=writing;rtl.wr_n=!writing;
        launched=true;
    }
    phase+=50000000;
    unsigned count=(unsigned)(phase/PICO1715_CLOCK_HZ);phase%=PICO1715_CLOCK_HZ;
    // Only skip clocks once all sequential normal-bus state is quiescent.
    if(active || settle || rtl.request || rtl.response_ack) {
        // cosim_observe supplies the final edge of this CPU-tick allocation.
        for(unsigned i=1;i<count;i++)clock_edge();
        if(!active && settle)settle--;
    } else { irq_inputs();rtl.eval(); }
}
static bool claimed(uint16_t a,int write) {unsigned p=a&255;return p<8 || (write && p>=0x20 && p<=0x23);}
extern "C" int cosim_wait(void *,uint16_t a,int write) {
    if(!claimed(a,write))return 0;
    if(!active) {active=true;launched=false;address=a;writing=write;return 1;}
    return !launched || rtl.wait_pull_low;
}
static void finish() {
    active=launched=false;rtl.iorq_n=rtl.rd_n=rtl.wr_n=1;rtl.eval();settle=8;
}
extern "C" int cosim_read(void *,uint16_t a,uint8_t *v) {
    if(!claimed(a,0))return 0;
    if(!rtl.host_data_enable)std::abort();
    *v=rtl.host_rdata;finish();return 1;
}
extern "C" void cosim_write(void *,uint16_t a,uint8_t) {if(claimed(a,1))finish();}
extern "C" int cosim_irq(void *) {irq_inputs();rtl.eval();return rtl.int_pull_low;}
extern "C" uint8_t cosim_ack(void *) {
    rtl.obs_m1_n=rtl.obs_iorq_n=0;rtl.obs_mreq_n=rtl.obs_rd_n=1;
    clock_edge();
    if(!rtl.irq_data_enable)std::abort();
    return rtl.vector_data;
}
extern "C" void cosim_reti(void *) {} // Real opcode fetches below drive RTL RETI recognition.
extern "C" void cosim_observe(void) {
    uint64_t p=machine->cpu.pins;
    rtl.obs_m1_n=!(p&Z80_M1);rtl.obs_iorq_n=!(p&Z80_IORQ);
    rtl.obs_mreq_n=!(p&Z80_MREQ);rtl.obs_rd_n=!(p&Z80_RD);rtl.obs_data=Z80_GET_DATA(p);
    // One observation edge is within the elapsed CPU tick, not additional CPU time.
    clock_edge();
}
extern "C" uint64_t cosim_requests(void){return requests;}
extern "C" uint64_t cosim_acks(void){return acks;}
extern "C" uint64_t cosim_returns(void){return returns;}
