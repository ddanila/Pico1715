/* SPDX-License-Identifier: MIT. SDHC/SDXC SPI block transport; no filesystem. */
#include "sd_spi.h"
#include "sd_crc.h"
#include "pico/stdlib.h"
#include "hardware/spi.h"
#define SD spi1
#define CS 22
static uint8_t exchange(uint8_t value){uint8_t r;spi_write_read_blocking(SD,&value,&r,1);return r;}
static void deselect(void){gpio_put(CS,1);exchange(0xff);}
static int ready(void){uint64_t end=time_us_64()+500000;
 do{if(exchange(0xff)==0xff)return 0;}while(time_us_64()<end);return -1;}
static int command(unsigned c,uint32_t arg){
 deselect();gpio_put(CS,0);if(ready())return -1;
 exchange(0x40|c);for(int shift=24;shift>=0;shift-=8)exchange((uint8_t)(arg>>shift));exchange(p1715_sd_crc7(c,arg));
 for(unsigned i=0;i<16;i++){uint8_t r=exchange(0xff);if(!(r&0x80))return r;}return -1;
}
int p1715_sd_init(void){
 gpio_init(CS);gpio_put(CS,1);gpio_set_dir(CS,GPIO_OUT);
 gpio_set_function(26,GPIO_FUNC_SPI);gpio_set_function(27,GPIO_FUNC_SPI);gpio_set_function(28,GPIO_FUNC_SPI);
 gpio_pull_up(28);spi_init(SD,400000);sleep_ms(2);for(unsigned i=0;i<10;i++)exchange(0xff);
 if(command(0,0)!=1){deselect();return -1;}
 if(command(8,0x1aa)!=1){deselect();return -1;}
 uint32_t r7=0;for(unsigned i=0;i<4;i++)r7=(r7<<8)|exchange(0xff);
 if(r7!=0x1aa){deselect();return -1;}
 uint64_t end=time_us_64()+2000000;int r;
 do{if(command(55,0)!=1){deselect();return -1;}r=command(41,0x40000000);
    if(r==0)break;
    if(r!=1){deselect();return -1;}sleep_ms(1);
 }while(time_us_64()<end);
 if(r!=0||command(58,0)!=0){deselect();return -1;}
 uint32_t ocr=0;for(unsigned i=0;i<4;i++)ocr=(ocr<<8)|exchange(0xff);deselect();
 if((ocr&0xc0000000)!=0xc0000000)return -1; /* Only block-addressed cards. */
 if(command(59,1)!=0){deselect();return -1;}deselect();
 spi_set_baudrate(SD,12000000);return 0;
}
int p1715_sd_read(void *p,uint32_t block,uint8_t *data){
 (void)p;if(command(17,block)){deselect();return -1;}
 uint64_t end=time_us_64()+200000;uint8_t token;
 do{token=exchange(0xff);if(token!=0xff)break;}while(time_us_64()<end);
 if(token!=0xfe){deselect();return -1;}
 spi_read_blocking(SD,0xff,data,512);
 uint16_t crc=(uint16_t)exchange(0xff)<<8;crc|=exchange(0xff);deselect();
 return crc==p1715_sd_crc16(data,512)?0:-1;
}
int p1715_sd_write(void *p,uint32_t block,const uint8_t *data){
 (void)p;if(command(24,block)){deselect();return -1;}
 exchange(0xfe);spi_write_blocking(SD,data,512);uint16_t crc=p1715_sd_crc16(data,512);exchange(crc>>8);exchange(crc&255);
 uint8_t response=exchange(0xff);int result=((response&31)==5)?ready():-1;
 if(!result){int r1=command(13,0);uint8_t status=exchange(0xff);if(r1!=0||status)result=-1;}
 deselect();return result;
}
