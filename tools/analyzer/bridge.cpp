// SPDX-License-Identifier: MIT
#include "Vcycle_capture_top.h"
#include "bridge.h"
extern "C" {
#include "sample.h"
}
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <string>

static Vcycle_capture_top rtl;
static pc1715 *machine;
static FILE *capture;
static std::string output_dir;
struct Expected {uint64_t tick; uint16_t address; uint8_t data; unsigned type;};
static std::deque<Expected> expected;
static uint64_t samples, observed_samples, matched, callbacks, record_count, waits, input_waits;
static uint64_t partials, saturated, unstable, refresh_intervals;
static bool refresh_before;
static bool io_only;
static uint32_t last_sequence;
static std::array<uint64_t,10> counts{};
static constexpr unsigned sample_hz=PC1715_CLOCK_HZ*4;
static void fail(const char *message) {
    std::fprintf(stderr,"Analyzer comparison failed: %s (sample %llu, record %llu)\n",
                 message,(unsigned long long)samples,(unsigned long long)record_count);
    std::exit(2);
}
static void le32(FILE *f,uint32_t value) {
    for(unsigned i=0;i<4;i++) if(std::fputc((value>>(8*i))&255,f)==EOF)fail("file write");
}
static void consume() {
    const uint32_t *words=rtl.read_record.data();
    unsigned flags=words[0]&15,kind=(words[0]>>4)&15;
    unsigned data=(words[0]>>8)&255,address=words[0]>>16;
    unsigned duration=words[1]>>16,wait=words[1]&65535;
    uint64_t start=words[2],end=start+duration;
    if((!io_only && words[3]!=record_count) || (record_count && words[3]<=last_sequence) || kind==0 || kind>8 || !duration)fail("invalid kind/sequence/duration");
    if(flags&4)fail("unexpected saturation");
    if(flags&8)fail("address changed inside bus cycle");
    partials+=!!(flags&3);saturated+=!!(flags&4);unstable+=!!(flags&8);
    uint64_t found=0;
    // Oracle comes from DAC's memory/I/O callbacks, not the HDL decode.
    while(!expected.empty() && expected.front().tick<end) {
        const auto e=expected.front();expected.pop_front();
        if(e.tick<start)fail("callback not represented by any captured interval");
        unsigned type=kind<=2?1:kind==3?2:kind==4?3:kind==5?4:kind==6?5:0;
        if(e.type!=type || (kind!=6 && e.address!=address) || e.data!=data) {
            std::fprintf(stderr,"Expected type=%u addr=%04x data=%02x at %llu; got kind=%u addr=%04x data=%02x [%llu,%llu)\n",
                e.type,e.address,e.data,(unsigned long long)e.tick,kind,address,data,
                (unsigned long long)start,(unsigned long long)end);
            fail("callback value/type mismatch");
        }
        found++;matched++;
    }
    if(kind<=6 && !found)fail("captured transaction has no DAC callback");
    waits+=wait;counts[kind]++;record_count++;last_sequence=words[3];
    for(unsigned i=0;i<4;i++)le32(capture,words[i]);
}
static void edge() {
    rtl.clk=0;rtl.eval();rtl.clk=1;rtl.eval();
    if(rtl.host_oe || rtl.wait_pull_low || rtl.int_pull_low || rtl.busrq_pull_low ||
       rtl.nmi_pull_low || rtl.memdi_pull_low || rtl.reset_pull_low || rtl.ieo!=rtl.iei)
        fail("analyzer drove host");
    if(rtl.overflow || rtl.dropped)fail("unexpected capture overflow");
    if(rtl.read_valid)consume();
    samples++;
}
extern "C" void analyzer_init(void *m,const char *dir) {
    machine=(pc1715 *)m;output_dir=dir;
    capture=std::fopen((output_dir+"/cycles.p1715").c_str(),"wbx");
    if(!capture)fail("cannot create exclusive capture file");
    // 32-byte P1715CY header, version/record size share one little-endian word.
    const char *mode=std::getenv("PICO1715_ANALYZER_IO_ONLY");
    if(mode && std::strcmp(mode,"1"))fail("invalid IO_ONLY setting");
    io_only=mode!=nullptr;
    rtl.capture_mask=io_only?0x170:0x3fe;
    if(std::fwrite("P1715CY\0",1,8,capture)!=8)fail("file write");
    le32(capture,1u|(16u<<16));le32(capture,sample_hz);
    le32(capture,0);le32(capture,0);le32(capture,0);le32(capture,rtl.capture_mask);
    rtl.clk=0;rtl.card_reset_n=0;rtl.enable=0;rtl.read_enable=0;rtl.iei=1;
    rtl.sample=0x3fbf000000ULL;
    rtl.eval();rtl.clk=1;rtl.eval();
    rtl.card_reset_n=1;rtl.enable=1;rtl.read_enable=1;
}
extern "C" void analyzer_event(const dac_trace_event *e) {
    unsigned type=!std::strcmp(e->kind,"MR")?1:!std::strcmp(e->kind,"MW")?2:
        !std::strcmp(e->kind,"IR")?3:!std::strcmp(e->kind,"IW")?4:
        !std::strcmp(e->kind,"IA")?5:0;
    if(!type)fail("unknown DAC trace callback");
    if(io_only && type<=2)return;
    expected.push_back({samples,(uint16_t)e->address,e->data,type});callbacks++;
}
extern "C" void analyzer_observe() {
    uint64_t p=machine->cpu.pins;
    uint64_t s=p1715_bus_sample(machine);
    if(machine->io_waiting)input_waits+=4;
    bool refresh=(p&Z80_MREQ) && (p&Z80_RFSH);
    if(refresh && !refresh_before)refresh_intervals++;
    refresh_before=refresh;
    // Four identical bus-level samples per CPU T-state; clock is illustrative.
    for(unsigned i=0;i<4;i++) {rtl.sample=s|((uint64_t)(i>=2)<<30);edge();observed_samples++;}
}
extern "C" void analyzer_finish() {
    rtl.enable=0;
    for(unsigned i=0;i<512;i++) {edge();if(rtl.idle && !rtl.queued && !rtl.read_valid)break;}
    if(!expected.empty() || callbacks!=matched || !rtl.idle || rtl.queued)fail("undrained callbacks/capture");
    if(waits!=input_waits)fail("wait duration mismatch");
    if(!io_only && counts[7]!=refresh_intervals)fail("refresh interval count mismatch");
    if(record_count>0xffffffff)fail("file count overflow");
    if(std::fseek(capture,16,SEEK_SET))fail("header seek");
    le32(capture,(uint32_t)record_count);le32(capture,rtl.dropped);le32(capture,rtl.filtered);
    if(std::fclose(capture))fail("file close");
    FILE *report=std::fopen((output_dir+"/analyzer.json").c_str(),"wx");
    if(!report)fail("report open");
    std::fprintf(report,"{\"sample_hz\":%u,\"observed_samples\":%llu,\"records\":%llu,\"callbacks_matched\":%llu,\"wait_samples\":%llu,\"partial_records\":%llu,\"saturated_records\":%llu,\"unstable_records\":%llu,\"dropped\":0,\"filtered\":%u,\"capture_mask\":%u,\"kinds\":[",
        sample_hz,(unsigned long long)observed_samples,(unsigned long long)record_count,
        (unsigned long long)matched,(unsigned long long)waits,(unsigned long long)partials,
        (unsigned long long)saturated,(unsigned long long)unstable,rtl.filtered,rtl.capture_mask);
    for(unsigned i=0;i<counts.size();i++)std::fprintf(report,"%s%llu",i?",":"",(unsigned long long)counts[i]);
    std::fprintf(report,"]}\n");
    if(std::fclose(report))fail("report close");
    std::fprintf(stderr,"Analyzer PASS: %llu records, %llu callbacks, %llu wait samples\n",
        (unsigned long long)record_count,(unsigned long long)matched,(unsigned long long)waits);
}
