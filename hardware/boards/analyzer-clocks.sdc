# Independent oscillator and divided acquisition clock. No host clock/reset gating.
create_clock -period 10 [get_ports clk100]
create_clock -period 20 [get_nets clk50]
