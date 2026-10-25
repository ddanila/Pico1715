// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module irq_tb;
 reg clk=0;always #10 clk=~clk;
 reg reset_n=0,power_good=1,iei=1,pending=0;
 reg [7:0] vector=8'h12,host_data=0;
 reg m1_n=1,iorq_n=1,mreq_n=1,rd_n=1;
 wire int_pull_low,ieo,data_enable,ack_pulse,reti_pulse,in_service;
 wire [7:0] vector_data;
 irq_frontend dut(.*);
 integer acks=0,retis=0,checks=0;
 always @(negedge clk) begin if(ack_pulse)acks++;if(reti_pulse)retis++;end
 task step;begin @(negedge clk);#1;end endtask
 task check(input bit ok,input [511:0] msg);begin checks++;if(!ok)$fatal(1,"%0s",msg);end endtask
 task fetch(input [7:0] data);begin
 host_data=8'h00;m1_n=0;mreq_n=0;rd_n=0;repeat(3)step();
 host_data=data;repeat(3)step();m1_n=1;mreq_n=1;rd_n=1;host_data=8'hff;step();end endtask
 initial begin
 step();reset_n=1;step();pending=1;step();check(int_pull_low&&!ieo,"pending claims chain");
 iei=0;step();check(!int_pull_low&&!ieo,"higher priority blocks");
 m1_n=0;iorq_n=0;repeat(3)step();check(!data_enable&&acks==0,"unowned IACK does not drive");
 m1_n=1;iorq_n=1;step();iei=1;step();m1_n=0;iorq_n=0;repeat(4)step();
 check(data_enable&&vector_data==8'h12&&acks==1&&in_service,"single vector acknowledgement");
 vector=8'h10;pending=0;step();check(vector_data==8'h12,"vector held during IACK");
 m1_n=1;iorq_n=1;step();check(!data_enable&&!int_pull_low&&!ieo,"service blocks lower chain");
 // Ordinary data reads of ED 4D cannot release service.
 mreq_n=0;rd_n=0;host_data=8'hed;step();host_data=8'h4d;step();mreq_n=1;rd_n=1;step();
 check(in_service&&retis==0,"only M1 fetches decode RETI");
 fetch(8'hed);fetch(8'h45);check(in_service,"RETN is not RETI");
 iei=0;fetch(8'hed);fetch(8'h4d);check(in_service,"higher-priority RETI cannot release us");
 // A transient early 4D after ED must not falsely release service.
 iei=1;fetch(8'hed);host_data=8'h4d;m1_n=0;mreq_n=0;rd_n=0;repeat(3)step();
 check(in_service,"early fetch byte cannot release service");
 host_data=8'h00;repeat(3)step();m1_n=1;mreq_n=1;rd_n=1;step();
 check(in_service&&retis==0,"final non-RETI byte defeats stale 4D");
 fetch(8'hed);fetch(8'h4d);check(!in_service&&retis==1&&ieo,"RETI releases service once");
 pending=1;step();m1_n=0;iorq_n=0;step();check(data_enable,"second IACK owned");
 power_good=0;#1;check(!data_enable&&!int_pull_low,"power loss gates IRQ outputs");
 step();check(!in_service,"reset clears interrupt state");
 $display("IRQ PASS: %0d checks",checks);$finish;
 end
 initial begin #10000;$fatal(1,"IRQ test timeout");end
endmodule
