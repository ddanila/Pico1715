// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module carrier_combined_tb;
 reg clk100=0;always #5 clk100=~clk100;
 reg power_good=0,backend_ready=0;
 reg [36:0] bus_sample=37'h1fbf000000;
 wire [7:0] host_dout;
 wire host_oe,wait_pull_low,int_pull_low,ieo,fault;
 tri [7:0] pico_data;
 wire [3:0] pico_reg;
 wire pico_write,pico_request;
 reg pico_ack=0,pico_index=0,pico_mark=0;
 wire ack_toggle,reti_toggle,ack_index,personality_controller;
 reg [7:0] response=0;
 assign pico_data=pico_request && !pico_write?response:8'bz;
 carrier_combined dut(.*);
 integer frame_pos=0,records=0,terminal=0,controller_calls=0;
 reg [7:0] frame[0:21];
 reg [7:0] command=1;
 reg armed=0;
 reg [15:0] crc;
 integer i,j;
 reg [3:0] reg_saved;
 reg write_saved;
 reg [7:0] data_saved;
 task step;begin @(negedge clk100);end endtask
 // Independent bounded firmware endpoint. Each byte has its own ACK drain.
 initial forever begin
  step;
  if(pico_request)begin
   reg_saved=pico_reg;write_saved=pico_write;data_saved=pico_data;
   if(pico_write && (pico_reg==13 || pico_reg==15))begin
    if(pico_reg==13)begin if(frame_pos!=0)$fatal(1,"truncated frame");end
    else if(frame_pos==0)$fatal(1,"missing frame start");
    frame[frame_pos]=pico_data;frame_pos=frame_pos+1;
    if(frame_pos==22)begin
     crc=16'hffff;
     for(i=0;i<20;i=i+1)begin
      crc=crc^{frame[i],8'b0};
      for(j=0;j<8;j=j+1)crc=crc[15]?(crc<<1)^16'h1021:crc<<1;
     end
     if({frame[21],frame[20]}!=crc)$fatal(1,"frame CRC");
     if(frame[0]==1)begin
      if(frame[4][7:4]!=4)$fatal(1,"not an I/O read");
      if(frame[5]!=8'ha5)$fatal(1,"captured wrong read data");
      records=records+1;
     end else if(frame[0]==2)begin
      if({frame[15],frame[14],frame[13],frame[12]}!=records)$fatal(1,"terminal record count");
      if({frame[7],frame[6],frame[5],frame[4]}!=0)$fatal(1,"unexpected loss");
      terminal=terminal+1;
     end else $fatal(1,"frame type");
     frame_pos=0;
    end
   end else if(!pico_write && pico_reg==14)response=8'ha7;
   else if(!pico_write && pico_reg==12)begin response=command;if(command==1)armed=1;command=0;end
   else begin
    if(pico_write || pico_reg!=2)$fatal(1,"unexpected controller operation");
    response=8'ha5;controller_calls=controller_calls+1;
   end
   repeat(5)step;
   if(!pico_request || pico_reg!=reg_saved || pico_write!=write_saved || (pico_write && pico_data!=data_saved))$fatal(1,"unstable request");
   pico_ack=1;
   while(pico_request)step;
   repeat(2)step;pico_ack=0;
  end
 end
 integer k;
 initial begin
  repeat(4)step;power_good=1;backend_ready=1;
  while(!armed)step;
  repeat(30)step;
  for(k=0;k<80;k=k+1)begin
   bus_sample[15:0]=16'h0002;bus_sample[25]=0;bus_sample[26]=0;
   repeat(8)step;
   while(wait_pull_low)begin if(fault)$fatal(1,"controller fault");step;end
   if(!host_oe || host_dout!=8'ha5)$fatal(1,"controller read corrupted");
   bus_sample[23:16]=host_dout;repeat(10)step;
   bus_sample[25]=1;bus_sample[26]=1;repeat(40)step;
  end
  command=2;
  while(!terminal)begin if(fault)$fatal(1,"link fault");step;end
  if(records!=80 || controller_calls!=80 || terminal!=1)$fatal(1,"missing transactions");
  power_good=0;step;
  if(host_oe || wait_pull_low || pico_request)$fatal(1,"power isolation");
  $display("carrier combined PASS: 80 controller reads during CRC-checked capture, terminal accounting, power isolation");$finish;
 end
 initial begin #3000000;$fatal(1,"timeout");end
endmodule
