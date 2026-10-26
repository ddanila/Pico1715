// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module analyzer_hx8k_tb;
 reg clk100=0;always #5 clk100=~clk100;
 wire clk=dut.clk50;
 reg card_reset_n=0,capture_clear=0,capture_enable=0,link_sync_n=0,pico_ack=0,iei=1;
 reg [39:0] sample=40'h3fbf000000;
 wire [7:0] pico_data;wire [4:0] pico_index;wire pico_request;
 wire host_oe,wait_pull_low,int_pull_low,busrq_pull_low,nmi_pull_low,memdi_pull_low,reset_pull_low,ieo;
 wire [31:0] dropped,filtered,sent_records;
 analyzer_hx8k dut(.clk100(clk100),.card_power_good(card_reset_n),.bus_sample(sample[36:0]),
 .pico_data(pico_data),.pico_index(pico_index),.pico_request(pico_request),
 .pico_ack(pico_ack),.link_sync_n(link_sync_n),.capture_clear(capture_clear),.capture_enable(capture_enable));
 assign {host_oe,wait_pull_low,int_pull_low,busrq_pull_low,nmi_pull_low,memdi_pull_low,reset_pull_low}=
 {dut.host_oe,dut.wait_low,dut.int_low,dut.busrq_low,dut.nmi_low,dut.memdi_low,dut.reset_low};
 assign ieo=dut.ieo;
 assign sent_records=dut.sent,dropped=dut.dropped,filtered=dut.filtered;
 reg [175:0] frame;
 integer i;
 task step;
  begin @(posedge clk);#1;
   if({host_oe,wait_pull_low,int_pull_low,busrq_pull_low,nmi_pull_low,memdi_pull_low,reset_pull_low}!==0 || ieo!==iei)$fatal(1,"host drive");
   @(negedge clk);
  end
 endtask
 task receive_frame;
  begin
   for(i=0;i<22;i=i+1)begin
    while(!pico_request)step;
    if(pico_index!=5'(i))$fatal(1,"packet index");
    frame[i*8+:8]=pico_data;
    repeat(3)step;
    if(pico_data!==frame[i*8+:8] || pico_index!=5'(i))$fatal(1,"byte stability");
    pico_ack=1;while(pico_request)step;
    pico_ack=0;repeat(3)step;
   end
  end
 endtask
 initial begin
  step;card_reset_n=1;repeat(5)step;link_sync_n=1;capture_enable=1;repeat(5)step;
  sample=40'h3fb9121234;sample[32]=0;repeat(3)step;
  sample[32]=1;sample[23:16]=8'hab;repeat(7)step;
  sample=40'h3fbf000000;receive_frame;
  if(frame[31:0]!=32'h00000101 || frame[95:32]!={16'd10,16'd3,16'h1234,8'hab,4'd4,4'd0})$fatal(1,"native encoder packet");
  // Host reset is an observed event, never a reset of the capture engine.
  sample[31]=0;repeat(6)step;sample[31]=1;receive_frame;
  if(frame[39:36]!=8 || frame[159:128]!=1 || frame[95:80]!=6)$fatal(1,"host reset must retain capture sequence");
  capture_enable=0;receive_frame;
  if(frame[31:0]!=32'h00010102 || frame[127:96]!=2 || frame[63:32]!=0 || frame[95:64]!=0)$fatal(1,"terminal status");
  if(sent_records!=2 || dropped!=0 || filtered!=0)$fatal(1,"terminal counts");
  card_reset_n=0;repeat(5)step;
  if(sent_records!=0 || pico_request)$fatal(1,"card power reset");
  $display("HX8K analyzer PASS: divided clock, sampling pipeline, full address, wait/data, host reset continuity");$finish;
 end
 initial begin #100000;$fatal(1,"timeout");end
endmodule
