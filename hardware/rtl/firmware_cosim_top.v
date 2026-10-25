// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Adapt the DAC deferred I/O seam to the unmodified board-level RTL.
module firmware_cosim_top(
 input wire clk100,reset_n,power_good,
 input wire transaction,
 input wire [7:0] host_addr,host_wdata,
 input wire iorq_n,rd_n,wr_n,
 input wire obs_m1_n,obs_iorq_n,obs_mreq_n,obs_rd_n,
 input wire [7:0] obs_data,
 input wire [31:0] gpio_out,gpio_dir,
 output wire [31:0] gpio_in,
 output wire wait_pull_low,host_data_enable,int_pull_low,fault,
 output wire [7:0] host_rdata,
 output wire contention
);
 wire [7:0] data;
 wire [3:0] reg_addr;
 wire request,write_req,ack_toggle,reti_toggle,ack_index,ieo;
 assign data=gpio_dir[7:0]==8'hff ?gpio_out[7:0]:8'bz;
 assign gpio_in={10'b0,1'b0,ack_index,reti_toggle,ack_toggle,2'b0,reset_n,
                 1'b0,request,write_req,reg_addr,data};
 assign contention=request && write_req && |gpio_dir[7:0];
 pico1715_top board(.clk100(clk100),.host_reset_n(reset_n),.power_good(power_good),
 .backend_ready(gpio_out[21]),.host_addr(host_addr),
 .host_din(transaction?host_wdata:obs_data),
 .iorq_n(transaction?iorq_n:(obs_iorq_n || obs_m1_n)),.m1_n(transaction?1'b1:obs_m1_n),
 .mreq_n(transaction?1'b1:obs_mreq_n),.rd_n(transaction?rd_n:obs_rd_n),
 .wr_n(transaction?wr_n:1'b1),.iei(1'b1),.host_dout(host_rdata),
 .host_oe(host_data_enable),.wait_pull_low(wait_pull_low),.int_pull_low(int_pull_low),
 .ieo(ieo),.fault(fault),.pico_data(data),.pico_reg(reg_addr),.pico_write(write_req),
 .pico_request(request),.pico_ack(gpio_out[14]),.pico_index(gpio_out[16]),
 .pico_mark(gpio_out[17]),.ack_toggle(ack_toggle),.reti_toggle(reti_toggle),.ack_index(ack_index));
 wire unused_ieo=ieo;
 wire [23:0] unused_gpio={gpio_out[31:22],gpio_out[20:18],gpio_out[15],gpio_out[13:8],gpio_dir[31:28]};
 wire [19:0] unused_dir=gpio_dir[27:8];
endmodule
