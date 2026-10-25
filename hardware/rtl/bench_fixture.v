// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Standalone FPGA/Pico fixture. NEVER load with a host or adapter connected.
module bench_fixture #(
 parameter integer BOOT_LIMIT=500000000,
 parameter integer IRQ_LIMIT=7500000,
 parameter integer UART_DIV=217,
 parameter integer GAP=50
)(
 input wire clk100, fixture_reset_n, backend_ready,
 inout wire [7:0] pico_data,
 output wire [3:0] pico_reg,
 output wire pico_write,pico_request,
 input wire pico_ack,pico_index,pico_mark,
 output wire ack_toggle,reti_toggle,ack_index,
 output reg test_reset_n=0,
 output wire passed,failed,
 output wire uart_tx
);
 reg [1:0] divider=0;
 always @(posedge clk100) divider<=divider+1'b1;
 wire fixture_clk=divider[1];
 reg [7:0] address=0,wdata=0;
 reg iorq_n=1,m1_n=1,mreq_n=1,rd_n=1,wr_n=1;
 wire [7:0] rdata;
 wire oe,wait_low,irq_low,ieo,fault;
 pico1715_top dut(.clk100(clk100),.host_reset_n(test_reset_n),.power_good(1'b1),
 .backend_ready(backend_ready),.host_addr(address),.host_din(wdata),
 .iorq_n(iorq_n),.m1_n(m1_n),.mreq_n(mreq_n),.rd_n(rd_n),.wr_n(wr_n),.iei(1'b1),
 .host_dout(rdata),.host_oe(oe),.wait_pull_low(wait_low),.int_pull_low(irq_low),
 .ieo(ieo),.fault(fault),.pico_data(pico_data),.pico_reg(pico_reg),
 .pico_write(pico_write),.pico_request(pico_request),.pico_ack(pico_ack),
 .pico_index(pico_index),.pico_mark(pico_mark),.ack_toggle(ack_toggle),
 .reti_toggle(reti_toggle),.ack_index(ack_index));
 localparam [3:0] RESET=0,BOOT=1,SETUP=2,ACTIVE=3,RELEASE=4,
 IRQWAIT=5,IACK=6,FETCH_ED=7,FETCH_GAP=8,FETCH_4D=9,RETIWAIT=10,DONE=11;
 reg [3:0] state=RESET;
 reg [31:0] timer=0,max_wait=0;
 reg [15:0] completed=0;
 reg [7:0] failure=0;
 reg [9:0] operation=0;
 wire read_op=!operation[0] ? 1'b0 : operation<512;
 // Safe control patterns: motor/mark disarmed, write gate off, no step edge.
 wire [7:0] pattern=8'ha5 | {1'b0,operation[2],1'b0,operation[3],4'b0};
 assign passed=state==DONE && failure==0;
 assign failed=state==DONE && failure!=0;
 wire unused_ieo=ieo;
 always @(posedge fixture_clk) begin
  if(!fixture_reset_n)begin
   state<=RESET;timer<=0;failure<=0;completed<=0;operation<=0;max_wait<=0;
   test_reset_n<=0;iorq_n<=1;m1_n<=1;mreq_n<=1;rd_n<=1;wr_n<=1;address<=0;wdata<=0;
  end else begin
   timer<=timer+1;
   if(state!=RESET && state!=BOOT && state!=DONE && (!backend_ready || fault))begin
    failure<=8'h01;state<=DONE;
   end else case(state)
   RESET:if(timer>=GAP)begin test_reset_n<=1;timer<=0;state<=BOOT;end
   BOOT:if(backend_ready)begin timer<=0;state<=SETUP;end
        else if(timer>=BOOT_LIMIT)begin failure<=8'h02;state<=DONE;end
   SETUP:if(timer>=GAP)begin
    address<=operation<512?8'h04:operation==512?8'h05:operation==513?8'h20:8'h05;
    wdata<=operation<512?pattern:operation==512?8'h10:operation==513?8'hef:8'h83;
    timer<=0;state<=ACTIVE;iorq_n<=0;rd_n<=!read_op;wr_n<=read_op;
   end
   ACTIVE:if(timer>=GAP && !wait_low)begin
    if(read_op && (!oe || rdata!=pattern))begin failure<=8'h03;state<=DONE;end
    else if(!read_op && oe)begin failure<=8'h04;state<=DONE;end
    else begin completed<=completed+1;state<=RELEASE;timer<=0;
     if(timer>max_wait)max_wait<=timer;end
    iorq_n<=1;rd_n<=1;wr_n<=1;
   end else if(timer>=5000)begin failure<=8'h05;state<=DONE;end
   RELEASE:if(timer>=GAP && !pico_request && !pico_ack)begin
    timer<=0;
    if(operation==514)state<=IRQWAIT;
    else begin operation<=operation+1;state<=SETUP;end
   end else if(timer>=5000)begin failure<=8'h06;state<=DONE;end
   IRQWAIT:if(irq_low)begin m1_n<=0;iorq_n<=0;timer<=0;state<=IACK;end
           else if(timer>=IRQ_LIMIT)begin failure<=8'h07;state<=DONE;end
   IACK:if(timer>=GAP)begin
    if(!oe || rdata!=8'h10 || !ack_toggle || !ack_index)begin failure<=8'h08;state<=DONE;end
    else begin state<=FETCH_ED;timer<=0;end
    m1_n<=1;iorq_n<=1;
   end
   FETCH_ED:if(timer==GAP)begin m1_n<=0;mreq_n<=0;rd_n<=0;wdata<=8'hed;end
            else if(timer>=2*GAP)begin m1_n<=1;mreq_n<=1;rd_n<=1;timer<=0;state<=FETCH_GAP;end
   FETCH_GAP:if(timer>=GAP)begin m1_n<=0;mreq_n<=0;rd_n<=0;wdata<=8'h4d;timer<=0;state<=FETCH_4D;end
   FETCH_4D:if(timer>=GAP)begin m1_n<=1;mreq_n<=1;rd_n<=1;timer<=0;state<=RETIWAIT;end
   RETIWAIT:if(timer>=GAP)begin if(!reti_toggle)failure<=8'h09;state<=DONE;end
   DONE:begin iorq_n<=1;m1_n<=1;mreq_n<=1;rd_n<=1;wr_n<=1;end
   default:begin failure<=8'hff;state<=DONE;end
   endcase
  end
 end
 // Repeating 9-byte binary frame: A5, result, completed LE16, max ticks LE32, XOR.
 wire [63:0] payload={max_wait,completed,failure,8'ha5};
 reg [3:0] byte_index=0;
 reg [7:0] checksum=0;
 reg [9:0] shift=10'h3ff;
 reg [3:0] bits_left=0;
 reg [31:0] baud_count=0;
 wire [7:0] next_byte=byte_index==8?checksum:payload[byte_index*8+:8];
 assign uart_tx=shift[0];
 always @(posedge fixture_clk)begin
  if(!fixture_reset_n || state!=DONE)begin
   byte_index<=0;checksum<=0;shift<=10'h3ff;bits_left<=0;baud_count<=0;
  end else if(baud_count!=0)baud_count<=baud_count-1;
  else if(bits_left!=0)begin
   shift<={1'b1,shift[9:1]};bits_left<=bits_left-1;baud_count<=UART_DIV-1;
  end else begin
   shift<={1'b1,next_byte,1'b0};bits_left<=10;baud_count<=UART_DIV-1;
   if(byte_index==8)begin byte_index<=0;checksum<=0;end
   else begin byte_index<=byte_index+1;checksum<=checksum^next_byte;end
  end
 end
endmodule
