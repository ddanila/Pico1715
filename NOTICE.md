# Licensing and provenance

Original Pico1715 work is MIT licensed, copyright 2026 Danila Sukharev.
The license covers original source, documentation and hardware design files in
this repository. It does not relicense historical firmware, disk images,
reference documents, third-party components or externally linked software.

No GUN drawings/layouts or PicoMEM implementation code are included.
GUN and PicoMEM are architectural references. GUN's project page and design
notes did not state a reuse license when inspected on 2026-10-25. PicoMEM's
repository carries GPL v2 software and explicitly describes its hardware as not
open. Do not import their implementation into this MIT project without reviewing
and recording applicable permissions and license consequences.

The optional host capture links a separately supplied dac-emulation checkout.
DAC's original code is MIT; its NOTICE also records BSD-3-Clause and zlib
components/references. Its licenses continue to apply to the linked executable.
The build places copies of the external LICENSE, NOTICE, chips/LICENSE and
Robotron REFERENCE_LICENSE beside the local executable. No external code or
binary is redistributed here. Preserve those notices if distributing that build.

ROMs, OS images and manual PDFs remain external inputs. Their hashes and source
locations document identity, not a redistribution grant. The captured trace may
include guest data and is not published automatically.

The prototype firmware links the separately installed Raspberry Pi Pico SDK
2.2.0 (BSD-3-Clause and its dependency notices). No SDK sources are vendored.
The PSRAM driver is original code using documented AP Memory commands and
RP2350 SDK register definitions. Olimex Rev B1 pin facts were extracted from
its published netlist; no board schematic or layout was copied. The linked
RP2040 spi-flasher programmer is an optional external GPL-2.0 tool, not part of
this firmware or the MIT source distribution.
