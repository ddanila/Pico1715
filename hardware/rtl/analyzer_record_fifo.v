// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module analyzer_record_fifo #(parameter PTR_BITS=8)(
 input wire clk,card_reset_n,enable,event_valid,read_enable,
 input wire [127:0] event_record,
 input wire [9:0] capture_mask,
 output reg read_valid,
 output reg [127:0] read_record,
 output reg [PTR_BITS:0] queued,
 output reg [31:0] dropped,filtered,
 output reg overflow
);
 // Reserve one slot: simultaneous pop/push never touches the same RAM address.
 localparam [PTR_BITS:0] CAPACITY={1'b0,{PTR_BITS{1'b1}}};
 reg [127:0] memory[0:(1<<PTR_BITS)-1];
 reg [PTR_BITS-1:0] rd_ptr, wr_ptr;
 reg [9:0] mask_latched;
 reg previous_enable;
 wire selected=mask_latched[event_record[7:4]];
 wire pop=read_enable && queued!=0;
 wire push=event_valid && selected && (queued<CAPACITY || pop);
 always @(posedge clk) begin
  if(push) memory[wr_ptr]<=event_record;
  if(pop) read_record<=memory[rd_ptr];
 end
 always @(posedge clk or negedge card_reset_n) begin
  if(!card_reset_n) begin
   rd_ptr<=0;wr_ptr<=0;queued<=0;dropped<=0;filtered<=0;overflow<=0;read_valid<=0;
   mask_latched<=0;previous_enable<=0;
  end else begin
   read_valid<=pop;previous_enable<=enable;
   if(enable && !previous_enable) mask_latched<=capture_mask;
   if(event_valid && !selected && filtered!=32'hffffffff) filtered<=filtered+1'b1;
   if(pop) rd_ptr<=rd_ptr+1'b1;
   if(push) wr_ptr<=wr_ptr+1'b1;
   case({push,pop})
    2'b10:queued<=queued+1'b1;
    2'b01:queued<=queued-1'b1;
    default:;
   endcase
   if(event_valid && selected && !push) begin
    overflow<=1;
    if(dropped!=32'hffffffff) dropped<=dropped+1'b1;
   end
  end
 end
endmodule
