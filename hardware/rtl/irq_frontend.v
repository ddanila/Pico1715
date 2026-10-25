// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Local-clock interrupt state. pending/vector must be coherent in this domain.
module irq_frontend(
    input wire clk, reset_n, power_good, iei, pending,
    input wire [7:0] vector,
    input wire m1_n, iorq_n, mreq_n, rd_n,
    input wire [7:0] host_data,
    output wire int_pull_low, ieo, data_enable,
    output reg [7:0] vector_data,
    output reg ack_pulse, reti_pulse,
    output reg in_service
);
    wire alive = reset_n && power_good;
    wire iack = !m1_n && !iorq_n;
    wire fetch = !m1_n && !mreq_n && !rd_n && iorq_n;
    reg ack_seen, ack_owned, fetch_seen, ed_prefix;
    assign int_pull_low = alive && iei && pending && !in_service;
    assign ieo = alive && iei && !in_service && !pending;
    assign data_enable = alive && iack && ack_owned;
    always @(posedge clk or negedge alive) begin
        if (!alive) begin
            in_service<=0; ack_seen<=0; ack_owned<=0; fetch_seen<=0;
            ed_prefix<=0; vector_data<=0; ack_pulse<=0; reti_pulse<=0;
        end else begin
            ack_pulse<=0; reti_pulse<=0;
            if (!iack) begin ack_seen<=0; ack_owned<=0; end
            else if (!ack_seen) begin
                ack_seen<=1;
                if (iei && pending && !in_service) begin
                    ack_owned<=1; vector_data<=vector; in_service<=1; ack_pulse<=1;
                end
            end
            if (!fetch) fetch_seen<=0;
            else if (!fetch_seen) begin
                fetch_seen<=1;
                if (ed_prefix && host_data==8'h4d && in_service && iei) begin
                    in_service<=0; reti_pulse<=1;
                end
                ed_prefix <= host_data==8'hed;
            end
        end
    end
endmodule
