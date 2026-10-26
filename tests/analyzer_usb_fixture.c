/* SPDX-License-Identifier: MIT. Native seam for Python/C wire interoperability tests. */
#include "../firmware/analyzer_usb.h"
static p1715_analyzer_usb usb;
static p1715_analyzer capture;
static uint8_t memory[P1715_LA_RAM_SIZE];
static uint32_t input_pins;
static uint64_t clock_us;
static uint32_t pins(void *p){(void)p;return input_pins;}
static void controls(void *p,uint32_t n){(void)p;(void)n;}
static uint64_t now(void *p){(void)p;return clock_us;}
static void fence(void *p){(void)p;}
void fixture_init(void){input_pins=0;clock_us=0;p1715_usb_init(&usb,&capture,(p1715_analyzer_io){0,pins,controls,now,fence},memory,sizeof(memory),50000000);}
void fixture_feed(uint8_t n){p1715_usb_receive(&usb,n);}
size_t fixture_read(uint8_t *out,size_t capacity){size_t n;const uint8_t *p=p1715_usb_output(&usb,&n);if(n>capacity)n=capacity;for(size_t i=0;i<n;i++)out[i]=p[i];p1715_usb_sent(&usb,n);return n;}
void fixture_disconnect(void){p1715_usb_disconnect(&usb);}
int fixture_complete(const uint8_t *data,size_t size){
 if(size<32 || size>sizeof(memory) || (size-32)%16)return -1;
 for(size_t i=0;i<size;i++)memory[i]=data[i];
 capture.records=(uint32_t)((size-32)/16);capture.state=P1715_LA_DONE;return 0;
}
uint32_t fixture_stopping(void){return capture.stopping;}
void fixture_error(void){capture.state=P1715_LA_ERROR;}

void fixture_frame(const uint8_t *frame){
 clock_us+=200;p1715_analyzer_step(&capture);
 for(unsigned i=0;i<22;i++){
  input_pins=(1u<<13)|(i<<8)|frame[i];clock_us++;p1715_analyzer_step(&capture);
  input_pins=0;clock_us++;p1715_analyzer_step(&capture);
  if(capture.state!=P1715_LA_REQUEST)break;
 }
}

/* Independent timer models autonomous PIO completion even when USB polling stalls. */
static uint64_t reset_until;
static uint32_t reset_calls;
static bool reset_fail;
static bool reset_start(void *p){(void)p;if(reset_fail)return false;reset_calls++;reset_until=clock_us+100000;return true;}
static void reset_cancel(void *p){(void)p;reset_until=0;}
static bool reset_active(void *p){(void)p;return clock_us<reset_until;}
void fixture_reset_enable(void){reset_calls=0;reset_fail=false;p1715_usb_reset_backend(&usb,(p1715_reset_io){0,reset_start,reset_cancel,reset_active});}
void fixture_advance(uint32_t us){clock_us+=us;}
void fixture_poll(void){p1715_usb_poll(&usb);}
void fixture_step(void){p1715_analyzer_step(&capture);p1715_usb_poll(&usb);}
uint32_t fixture_reset_active(void){return reset_active(0);}
uint32_t fixture_reset_calls(void){return reset_calls;}
void fixture_reset_fail(void){reset_fail=true;}
