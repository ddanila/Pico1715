/* SPDX-License-Identifier: MIT. Actual Pico1715 controller plus DAC motherboard. */
#include "machines/robotron1715/pc1715.h"
#include "../model/controller.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static pc1715 board;
static pico1715_controller controller;
static uint8_t disk[819200], vectors[16];
static unsigned acknowledgements;
static void observe(void *p,const dac_trace_event *e){
 (void)p;if(!strcmp(e->kind,"IA")){assert(acknowledgements<16);vectors[acknowledgements++]=e->data;}
}
static void ow(unsigned port,uint8_t value){assert(pc1715_onboard_write(&board,port,value));}
static void sw(unsigned ch,unsigned reg,uint8_t value){ow(14+ch,reg);ow(14+ch,value);}
static void setup(void){
 pc1715_init(&board);assert(!pc1715_onboard_enable(&board));
 assert(!pico1715_mount(&controller,disk,sizeof(disk),80,2,5,3));
 pc1715_card card={&controller,pico1715_read,pico1715_write,pico1715_tick,
  pico1715_irq,pico1715_ack,pico1715_reti,pico1715_reset,pico1715_wait};
 assert(!pc1715_attach(&board,&card));
 board.trace=(dac_trace_sink){observe,NULL,0,0};acknowledgements=0;
 pico1715_write(&controller,0x20,0xee);pico1715_write(&controller,6,4);
 pico1715_write(&controller,5,0x10);pico1715_write(&controller,5,0x83);
 pico1715_write(&controller,7,0x12);pico1715_write(&controller,7,0xb7);pico1715_write(&controller,7,0xfd);
 ow(8,0x40);ow(8,0xd7);ow(8,1);
 sw(1,2,0x60);sw(1,1,4);sw(0,1,0x10);sw(0,3,1);
}
static void requests(void){
 board.cpu.cycles=PICO1715_CLOCK_HZ/5;
 pico1715_tick(&controller,board.cpu.cycles); /* first rotation boundary */
 pico1715_write(&controller,4,0xa5);pico1715_write(&controller,4,0x85);
 assert(controller.pending && controller.mark_pending);
 pc1715_ctc_input(&board,0,1);
 assert(!pc1715_sio_receive(&board,0,0x55));
}
int main(void){
 setup();requests();
 const uint8_t boot[]={0x31,0,0xf0,0x3e,0x80,0xed,0x47,0xed,0x5e,0xfb,0x76,0x18,0xfd};
 memcpy(board.rom,boot,sizeof(boot));
 const uint8_t expected[]={0x10,0x12,0x40,0x6c};
 for(unsigned i=0;i<4;i++){
  unsigned address=0x9000+16*i;board.ram[0x8000+expected[i]]=address;board.ram[0x8001+expected[i]]=address>>8;
  uint8_t handler[]={0x21,(uint8_t)i,0xa0,0x34,0xdb,0x0c,0xfb,0xed,0x4d};
  if(i!=3){handler[4]=0;handler[5]=0;}
  memcpy(board.ram+address,handler,sizeof(handler));
 }
 pc1715_run(&board,3000);
 assert(acknowledgements==4 && !memcmp(vectors,expected,4));
 for(unsigned i=0;i<4;i++)assert(board.ram[0xa000+i]==1);
 assert(!board.card_service && !controller.service && !pc1715_irq_pending(&board));
 puts("PASS real controller IM2: index 10, mark 12, CTC 40, SIO 6c; one ISR/RETI each");
 setup();requests();assert(pc1715_irq_ack(&board)==0x10);
 pc1715_card_quiesce(&board);assert(pc1715_irq_ack(&board)==0x40);
 pc1715_irq_reti(&board);assert(pc1715_irq_ack(&board)==0x6c);
 uint8_t data;assert(pc1715_onboard_read(&board,12,&data) && data==0x55);
 pc1715_irq_reti(&board);assert(controller.service); /* no stray RETI callback to isolated card */
 pc1715_reset(&board);assert(!controller.service && !pc1715_irq_pending(&board));
 assert(!board.card_offline && board.onboard);
 puts("PASS active-card quiesce releases CTC/SIO; reset clears chain and controller ownership");
 return 0;
}
