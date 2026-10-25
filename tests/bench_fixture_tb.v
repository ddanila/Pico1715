// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module bench_fixture_tb;
 reg clk100=0;always #5 clk100=~clk100;
 reg fixture_reset_n=0,backend_ready=0;
 tri [7:0] pico_data;
 wire [3:0] pico_reg;
 wire pico_write,pico_request,ack_toggle,reti_toggle,ack_index,test_reset_n,passed,failed,uart_tx;
 reg pico_ack=0,pico_index=0,pico_mark=0;
 reg drive=0;reg [7:0] reply=0,control=8'hff;
 assign pico_data=drive?reply:8'bz;
 bench_fixture #(.BOOT_LIMIT(2000),.IRQ_LIMIT(2000),.UART_DIV(8),.GAP(20)) dut(.*);
 integer delay_count=0,transactions=0,mode=0;
 reg seen=0,irq_enable=0;
 always @(posedge clk100)begin
  if(!fixture_reset_n || !test_reset_n)begin
   pico_ack<=0;drive<=0;seen<=0;delay_count<=0;transactions<=0;control<=8'hff;
   pico_index<=0;irq_enable<=0;
  end else begin
   if(irq_enable && !ack_toggle)pico_index<=1;
   if(ack_toggle)pico_index<=0;
   if(!pico_request)begin
    if(mode!=3)begin drive<=0;pico_ack<=0;end
    seen<=0;delay_count<=0;
   end else if(!seen)begin
    delay_count<=delay_count+1;
    if(delay_count==12+(transactions%17))begin
     seen<=1;transactions<=transactions+1;pico_ack<=1;
     if(pico_write)begin
      if(pico_reg==4)control<=pico_data;
      if(pico_reg==5 && pico_data==8'h83)irq_enable<=1;
     end else begin drive<=1;reply<=mode==2?~control:control;end
    end
   end
  end
 end
 task tick(input integer n);begin repeat(n)@(negedge clk100);end endtask
 task start(input integer m);begin
  fixture_reset_n=0;backend_ready=0;mode=m;tick(10);fixture_reset_n=1;tick(30);
  if(m!=1)backend_ready=1;
 end endtask
 task finish_case(input [7:0] expected);begin
  wait(passed||failed);tick(1);
  if(dut.failure!==expected)$fatal(1,"mode %0d: expected %0d got %0d",mode,expected,dut.failure);
 end endtask
 task uart_byte(output [7:0] value);integer b;begin
  @(negedge uart_tx);tick(48);
  for(b=0;b<8;b=b+1)begin value[b]=uart_tx;tick(32);end
  if(!uart_tx)$fatal(1,"UART stop bit");
 end endtask
 reg [7:0] frame[0:8];reg [7:0] sum;integer i;
 initial begin
  start(0);finish_case(0);
  if(dut.completed!=515 || transactions!=515 || !reti_toggle || dut.max_wait==0)
   $fatal(1,"normal fixture did not exercise complete path");
  // Capture from the NEXT complete frame, after the initial one has started.
  tick(1000);
  // Synchronize by byte value; 0xA5 cannot occur in this short-run payload.
  uart_byte(frame[0]);while(frame[0]!=8'ha5)uart_byte(frame[0]);
  for(i=1;i<9;i=i+1)uart_byte(frame[i]);
  sum=0;for(i=0;i<8;i=i+1)sum=sum^frame[i];
  if(sum!=frame[8] || frame[1]!=0 || {frame[3],frame[2]}!=515)$fatal(1,"UART summary invalid");
  start(1);finish_case(2); // Missing backend fails within bounded boot time.
  start(2);finish_case(3); // Wrong read byte is detected.
  start(3);finish_case(6); // ACK stuck after completion fails drain timeout.
  start(0);wait(dut.completed==4);backend_ready=0;finish_case(1);
  $display("bench fixture PASS: 515 transactions, IRQ/RETI, UART, four fault paths");$finish;
 end
 initial begin #20000000;$fatal(1,"fixture test global timeout");end
endmodule
