// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Test-only timed record ingress, sharing the production FIFO and link RTL.
module analyzer_transport_fixture(
 input wire clk,card_reset_n,capture_clear,capture_enable,link_sync_n,pico_ack,
 input wire event_valid,
 input wire [127:0] event_record,
 output wire [7:0] pico_data,
 output wire [4:0] pico_index,
 output wire pico_request,
 output wire [31:0] dropped,filtered,sent_records
);
 wire reset_assert_n=card_reset_n && !capture_clear;
 reg [1:0] reset_release;
 always @(posedge clk or negedge reset_assert_n)
  if(!reset_assert_n)reset_release<=0;else reset_release<={reset_release[0],1'b1};
 wire reset_n=reset_release[1];
 wire read_enable,read_valid,unused_overflow;
 wire [127:0] read_record;
 wire [8:0] queued;
 analyzer_record_fifo fifo(.clk(clk),.card_reset_n(reset_n),.enable(capture_enable),
 .event_valid(event_valid),.event_record(event_record),.capture_mask(10'h170),
 .read_enable(read_enable),.read_valid(read_valid),.read_record(read_record),
 .queued(queued),.dropped(dropped),.filtered(filtered),.overflow(unused_overflow));
 analyzer_link link(.clk(clk),.reset_n(reset_n),.sync_n(link_sync_n),.ack(pico_ack),
 .capture_enable(capture_enable),.capture_idle(!capture_enable),.queued(queued),
 .dropped(dropped),.filtered(filtered),.capture_mask(10'h170),.read_enable(read_enable),
 .read_valid(read_valid),.read_record(read_record),.data(pico_data),.byte_index(pico_index),
 .request(pico_request),.sent_records(sent_records));
endmodule
