// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Arbitration only: controller and trace endpoints use four-phase handshakes.
// Auxiliary timeouts quarantine the link until reset: a late ACK must never be
// reassigned to a controller transaction. Trace is admitted only between cycles.
module combined_mailbox #(
 parameter integer AUX_TIMEOUT=1024,
 parameter integer POLL_INTERVAL=1024
)(
 input wire clk,reset_n,
 input wire controller_request,controller_write,
 input wire [3:0] controller_reg,
 input wire [7:0] controller_data,
 output wire controller_ack,
 output wire [7:0] controller_response,
 input wire trace_request,
 input wire [7:0] trace_data,
 input wire [4:0] trace_index,
 output wire trace_ack,
 output reg command_valid,
 output reg [7:0] command,
 output reg negotiated,unsupported,fault,
 output wire request,write,
 output wire [3:0] address,
 output wire [7:0] data,
 input wire ack,
 input wire [7:0] response
);
 localparam [2:0] IDLE=0,CTRL=1,PROBE=2,POLL=3,TRACE=4,DRAIN=5,QUARANTINE=6;
 reg [2:0] state;
 reg [1:0] ack_sync;
 reg [7:0] latched_data;
 reg [3:0] latched_address;
 reg trace_accepted;
 integer age,poll_age;
 wire auxiliary=state==PROBE || state==POLL || state==TRACE;
 assign request=reset_n && !fault && (state==CTRL?controller_request:auxiliary);
 assign write=state==CTRL?controller_write:state==TRACE;
 assign address=state==CTRL?controller_reg:latched_address;
 assign data=state==CTRL?controller_data:latched_data;
 assign controller_ack=reset_n && !fault && state==CTRL && ack_sync[1];
 assign controller_response=response;
 // Retain acknowledgement until the trace endpoint lowers its request.
 assign trace_ack=reset_n && !fault && trace_accepted;
 always @(posedge clk or negedge reset_n)begin
  if(!reset_n)begin
   state<=IDLE;ack_sync<=0;latched_data<=0;latched_address<=0;
   trace_accepted<=0;age<=0;poll_age<=0;
   negotiated<=0;unsupported<=0;fault<=0;command_valid<=0;command<=0;
  end else begin
   ack_sync<={ack_sync[0],ack};command_valid<=0;
   if(!trace_request)trace_accepted<=0;
   if(poll_age<POLL_INTERVAL)poll_age<=poll_age+1;
   if(auxiliary || state==DRAIN)age<=age+1;else age<=0;
   if((auxiliary || state==DRAIN) && age>=AUX_TIMEOUT-1)begin
    fault<=1;state<=QUARANTINE;
   end else case(state)
    IDLE:if(!ack_sync[1])begin
     if(controller_request)state<=CTRL;
     else if(!negotiated && !unsupported)begin state<=PROBE;latched_address<=14;end
     else if(negotiated && poll_age>=POLL_INTERVAL)begin state<=POLL;latched_address<=12;end
     else if(negotiated && trace_request && !trace_accepted)begin
      state<=TRACE;latched_address<=trace_index==0?13:15;latched_data<=trace_data;
     end
    end
    CTRL:if(!controller_request)begin state<=DRAIN;age<=0;end
    PROBE:if(ack_sync[1])begin
     negotiated<=response==8'ha7;unsupported<=response!=8'ha7;
     state<=DRAIN;age<=0;
    end
    POLL:if(ack_sync[1])begin
     command<=response;command_valid<=1;poll_age<=0;state<=DRAIN;age<=0;
    end
    TRACE:if(ack_sync[1])begin trace_accepted<=1;state<=DRAIN;age<=0;end
    DRAIN:if(!ack_sync[1])begin state<=IDLE;age<=0;end
    QUARANTINE:begin end
    default:begin fault<=1;state<=QUARANTINE;end
   endcase
  end
 end
endmodule
