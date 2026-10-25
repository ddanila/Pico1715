DAC ?= ../dac-emulation
CC ?= cc
CFLAGS ?= -O2 -g
WARN = -std=c11 -Wall -Wextra -Werror

.PHONY: classic-probe test
classic-probe: build/classic-probe
build/classic-probe: tools/classic_probe.c model/controller.c model/controller.h $(DAC)/machines/robotron1715/pc1715.c
	@mkdir -p build
	$(CC) $(CFLAGS) $(WARN) -I$(DAC) tools/classic_probe.c model/controller.c $(DAC)/machines/robotron1715/pc1715.c $(DAC)/common/cpu/z80.c $(DAC)/common/trace/trace.c -o $@
build/controller-test: tests/controller_test.c model/controller.c model/controller.h
	@mkdir -p build
	$(CC) $(CFLAGS) $(WARN) tests/controller_test.c model/controller.c -o $@

build/timing-test: tests/timing_test.c model/controller.c model/controller.h
	@mkdir -p build
	$(CC) $(CFLAGS) $(WARN) tests/timing_test.c model/controller.c -o $@

test: build/controller-test build/timing-test
	./build/timing-test
	./build/controller-test
	python3 -m unittest discover -s tests -v

.PHONY: test-frontend lint-frontend synth-frontend
test-frontend: build/frontend-test
	vvp build/frontend-test
build/frontend-test: hardware/rtl/bus_frontend.v tests/frontend_tb.v
	@mkdir -p build
	iverilog -g2012 -Wall -s frontend_tb -o $@ $^
lint-frontend:
	verilator --lint-only -Wall --top-module bus_frontend hardware/rtl/bus_frontend.v
synth-frontend:
	@mkdir -p build
	yosys -Q -T -p 'read_verilog -sv hardware/rtl/bus_frontend.v; synth -top bus_frontend; check -assert; stat' > build/frontend-synthesis.log

.PHONY: test-irq
test-irq: build/irq-test
	vvp build/irq-test
build/irq-test: hardware/rtl/irq_frontend.v tests/irq_tb.v
	@mkdir -p build
	iverilog -g2012 -Wall -s irq_tb -o $@ $^

.PHONY: test-store
test-store: build/store-test
	./build/store-test
build/store-test: tests/store_test.c firmware/store.c firmware/store.h firmware/sd_crc.h
	@mkdir -p build
	$(CC) $(CFLAGS) $(WARN) tests/store_test.c firmware/store.c -o $@

.PHONY: test-pico-top
test-pico-top: build/pico-top-test
	vvp build/pico-top-test
build/pico-top-test: hardware/rtl/pico1715_top.v hardware/rtl/bus_frontend.v hardware/rtl/irq_frontend.v tests/pico_top_tb.v
	@mkdir -p build
	iverilog -g2012 -Wall -s pico_top_tb -o $@ $^
