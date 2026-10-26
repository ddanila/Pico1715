// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module cycle_analyzer_tb;
 reg clk=0;always #10 clk=~clk;
 reg card_reset_n=0,enable=0,iei=1,read_enable=0;
 localparam [39:0] RELEASED=40'h3fbf000000;
 reg [39:0] sample=RELEASED;
 wire read_valid,idle,overflow;
 wire [127:0] read_record;
 wire [2:0] queued;
 wire [31:0] dropped,filtered;
 reg [9:0] capture_mask=10'h3fe;
 wire host_oe,wait_pull_low,int_pull_low,busrq_pull_low,nmi_pull_low,memdi_pull_low,reset_pull_low,ieo;
 cycle_capture_top #(.PTR_BITS(2)) dut(.*);
 integer checks=0,i;
 reg [31:0] expected_seq=0;
 task check(input bit ok,input [511:0] message);
  begin checks=checks+1;if(!ok)$fatal(1,"%0s",message);end
 endtask
 task step;
  begin @(posedge clk);#1;
   if({host_oe,wait_pull_low,int_pull_low,busrq_pull_low,nmi_pull_low,memdi_pull_low,reset_pull_low}!==0 || ieo!==iei) $fatal(1,"passivity");
   if(dut.pop && dut.push && dut.rd_ptr==dut.wr_ptr) $fatal(1,"RAM collision");
   @(negedge clk);
  end
 endtask
 task reset;
  begin card_reset_n=0;enable=0;read_enable=0;sample=RELEASED;step;
   card_reset_n=1;expected_seq=0;step;enable=1;step;
  end
 endtask
 task bus(input [3:0] kind,input [15:0] addr,input [7:0] data);
  begin sample=RELEASED | {16'd0,data,addr};
   case(kind)
    1:begin sample[24]=0;sample[26]=0;sample[28]=0;end
    2:begin sample[24]=0;sample[26]=0;end
    3:begin sample[24]=0;sample[27]=0;end
    4:begin sample[25]=0;sample[26]=0;end
    5:begin sample[25]=0;sample[27]=0;end
    6:begin sample[25]=0;sample[28]=0;end
    7:begin sample[24]=0;sample[29]=0;sample[28]=0;end
    8:sample[31]=0;
    9:begin sample[24]=0;sample[25]=0;end
    default:;
   endcase
  end
 endtask
 task finish_cycle;
  begin sample=RELEASED;step;step;end
 endtask
 task record_check(input [3:0] kind,input [15:0] addr,input [7:0] data,input [15:0] length,input [15:0] waits,input [3:0] flags);
  begin read_enable=1;step;read_enable=0;
   check(read_valid,"record present");
   check(read_record[127:96]==expected_seq,"sequence");expected_seq=expected_seq+1;
   check(read_record[63:0]=={length,waits,addr,data,kind,flags},"decoded record");
  end
 endtask
 initial begin
  reset;
  for(i=1;i<=7;i=i+1) begin
   bus(4'(i),16'hbeef,8'h11);step;sample[23:16]=8'h5a;step;
   finish_cycle;record_check(4'(i),16'hbeef,8'h5a,2,0,0);
   check(read_record[95:64]==32'(2+5*(i-1)),"start timestamp");
  end
  // Long held I/O cycle is one record, including sampled /WAIT duration.
  bus(4,16'h1234,8'hff);sample[32]=0;repeat(5)step;
  sample[32]=1;sample[23:16]=8'h80;step;finish_cycle;
  record_check(4,16'h1234,8'h80,6,5,0);
  // Adjacent distinct kinds need no idle sample to separate them.
  bus(1,16'h2000,8'hcb);step;bus(7,16'h0010,0);step;finish_cycle;
  record_check(1,16'h2000,8'hcb,1,0,0);record_check(7,16'h0010,0,1,0,0);
  bus(2,16'h1000,1);step;sample[15:0]=16'h1001;step;finish_cycle;
  record_check(2,16'h1000,1,2,0,8);
  bus(3,16'h8888,8'h77);step;bus(8,0,0);repeat(3)step;finish_cycle;
  record_check(3,16'h8888,8'h77,1,0,2);record_check(8,0,0,3,0,0);
  bus(9,0,0);step;finish_cycle;record_check(9,0,0,1,0,0);
  bus(2,1,2);step;enable=0;step;step;
  check(idle,"stop flush complete");record_check(2,1,2,1,0,2);
  bus(5,3,4);enable=1;step;finish_cycle;record_check(5,3,4,1,0,1);
  // Saturation is explicit; duration never wraps into an apparently short cycle.
  bus(2,7,8);sample[32]=0;repeat(65537)step;finish_cycle;
  record_check(2,7,8,16'hffff,16'hffff,4);
  // Finite FIFO does not stall the host and reports loss with sequence gaps.
  reset;
  for(i=0;i<6;i=i+1) begin bus(3,16'(i),8'(i));step;finish_cycle;end
  check(queued==3 && dropped==3 && overflow,"overflow accounting");
  for(i=0;i<3;i=i+1) record_check(3,16'(i),8'(i),1,0,0);
  bus(3,6,6);step;finish_cycle;expected_seq=6;record_check(3,6,6,1,0,0);
  read_enable=1;step;check(!read_valid,"empty read");read_enable=0;
  // Full FIFO with simultaneous dequeue/enqueue loses nothing (read old head).
  reset;
  for(i=0;i<3;i=i+1) begin bus(3,16'(i),8'(i));step;finish_cycle;end
  bus(3,3,3);step;sample=RELEASED;step;
  record_check(3,0,0,1,0,0);
  check(queued==3 && dropped==0,"full simultaneous pop/push");
  for(i=1;i<=3;i=i+1)record_check(3,16'(i),8'(i),1,0,0);
  capture_mask=10'h170;reset;capture_mask=10'h3fe;
  bus(1,16'h8000,1);step;finish_cycle;
  bus(4,16'h1204,8'h77);step;finish_cycle;
  check(filtered==1 && queued==1 && dropped==0,"latched filter is not overflow");
  expected_seq=1;record_check(4,16'h1204,8'h77,1,0,0);
  $display("cycle analyzer PASS: %0d checks",checks);$finish;
 end
 initial begin #2000000;$fatal(1,"timeout");end
endmodule
