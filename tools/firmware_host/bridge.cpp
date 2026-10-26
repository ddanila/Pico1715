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
#include <ucontext.h>
#include <cerrno>
#include <cassert>
static Vfirmware_cosim_top rtl;
static pc1715 *machine;
static pico1715_controller *card;
static uint8_t *output_image;
static bool active,launched,ready,last_ack,last_reti,last_response;
static uint16_t address;
static int writing;
static uint64_t phase,requests,acks,returns,last_poll,last_worker;
static unsigned settle;
static ucontext_t serving_context;
static uint8_t serving_stack[128*1024];
static bool serving_busy,reset_observed,exporting;
static uint64_t serving_due;
static unsigned current_core=2,lock_owner=2;
static unsigned costs[P1715_COST_COUNT];
static uint64_t cost_calls[P1715_COST_COUNT],cost_yields,lock_wait_us;
static uint64_t fault_count,first_fault_us;
static bool last_fault;
// Separate deterministic worker stack: SD waits yield while the real CPU/RTL
// and firmware serving loop continue. No OS threads or lock preemption.
static ucontext_t worker_context, caller_context;
static uint8_t worker_stack[128*1024];
static bool worker_busy;
static uint64_t worker_due,clock_epoch;
static unsigned sd_write_delay;
static uint64_t sd_yields,resets_while_busy;
// Optional bounded diagnostic window: 256 microsecond samples before the first
// RX overrun/TX underrun, followed by 64 samples. No guest or model mutation.
struct LossSample {
    uint64_t us, cycle, overruns, underruns, waits;
    unsigned pc, address, active, write, inputs, outputs, pos, length, rx;
    unsigned pending, mark, irq_service, lock, core_due, tx_full, prepared;
};
static LossSample loss_ring[256];
static unsigned loss_count,loss_next,loss_tail;
static bool loss_triggered;
static FILE *loss_file;
static void loss_line(const LossSample &s){
    std::fprintf(loss_file,"%llu,%llu,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%llu,%llu,%llu,%u\n",
        (unsigned long long)s.us,(unsigned long long)s.cycle,s.pc,s.address,s.active,s.write,
        s.inputs,s.outputs,s.pos,s.length,s.rx,s.pending,s.mark,s.irq_service,s.lock,s.core_due,s.tx_full,
        (unsigned long long)s.overruns,(unsigned long long)s.underruns,(unsigned long long)s.waits,s.prepared);
}
static void loss_sample(){
    if(!loss_file)return;
    LossSample s={host_time_us,card->cycle,card->overruns,card->tx_late,lock_wait_us,
        machine->cpu.cpu.pc,address,(unsigned)active,(unsigned)writing,host_inputs,host_outputs,
        card->pos,card->length,card->rx_count,card->pending,card->mark_pending,card->service,
        lock_owner,(unsigned)(serving_busy && serving_due>host_time_us?serving_due-host_time_us:0),card->tx_full,card->prepared};
    if(loss_triggered){
        loss_line(s);
        if(!--loss_tail){std::fclose(loss_file);loss_file=nullptr;}
        return;
    }
    loss_ring[loss_next]=s;loss_next=(loss_next+1)%256;if(loss_count<256)loss_count++;
    if(s.overruns || s.underruns){
        loss_triggered=true;loss_tail=64;
        for(unsigned i=0;i<loss_count;i++)loss_line(loss_ring[(loss_next+256-loss_count+i)%256]);
        std::fflush(loss_file);
    }
}
static void pause_core(unsigned delay){
    assert(current_core<2);
    uint64_t &due=current_core?worker_due:serving_due;
    due=host_time_us+delay;
    if(swapcontext(current_core?&worker_context:&serving_context,&caller_context))std::abort();
}
static unsigned stress_period=257,stress_width,stress_phase,stress_extra[6];
static unsigned sd_sequence[16],sd_count,sd_min=1000001,sd_max;
static int index_phase_us;
static uint64_t stress_hits[6],sd_calls,index_start_tick,index_resets,fault_iacks;
static unsigned setting(const char *key,unsigned fallback,unsigned maximum){
    const char *v=std::getenv(key);if(!v)return fallback;
    if(!*v)std::exit(2);
    for(const char *p=v;*p;p++)if(*p<'0'||*p>'9'){std::fprintf(stderr,"invalid %s\n",key);std::exit(2);}
    char *end;errno=0;unsigned long n=std::strtoul(v,&end,10);
    if(errno || *end || n>maximum){std::fprintf(stderr,"invalid %s\n",key);std::exit(2);}
    return (unsigned)n;
}
static void stress_init(){
    stress_period=setting("PICO1715_STRESS_PERIOD",257,1000000);
    if(!stress_period)std::exit(2);
    stress_width=setting("PICO1715_STRESS_WIDTH",0,stress_period);
    stress_phase=setting("PICO1715_STRESS_PHASE",0,stress_period-1);
    const char *names[]={"POLL","FIELD","READ","WRITE","COMMIT","SNAPSHOT"};
    for(unsigned i=0;i<6;i++){
        char key[64];std::snprintf(key,sizeof(key),"PICO1715_STRESS_EXTRA_%s",names[i]);
        stress_extra[i]=setting(key,0,1000000);
    }
    if(const char *v=std::getenv("PICO1715_STRESS_INDEX_PHASE_US")){
        const char *p=v;if(*p=='-')p++;
        if(!*p)std::exit(2);
        for(;*p;p++)if(*p<'0'||*p>'9')std::exit(2);
        char *end;errno=0;long n=std::strtol(v,&end,10);
        if(errno || *end || n< -100000 || n>100000)std::exit(2);
        index_phase_us=(int)n;
    }
    if(const char *v=std::getenv("PICO1715_STRESS_SD_SEQUENCE")){
        do{
            if(sd_count==16 || *v<'0'||*v>'9')std::exit(2);
            char *end;errno=0;unsigned long n=std::strtoul(v,&end,10);
            if(errno || n>1000000 || (*end && *end!=','))std::exit(2);
            sd_sequence[sd_count++]=(unsigned)n;
            if(!*end)break;
            v=end+1;
        }while(true);
    }
}
static void stress_report(){
    std::fprintf(stderr,"Stress {\"config\":{\"period\":%u,\"width\":%u,\"phase\":%u,\"index_phase_us\":%d,\"extra_us\":[",stress_period,stress_width,stress_phase,index_phase_us);
    for(unsigned i=0;i<6;i++)std::fprintf(stderr,"%s%u",i?",":"",stress_extra[i]);
    std::fputs("],\"sd_delays_us\":[",stderr);
    for(unsigned i=0;i<sd_count;i++)std::fprintf(stderr,"%s%u",i?",":"",sd_sequence[i]);
    std::fputs("]},\"hits\":[",stderr);
    for(unsigned i=0;i<6;i++)std::fprintf(stderr,"%s%llu",i?",":"",(unsigned long long)stress_hits[i]);
    std::fprintf(stderr,"],\"sd_calls\":%llu,\"sd_min_us\":%u,\"sd_max_us\":%u,\"index_resets\":%llu,\"index_start_tick\":%llu,\"fault_iacks\":%llu}\n",(unsigned long long)sd_calls,sd_calls?sd_min:0,sd_max,(unsigned long long)index_resets,(unsigned long long)index_start_tick,(unsigned long long)fault_iacks);
}
static void charge(unsigned kind){
    assert(kind<P1715_COST_COUNT);cost_calls[kind]++;
    unsigned delay=costs[kind];
    if(stress_extra[kind] && (cost_calls[kind]-1+stress_phase)%stress_period<stress_width){
        delay+=stress_extra[kind];stress_hits[kind]++;
    }
    if(delay){cost_yields++;pause_core(delay);}
}
static void image_lock(critical_section_t *,bool enter){
    assert(current_core<2);
    if(enter){
        assert(lock_owner!=current_core);
        while(lock_owner!=2){lock_wait_us++;pause_core(1);}
        lock_owner=current_core;
    }else{assert(lock_owner==current_core);lock_owner=2;}
}
static void resume_core(unsigned core){
    current_core=core;
    if(swapcontext(&caller_context,core?&worker_context:&serving_context))std::abort();
    current_core=2;
}
static void serving_entry(){
    for(;;){
        p1715_service_step();serving_busy=false;
        if(!rtl.reset_n && !(host_outputs&(1u<<21)))reset_observed=true;
        if(swapcontext(&serving_context,&caller_context))std::abort();
    }
}
static void sd_pause(bool writing,uint32_t){
    if(writing){
        unsigned delay=sd_count?sd_sequence[sd_calls%sd_count]:sd_write_delay;
        sd_calls++;if(delay<sd_min)sd_min=delay;if(delay>sd_max)sd_max=delay;
        if(delay){sd_yields++;pause_core(delay);}
    }
}
static void worker_entry(){
    for(;;){
        p1715_storage_step();worker_busy=false;
        if(swapcontext(&worker_context,&caller_context))std::abort();
    }
}
static void worker_pump(){
    if(!host_worker || p1715_status.storage_error)return;
    if(!worker_busy){
        if(!p1715_status.dirty_blocks || host_time_us-last_worker<100)return;
        last_worker=host_time_us;worker_busy=true;worker_due=host_time_us;
    }
    if(host_time_us>=worker_due)resume_core(1);
}
static void pins() {rtl.gpio_out=host_outputs;rtl.gpio_dir=host_directions;rtl.eval();host_inputs=rtl.gpio_in;}
static void service(bool force=false) {
    pins();
    if(ready && (force || host_time_us!=last_poll)) {
        last_poll=host_time_us;
        if(!serving_busy && !exporting){serving_busy=true;serving_due=host_time_us;}
        if(serving_busy && host_time_us>=serving_due)resume_core(0);
        pins();
        loss_sample();
    }
    worker_pump();
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
    if(rtl.fault && !last_fault){if(!fault_count)first_fault_us=host_time_us;fault_count++;}
    last_fault=rtl.fault;
    if(rtl.contention) {std::fprintf(stderr,"Firmware RTL fault=%u contention=%u time=%llu inputs=%08x outputs=%08x dir=%08x\n",rtl.fault,rtl.contention,(unsigned long long)host_time_us,host_inputs,host_outputs,host_directions);std::abort();}
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
    stress_init();
    bool writable=card->writable;
    host_storage_init(output_image,absent);
    ready=p1715_service_init(card,writable)==0;
    last_poll=UINT64_MAX;last_worker=clock_epoch=0;worker_busy=false;
    sd_write_delay=0;sd_yields=resets_while_busy=0;
    if(const char *path=std::getenv("PICO1715_LOSS_TRACE")){
        loss_file=std::fopen(path,"wx");
        if(!loss_file){std::perror("loss trace");std::exit(2);}
        std::fputs("us,cycle,pc,address,active,write,inputs,outputs,pos,length,rx,pending,mark,irq_service,lock,service_due_us,tx_full,overruns,underruns,lock_wait_us,prepared\n",loss_file);
    }
    serving_busy=reset_observed=exporting=false;serving_due=0;current_core=lock_owner=2;
    cost_yields=lock_wait_us=fault_count=first_fault_us=0;last_fault=false;
    const char *names[]={"POLL","FIELD","READ","WRITE","COMMIT","SNAPSHOT"};
    for(unsigned i=0;i<P1715_COST_COUNT;i++){
        char key[64];std::snprintf(key,sizeof(key),"PICO1715_COST_%s_US",names[i]);
        costs[i]=0;cost_calls[i]=0;
        if(const char *value=std::getenv(key)){
            char *end;errno=0;unsigned long n=std::strtoul(value,&end,10);
            if(errno || !*value || *end || *value=='-' || n>1000000){
                std::fprintf(stderr,"invalid %s\n",key);std::exit(2);
            }
            costs[i]=(unsigned)n;
        }
    }
    if(getcontext(&serving_context))std::abort();
    serving_context.uc_stack.ss_sp=serving_stack;
    serving_context.uc_stack.ss_size=sizeof(serving_stack);
    serving_context.uc_link=nullptr;
    makecontext(&serving_context,serving_entry,0);
    if(const char *value=std::getenv("PICO1715_SD_WRITE_DELAY_US")){
        char *end;errno=0;unsigned long n=std::strtoul(value,&end,10);
        if(errno || !*value || *end || *value=='-' || n>1000000){
            std::fputs("invalid PICO1715_SD_WRITE_DELAY_US\n",stderr);std::exit(2);
        }
        sd_write_delay=(unsigned)n;
    }
    if(host_worker){
        if(getcontext(&worker_context))std::abort();
        worker_context.uc_stack.ss_sp=worker_stack;
        worker_context.uc_stack.ss_size=sizeof(worker_stack);
        worker_context.uc_link=nullptr;
        makecontext(&worker_context,worker_entry,0);
    }
    host_io_hook=sd_pause;host_cost_hook=charge;host_lock_hook=image_lock;
}
extern "C" int firmware_cosim_storage_busy(void){return worker_busy;}
extern "C" void cosim_reset(void *) {
    if(worker_busy)resets_while_busy++;
    active=launched=false;phase=0;settle=8;
    clock_epoch=host_time_us;last_poll=UINT64_MAX;last_worker=host_time_us;
    rtl.transaction=0;rtl.iorq_n=rtl.rd_n=rtl.wr_n=1;
    rtl.obs_m1_n=rtl.obs_mreq_n=rtl.obs_iorq_n=rtl.obs_rd_n=1;
    rtl.power_good=1;rtl.reset_n=0;last_ack=last_reti=false;
    // A response held before reset is not a new ACK while delayed service
    // waits to observe reset and release its GPIOs.
    last_response=(host_outputs&(1u<<14))!=0;
    reset_observed=false;
    service(true);clock_edge();
    // Hold reset while stalled service/worker contexts advance. No stack is
    // discarded while it owns the image lock; the CPU itself remains reset.
    uint64_t deadline=host_time_us+10000000;
    while(ready && !reset_observed){
        host_time_us++;for(unsigned i=0;i<100;i++)clock_edge();
        if(host_time_us>=deadline){std::fputs("reset service deadline exceeded\n",stderr);std::abort();}
    }
    clock_epoch=host_time_us;
    if(ready){
        card->next_index=PICO1715_CLOCK_HZ/5+(int64_t)index_phase_us*PICO1715_CLOCK_HZ/1000000;
        index_start_tick=card->next_index;index_resets++;
    }
    rtl.reset_n=1;service(true);
    for(unsigned i=0;i<12;i++)clock_edge();
}
extern "C" void cosim_tick(void *,uint64_t cycle) {
    host_time_us=clock_epoch+cycle*1000000/PICO1715_CLOCK_HZ;
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
    if(!rtl.host_data_enable && ready && (host_outputs&(1u<<21)) && !rtl.fault)std::abort();
    *v=rtl.host_data_enable?rtl.host_rdata:0xff;finish();return 1;
}
extern "C" void cosim_write(void *,uint16_t a,uint8_t){if(claimed(a,1))finish();}
extern "C" int cosim_irq(void *){pins();return rtl.int_pull_low;}
extern "C" uint8_t cosim_ack(void *){
    rtl.obs_m1_n=rtl.obs_iorq_n=0;rtl.obs_mreq_n=rtl.obs_rd_n=1;
    clock_edge();clock_edge();
    if(!rtl.host_data_enable){
        if(!rtl.fault){std::fputs("undriven interrupt acknowledgement without fault\n",stderr);std::abort();}
        fault_iacks++;return 0xff;
    }
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
    // Finish any exposed host transaction before stopping new serving steps.
    // Suspended steps must finish so the worker cannot inherit a stranded lock.
    if(active){
        if(!launched){
            rtl.host_addr=address;rtl.host_wdata=Z80_GET_DATA(machine->cpu.pins);
            rtl.transaction=1;rtl.iorq_n=0;rtl.rd_n=writing;rtl.wr_n=!writing;launched=true;
        }
        unsigned waited=0;
        do{host_time_us++;for(unsigned i=0;i<100;i++)clock_edge();
            if(++waited>1000000)std::abort();
        }while(rtl.wait_pull_low);
        finish();
    }
    exporting=true;
    uint64_t deadline=host_time_us+60000000;
    while(serving_busy || (host_worker && !p1715_status.storage_error &&
                          (worker_busy || p1715_status.dirty_blocks))){
        host_time_us++;
        for(unsigned i=0;i<100;i++)clock_edge();
        if(host_time_us>=deadline){std::fputs("export drain deadline exceeded\n",stderr);std::abort();}
    }
    if(ready && std::memcmp(card->image,host_storage_image(),P1715_IMAGE_BYTES)) {
        std::fputs("PSRAM differs from persisted SD image\n",stderr);std::abort();
    }
    std::memcpy(output_image,host_storage_image(),P1715_IMAGE_BYTES);
    if(loss_file){std::fclose(loss_file);loss_file=nullptr;}
    stress_report();
    std::fprintf(stderr,"Costs config=[%u,%u,%u,%u,%u,%u] calls=[%llu,%llu,%llu,%llu,%llu,%llu] yields=%llu lock_wait_us=%llu faults=%llu first_fault_us=%llu\n",
        costs[0],costs[1],costs[2],costs[3],costs[4],costs[5],
        (unsigned long long)cost_calls[0],(unsigned long long)cost_calls[1],(unsigned long long)cost_calls[2],
        (unsigned long long)cost_calls[3],(unsigned long long)cost_calls[4],(unsigned long long)cost_calls[5],
        (unsigned long long)cost_yields,(unsigned long long)lock_wait_us,
        (unsigned long long)fault_count,(unsigned long long)first_fault_us);
    std::fprintf(stderr,"Storage delay_us=%u yields=%llu resets_while_busy=%llu\n",sd_write_delay,
        (unsigned long long)sd_yields,(unsigned long long)resets_while_busy);
    std::fprintf(stderr,"Firmware state=%u requests=%llu sd_reads=%llu sd_writes=%llu dirty=%u error=%u\n",
        p1715_status.state,(unsigned long long)p1715_status.requests,
        (unsigned long long)host_sd_reads,(unsigned long long)host_sd_writes,
        p1715_status.dirty_blocks,p1715_status.storage_error);
}
