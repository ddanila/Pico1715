/* SPDX-License-Identifier: MIT */
#include "machines/robotron1715/pc1715.h"
#include "../model/controller.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

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
  return pico1715_read(p, a, data);
}
static void output(void *p, uint16_t a, uint8_t data) {
  fixture *f = p;
  if ((a & 255) == 14) {
    if (f->sio_register) f->sio_register = 0;
    else f->sio_register = data & 7;
  } else pico1715_write(p, a, data);
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
  if (argc == 6 && !strcmp(argv[5], "absent")) f.controller.image = NULL;
  pc1715_card card = {&f, input, output, pico1715_tick,
    pico1715_irq, pico1715_ack, pico1715_reti, pico1715_reset};
  pc1715_attach(m, &card);
  m->trace = (dac_trace_sink){trace, NULL, 0, 0};
  uint64_t handoff = 0;
  unsigned target = 0;
  for (unsigned i = 0; i < 100000000; i++) {
    pc1715_run(m, 1);
    if (!handoff && m->cpu.cpu.pc == 0x204) {
      handoff = m->cpu.cycles;
      target = m->ram[0x81e] | (m->ram[0x81f] << 8);
    }
  }
  pico1715_controller c = f.controller;
  printf("{\"cycles\":%" PRIu64 ",\"pc\":%u,\"rom_handoff_cycle\":%" PRIu64
    ",\"rom_handoff_target\":%u,\"fields\":%" PRIu64 ",\"bytes\":%" PRIu64
    ",\"index_interrupts\":%" PRIu64 ",\"steps\":%" PRIu64
    ",\"cylinder\":%u,\"sector\":%u,\"format\":%u,\"control\":%u,"
    "\"writes\":%" PRIu64 ",\"rejected_writes\":%" PRIu64 "}\n",
    m->cpu.cycles, m->cpu.cpu.pc, handoff, target, c.fields, c.bytes,
    c.interrupts, c.steps, c.cylinder, c.sector, c.format, c.control,
    c.writes, c.rejected_writes);
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
  free(m); free(disk);
  return handoff && !failed ? 0 : 1;
}
