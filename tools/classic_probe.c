/* SPDX-License-Identifier: MIT */
#include "machines/robotron1715/pc1715.h"
#include "../model/controller.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include <errno.h>
#include "keyboard_schedule.h"
static int scheduled_receive(void *m,uint8_t byte){return pc1715_sio_receive(m,0,byte);}

#ifdef P1715_ANALYZER
#include "analyzer/bridge.h"
#endif

#ifdef PICO1715_COSIM
#include "cosim/bridge.h"
#ifdef P1715_FIRMWARE_COSIM
void firmware_cosim_start(int absent);
void firmware_cosim_export(void);
int firmware_cosim_storage_busy(void);
#endif
#define card_read cosim_read
#define card_write cosim_write
#define card_tick cosim_tick
#define card_irq cosim_irq
#define card_ack cosim_ack
#define card_reti cosim_reti
#define card_reset cosim_reset
#define card_wait cosim_wait
#else
#define card_read pico1715_read
#define card_write pico1715_write
#define card_tick pico1715_tick
#define card_irq pico1715_irq
#define card_ack pico1715_ack
#define card_reti pico1715_reti
#define card_reset pico1715_reset
#define card_wait pico1715_wait
#endif

static FILE *logfile;
/* Opt-in bounded diagnostics: no ROM/media patches or I/O substitution. */
static FILE *diagnostic;
static unsigned diagnostic_active, diagnostic_fetches;
static uint64_t diagnostic_pc[65536], diagnostic_reads[256], diagnostic_writes[256];
/* Completed-byte keyboard source. All port reads/status/register writes belong
 * to DAC's onboard SIO; this fixture never supplies guest I/O values. */
