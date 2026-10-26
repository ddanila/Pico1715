/* SPDX-License-Identifier: MIT
 * APS6404L SPI-mode quad read/write; original implementation from AP Memory
 * command table and RP2350 QMI register descriptions. Bench qualification pending.
 */
#include "pico/stdlib.h"
#include "hardware/structs/qmi.h"
#include "hardware/structs/xip_ctrl.h"
#include "hardware/sync.h"
static void __no_inline_not_in_flash_func(command)(uint8_t cmd,unsigned width){
 qmi_hw->direct_csr=(8u<<QMI_DIRECT_CSR_CLKDIV_LSB)|QMI_DIRECT_CSR_EN_BITS|QMI_DIRECT_CSR_ASSERT_CS1N_BITS;
 qmi_hw->direct_tx=QMI_DIRECT_TX_NOPUSH_BITS|QMI_DIRECT_TX_OE_BITS|(width<<QMI_DIRECT_TX_IWIDTH_LSB)|cmd;
 while((qmi_hw->direct_csr&QMI_DIRECT_CSR_BUSY_BITS)||!(qmi_hw->direct_csr&QMI_DIRECT_CSR_TXEMPTY_BITS)){}
 qmi_hw->direct_csr=(8u<<QMI_DIRECT_CSR_CLKDIV_LSB)|QMI_DIRECT_CSR_EN_BITS;
 for(volatile unsigned i=0;i<64;i++){}
}
static void __no_inline_not_in_flash_func(configure)(void){
 uint32_t saved=save_and_disable_interrupts();
 command(0xf5,2); /* Leave QPI after a warm reset, if necessary. */
 command(0x66,0);command(0x99,0); /* Separate CE frames. */
 qmi_hw->m[1].timing=(8u<<QMI_M1_TIMING_MAX_SELECT_LSB)|
   (4u<<QMI_M1_TIMING_MIN_DESELECT_LSB)|(2u<<QMI_M1_TIMING_RXDELAY_LSB)|4u;
 qmi_hw->m[1].rfmt=QMI_M1_RFMT_PREFIX_LEN_BITS|
   (2u<<QMI_M1_RFMT_ADDR_WIDTH_LSB)|(2u<<QMI_M1_RFMT_DATA_WIDTH_LSB)|
   (2u<<QMI_M1_RFMT_DUMMY_WIDTH_LSB)|(6u<<QMI_M1_RFMT_DUMMY_LEN_LSB);
 qmi_hw->m[1].rcmd=0xeb;
 qmi_hw->m[1].wfmt=QMI_M1_WFMT_PREFIX_LEN_BITS|
   (2u<<QMI_M1_WFMT_ADDR_WIDTH_LSB)|(2u<<QMI_M1_WFMT_DATA_WIDTH_LSB);
 qmi_hw->m[1].wcmd=0x38;
 qmi_hw->direct_csr=0;
 hw_set_bits(&xip_ctrl_hw->ctrl,XIP_CTRL_WRITABLE_M1_BITS);
 restore_interrupts(saved);
}
uint8_t *p1715_psram_region(uint32_t offset,uint32_t size){
 if(!size || offset>8u*1024u*1024u || size>8u*1024u*1024u-offset || (offset&3) || (size&3))return NULL;
 gpio_set_function(47,GPIO_FUNC_XIP_CS1);sleep_us(200);configure();
 volatile uint32_t *ram=(volatile uint32_t *)(0x15000000u+offset); /* Uncached memory window 1. */
 for(unsigned i=0;i<size/4;i++)ram[i]=i^0xa55ac33cu;
 for(unsigned i=0;i<size/4;i++)if(ram[i]!=(i^0xa55ac33cu))return NULL;
 return (uint8_t *)ram;
}

uint8_t *p1715_psram(void){return p1715_psram_region(0,819200);}
