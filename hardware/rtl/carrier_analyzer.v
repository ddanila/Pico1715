// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Combined carrier A: no host-driving ports; signature also blocks hardware ARM.
module carrier_analyzer(
 input wire clk100,card_power_good,
 input wire [36:0] bus_sample,
 output wire [7:0] pico_data,
 output wire [4:0] pico_index,
 output wire pico_request,
 input wire pico_ack,link_sync_n,capture_clear,capture_enable,
 output wire personality_controller
);
 assign personality_controller=1'b0;
 analyzer_hx8k core(.*);
endmodule
