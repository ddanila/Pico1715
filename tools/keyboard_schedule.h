/* SPDX-License-Identifier: MIT
 * Completed-byte deadlines, independent of guest readiness and CPU resets.
 * Input grammar: decimal tick, whitespace, decimal byte, newline; no comments.
 */
#ifndef P1715_KEYBOARD_SCHEDULE_H
#define P1715_KEYBOARD_SCHEDULE_H
#include <ctype.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#define KEY_EVENTS_MAX 65536
struct key_event { uint64_t tick; uint8_t byte; };
struct key_schedule {
    struct key_event *events;
    unsigned count, next, attempted, accepted, rejected, late;
    unsigned disabled, full;
};
static int key_schedule_load(struct key_schedule *s, const char *path) {
    FILE *f=fopen(path,"r");if(!f)return -1;
    s->events=calloc(KEY_EVENTS_MAX,sizeof(*s->events));
    if(!s->events){fclose(f);return -1;}
    char line[128];int bad=0;
    while(fgets(line,sizeof(line),f)) {
        char *p=line,*end;
        if(s->count==KEY_EVENTS_MAX || !strchr(line,'\n') || !isdigit((unsigned char)*p)){bad=1;break;}
        errno=0;unsigned long long tick=strtoull(p,&end,10);
        if(errno || tick>=2000000000u || (*end!=' ' && *end!='\t')){bad=1;break;}
        p=end;while(*p==' ' || *p=='\t')p++;
        if(!isdigit((unsigned char)*p)){bad=1;break;}
        errno=0;unsigned long byte=strtoul(p,&end,10);
        while(*end==' ' || *end=='\t' || *end=='\r')end++;
        if(errno || byte>255 || strcmp(end,"\n") || (s->count && tick<s->events[s->count-1].tick)){bad=1;break;}
        s->events[s->count++]=(struct key_event){tick,(uint8_t)byte};
    }
    if(ferror(f))bad=1;
    if(fclose(f))bad=1;
    if(bad){free(s->events);s->events=NULL;return -1;}
    return 0;
}
/* Receiver returns 0, -EAGAIN (disabled), -ENOSPC (full), or another rejection. */
static void key_schedule_step(struct key_schedule *s,uint64_t tick,
                              int (*receive)(void *,uint8_t),void *user) {
    while(s->next<s->count && s->events[s->next].tick<=tick) {
        struct key_event *e=&s->events[s->next++];s->attempted++;
        if(e->tick<tick)s->late++;
        int rc=receive(user,e->byte);
        if(!rc)s->accepted++;
        else {s->rejected++;if(rc==-EAGAIN)s->disabled++;if(rc==-ENOSPC)s->full++;}
    }
}
#endif
