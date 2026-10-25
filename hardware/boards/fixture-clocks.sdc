# 100 MHz board clock, divide-by-four diagnostic sequencer, divide-by-two frontend.
create_clock -period 10 [get_ports clk100]
create_clock -period 40 [get_nets {divider[1]}]
create_clock -period 20 [get_nets dut.clk50]
