/* SPDX-License-Identifier: MIT. Static ROM disassembly, no running machine. */
#include <stdint.h>
#include <stddef.h>
#define CHIPS_UTIL_IMPL
#include "third_party/cpu/chips/z80dasm.h"
static char text[128];
static const uint8_t *bytes;
static unsigned length,used,written;
static uint8_t input(void *p){(void)p;return used<length?bytes[used++]:0;}
static void output(char c,void *p){(void)p;if(written<127)text[written++]=c;}
unsigned disassemble(const uint8_t *p,unsigned n,unsigned pc){bytes=p;length=n;used=written=0;unsigned next=z80dasm_op((uint16_t)pc,input,output,NULL);text[written]=0;return next;}
const char *dis_text(void){return text;}
unsigned dis_count(void){return used;}
