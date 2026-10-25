/* SPDX-License-Identifier: MIT */
#include "machines/robotron1715/pc1715.h"
#include "../model/controller.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include <errno.h>

#ifdef PICO1715_COSIM
#include "cosim/bridge.h"
#ifdef P1715_FIRMWARE_COSIM
void firmware_cosim_start(int absent);
void firmware_cosim_export(void);
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
/* Headless motherboard fixture, separate from the expansion card. It injects
 * the keyboard's E0/ASCII serial frames through SIO receive registers. */
typedef struct {
  pico1715_controller controller;
  const char *command;
  unsigned key_pos, key_half, sio_register;
  uint64_t key_due;
} fixture;
static int input(void *p, uint16_t a, uint8_t *data) {
  fixture *f = p;
  if ((a & 255) == 14) {
    *data = f->sio_register == 1 ? 0 :
      4 | ((f->command[f->key_pos] && f->controller.cycle >= f->key_due) ? 1 : 0);
    f->sio_register = 0; return 1;
  }
  if ((a & 255) == 12) {
    *data = 0;
    if (f->command[f->key_pos] && f->controller.cycle >= f->key_due) {
      if (!f->key_half) { *data = 0xe0; f->key_half = 1; }
      else { *data = f->command[f->key_pos++]; f->key_half = 0;
             f->key_due = f->controller.cycle + (*data == '\r' ? 10000000 : 100000); }
    }
    return 1;
  }
  return card_read(p, a, data);
}
static void output(void *p, uint16_t a, uint8_t data) {
  fixture *f = p;
  if ((a & 255) == 14) {
    if (f->sio_register) f->sio_register = 0;
    else f->sio_register = data & 7;
  } else card_write(p, a, data);
}
static void trace(void *p, const dac_trace_event *e) {
  (void)p;
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
  fixture f = {.command = argc >= 5 ? argv[4] : "", .key_due = 20000000};
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
  unsigned reset_phase = option("PICO1715_RESET_PHASE", 0, 2);
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
  m->trace = (dac_trace_sink){trace, NULL, 0, 0};
  uint64_t handoff = 0;
  unsigned target = 0;
  unsigned cycle_limit = option("PICO1715_CYCLES", 100000000, 100000000);
  for (unsigned i = 0; i < cycle_limit; i++) {
    pc1715_run(m, 1);
#ifdef PICO1715_COSIM
    cosim_observe();
#endif
    if (!resets && ((reset_phase == 1 && f.controller.stream_active &&
                     f.controller.pos > 16) ||
                    (reset_phase == 2 && f.controller.write_active &&
                     f.controller.write_pos > 16))) {
      memcpy(reset_image, disk, 819200);
      pc1715_reset(m);
      reset_unchanged = !memcmp(reset_image, disk, 819200);
      resets++; reset_at = i + 1;
      f.key_pos = f.key_half = f.sio_register = 0; f.key_due = 20000000;
      handoff = 0; target = 0;
    }
    if (!handoff && m->cpu.cpu.pc == 0x204) {
      handoff = m->cpu.cycles;
      target = m->ram[0x81e] | (m->ram[0x81f] << 8);
    }
  }
  #ifdef P1715_FIRMWARE_COSIM
  firmware_cosim_export();
#endif
  pico1715_controller c = f.controller;
  printf("{\"cycles\":%" PRIu64 ",\"pc\":%u,\"rom_handoff_cycle\":%" PRIu64
    ",\"rom_handoff_target\":%u,\"fields\":%" PRIu64 ",\"bytes\":%" PRIu64
    ",\"index_interrupts\":%" PRIu64 ",\"steps\":%" PRIu64
    ",\"cylinder\":%u,\"sector\":%u,\"format\":%u,\"control\":%u,"
    "\"writes\":%" PRIu64 ",\"rejected_writes\":%" PRIu64
    ",\"timed\":%u,\"wait_ticks\":%" PRIu64 ",\"arrivals\":%" PRIu64
    ",\"overruns\":%" PRIu64 ",\"underflows\":%" PRIu64
    ",\"drops\":%" PRIu64 ",\"tx_overruns\":%" PRIu64
    ",\"tx_underruns\":%" PRIu64 ",\"max_read_age\":%" PRIu64
    ",\"max_tx_interval\":%" PRIu64 ",\"resets\":%u,\"reset_at\":%" PRIu64
    ",\"reset_image_unchanged\":%u}\n",
    m->cpu.cycles, m->cpu.cpu.pc, handoff, target, c.fields, c.bytes,
    c.interrupts, c.steps, c.cylinder, c.sector, c.format, c.control,
    c.writes, c.rejected_writes, c.timing.enabled, m->wait_ticks, c.arrivals,
    c.overruns, c.underflows, c.drops, c.tx_early, c.tx_late, c.max_read_age,
    c.max_tx_interval, resets, reset_at, reset_unchanged);
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
  free(reset_image); free(m); free(disk);
  return handoff && !failed ? 0 : 1;
}
