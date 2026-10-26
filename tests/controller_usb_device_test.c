/* SPDX-License-Identifier: MIT */
#include "usb_stub/tusb.h"
#include "../firmware/store.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
void fixture_init(unsigned);
void fixture_core(void);
unsigned fixture_shutdown(void);
void p1715_controller_usb_device(void);
void tud_cdc_line_state_cb(uint8_t,bool,bool);
void tud_umount_cb(void);
static uint8_t rx[32],tx[256];
static unsigned received,read_pos,written,space=7,reads,writes;
static bool rapid_reconnect;
void tusb_init(void){}
void tud_task(void){if(rapid_reconnect){rapid_reconnect=false;tud_cdc_line_state_cb(0,false,false);tud_cdc_line_state_cb(0,true,false);}}
bool tud_cdc_connected(void){return true;}
uint32_t tud_cdc_available(void){return received-read_pos;}
uint32_t tud_cdc_read(void *p,uint32_t n){assert(n==1 && tud_cdc_available());*(uint8_t *)p=rx[read_pos++];reads++;return 1;}
void tud_cdc_read_flush(void){received=read_pos=0;}
void tud_cdc_write_clear(void){written=0;}
uint32_t tud_cdc_write_available(void){return space;}
uint32_t tud_cdc_write(const void *p,uint32_t n){assert(n<=64 && n<=space && written+n<=sizeof(tx));memcpy(tx+written,p,n);written+=n;writes+=n;return n;}
void tud_cdc_write_flush(void){}
static void visit(void){reads=writes=0;p1715_controller_usb_device();assert(reads<=16 && writes<=64);}
static void put32(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void request(unsigned cmd,unsigned length){
 uint8_t bytes[16]={'P','1','C','Q',1,(uint8_t)cmd,0,0,7};put32(bytes+12,p1715_crc32(bytes,12));
 memcpy(rx,bytes,length);received=length;read_pos=0;
}
static void finish(unsigned shutdown){
 for(unsigned i=0;i<30 && written<132;i++)visit();
 assert(written==132 && !memcmp(tx,"P1CR",4) && tx[6]==0);
 assert(get32(tx+128)==p1715_crc32(tx,128) && get32(tx+32)==shutdown);
}
int main(void){
 fixture_init(1);visit();
 request(1,16);visit();fixture_core();space=0;visit();assert(!written);
 space=7;finish(0);tud_umount_cb();
 // A complete drop/rise during one task visit must clear a partial request.
 request(1,8);visit();rapid_reconnect=true;visit();request(1,16);visit();fixture_core();finish(0);
 tud_umount_cb();request(2,16);visit();rapid_reconnect=true;visit();
 fixture_core();visit();assert(!written && fixture_shutdown()==2);
 request(1,16);visit();fixture_core();visit();assert(written==7);
 // A disconnect also clears an already partially transmitted response.
 rapid_reconnect=true;visit();assert(!written);
 request(1,16);visit();fixture_core();finish(2);
 puts("controller USB adapter PASS: bounded visits, backpressure, rapid reconnect and retained eject");
}
