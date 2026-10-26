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

.PHONY: test-bench-fixture lint-bench-fixture
test-bench-fixture: build/bench-fixture-test
	vvp build/bench-fixture-test
build/bench-fixture-test: hardware/rtl/bench_fixture.v hardware/rtl/pico1715_top.v hardware/rtl/bus_frontend.v hardware/rtl/irq_frontend.v tests/bench_fixture_tb.v
	@mkdir -p build
	iverilog -g2012 -Wall -s bench_fixture_tb -o $@ $^
lint-bench-fixture:
	verilator --lint-only -Wall --top-module bench_fixture hardware/rtl/bench_fixture.v hardware/rtl/pico1715_top.v hardware/rtl/bus_frontend.v hardware/rtl/irq_frontend.v

.PHONY: test-interface
test-interface:
	@mkdir -p build
	kicad-cli sch erc hardware/interface/bench-interface.kicad_sch --exit-code-violations --output build/interface-erc.rpt
	kicad-cli sch export netlist hardware/interface/bench-interface.kicad_sch --format kicadxml --output build/interface.net.xml
	python3 tools/check_interface.py --netlist build/interface.net.xml

.PHONY: test-firmware-service
test-firmware-service: build/firmware-service-test
	./build/firmware-service-test
build/firmware-service-test: tests/firmware_service_test.c firmware/service.c firmware/service.h firmware/platform.h firmware/store.c firmware/store.h model/controller.c model/controller.h tools/firmware_host/host_hal.c tools/firmware_host/host_hal.h
	@mkdir -p build
	$(CC) $(CFLAGS) $(WARN) -DP1715_HOST_SIM -Itools/firmware_host tests/firmware_service_test.c firmware/service.c firmware/store.c model/controller.c tools/firmware_host/host_hal.c -o $@

.PHONY: test-analyzer lint-analyzer synth-analyzer
test-analyzer: build/analyzer-test
	vvp build/analyzer-test
	python3 tests/analyzer_random.py
	python3 tools/analyzer_trace.py pack build/analyzer-samples.txt build/analyzer.p1715 --clock-hz 50000000 --pre 3 --post 2 --trigger-index 3 --mask 0xff --value 0x55
	python3 tools/analyzer_trace.py export build/analyzer.p1715 --csv build/analyzer.csv --vcd build/analyzer.vcd
build/analyzer-test: hardware/rtl/analyzer_top.v tests/analyzer_tb.v
	@mkdir -p build
	iverilog -g2012 -Wall -s analyzer_tb -o $@ $^
lint-analyzer:
	verilator --lint-only -Wall --top-module analyzer_top hardware/rtl/analyzer_top.v
synth-analyzer:
	@mkdir -p build
	yosys -Q -T -p 'read_verilog -sv hardware/rtl/analyzer_top.v; synth_ice40 -top analyzer_top; check -assert; stat' > build/analyzer-synthesis.log
