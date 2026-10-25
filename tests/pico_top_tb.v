// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module pico_top_tb;
 reg clk100=0;always #5 clk100=~clk100;
 reg host_reset_n=0,power_good=1,backend_ready=0;
 reg [7:0] host_addr=0,host_din=0;
 reg iorq_n=1,m1_n=1,mreq_n=1,rd_n=1,wr_n=1,iei=1;
 wire [7:0] host_dout;
 wire host_oe,wait_pull_low,int_pull_low,ieo,fault;
 tri [7:0] pico_data;
 wire [3:0] pico_reg;
 wire pico_write,pico_request;
 reg pico_ack=0,pico_index=0,pico_mark=0,drive=0;
 reg [7:0] reply=0;
 wire ack_toggle,reti_toggle,ack_index;
 assign pico_data=drive?reply:8'bz;
 pico1715_top dut(.*);
 integer checks=0;
 task step;begin #20;end endtask
 task check(input bit ok,input [511:0] msg);begin checks++;if(!ok)$fatal(1,"%0s",msg);end endtask
 task write_port(input [7:0] port,input [7:0] value);
  begin host_addr=port;host_din=value;iorq_n=0;wr_n=0;#1;check(wait_pull_low,"write waits");
   repeat(3)step();check(pico_request&&pico_write&&pico_data==value,"shared write data");
   pico_ack=1;repeat(5)step();check(!wait_pull_low&&!host_oe,"write completed without driving host");
   iorq_n=1;wr_n=1;repeat(2)step();check(!pico_request,"request fell");
   pico_ack=0;repeat(5)step();
  end
 endtask
 task fetch(input [7:0] data);begin
  m1_n=0;mreq_n=0;rd_n=0;host_din=data;repeat(3)step();
  m1_n=1;mreq_n=1;rd_n=1;repeat(2)step();end endtask
 initial begin
  #2;check(!host_oe&&!wait_pull_low&&!int_pull_low,"unready gated");
  repeat(4)step();host_reset_n=1;backend_ready=1;repeat(8)step();
  write_port(5,8'h10);write_port(7,8'hcf);write_port(7,8'he3);
  write_port(7,8'h12);write_port(7,8'h37);write_port(7,8'hfd);write_port(7,8'h83);
  host_addr=2;iorq_n=0;rd_n=0;repeat(3)step();
  check(pico_request&&!pico_write&&pico_data===8'bz,"read bus released by FPGA");
  reply=8'h96;drive=1;step();pico_ack=1;repeat(5)step();
  check(host_oe&&host_dout==8'h96&&!wait_pull_low,"shared read response");
  iorq_n=1;rd_n=1;repeat(2)step();drive=0;pico_ack=0;repeat(5)step();
  pico_mark=1;repeat(4)step();check(int_pull_low,"mark IRQ");
  m1_n=0;iorq_n=0;repeat(3)step();
  check(host_oe&&host_dout==8'h12&&ack_toggle&&!ack_index,"cached mark vector and source");
  pico_mark=0;repeat(4)step();check(host_dout==8'h12&&ack_toggle,"IACK held once");
  m1_n=1;iorq_n=1;repeat(3)step();fetch(8'hed);fetch(8'h4d);check(reti_toggle,"RETI notification");
  pico_mark=1;pico_index=1;repeat(4)step();m1_n=0;iorq_n=0;repeat(3)step();
  check(host_dout==8'h10&&!ack_toggle&&ack_index,"index priority and source");
  backend_ready=0;#1;check(!host_oe&&!wait_pull_low&&!int_pull_low,"backend loss gates bus");
  check(!fault,"no frontend faults");
  $display("Pico link top PASS: %0d checks",checks);$finish;
 end
 initial begin #100000;$fatal(1,"top test timeout");end
endmodule
