// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Sampled-level bus segment encoder. No host outputs or backpressure path.
module cycle_encoder(
 input wire clk, card_reset_n, enable,
 input wire [39:0] sample,
 output reg record_valid,
 output reg [127:0] record_data,
 output wire busy
);
 // kinds: fetch=1, MR=2, MW=3, IR=4, IW=5, IACK=6, refresh=7,
 // reset interval=8, invalid bus combination=9. Zero means no segment.
 reg [3:0] kind_now;
 always_comb begin
  kind_now=0;
  if(!sample[31]) kind_now=8;
  else if((!sample[24] && !sample[25]) || (!sample[26] && !sample[27])) kind_now=9;
  else if(!sample[25] && !sample[28]) kind_now=6;
  else if(!sample[24] && !sample[29]) kind_now=7;
  else if(!sample[24] && !sample[26]) kind_now=sample[28]?4'd2:4'd1;
  else if(!sample[24] && !sample[27]) kind_now=3;
  else if(!sample[25] && !sample[26]) kind_now=4;
  else if(!sample[25] && !sample[27]) kind_now=5;
 end
 reg [31:0] tick, sequence_number, started;
 reg [15:0] duration, wait_samples, address;
 reg [7:0] data;
 reg [3:0] kind, flags;
 reg previous_enable;
 wire unused_sample = ^{sample[39:33],sample[30]};
 assign busy=kind!=0;
 always @(posedge clk or negedge card_reset_n) begin
  if(!card_reset_n) begin
   tick<=0;sequence_number<=0;started<=0;duration<=0;wait_samples<=0;
   address<=0;data<=0;kind<=0;flags<=0;previous_enable<=0;
   record_valid<=0;record_data<=0;
  end else begin
   tick<=tick+1'b1;previous_enable<=enable;record_valid<=0;
   if(kind!=0 && (!enable || kind_now!=kind)) begin
    record_valid<=1;
    record_data<={sequence_number,started,duration,wait_samples,address,data,kind,
                  (flags | ((!enable || kind_now==8)?4'b0010:4'b0000))};
    sequence_number<=sequence_number+1'b1;
   end
   if(!enable) kind<=0;
   else if(kind_now!=kind || !previous_enable) begin
    kind<=kind_now;started<=tick;duration<=1;
    wait_samples<=(!sample[32] && kind_now!=8)?16'd1:16'd0;
    address<=kind_now==8?16'd0:sample[15:0];
    data<=kind_now==8?8'd0:sample[23:16];
    flags<=!previous_enable?4'b0001:4'b0000;
   end else if(kind!=0) begin
    if(duration!=16'hffff) duration<=duration+1'b1;
    else flags[2]<=1;
    if(!sample[32] && kind!=8) begin
     if(wait_samples!=16'hffff) wait_samples<=wait_samples+1'b1;
     else flags[2]<=1;
    end
    // Sample data throughout the asserted window, never from its trailing idle.
    if(kind!=8) begin
     data<=sample[23:16];
     if(address!=sample[15:0]) flags[3]<=1;
    end
   end
  end
 end
endmodule
