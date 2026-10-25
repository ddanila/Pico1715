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

test: build/controller-test
	./build/controller-test
	python3 -m unittest discover -s tests -v
