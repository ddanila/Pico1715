// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Bench reference transport, not a complete FDC or a device-mapped netlist.
module bus_frontend #(
    parameter integer TIMEOUT_CYCLES = 4096
)(
    input wire clk, reset_n, power_good,
    input wire [15:0] host_addr,
    input wire [7:0] host_wdata,
    input wire iorq_n, m1_n, rd_n, wr_n,
    // Four-phase bundled-data mailbox. See ../frontend.md for CDC contract.
    output reg request,
    output reg request_write,
    output reg [3:0] request_reg,
    output reg [7:0] request_data,
    input wire response_ack,
    input wire [7:0] response_data,
    output wire wait_pull_low,
    output wire host_data_enable,
    output reg [7:0] host_rdata,
    output reg fault
);
    wire async_reset_n = reset_n & power_good;
    reg [1:0] reset_release;
    always @(posedge clk or negedge async_reset_n)
        if (!async_reset_n) reset_release <= 0;
        else reset_release <= {reset_release[0], 1'b1};
    wire alive = async_reset_n & reset_release[1];
    (* ASYNC_REG = "TRUE" *) reg ack_meta, ack_sync;
    always @(posedge clk or negedge async_reset_n) begin
        if (!async_reset_n) begin ack_meta <= 0; ack_sync <= 0; end
        else begin ack_meta <= response_ack; ack_sync <= ack_meta; end
    end
    // The original motherboard aliases the upper address byte.
    wire unused_upper_address = ^host_addr[15:8];
    wire normal_io = !iorq_n && m1_n;
    wire read_cycle = !rd_n && wr_n;
    wire write_cycle = !wr_n && rd_n;
    wire pio_selected = host_addr[7:3] == 5'b00000;
    wire latch_selected = host_addr[7:2] == 6'b001000;
    wire selected = normal_io && ((pio_selected && (read_cycle || write_cycle)) ||
                                   (latch_selected && write_cycle));
    localparam [2:0] IDLE=0, BUSY=1, SETTLE=2, COMPLETE=3, DRAIN=4;
    reg [2:0] state;
    localparam integer COUNTER_BITS = $clog2(TIMEOUT_CYCLES + 1);
    localparam [COUNTER_BITS-1:0] LAST_COUNT = COUNTER_BITS'(TIMEOUT_CYCLES - 1);
    reg [COUNTER_BITS-1:0] age;
    // Combinational assertion: no synchronizer or software in the assertion path.
    // Physical implementation requires a hazard/setup/hold review and an open drain.
    assign wait_pull_low = alive && !fault && selected && state != COMPLETE;
    assign host_data_enable = alive && !fault && selected && read_cycle &&
                              !request_write && (state == SETTLE || state == COMPLETE);
    always @(posedge clk or negedge async_reset_n) begin
        if (!async_reset_n) begin
            state <= IDLE; age <= 0; request <= 0; fault <= 0;
            request_write <= 0; request_reg <= 0; request_data <= 0; host_rdata <= 0;
        end else if (!alive) begin
            state <= IDLE; age <= 0; request <= 0;
        end else if (fault) begin
            request <= 0;
        end else if (selected && state != COMPLETE && age == LAST_COUNT) begin
            // Fail open and latch fault until reset. No invented successful reply.
            fault <= 1; request <= 0; state <= DRAIN;
        end else begin
            if (selected && state != COMPLETE) age <= age + 1'b1;
            else age <= 0;
            case (state)
            IDLE: if (selected && !ack_sync) begin
                request_write <= write_cycle;
                request_reg <= {latch_selected, host_addr[2:0]};
                request_data <= host_wdata;
                request <= 1;
                state <= BUSY;
            end
            BUSY: if (!selected) begin
                      // A late CDC reply cannot be safely matched after an abort.
                      fault <= 1; request <= 0; state <= DRAIN;
                  end
                  else if (ack_sync) begin
                      host_rdata <= response_data;
                      state <= SETTLE;
                  end
            // One full local clock for data/driver settling before releasing WAIT.
            SETTLE: if (!selected) begin fault <= 1; request <= 0; state <= DRAIN; end
                    else state <= COMPLETE;
            COMPLETE: if (!selected) begin request <= 0; state <= DRAIN; end
            DRAIN: if (!ack_sync) state <= IDLE;
            default: begin fault <= 1; request <= 0; state <= DRAIN; end
            endcase
        end
    end
endmodule
