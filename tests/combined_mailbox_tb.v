// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module combined_mailbox_tb;
 reg clk=0;always #10 clk=~clk;
 reg reset_n=0,controller_request=0,controller_write=0,trace_request=0,ack=0;
 reg [3:0] controller_reg=2;
 reg [7:0] controller_data=0,trace_data=8'h55,response=8'ha7;
 reg [4:0] trace_index=0;
 wire controller_ack,trace_ack,command_valid,negotiated,unsupported,fault,request,write;
 wire [7:0] controller_response,command,data;
 wire [3:0] address;
 combined_mailbox #(.AUX_TIMEOUT(32),.POLL_INTERVAL(64)) dut(.*);
 task step;begin @(posedge clk);#1;@(negedge clk);end endtask
 task restart;begin reset_n=0;controller_request=0;trace_request=0;ack=0;step;reset_n=1;end endtask
 task wait_request;begin while(!request)step;end endtask
 task release_ack;begin ack=0;repeat(5)step;end endtask
 initial begin
  restart;wait_request;
  if(address!=14 || write)$fatal(1,"unsafe negotiation");
  response=255;ack=1;while(request)step;release_ack;
  trace_request=1;repeat(70)begin step;if(request)$fatal(1,"legacy firmware received extension");end
  if(!unsupported || negotiated)$fatal(1,"unsupported state");
  controller_request=1;wait_request;
  if(address!=2 || write)$fatal(1,"legacy controller unavailable");
  response=8'h31;ack=1;while(!controller_ack)step;
  if(controller_response!=8'h31)$fatal(1,"controller reply");
  controller_request=0;step;release_ack;
  restart;response=8'ha7;wait_request;ack=1;while(request)step;release_ack;
  if(!negotiated)$fatal(1,"negotiation failed");
  trace_request=1;wait_request;
  if(address!=13 || !write || data!=8'h55)$fatal(1,"first trace byte");
  controller_request=1;controller_write=1;controller_reg=4;controller_data=8'h99;
  repeat(4)begin step;if(address!=13 || data!=8'h55 || controller_ack)$fatal(1,"preempted live trace byte");end
  ack=1;while(!trace_ack)step;
  if(controller_ack)$fatal(1,"trace ACK reached controller");
  trace_request=0;while(request)step;
  repeat(3)begin step;if(request || controller_ack)$fatal(1,"stale ACK reuse");end
  release_ack;wait_request;
  if(address!=4 || data!=8'h99 || !write)$fatal(1,"controller did not take priority");
  ack=1;while(!controller_ack)step;controller_request=0;step;release_ack;
  // A wedged auxiliary request quarantines late ACKs, even with host pending.
  restart;response=8'ha7;wait_request;ack=1;while(request)step;release_ack;
  trace_request=1;wait_request;controller_request=1;
  repeat(40)step;
  if(!fault || request || controller_ack)$fatal(1,"timeout did not quarantine");
  ack=1;repeat(10)begin step;if(request || controller_ack || trace_ack)$fatal(1,"late ACK escaped quarantine");end
  restart;wait_request;ack=1;while(request)step;
  repeat(40)step;if(!fault)$fatal(1,"ACK drain timeout");
  $display("combined mailbox PASS: negotiation, legacy fallback, priority, stable bytes, late ACK quarantine");$finish;
 end
 initial begin #1000000;$fatal(1,"timeout");end
endmodule
