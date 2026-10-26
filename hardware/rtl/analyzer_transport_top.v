// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Analyzer personality, 50-MHz acquisition clock intended; no board pads assigned.
module analyzer_transport_top # (parameter [9:0] CAPTURE_MASK=10'h170)(
 input wire clk, card_reset_n, capture_clear, capture_enable, link_sync_n, pico_ack,
 input wire [39:0] sample,
 input wire iei,
 output wire [7:0] pico_data,
 output wire [4:0] pico_index,
 output wire pico_request,
 output wire host_oe,wait_pull_low,int_pull_low,busrq_pull_low,
 output wire nmi_pull_low,memdi_pull_low,reset_pull_low,ieo,
 output wire [31:0] dropped, filtered, sent_records
);
 wire reset_assert_n=card_reset_n && !capture_clear;
 reg [1:0] reset_release;
 always @(posedge clk or negedge reset_assert_n)
  if(!reset_assert_n)reset_release<=0;else reset_release<={reset_release[0],1'b1};
 wire reset_n=reset_release[1];
 reg [1:0] enable_sync;
 always @(posedge clk or negedge reset_n)
  if(!reset_n)enable_sync<=0;else enable_sync<={enable_sync[0],capture_enable};
 wire read_enable,read_valid,idle,unused_overflow;
 wire [127:0] read_record;
 wire [8:0] queued;
 cycle_capture_top capture(.clk(clk),.card_reset_n(reset_n),.enable(enable_sync[1]),
 .sample(sample),.capture_mask(CAPTURE_MASK),.iei(iei),.read_enable(read_enable),
 .read_valid(read_valid),.read_record(read_record),.queued(queued),.dropped(dropped),
 .filtered(filtered),.overflow(unused_overflow),.idle(idle),.host_oe(host_oe),
 .wait_pull_low(wait_pull_low),.int_pull_low(int_pull_low),.busrq_pull_low(busrq_pull_low),
 .nmi_pull_low(nmi_pull_low),.memdi_pull_low(memdi_pull_low),.reset_pull_low(reset_pull_low),.ieo(ieo));
 analyzer_link link(.clk(clk),.reset_n(reset_n),.sync_n(link_sync_n),.ack(pico_ack),
 .capture_enable(enable_sync[1]),.capture_idle(idle),.queued(queued),.dropped(dropped),
 .filtered(filtered),.capture_mask(CAPTURE_MASK),.read_enable(read_enable),.read_valid(read_valid),
 .read_record(read_record),.data(pico_data),.byte_index(pico_index),.request(pico_request),
 .sent_records(sent_records));
endmodule
