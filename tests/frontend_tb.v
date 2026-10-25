// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module frontend_tb;
    localparam integer TIMEOUT_CYCLES=4096;
    reg clk=0;
    always #10 clk=~clk; // proposed 50 MHz fixture clock, not a fitted device
    reg reset_n=0, power_good=1;
    reg [15:0] host_addr=0;
    reg [7:0] host_wdata=0;
    reg iorq_n=1,m1_n=1,rd_n=1,wr_n=1,response_ack=0;
    reg [7:0] response_data=0;
    wire request,request_write,wait_pull_low,host_data_enable,fault;
    wire [3:0] request_reg;
    wire [7:0] request_data,host_rdata;
    bus_frontend #(.TIMEOUT_CYCLES(TIMEOUT_CYCLES)) dut(.*);
    integer requests=0, completed=0, checks=0;
    reg old_request=0;
    always @(posedge clk) begin
        #1;
        if(request && !old_request) requests=requests+1;
        old_request=request;
        if(host_data_enable && (!reset_n || !power_good || iorq_n || !m1_n || rd_n || !wr_n))
            $fatal(1,"unsafe data drive");
    end
    task check(input bit condition, input [511:0] message);
        begin checks=checks+1; if(!condition) $fatal(1,"%0s",message); end
    endtask
    task clocks(input integer n);
        begin repeat(n) @(negedge clk); #1; end
    endtask
    task idle;
        begin iorq_n=1;rd_n=1;wr_n=1;m1_n=1; end
    endtask
    task reset;
        begin
            idle();response_ack=0;reset_n=0; #3;
            check(!wait_pull_low && !host_data_enable,"reset must release pins asynchronously");
            clocks(2);reset_n=1;clocks(5);check(!fault,"reset clears fault");
        end
    endtask
    task begin_cycle(input [15:0] address,input bit writing,input [7:0] value);
        begin
            host_addr=address;host_wdata=value;iorq_n=0;m1_n=1;
            rd_n=writing;wr_n=!writing; #1;
            check(wait_pull_low,"selected request must assert WAIT without a clock");
            check(!host_data_enable,"no read drive before response");
        end
    endtask
    task finish_cycle;
        begin
            idle();#1;check(!wait_pull_low && !host_data_enable,"cycle end gates outputs");
            clocks(2);check(!request,"request drops after host end");
            response_ack=0;clocks(5);
        end
    endtask
    task transaction(input [15:0] address,input bit writing,input [7:0] value,input integer delay_clocks);
        integer before_count, timeout;
        begin
            before_count=requests;
            begin_cycle(address,writing,value);
            clocks(2);
            check(request && request_write==writing,"request captured");
            check(request_reg=={(address[7:2]==6'b001000),address[2:0]},"register alias decode");
            check(request_data==value,"write data captured");
            clocks(delay_clocks);
            check(wait_pull_low && requests==before_count+1,"one request while waiting");
            // Bundled data precedes ack; response remains stable until request falls.
            response_data=value^8'hff;#3;response_ack=1;
            timeout=0;
            while(wait_pull_low && timeout<10) begin clocks(1);timeout=timeout+1; end
            check(!wait_pull_low && !fault,"response releases WAIT");
            check(host_data_enable==!writing,"drive only completed reads");
            if(!writing) check(host_rdata==(value^8'hff),"latched response data");
            clocks(3);check(requests==before_count+1,"held strobe must not repeat side effects");
            completed=completed+1;
            finish_cycle();
        end
    endtask
    time drive_start;
    always @(posedge host_data_enable) drive_start=$time;
    always @(negedge wait_pull_low) begin
        if(reset_n && power_good && !fault && !iorq_n && !rd_n && wr_n)
            check(host_data_enable && ($time-drive_start)>=20,
                  "read data enabled for a full clock before WAIT release");
    end
    integer a,phase,before_count;
    initial begin
        $dumpfile("build/frontend.vcd");$dumpvars(0,frontend_tb);
        reset();
        // Every low-byte address; every valid direction, plus upper-byte aliases.
        for(a=0;a<256;a=a+1) begin
            if(a<8) transaction(16'hac00|16'(a),0,8'(a),a%5);
            if(a<8 || (a>=32 && a<36)) transaction(16'h7300|16'(a),1,8'(a),a%7);
            if(a>=8) begin
                host_addr=16'(a);iorq_n=0;rd_n=0;wr_n=1;#1;
                check(!wait_pull_low && !host_data_enable,"unclaimed read");clocks(1);idle();clocks(3);
            end
            if(!(a<8 || (a>=32 && a<36))) begin
                host_addr=16'(a);iorq_n=0;rd_n=1;wr_n=0;#1;
                check(!wait_pull_low,"unclaimed write");clocks(1);idle();clocks(3);
            end
        end
        before_count=requests;
        host_addr=2;iorq_n=0;m1_n=0;rd_n=0;#1;
        check(!wait_pull_low && !host_data_enable,"IACK must bypass normal transport");
        clocks(4);check(requests==before_count,"no IACK mailbox request");idle();clocks(3);
        // Invalid strobes and memory cycles never claim the bus.
        iorq_n=0;rd_n=0;wr_n=0;clocks(3);check(!request && !wait_pull_low,"invalid strobes");
        idle();rd_n=0;clocks(3);check(!request && !host_data_enable,"memory read bypass");idle();
        // Unexpected host abort quarantines late replies until a shared reset.
        begin_cycle(2,0,0);clocks(2);idle();clocks(2);
        response_ack=1;clocks(3);check(!host_data_enable,"late reply cannot drive aborted cycle");
        check(fault,"aborted request requires reset");
        reset();transaction(2,0,8'h55,2);
        // Next host cycle may start before backend ACK has drained.
        begin_cycle(0,1,8'h33);clocks(2);response_ack=1;clocks(6);
        check(!wait_pull_low,"first write completed");
        idle();clocks(1);begin_cycle(2,0,0);clocks(4);
        check(wait_pull_low && !request,"new cycle waits for ACK to drain");
        response_ack=0;clocks(6);
        check(request && !request_write,"new read launched after ACK drain");
        response_data=8'hc3;#3;response_ack=1;clocks(6);
        check(!wait_pull_low && host_data_enable && host_rdata==8'hc3,"new read has fresh reply");
        completed=completed+2;finish_cycle();
        // Request arrival at each ns offset relative to the 20 ns local clock.
        for(phase=0;phase<20;phase=phase+1) begin
            clocks(1);#(phase);transaction(2,0,8'(phase),phase%9);
        end
        // All byte patterns through the captured write and latched read paths.
        for(a=0;a<256;a=a+1) begin
            transaction(16'hff00,1,8'(a),a%3);
            transaction(16'h0002,0,8'(a),a%3);
        end
        // Reset/power failure while waiting and while driving a completed read.
        begin_cycle(2,0,0);clocks(3);reset();
        begin_cycle(0,1,8'h81);clocks(3);reset();
        begin_cycle(2,0,0);clocks(2);response_data=8'h42;response_ack=1;clocks(6);
        check(host_data_enable,"fixture has active read before power loss");
        power_good=0;#1;check(!host_data_enable && !wait_pull_low,"power loss gates outputs");
        reset_n=0;idle();response_ack=0;clocks(2);power_good=1;reset();
        // Stuck-high ACK must never be interpreted as a fresh completion.
        response_ack=1;clocks(4);before_count=requests;begin_cycle(2,0,0);clocks(TIMEOUT_CYCLES+6);
        check(fault && !request && !host_data_enable && !wait_pull_low,"stale ACK bounded by watchdog");
        check(requests==before_count,"stale ACK did not launch request");reset();
        // Dead backend cannot hold WAIT forever; fault remains latched.
        begin_cycle(0,1,8'h5a);clocks(TIMEOUT_CYCLES+6);
        check(fault && !wait_pull_low && !host_data_enable && !request,"dead backend fails open");
        idle();clocks(4);host_addr=2;iorq_n=0;rd_n=0;#1;
        check(fault && !wait_pull_low && !host_data_enable,"fault requires reset");
        reset();transaction(2,0,8'ha5,0);
        $display("frontend PASS: %0d checks, %0d completed transactions",checks,completed);
        $finish;
    end
    initial begin #1000000; $fatal(1,"testbench timeout"); end
endmodule
