/* SPDX-License-Identifier: MIT
 * Pico1715 observer for an externally supplied DAC W/M reference model.
 * This does not implement or substitute a Pico1715 controller.
 */
#include "machines/robotron1715m/robotron.h"
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { FILE *file; uint64_t count, dropped; int failed; } capture;

static int load_exact(const char *path, void *buffer, size_t length) {
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    int ok = fread(buffer, 1, length, f) == length && fgetc(f) == EOF && !ferror(f);
    if (fclose(f)) ok = 0;
    return ok;
}

static void observe(void *context, const dac_trace_event *e) {
    capture *c = context;
    if (strcmp(e->kind, "IR") && strcmp(e->kind, "IW") && strcmp(e->kind, "IA"))
        return;
    if (c->count >= 2000000) { c->dropped++; return; }
    if (fprintf(c->file,
        "{\"cycle\":%" PRIu64 ",\"kind\":\"%s\",\"address\":%" PRIu32
        ",\"data\":%u,\"master\":%u}\n",
        e->cycle, e->kind, e->address, e->data, e->master) < 0) c->failed = 1;
    c->count++;
}

int main(int argc, char **argv) {
    if (argc != 6) {
        fprintf(stderr, "usage: dac-capture ROM CAS RAW-DISK TICKS TRACE-OUTPUT\n");
        return 2;
    }
    char *end;
    errno = 0;
    unsigned long ticks = strtoul(argv[4], &end, 10);
    if (errno || !*argv[4] || *end || ticks < 1 || ticks > 500000000UL) return 2;
    robotron *machine = calloc(1, sizeof(*machine));
    uint8_t *disk = malloc(819200);
    int status = 2;
    capture c = {0};
    if (!machine || !disk) goto done;
    robotron_init(machine);
    if (!load_exact(argv[1], machine->rom, sizeof(machine->rom)) ||
        !load_exact(argv[2], machine->prom, sizeof(machine->prom)) ||
        !load_exact(argv[3], disk, 819200)) {
        fprintf(stderr, "Cannot read exact-size W/M reference ROM, PROM or raw disk\n");
        goto done;
    }
    if (robotron_disk(machine, dac_memory_storage(disk, 819200, 0), 0)) goto done;
    c.file = fopen(argv[5], "wx");
    if (!c.file) { perror("trace output"); goto done; }
    machine->trace = (dac_trace_sink){.emit = observe, .user = &c};
    for (unsigned long i = 0; i < ticks;) {
        unsigned n = ticks - i > 1000 ? 1000 : (unsigned)(ticks - i);
        robotron_run(machine, n);
        i += n;
    }
    for (unsigned row = 0; row < 24; row++) {
        for (unsigned col = 0; col < 80; col++) {
            unsigned ch = machine->vram[row * 80 + col] & 127;
            putchar(ch >= 32 && ch < 127 ? (int)ch : ' ');
        }
        putchar('\n');
    }
    fprintf(stderr, "{\"profile\":\"robotron1715m-wm-reference\","
        "\"ticks\":%" PRIu64 ",\"pc\":%u,\"disk_reads\":%" PRIu64
        ",\"disk_writes\":%" PRIu64 ",\"events\":%" PRIu64
        ",\"dropped\":%" PRIu64 "}\n",
        machine->cpu.cycles, machine->cpu.cpu.pc, machine->disk_reads,
        machine->disk_writes, c.count, c.dropped);
    status = c.failed || c.dropped || ferror(stdout) ? 1 : 0;
done:
    if (c.file && fclose(c.file)) status = 1;
    free(disk);
    free(machine);
    return status;
}
