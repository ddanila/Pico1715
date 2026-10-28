// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Experimental third personality. All acquisition and controller logic share
// the same 50 MHz domain. No new Pico link pins are allocated.
module carrier_combined(
 input wire clk100,power_good,backend_ready,
 input wire [36:0] bus_sample,
 output wire [7:0] host_dout,
 output wire host_oe,wait_pull_low,int_pull_low,ieo,fault,
 inout wire [7:0] pico_data,
 output wire [3:0] pico_reg,
 output wire pico_write,pico_request,
 input wire pico_ack,pico_index,pico_mark,
 output wire ack_toggle,reti_toggle,ack_index,
 output wire personality_controller
);
 reg clk50=0;
 always @(posedge clk100)clk50<=!clk50;
 wire link_reset_n=power_good && backend_ready && bus_sample[31];
 wire link_fault,controller_fault;
 wire ctrl_request,ctrl_write,ctrl_ack;
 wire [3:0] ctrl_reg;
 wire [7:0] ctrl_response,link_data;
 wire [7:0] ctrl_data;
 assign pico_data=power_good && pico_request && pico_write?link_data:8'bz;
 assign fault=link_fault || controller_fault;
 assign personality_controller=1'b1;
 pico1715_core controller(
 .clk50(clk50),.host_reset_n(bus_sample[31]),.power_good(power_good && !link_fault),.backend_ready(backend_ready),
 .host_addr(bus_sample[7:0]),.host_din(bus_sample[23:16]),
 .iorq_n(bus_sample[25]),.m1_n(bus_sample[28]),.mreq_n(bus_sample[24]),
 .rd_n(bus_sample[26]),.wr_n(bus_sample[27]),.iei(bus_sample[36]),
 .host_dout(host_dout),.host_oe(host_oe),.wait_pull_low(wait_pull_low),
 .int_pull_low(int_pull_low),.ieo(ieo),.fault(controller_fault),
 .request_data(ctrl_data),.response_data(ctrl_response),.pico_reg(ctrl_reg),.pico_write(ctrl_write),.pico_request(ctrl_request),
 .pico_ack(ctrl_ack),.pico_index(pico_index),.pico_mark(pico_mark),
 .ack_toggle(ack_toggle),.reti_toggle(reti_toggle),.ack_index(ack_index));
 wire trace_request,trace_ack,command_valid,negotiated,unsupported;
 wire [7:0] trace_data,command;
 wire [4:0] trace_index;
 combined_mailbox link_arbiter(.clk(clk50),.reset_n(link_reset_n),
 .controller_request(ctrl_request),.controller_write(ctrl_write),.controller_reg(ctrl_reg),.controller_data(ctrl_data),
 .controller_ack(ctrl_ack),.controller_response(ctrl_response),
 .trace_request(trace_request),.trace_data(trace_data),.trace_index(trace_index),.trace_ack(trace_ack),
 .command_valid(command_valid),.command(command),.negotiated(negotiated),.unsupported(unsupported),.fault(link_fault),
 .request(pico_request),.write(pico_write),.address(pico_reg),.data(link_data),.ack(pico_ack),.response(pico_data));
 reg capture_enable,capture_clear;
 always @(posedge clk50 or negedge power_good)begin
  if(!power_good)begin capture_enable<=0;capture_clear<=0;end
  else begin
   capture_clear<=0;
   if(command_valid)case(command)
    1:capture_enable<=1;
    2:capture_enable<=0;
    3:begin capture_enable<=0;capture_clear<=1;end
    default:begin end
   endcase
  end
 end
 (* keep=1 *) reg [36:0] sample_meta=37'h1fffffffff,sample_sync=37'h1fffffffff;
 always @(posedge clk50)begin sample_meta<=bus_sample;sample_sync<=sample_meta;end
 wire [31:0] dropped,filtered,sent;
 wire unused_oe,unused_wait,unused_int,unused_busrq,unused_nmi,unused_memdi,unused_reset,unused_ieo;
 analyzer_transport_top capture(.clk(clk50),.card_reset_n(power_good),
 .capture_clear(capture_clear),.capture_enable(capture_enable),.link_sync_n(link_reset_n && negotiated && !link_fault),
 .pico_ack(trace_ack),.sample({2'b0,sample_sync[36],sample_sync}),.iei(sample_sync[36]),
 .pico_data(trace_data),.pico_index(trace_index),.pico_request(trace_request),
 .host_oe(unused_oe),.wait_pull_low(unused_wait),.int_pull_low(unused_int),.busrq_pull_low(unused_busrq),
 .nmi_pull_low(unused_nmi),.memdi_pull_low(unused_memdi),.reset_pull_low(unused_reset),.ieo(unused_ieo),
 .dropped(dropped),.filtered(filtered),.sent_records(sent));
 wire unused=^{unsupported,dropped,filtered,sent,unused_oe,unused_wait,unused_int,unused_busrq,unused_nmi,unused_memdi,unused_reset,unused_ieo};
endmodule
