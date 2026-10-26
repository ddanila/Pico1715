// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module analyzer_tb;
 reg clk=0; always #10 clk=~clk;
 reg card_reset_n=0,iei=0,arm=0,stop=0,read_enable=0;
 reg [39:0] sample=0,trigger_mask=0,trigger_value=0;
 reg [3:0] pre_samples=0,post_samples=0;
 reg [2:0] read_index=0;
 wire read_valid,active,done,triggered,stopped,config_error,command_rejected;
 wire [71:0] read_record;
 wire [3:0] count,trigger_index;
 wire host_oe,wait_pull_low,int_pull_low,busrq_pull_low,nmi_pull_low;
 wire memdi_pull_low,reset_pull_low,ieo;
 analyzer_top #(.PTR_BITS(3)) dut(.*);
 integer checks=0,i,fd;
 task check(input bit ok,input [511:0] message);
  begin checks=checks+1; if(!ok) $fatal(1,"%0s",message); end
 endtask
 task step;
  begin @(posedge clk); #1;
   check({host_oe,wait_pull_low,int_pull_low,busrq_pull_low,nmi_pull_low,
          memdi_pull_low,reset_pull_low}==0,"passive outputs");
   check(ieo==iei,"priority bypass");
   @(negedge clk);
  end
 endtask
 task begin_capture(input [3:0] pre,input [3:0] post,input [39:0] mask,input [39:0] value);
  begin pre_samples=pre;post_samples=post;trigger_mask=mask;trigger_value=value;
   arm=1;step;arm=0;
  end
 endtask
 task get_record(input [2:0] index,input [31:0] timestamp,input [39:0] value);
  begin read_enable=1;read_index=index;step;
   check(read_valid,"record valid");check(read_record=={timestamp,value},"record contents/order");
   read_enable=0;
  end
 endtask
 initial begin
  step;card_reset_n=1;step;
  begin_capture(3,2,40'hff,40'h55);
  check(active,"armed");
  // Roll the pretrigger ring multiple times; source changes cannot change config.
  trigger_value=0;pre_samples=0;post_samples=0;
  for(i=0;i<19;i=i+1) begin sample=40'(i);iei=~iei;step;end
  sample=40'h55;step;
  check(triggered && trigger_index==3 && count==4,"trigger after wrapped history");
  sample=40'h66;step;sample=40'h77;step;
  check(done && !active && count==6,"exact posttrigger length");
  fd=$fopen("build/analyzer-samples.txt","w");
  get_record(0,16,16);$fdisplay(fd,"%0d %010h",read_record[71:40],read_record[39:0]);
  get_record(1,17,17);$fdisplay(fd,"%0d %010h",read_record[71:40],read_record[39:0]);
  get_record(2,18,18);$fdisplay(fd,"%0d %010h",read_record[71:40],read_record[39:0]);
  get_record(3,19,40'h55);$fdisplay(fd,"%0d %010h",read_record[71:40],read_record[39:0]);
  get_record(4,20,40'h66);$fdisplay(fd,"%0d %010h",read_record[71:40],read_record[39:0]);
  get_record(5,21,40'h77);$fdisplay(fd,"%0d %010h",read_record[71:40],read_record[39:0]);
  $fclose(fd);
  read_enable=1;read_index=6;step;check(!read_valid,"out of bounds download rejected");read_enable=0;
  begin_capture(0,0,0,0);sample=40'hab;step;
  check(done && count==1 && trigger_index==0,"immediate trigger no history/post");
  get_record(0,0,40'hab);
  begin_capture(7,1,0,0);check(config_error && !active,"overcapacity rejected");
  begin_capture(15,15,0,0);check(config_error && !active,"sum cannot wrap");
  begin_capture(7,0,40'hff,40'hfe);
  sample=1;step;sample=2;step;sample=40'hfe;step;
  check(done && count==3 && trigger_index==2,"early trigger retains only existing history");
  get_record(0,0,1);get_record(2,2,40'hfe);
  begin_capture(0,7,0,0);
  for(i=0;i<8;i=i+1) begin sample=40'(i);step;end
  check(done && count==8,"full buffer capture");get_record(7,7,7);
  begin_capture(3,2,40'h0080000000,40'h0080000000);
  sample=0;step;
  arm=1;step;arm=0;check(command_rejected && active,"active rearm rejected");
  // Host reset is an observed bit, not card reset; record both edges.
  sample=40'h0080000000;step;sample=0;step;sample=40'h0080000000;step;
  check(done && count==5,"host reset did not erase capture");
  get_record(2,2,40'h0080000000);get_record(3,3,0);
  begin_capture(2,2,40'hff,40'hff);sample=1;step;sample=2;step;
  read_enable=1;step;check(!read_valid,"no reads while acquiring");read_enable=0;
  stop=1;sample=40'hff;step;stop=0;
  check(done && stopped && !triggered && count==2,"stop wins over trigger");
  get_record(0,1,2);get_record(1,2,2);
  begin_capture(0,2,0,0);step;stop=1;step;stop=0;
  check(done && stopped && triggered && count==1,"stop during posttrigger");
  begin_capture(0,0,40'hff,40'hff);sample=0;step;
  stop=1;step;stop=0;check(done && count==0,"empty stopped capture");
  begin_capture(1,1,40'hff,40'hff);card_reset_n=0;step;
  check(!active && !done && count==0,"card reset clears capture metadata");
  card_reset_n=1;step;
  $display("analyzer PASS: %0d checks",checks);$finish;
 end
 initial begin #100000; $fatal(1,"timeout");end
endmodule
