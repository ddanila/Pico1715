/* SPDX-License-Identifier: MIT. Native seam for Python/C wire interoperability tests. */
#include "../firmware/analyzer_usb.h"
static p1715_analyzer_usb usb;
static p1715_analyzer capture;
static uint8_t memory[P1715_LA_RAM_SIZE];
static uint32_t pins(void *p){(void)p;return 0;}
static void controls(void *p,uint32_t n){(void)p;(void)n;}
static uint64_t now(void *p){(void)p;return 0;}
static void fence(void *p){(void)p;}
void fixture_init(void){p1715_usb_init(&usb,&capture,(p1715_analyzer_io){0,pins,controls,now,fence},memory,sizeof(memory),50000000);}
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
