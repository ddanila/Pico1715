// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Bench top: HX8K board 100 MHz -> 50 MHz frontend. No X2 contacts assumed.
module pico1715_top(
 input wire clk100, host_reset_n, power_good, backend_ready,
 input wire [7:0] host_addr,host_din,
 input wire iorq_n,m1_n,mreq_n,rd_n,wr_n,iei,
 output wire [7:0] host_dout,
 output wire host_oe,wait_pull_low,int_pull_low,ieo,fault,
 inout wire [7:0] pico_data,
 output wire [3:0] pico_reg,
 output wire pico_write,pico_request,
 input wire pico_ack,pico_index,pico_mark,
 output reg ack_toggle,reti_toggle,ack_index
);
 reg clk50=0;
 always @(posedge clk100) clk50<=!clk50;
 wire reset_n=host_reset_n && backend_ready;
 wire alive=reset_n && power_good;
 wire [7:0] request_data,normal_data,vector_data;
 wire normal_oe,irq_oe,ack_pulse,reti_pulse,in_service;
 reg [1:0] index_sync,mark_sync;
 reg [7:0] index_vector,mark_vector;
 reg direction_next,mask_next,mirrored;
 wire index_pending=index_sync[1];
 wire mark_pending=mark_sync[1];
 assign pico_data=(alive && pico_request && pico_write)?request_data:8'bz;
 assign host_dout=irq_oe?vector_data:normal_data;
 assign host_oe=alive && !fault && (normal_oe || irq_oe);
 bus_frontend bus(.clk(clk50),.reset_n(reset_n),.power_good(power_good),
 .host_addr({8'b0,host_addr}),.host_wdata(host_din),.iorq_n(iorq_n),.m1_n(m1_n),
 .rd_n(rd_n),.wr_n(wr_n),.request(pico_request),.request_write(pico_write),
 .request_reg(pico_reg),.request_data(request_data),.response_ack(pico_ack),
 .response_data(pico_data),.wait_pull_low(wait_pull_low),.host_data_enable(normal_oe),
 .host_rdata(normal_data),.fault(fault));
 irq_frontend irq(.clk(clk50),.reset_n(reset_n),.power_good(power_good),.iei(iei),
 .pending(index_pending||mark_pending),.vector(index_pending?index_vector:mark_vector),
 .m1_n(m1_n),.iorq_n(iorq_n),.mreq_n(mreq_n),.rd_n(rd_n),.host_data(host_din),
 .int_pull_low(int_pull_low),.ieo(ieo),.data_enable(irq_oe),.vector_data(vector_data),
 .ack_pulse(ack_pulse),.reti_pulse(reti_pulse),.in_service(in_service));
 wire unused_service=in_service;
 always @(posedge clk50 or negedge alive) begin
  if(!alive) begin
   index_sync<=0;mark_sync<=0;index_vector<=0;mark_vector<=0;
   ack_toggle<=0;reti_toggle<=0;ack_index<=0;direction_next<=0;mask_next<=0;mirrored<=0;
  end else begin
   index_sync<={index_sync[0],pico_index};mark_sync<={mark_sync[0],pico_mark};
   if(ack_pulse)begin ack_toggle<=!ack_toggle;ack_index<=index_pending;end
   if(reti_pulse)reti_toggle<=!reti_toggle;
   if(!pico_request)mirrored<=0;
   else if(!wait_pull_low && !mirrored && !fault) begin
    mirrored<=1;
    if(pico_write && pico_reg==5 && !request_data[0])index_vector<=request_data;
    if(pico_write && pico_reg==7) begin
     if(direction_next)direction_next<=0;
     else if(mask_next)mask_next<=0;
     else if(request_data==8'hcf)direction_next<=1;
     else if(!request_data[0])mark_vector<=request_data;
     else if(request_data[3:0]==7 && request_data[4])mask_next<=1;
    end
   end
  end
 end
endmodule
