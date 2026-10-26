// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Combined carrier A: dedicated hardware qualifier; never reuse old analyzer wiring.
module carrier_controller(
 input wire clk100, host_reset_n, power_good, backend_ready,
 input wire [7:0] host_addr,host_din,
 input wire iorq_n,m1_n,mreq_n,rd_n,wr_n,iei,
 output wire [7:0] host_dout,
 output wire host_oe,wait_pull_low,int_pull_low,ieo,fault,
 inout wire [7:0] pico_data,
 output wire [3:0] pico_reg,
 output wire pico_write,pico_request,
 input wire pico_ack,pico_index,pico_mark,
 output reg ack_toggle,reti_toggle,ack_index,
 output wire personality_controller
);
 assign personality_controller=1'b1;
 pico1715_top core(.*);
endmodule
