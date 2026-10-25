/* SPDX-License-Identifier: MIT */
#ifndef P1715_SD_CRC_H
#define P1715_SD_CRC_H
#include <stdint.h>
static inline uint8_t p1715_sd_crc7(unsigned cmd,uint32_t arg){
 uint8_t bytes[5]={(uint8_t)(0x40|cmd),(uint8_t)(arg>>24),(uint8_t)(arg>>16),(uint8_t)(arg>>8),(uint8_t)arg};
 uint8_t crc=0;
 for(unsigned i=0;i<5;i++){uint8_t b=bytes[i];for(unsigned j=0;j<8;j++){
  crc<<=1;if((b^crc)&0x80)crc^=9;b<<=1;
 }}return (uint8_t)((crc<<1)|1);
}
static inline uint16_t p1715_sd_crc16(const uint8_t *data,unsigned length){
 uint16_t crc=0;while(length--){crc^=(uint16_t)*data++<<8;
  for(unsigned i=0;i<8;i++)crc=(uint16_t)((crc<<1)^((crc&0x8000)?0x1021:0));
 }return crc;
}
#endif
