// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module cycle_capture_top #(parameter PTR_BITS=8)(
 input wire clk, card_reset_n, enable,
 input wire [39:0] sample,
 input wire [9:0] capture_mask,
 input wire iei, read_enable,
 output wire read_valid,
 output wire [127:0] read_record,
 output wire [PTR_BITS:0] queued,
 output wire [31:0] dropped, filtered,
 output wire overflow,
 output wire idle,
 output wire host_oe, wait_pull_low, int_pull_low, busrq_pull_low,
 output wire nmi_pull_low, memdi_pull_low, reset_pull_low, ieo
);
 wire event_valid,busy;
 wire [127:0] event_record;
 cycle_encoder encoder(.clk(clk),.card_reset_n(card_reset_n),.enable(enable),
 .sample(sample),.record_valid(event_valid),.record_data(event_record),.busy(busy));
 analyzer_record_fifo #(.PTR_BITS(PTR_BITS)) fifo(.clk(clk),.card_reset_n(card_reset_n),
 .enable(enable),.event_valid(event_valid),.event_record(event_record),.capture_mask(capture_mask),
 .read_enable(read_enable),.read_valid(read_valid),.read_record(read_record),.queued(queued),
 .dropped(dropped),.filtered(filtered),.overflow(overflow));
 assign idle=!enable && !busy && !event_valid;
 assign host_oe=0,wait_pull_low=0,int_pull_low=0,busrq_pull_low=0;
 assign nmi_pull_low=0,memdi_pull_low=0,reset_pull_low=0,ieo=iei;
endmodule
