// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Separate observed fetch/IACK bus from deferred normal-I/O transaction seam.
module cosim_top(
 input wire clk, reset_n, power_good,
 input wire [15:0] host_addr,
 input wire [7:0] host_wdata,
 input wire iorq_n,m1_n,rd_n,wr_n,
 output wire request,request_write,
 output wire [3:0] request_reg,
 output wire [7:0] request_data,
 input wire response_ack,
 input wire [7:0] response_data,
 output wire wait_pull_low,host_data_enable,
 output wire [7:0] host_rdata,
 output wire fault,
 input wire irq_pending,
 input wire [7:0] irq_vector,
 input wire obs_m1_n,obs_iorq_n,obs_mreq_n,obs_rd_n,
 input wire [7:0] obs_data,
 output wire int_pull_low,irq_data_enable,
 output wire [7:0] vector_data,
 output wire ack_pulse,reti_pulse,in_service
);
 bus_frontend bus(.clk(clk),.reset_n(reset_n),.power_good(power_good),
 .host_addr(host_addr),.host_wdata(host_wdata),.iorq_n(iorq_n),.m1_n(m1_n),
 .rd_n(rd_n),.wr_n(wr_n),.request(request),.request_write(request_write),
 .request_reg(request_reg),.request_data(request_data),.response_ack(response_ack),
 .response_data(response_data),.wait_pull_low(wait_pull_low),
 .host_data_enable(host_data_enable),.host_rdata(host_rdata),.fault(fault));
 wire unused_ieo;
 irq_frontend irq(.clk(clk),.reset_n(reset_n),.power_good(power_good),.iei(1'b1),
 .pending(irq_pending),.vector(irq_vector),.m1_n(obs_m1_n),.iorq_n(obs_iorq_n),
 .mreq_n(obs_mreq_n),.rd_n(obs_rd_n),.host_data(obs_data),.int_pull_low(int_pull_low),
 .ieo(unused_ieo),.data_enable(irq_data_enable),.vector_data(vector_data),
 .ack_pulse(ack_pulse),.reti_pulse(reti_pulse),.in_service(in_service));
endmodule
