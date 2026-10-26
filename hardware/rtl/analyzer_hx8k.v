// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Passive adapter only: there are deliberately no host-output ports.
module analyzer_hx8k(
 input wire clk100,card_power_good,
 input wire [36:0] bus_sample,
 output wire [7:0] pico_data,
 output wire [4:0] pico_index,
 output wire pico_request,
 input wire pico_ack,link_sync_n,capture_clear,capture_enable
);
 reg clk50=0;
 always @(posedge clk100)clk50<=!clk50;
 // Matched two-stage sampling; keeps future raw-observation inputs routed too.
 // Multibit transitions still require receiver/setup/hold bench qualification.
 (* keep=1 *) reg [36:0] sample_meta=37'h1fffffffff;
 (* keep=1 *) reg [36:0] sample_sync=37'h1fffffffff;
 always @(posedge clk50)begin sample_meta<=bus_sample;sample_sync<=sample_meta;end
 wire [39:0] sample={2'b0,sample_sync[36],sample_sync};
 wire [31:0] dropped,filtered,sent;
 wire host_oe,wait_low,int_low,busrq_low,nmi_low,memdi_low,reset_low,ieo;
 analyzer_transport_top transport(.clk(clk50),.card_reset_n(card_power_good),
 .capture_clear(capture_clear),.capture_enable(capture_enable),.link_sync_n(link_sync_n),
 .pico_ack(pico_ack),.sample(sample),.iei(sample_sync[36]),
 .pico_data(pico_data),.pico_index(pico_index),.pico_request(pico_request),
 .host_oe(host_oe),.wait_pull_low(wait_low),.int_pull_low(int_low),
 .busrq_pull_low(busrq_low),.nmi_pull_low(nmi_low),.memdi_pull_low(memdi_low),
 .reset_pull_low(reset_low),.ieo(ieo),.dropped(dropped),.filtered(filtered),.sent_records(sent));
 wire unused=^{dropped,filtered,sent,host_oe,wait_low,int_low,busrq_low,nmi_low,memdi_low,reset_low,ieo};
endmodule
