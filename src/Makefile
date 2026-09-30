# SPDX-FileCopyrightText: 2026 Adafruit Industries
# SPDX-License-Identifier: MIT
# klatt_kernel, one viper .mpy per architecture, built by mpy-cross -march:
#   make MPY_CROSS=path/to/circuitpython/mpy-cross/build/mpy-cross
# Writes ../adafruit_moonshine_klatt/klatt_kernel.<arch>.mpy for each arch in ARCHES. Use an
# mpy-cross from the CircuitPython tree whose firmware will load it (the .mpy version must
# match). Boards find the file by the name in microcontroller.cpu.architecture (#11453).
# klatt_kernel.c is the gcc build of the same kernel, kept for reference (bit exact).
MPY_CROSS ?= mpy-cross
SRC ?= klatt_viper.py
OUT = ../adafruit_moonshine_klatt
ARCHES = armv6m armv7emsp xtensawin rv32imc

all: $(foreach a,$(ARCHES),$(OUT)/klatt_kernel.$(a).mpy)

$(OUT)/klatt_kernel.%.mpy: $(SRC)
	$(MPY_CROSS) -march=$* -o $@ $<

.PHONY: all
