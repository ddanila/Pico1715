// SPDX-License-Identifier: MIT
#include "Vanalyzer_transport_fixture.h"
extern "C" {
#include "firmware/analyzer.h"
}
#include <array>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>
using Record=std::array<uint8_t,16>;
static uint32_t get32(const uint8_t *p){return p[0]|uint32_t(p[1])<<8|uint32_t(p[2])<<16|uint32_t(p[3])<<24;}
static void put32(uint8_t *p,uint32_t x){for(unsigned i=0;i<4;i++)p[i]=uint8_t(x>>(8*i));}
static void require(bool ok,const char *why){if(!ok){std::fprintf(stderr,"FAIL: %s\n",why);std::exit(2);}}
struct Fixture {
 Vanalyzer_transport_fixture rtl;
 p1715_analyzer fw{};
 uint64_t tick=0,busy_until=0,origin=0,last_event=0;
 uint32_t hz=50000000,record_hz=50000000,ctrl=0;
 bool injected=false,suppress_ack=false,started=false;
 unsigned poll=5,write_delay=50;
 std::string scenario;
 std::vector<uint8_t> ram=std::vector<uint8_t>(8u*1024u*1024u+64,0xa5);
 static uint32_t pins(void *v){
  auto &f=*(Fixture *)v;
  uint32_t p=f.rtl.pico_data|(uint32_t(f.rtl.pico_index)<<8)|(uint32_t(f.rtl.pico_request)<<13);
  if(f.rtl.pico_request && f.fw.state==P1715_LA_REQUEST){
   if(((f.scenario=="crc" || f.scenario=="trigger-crc") || f.scenario=="permanent_crc") && f.rtl.pico_index==7 && (!f.injected || f.scenario=="permanent_crc")){
    p^=1;f.injected=true;
   }
   if(f.scenario=="index" && f.rtl.pico_index==5 && !f.injected){p^=1u<<8;f.injected=true;}
  }
  return p;
 }
 static void controls(void *v,uint32_t c){((Fixture *)v)->ctrl=c;}
 static uint64_t time(void *v){auto &f=*(Fixture *)v;return f.tick*1000000/f.hz;}
 static void fence(void *v){auto &f=*(Fixture *)v;f.busy_until=f.tick+f.write_delay;}
 void step_controls(){
  if((scenario=="lost_ack" || scenario=="trigger-lost-ack") && !injected && (ctrl&P1715_LA_ACK) && rtl.pico_index==21 && fw.records){
   injected=true;suppress_ack=true;
  }
  if(!(ctrl&P1715_LA_SYNC))suppress_ack=false;
  rtl.capture_clear=!!(ctrl&P1715_LA_CLEAR);rtl.capture_enable=!!(ctrl&P1715_LA_RUN);
  rtl.link_sync_n=!!(ctrl&P1715_LA_SYNC);
  rtl.pico_ack=!!(ctrl&P1715_LA_ACK) && !suppress_ack && tick>=busy_until;
 }
};
int main(int argc,char **argv){
 require(argc==3 || argc==4,"usage: transport-test scenario output-dir [full compact workload]");
 Fixture f;f.scenario=argv[1];std::string out=argv[2];
 const std::vector<std::string> modes={"normal","slow","crc","index","lost_ack","disconnect","overflow","full","permanent_crc","trigger","trigger-early","trigger-never","trigger-overflow","trigger-crc","trigger-lost-ack"};
 require(std::find(modes.begin(),modes.end(),f.scenario)!=modes.end(),"scenario");
 std::vector<Record> source;
 if(argc==4){
  std::ifstream in(argv[3],std::ios::binary);std::array<uint8_t,32> h{};
  in.read((char *)h.data(),h.size());
  require(in.good() && !std::memcmp(h.data(),"P1715CY\0",8) && h[8]==1 && h[10]==16,"workload header");
  require(get32(h.data()+20)==0 && get32(h.data()+24)==0,"workload must be unfiltered and lossless");
  f.record_hz=get32(h.data()+12);source.resize(get32(h.data()+16));
  in.read((char *)source.data(),std::streamsize(source.size()*16));
  require(in.good() && in.peek()==EOF,"workload size");
 }else{
  unsigned n=f.scenario=="lost_ack"?12:1200;
  for(unsigned i=0;i<n;i++){
   Record r{};r[0]=uint8_t((i%5==0?1:(i%2?4:5))<<4);r[1]=uint8_t(i);
   r[2]=uint8_t(i);r[3]=0x12;r[6]=40;put32(r.data()+8,i*2000);put32(r.data()+12,i);source.push_back(r);
  }
 }
 if(f.scenario=="slow")f.poll=10;
 size_t size=f.scenario=="full"?32+8*16:P1715_LA_RAM_SIZE;
 auto buffer=f.ram.data()+P1715_LA_RAM_OFFSET;
 p1715_analyzer_io io{&f,Fixture::pins,Fixture::controls,Fixture::time,Fixture::fence};
 f.rtl.card_reset_n=0;f.rtl.clk=0;f.rtl.eval();f.rtl.clk=1;f.rtl.eval();f.rtl.card_reset_n=1;
 bool triggered_mode=f.scenario.rfind("trigger",0)==0;
 p1715_trigger_config config{};
 if(triggered_mode){
  config={1,16,0xffff12c9u,0,8,4};
  if(f.scenario=="trigger-early"){config.address=0xffff1201u;config.post=0;}
  if(f.scenario=="trigger-never")config.address=0xffffffffu;
  if(argc==4){config.kinds=64;config.address=0;}
 }
 require(!p1715_analyzer_start_trigger(&f.fw,io,buffer,size,f.record_hz,&config),"firmware initialization");
 std::vector<Record> selected;
 size_t cursor=0;
 uint64_t stall_start=uint64_t(f.hz)/1000,stall_end=stall_start;
 if(f.scenario=="disconnect")stall_end+=f.hz/2000; // 0.5 ms
 if(f.scenario=="overflow" || f.scenario=="trigger-overflow")stall_end+=f.hz/20; // 50 ms
 const uint64_t last_due=source.empty()?0:uint64_t(get32(source.back().data()+8))+65535;
 uint64_t limit=last_due*f.hz/f.record_hz+f.hz/2;
 bool held=false;unsigned old_data=0,old_index=0;
 for(f.tick=0;f.tick<limit;f.tick++){
  bool paused=f.started && f.tick-f.origin>=stall_start && f.tick-f.origin<stall_end;
  if(f.tick%f.poll==0 && f.tick>=f.busy_until && !paused){
   if(cursor==source.size() && f.started && f.tick>f.last_event+(triggered_mode?f.hz/10:0) &&
      (!triggered_mode || f.scenario=="trigger-never"))p1715_analyzer_stop(&f.fw);
   p1715_analyzer_step(&f.fw);
  }
  f.step_controls();
  if(f.rtl.capture_enable && !f.started){f.started=true;f.origin=f.tick;}
  f.rtl.event_valid=0;
  if(f.started && f.rtl.capture_enable && cursor<source.size()){
   const auto &r=source[cursor];uint64_t due=uint64_t(get32(r.data()+8))+(unsigned(r[6])|(unsigned(r[7])<<8))+1;
   due=due*f.hz/f.record_hz;
   if(f.tick-f.origin>=due){
    for(unsigned i=0;i<4;i++)f.rtl.event_record[i]=get32(r.data()+i*4);
    f.rtl.event_valid=1;
    if((0x170u>>(r[0]>>4))&1)selected.push_back(r);
    cursor++;f.last_event=f.tick;
   }
  }
  f.rtl.clk=0;f.rtl.eval();
  if(held && f.rtl.pico_request && f.rtl.link_sync_n)
   require(f.rtl.pico_data==old_data && f.rtl.pico_index==old_index,"unstable unacknowledged byte");
  held=f.rtl.pico_request && !f.rtl.pico_ack;old_data=f.rtl.pico_data;old_index=f.rtl.pico_index;
  f.rtl.clk=1;f.rtl.eval();
  if(f.fw.state==P1715_LA_DONE || f.fw.state==P1715_LA_ERROR)break;
 }
 require(f.tick<limit,"bounded completion");
 require(std::all_of(f.ram.begin(),f.ram.begin()+P1715_LA_RAM_OFFSET,[](uint8_t b){return b==0xa5;}),"disk region overwritten");
 require(std::all_of(f.ram.begin()+P1715_LA_RAM_OFFSET+size,f.ram.end(),[](uint8_t b){return b==0xa5;}),"PSRAM bounds overwritten");
 if(f.scenario=="permanent_crc"){
  require(f.fw.state==P1715_LA_ERROR && f.fw.crc_errors==4 && f.fw.records==0 && !f.ctrl,"permanent error not fail-closed");
 }else{
  require(f.fw.state==P1715_LA_DONE,"capture did not finish");
  size_t header=p1715_analyzer_header_size(&f.fw);
  std::vector<uint8_t> file_data(header+f.fw.records*16);
  require(!p1715_analyzer_read(&f.fw,0,file_data.data(),file_data.size()),"logical capture read");
  buffer=file_data.data();
  require(!std::memcmp(buffer,"P1715CY\0",8),"final capture header");
  require(get32(buffer+16)==f.fw.records && get32(buffer+20)==f.rtl.dropped+f.fw.local_dropped,"loss metadata");
  require(selected.size()==f.fw.records+f.rtl.dropped+f.fw.local_dropped+f.fw.omitted,"unaccounted record loss/duplicate");
  size_t match=0;
  for(unsigned i=0;i<f.fw.records;i++){
   const uint8_t *r=buffer+header+i*16;
   while(match<selected.size() && get32(selected[match].data()+12)!=get32(r+12))match++;
   require(match<selected.size() && !std::memcmp(r,selected[match].data(),16),"record changed/reordered");match++;
  }
  if(f.scenario=="normal" || f.scenario=="slow" || (f.scenario=="crc" || f.scenario=="trigger-crc") || f.scenario=="index" || f.scenario=="lost_ack" || f.scenario=="disconnect")
   require(!f.rtl.dropped && !f.fw.local_dropped,"unexpected loss");
  if(f.scenario=="crc")require(f.fw.crc_errors==1 && f.fw.retries==1,"CRC recovery");
  if(f.scenario=="index")require(f.fw.index_errors==1 && f.fw.retries==1,"index recovery");
  if(f.scenario=="lost_ack")require(f.fw.duplicates==1 && f.fw.retries==1,"commit deduplication");
  if(f.scenario=="overflow")require(f.rtl.dropped>0,"overflow not exercised");
  if(f.scenario=="full")require(f.fw.records==8 && f.fw.full && f.fw.local_dropped>0,"bounded buffer stop");
  if(triggered_mode){
   require(!f.fw.local_dropped && !f.fw.full,"trigger window capacity");
   if(f.scenario=="trigger-never"){
    require(!f.fw.triggered && f.fw.records==8 && f.fw.stop_reason==2,"untriggered manual snapshot");
    for(unsigned i=0;i<8;i++)require(!std::memcmp(buffer+header+i*16,selected[selected.size()-8+i].data(),16),"last prehistory");
   }else{
    require(f.fw.triggered && f.fw.stop_reason==1 && f.fw.post_collected==config.post,"automatic trigger stop");
    auto hit=std::find_if(selected.begin(),selected.end(),[&](const Record &r){
     unsigned addr=unsigned(r[2])|(unsigned(r[3])<<8);
     return ((config.kinds>>(r[0]>>4))&1) && !((addr^config.address)&(config.address>>16)) && !((r[1]^config.data)&(config.data>>8));
    });
    require(hit!=selected.end(),"reference trigger exists");
    // For lossless profiles compare the entire window to an independent source slice.
    if(!f.rtl.dropped){
     size_t at=size_t(hit-selected.begin()),before=std::min(size_t(config.pre),at);
     require(f.fw.trigger_index==before && f.fw.records==before+1+config.post,"trigger boundary");
     for(unsigned i=0;i<f.fw.records;i++)require(!std::memcmp(buffer+header+i*16,selected[at-before+i].data(),16),"reference window differs");
    }
   }
   if(f.scenario=="trigger-overflow")require(f.rtl.dropped>0,"trigger overflow exercised");
   if(f.scenario=="trigger-crc")require(f.fw.crc_errors==1 && f.fw.retries==1,"trigger CRC recovery");
   if(f.scenario=="trigger-lost-ack")require(f.fw.duplicates==1 && f.fw.retries==1,"trigger deduplication");
  }
  std::ofstream file(out+"/capture.p1715",std::ios::binary);file.write((char *)buffer,header+f.fw.records*16);require(file.good(),"capture write");
 }
 FILE *report=std::fopen((out+"/report.json").c_str(),"wx");require(report,"report open");
 std::fprintf(report,"{\"scenario\":\"%s\",\"state\":%u,\"fpga_clock_hz\":%u,\"poll_ticks\":%u,\"psram_delay_ticks\":%u,\"records\":%u,\"fpga_dropped\":%u,\"local_dropped\":%u,\"filtered\":%u,\"retries\":%u,\"duplicates\":%u,\"crc_errors\":%u,\"index_errors\":%u,\"ticks\":%llu}\n",
 f.scenario.c_str(),f.fw.state,f.hz,f.poll,f.write_delay,f.fw.records,f.rtl.dropped,f.fw.local_dropped,f.rtl.filtered,f.fw.retries,f.fw.duplicates,f.fw.crc_errors,f.fw.index_errors,(unsigned long long)f.tick);
 require(!std::fclose(report),"report close");
 std::printf("transport PASS: %s, %u records, %u FPGA drops, %u retries\n",f.scenario.c_str(),f.fw.records,f.rtl.dropped,f.fw.retries);
}