typedef struct {
  pico1715_controller controller;
  const char *command;
  unsigned key_pos, key_half, key_bytes, sio_reads, sio_writes, ctc_writes;
  uint64_t key_due, command_gap;
} fixture;
static void keyboard_step(pc1715 *m,fixture *f){
  if(!f->command[f->key_pos] || m->cpu.cycles<f->key_due || m->sio[0].count==3)return;
  uint8_t data=f->key_half?(uint8_t)f->command[f->key_pos]:0xe0;
  int result=pc1715_sio_receive(m,0,data);
  if(result==-EAGAIN)return; /* guest has not enabled receive yet */
  if(result){fprintf(stderr,"keyboard receive failed: %d\n",result);exit(2);}
  f->key_bytes++;
  if(!f->key_half){f->key_half=1;f->key_due=m->cpu.cycles+1000;}
  else {f->key_pos++;f->key_half=0;f->key_due=m->cpu.cycles+(data=='\r'?f->command_gap:100000);}
}
static int input(void *p,uint16_t a,uint8_t *data){return card_read(p,a,data);}
static void output(void *p,uint16_t a,uint8_t data){card_write(p,a,data);}
static void trace(void *p, const dac_trace_event *e) {
  fixture *f=p;
  if(diagnostic_active){
    if(!strcmp(e->kind,"IR"))diagnostic_reads[e->address&255]++;
    if(!strcmp(e->kind,"IW"))diagnostic_writes[e->address&255]++;
  }
  if(!strcmp(e->kind,"IR") && (e->address&255)==12)f->sio_reads++;
  if(!strcmp(e->kind,"IW")){
    if((e->address&255)>=12 && (e->address&255)<=15)f->sio_writes++;
    if((e->address&255)>=8 && (e->address&255)<=11)f->ctc_writes++;
  }
#ifdef P1715_ANALYZER
  analyzer_event(e);
#endif
  if (logfile && (((!strcmp(e->kind, "IW") || !strcmp(e->kind, "IR")) &&
      ((e->address & 255) < 8 || ((e->address & 255) >= 0x20 &&
       (e->address & 255) <= 0x23))) || !strcmp(e->kind, "IA")))
    fprintf(logfile, "%" PRIu64 " %s %04x %02x\n", e->cycle, e->kind,
            (unsigned)e->address, e->data);
}
static int read_file(const char *path, uint8_t *b, size_t n) {
  FILE *f = fopen(path, "rb");
  if (!f) return 0;
  int ok = fread(b, 1, n, f) == n && fgetc(f) == EOF && !ferror(f);
  fclose(f); return ok;
}
static unsigned option(const char *name, unsigned fallback, unsigned maximum) {
  const char *value = getenv(name);
  if (!value) return fallback;
  char *end; errno = 0;
  unsigned long n = strtoul(value, &end, 10);
  if (errno || !*value || *end || *value == '-' || n > maximum) {
    fprintf(stderr, "invalid %s\n", name); exit(2);
  }
  return (unsigned)n;
}
int main(int argc, char **argv) {
  if (argc < 4 || argc > 6) {
    fprintf(stderr, "usage: %s ROM RAW-80x2x5x1024 EMPTY-OUTPUT-DIR [command] [readonly|absent]\n", argv[0]);
    return 2;
  }
  if (argc == 6 && strcmp(argv[5], "readonly") && strcmp(argv[5], "absent")) return 2;
  pc1715 *m = calloc(1, sizeof(*m));
  uint8_t *disk = malloc(819200);
  if (!m || !disk) return 2;
  pc1715_init(m);
  if(pc1715_onboard_enable(m))return 2;
  if (!read_file(argv[1], m->rom, 2048) || !read_file(argv[2], disk, 819200)) return 2;
  const char *names[] = {"io.trace", "ram.bin", "disk.img", "screen.txt"};
  FILE *outputs[4] = {0};
  for (unsigned i = 0; i < 4; i++) {
    char path[4096];
    int n = snprintf(path, sizeof(path), "%s/%s", argv[3], names[i]);
    if (n < 0 || (size_t)n >= sizeof(path)) return 2;
    outputs[i] = fopen(path, "wx");
    if (!outputs[i]) { perror(path); return 2; }
  }
  logfile = outputs[0];
  fixture f = {.command = argc >= 5 ? argv[4] : "",
    .key_due = option("PICO1715_KEY_START", 20000000, 1000000000),
    .command_gap = option("PICO1715_COMMAND_GAP", 10000000, 1000000000)};
  struct key_schedule scheduled={0};
  const char *schedule_path=getenv("PICO1715_KEY_SCHEDULE");
  if(schedule_path && (*f.command || key_schedule_load(&scheduled,schedule_path))) {
    fprintf(stderr,"invalid keyboard schedule (or conflicting command)\n");return 2;
  }
  unsigned service_pc=option("PICO1715_KEY_SERVICE_PC",0,65535),previous_pc=65536;
  uint64_t service_last=0,service_gap=0,service_visits=0;
  if (pico1715_mount(&f.controller, disk, 819200, 80, 2, 5, 3)) return 2;
  f.controller.writable = argc != 6; /* Only this process-owned copy can be modified. */
  #ifndef P1715_FIRMWARE_COSIM
  if (argc == 6 && !strcmp(argv[5], "absent")) f.controller.image = NULL;
#endif
  if (getenv("PICO1715_TIMED")) {
    f.controller.timing.enabled = 1;
    f.controller.timing.read_delay = option("PICO1715_TIMED", 0, 1000000);
    f.controller.timing.write_delay = option("PICO1715_WRITE_DELAY", 0, 1000000);
    f.controller.timing.mark_delay = option("PICO1715_MARK_DELAY", 0, 1000000);
    f.controller.timing.irq_delay = option("PICO1715_IRQ_DELAY", 0, 1000000);
    f.controller.timing.fifo_depth = option("PICO1715_FIFO", 1, 16);
    f.controller.timing.drop_byte = option("PICO1715_DROP_BYTE", 0, 1030);
    f.controller.timing.corrupt_crc = option("PICO1715_CORRUPT_CRC", 0, 1);
    f.controller.timing.no_wait = option("PICO1715_NO_WAIT", 0, 1);
  }
#ifdef P1715_FIRMWARE_COSIM
  unsigned reset_phase = option("PICO1715_RESET_PHASE", 0, 3);
#else
  unsigned reset_phase = option("PICO1715_RESET_PHASE", 0, 2);
#endif
  unsigned resets = 0, reset_unchanged = 0;
  uint64_t reset_at = 0;
  uint8_t *reset_image = reset_phase ? malloc(819200) : NULL;
  if (reset_phase && !reset_image) return 2;
  #ifdef PICO1715_COSIM
  cosim_init(m, &f.controller);
#ifdef P1715_FIRMWARE_COSIM
  firmware_cosim_start(argc == 6 && !strcmp(argv[5], "absent"));
#endif
#endif
  pc1715_card card = {&f, input, output, card_tick,
    card_irq, card_ack, card_reti, card_reset, card_wait};
  pc1715_attach(m, &card);
  m->trace = (dac_trace_sink){trace, &f, 0, 0};
#ifdef P1715_ANALYZER
  analyzer_init(m, argv[3]);
#endif
  if(option("PICO1715_BOOT_DIAGNOSTICS",0,1)){
    char path[4096];
    if(snprintf(path,sizeof(path),"%s/boot-diagnostic.json",argv[3]) >= (int)sizeof(path))return 2;
    diagnostic=fopen(path,"wx");if(!diagnostic)return 2;
    fprintf(diagnostic,"{\"fetches\":[");
  }
  uint64_t previous_fetch=0;
  uint64_t handoff = 0;
  unsigned target = 0;
  unsigned cycle_limit = option("PICO1715_CYCLES", 100000000, 2000000000);
  const char *stop_text = getenv("PICO1715_STOP_TEXT");
  size_t stop_length = stop_text ? strlen(stop_text) : 0;
  if (stop_text && (!stop_length || stop_length > 1920)) return 2;
  unsigned stop_tail = option("PICO1715_STOP_TAIL", 20000000, 1000000000);
  uint64_t stop_at = 0;
  for (unsigned i = 0; i < cycle_limit; i++) {
    /* Optional observation-only completion bound for long generated-OS tests.
     * It never changes guest registers, memory, peripheral state or I/O. */
    if (stop_length && !stop_at && !(i & 16383)) {
      for (size_t off = 0; off + stop_length <= 1920; off++) {
        if (!memcmp(m->ram + 0xf800 + off, stop_text, stop_length)) {
          stop_at = (uint64_t)i + stop_tail + 1;
          break;
        }
      }
    }
    if (stop_at && i >= stop_at) break;
    if(schedule_path)key_schedule_step(&scheduled,i,scheduled_receive,m);
    else keyboard_step(m,&f);
    if(service_pc && m->cpu.cpu.pc==service_pc && previous_pc!=service_pc){
      if(service_visits && i-service_last>service_gap)service_gap=i-service_last;
      service_last=i;service_visits++;
    }
    previous_pc=m->cpu.cpu.pc;
    pc1715_run(m, 1);
    if(diagnostic_active){
      diagnostic_pc[m->cpu.cpu.pc]++;
      uint64_t fetch=m->cpu.pins & (Z80_M1|Z80_MREQ|Z80_RD);
      if(fetch==(Z80_M1|Z80_MREQ|Z80_RD) && fetch!=previous_fetch && diagnostic_fetches<512){
        unsigned a=Z80_GET_ADDR(m->cpu.pins);
        fprintf(diagnostic,"%s[%" PRIu64 ",%u,%u]",diagnostic_fetches?",":"",m->cpu.cycles,a,m->ram[a]);
        diagnostic_fetches++;
      }
      previous_fetch=fetch;
    }
#ifdef P1715_ANALYZER
    analyzer_observe();
#endif
#ifdef PICO1715_COSIM
    cosim_observe();
#endif
    int reset_during_storage = 0;
#ifdef P1715_FIRMWARE_COSIM
    reset_during_storage = reset_phase == 3 && firmware_cosim_storage_busy();
#endif
    if (!resets && (reset_during_storage || (reset_phase == 1 && f.controller.stream_active &&
                     f.controller.pos > 16) ||
                    (reset_phase == 2 && f.controller.write_active &&
                     f.controller.write_pos > 16))) {
      /* Firmware has a separate PSRAM cache; the original disk buffer is only
       * its eventual SD export and cannot prove reset preservation. */
      uint8_t *cache = f.controller.image ? f.controller.image : disk;
      memcpy(reset_image, cache, 819200);
      pc1715_reset(m);
      reset_unchanged = !memcmp(reset_image, cache, 819200);
      resets++; reset_at = i + 1;
      f.key_pos = f.key_half = 0; f.key_due = 20000000;
      handoff = 0; target = 0;
    }
    if (!handoff && m->cpu.cpu.pc == 0x204) {
      handoff = m->cpu.cycles;
      target = m->ram[0x81e] | (m->ram[0x81f] << 8);
      if(diagnostic)diagnostic_active=1;
    }
  }
  #ifdef P1715_FIRMWARE_COSIM
  firmware_cosim_export();
#endif
#ifdef P1715_ANALYZER
  analyzer_finish();
#endif
  if(diagnostic){
    fprintf(diagnostic,"],\"pc_ticks\":{");unsigned n=0;
    for(unsigned a=0;a<65536;a++)if(diagnostic_pc[a])fprintf(diagnostic,"%s\"%u\":%" PRIu64,n++?",":"",a,diagnostic_pc[a]);
    fprintf(diagnostic,"},\"io_reads\":{");n=0;
    for(unsigned a=0;a<256;a++)if(diagnostic_reads[a])fprintf(diagnostic,"%s\"%u\":%" PRIu64,n++?",":"",a,diagnostic_reads[a]);
    fprintf(diagnostic,"},\"io_writes\":{");n=0;
    for(unsigned a=0;a<256;a++)if(diagnostic_writes[a])fprintf(diagnostic,"%s\"%u\":%" PRIu64,n++?",":"",a,diagnostic_writes[a]);
    fprintf(diagnostic,"}}\n");if(fclose(diagnostic))return 2;
  }
  pico1715_controller c = f.controller;
  printf("{\"key_scheduled\":%u,\"key_attempted\":%u,\"key_accepted\":%u,\"key_rejected\":%u,"
         "\"key_late\":%u,\"key_disabled\":%u,\"key_full\":%u,\"key_pending\":%u,"
         "\"key_service_visits\":%" PRIu64 ",\"key_service_max_gap\":%" PRIu64 ",",
         schedule_path!=NULL,scheduled.attempted,scheduled.accepted,scheduled.rejected,
         scheduled.late,scheduled.disabled,scheduled.full,scheduled.count-scheduled.next,
         service_visits,service_gap);
  printf("\"cycles\":%" PRIu64 ",\"pc\":%u,\"rom_handoff_cycle\":%" PRIu64
    ",\"rom_handoff_target\":%u,\"fields\":%" PRIu64 ",\"bytes\":%" PRIu64
    ",\"index_interrupts\":%" PRIu64 ",\"steps\":%" PRIu64
    ",\"cylinder\":%u,\"sector\":%u,\"format\":%u,\"control\":%u,"
    "\"writes\":%" PRIu64 ",\"rejected_writes\":%" PRIu64
    ",\"rx_capacity\":%u,\"timed\":%u,\"wait_ticks\":%" PRIu64 ",\"arrivals\":%" PRIu64
    ",\"overruns\":%" PRIu64 ",\"underflows\":%" PRIu64
    ",\"drops\":%" PRIu64 ",\"tx_overruns\":%" PRIu64
    ",\"tx_underruns\":%" PRIu64 ",\"max_read_age\":%" PRIu64
    ",\"max_tx_interval\":%" PRIu64 ",\"resets\":%u,\"reset_at\":%" PRIu64
    ",\"reset_image_unchanged\":%u,\"onboard\":%u,\"keyboard_bytes\":%u,\"sio_reads\":%u,\"sio_writes\":%u,\"ctc_writes\":%u,\"sio_errors\":%u}\n",
    m->cpu.cycles, m->cpu.cpu.pc, handoff, target, c.fields, c.bytes,
    c.interrupts, c.steps, c.cylinder, c.sector, c.format, c.control,
    c.writes, c.rejected_writes, c.timing.fifo_depth?c.timing.fifo_depth:1, c.timing.enabled, m->wait_ticks, c.arrivals,
    c.overruns, c.underflows, c.drops, c.tx_early, c.tx_late, c.max_read_age,
    c.max_tx_interval, resets, reset_at, reset_unchanged, m->onboard, f.key_bytes, f.sio_reads, f.sio_writes, f.ctc_writes, m->sio[0].errors);
#ifdef PICO1715_COSIM
  fprintf(stderr, "RTL requests=%" PRIu64 " acks=%" PRIu64 " reti=%" PRIu64 "\n",
          cosim_requests(), cosim_acks(), cosim_returns());
#endif
  /* Local diagnostic dump; never modify ROM or disk source files. */
  fwrite(m->ram, 1, sizeof(m->ram), outputs[1]);
  fwrite(disk, 1, 819200, outputs[2]);
  for (unsigned row = 0; row < 24; row++) {
    for (unsigned col = 0; col < 80; col++) {
      unsigned ch = m->ram[0xf800 + row * 80 + col];
      fputc(ch >= 32 && ch < 127 ? ch : '.', outputs[3]);
    }
    fputc('\n', outputs[3]);
  }
  int failed = ferror(stdout);
  for (unsigned i = 0; i < 4; i++) {
    if (ferror(outputs[i])) failed = 1;
    if (fclose(outputs[i])) failed = 1;
  }
  free(scheduled.events); free(reset_image); free(m); free(disk);
  return handoff && !failed ? 0 : 1;
}
