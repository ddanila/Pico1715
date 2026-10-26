// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Standalone passive personality. Not yet connected to board pads or USB.
module analyzer_top #(
 parameter PTR_BITS=8
)(
 input wire clk, card_reset_n,
 input wire [39:0] sample,
 input wire iei,
 input wire arm, stop,
 input wire [39:0] trigger_mask, trigger_value,
 input wire [PTR_BITS:0] pre_samples, post_samples,
 input wire read_enable,
 input wire [PTR_BITS-1:0] read_index,
 output reg read_valid,
 output reg [71:0] read_record,
 output reg active, done, triggered, stopped, config_error, command_rejected,
 output reg [PTR_BITS:0] count, trigger_index,
 output wire host_oe, wait_pull_low, int_pull_low, busrq_pull_low,
 output wire nmi_pull_low, memdi_pull_low, reset_pull_low, ieo
);
 localparam [PTR_BITS:0] DEPTH = {1'b1,{PTR_BITS{1'b0}}};
 reg [71:0] memory [0:(1<<PTR_BITS)-1];
 reg [PTR_BITS-1:0] start_ptr, write_ptr;
 reg [PTR_BITS:0] pre_limit, remaining;
 reg [39:0] mask_latched, value_latched;
 reg [31:0] tick;
 wire match_sample = (sample & mask_latched) == (value_latched & mask_latched);
 wire [PTR_BITS+1:0] requested = {1'b0,pre_samples}+{1'b0,post_samples}+1'b1;
 wire [PTR_BITS-1:0] read_address = start_ptr + read_index;
 // Analyzer has no path that can assert a host drive. Priority passes through.
 assign host_oe=1'b0, wait_pull_low=1'b0, int_pull_low=1'b0;
 assign busrq_pull_low=1'b0, nmi_pull_low=1'b0, memdi_pull_low=1'b0;
 assign reset_pull_low=1'b0, ieo=iei;
 // RAM ports deliberately have no reset so iCE40 block RAM can be inferred.
 // read_record is unspecified unless read_valid is asserted.
 always @(posedge clk) begin
  if(active && !stop && (triggered || match_sample || pre_limit!=0))
   memory[write_ptr]<={tick,sample};
  if(read_enable && done && !arm && {1'b0,read_index}<count)
   read_record<=memory[read_address];
 end
 always @(posedge clk or negedge card_reset_n) begin
  if(!card_reset_n) begin
   start_ptr<=0; write_ptr<=0; pre_limit<=0; remaining<=0;
   mask_latched<=0; value_latched<=0; tick<=0;
   active<=0; done<=0; triggered<=0; stopped<=0;
   config_error<=0; command_rejected<=0; count<=0; trigger_index<=0;
   read_valid<=0;
  end else begin
   read_valid<=0;
   // Downloads are synchronous and only possible from a frozen capture.
   if(read_enable && done && !arm && {1'b0,read_index}<count) begin
    read_valid<=1;
   end
   if(arm && active) command_rejected<=1;
   if(arm && !active) begin
    active<=0; done<=0; triggered<=0; stopped<=0; count<=0;
    trigger_index<=0; start_ptr<=0; write_ptr<=0; tick<=0;
    command_rejected<=0; config_error<=0;
    if(stop || requested>{1'b0,DEPTH}) config_error<=1;
    else begin
     active<=1; pre_limit<=pre_samples; remaining<=post_samples;
     mask_latched<=trigger_mask; value_latched<=trigger_value;
    end
   end else if(active) begin
    // Stop wins over sampling: no ambiguous extra record on a stop edge.
    if(stop) begin active<=0; done<=1; stopped<=1; end
    else begin
     tick<=tick+1'b1;
     if(triggered) begin
      write_ptr<=write_ptr+1'b1;
      count<=count+1'b1; remaining<=remaining-1'b1;
      if(remaining==1) begin active<=0; done<=1; end
     end else if(match_sample) begin
      write_ptr<=write_ptr+1'b1;
      trigger_index<=count; count<=count+1'b1; triggered<=1;
      if(remaining==0) begin active<=0; done<=1; end
     end else if(pre_limit!=0) begin
      write_ptr<=write_ptr+1'b1;
      if(count==pre_limit) start_ptr<=start_ptr+1'b1;
      else count<=count+1'b1;
     end
    end
   end
  end
 end
endmodule
