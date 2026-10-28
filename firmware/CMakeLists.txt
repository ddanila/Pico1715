cmake_minimum_required(VERSION 3.13)
set(PICO_BOARD pimoroni_pico_plus2_rp2350 CACHE STRING "Prototype board")
if(NOT PICO_SDK_PATH)
  set(PICO_SDK_PATH "$ENV{PICO_SDK_PATH}" CACHE PATH "Pico SDK checkout")
endif()
include(${PICO_SDK_PATH}/external/pico_sdk_import.cmake)
project(pico1715 C CXX ASM)
pico_sdk_init()
option(P1715_WRITEBACK "EXPERIMENTAL SD writeback; unqualified on hardware" OFF)
add_executable(pico1715 main.c service.c controller_usb.c controller_usb_device.c store.c sd_spi.c psram.c ../model/controller.c)
set_target_properties(pico1715 PROPERTIES LINKER_LANGUAGE C)
target_compile_definitions(pico1715 PRIVATE P1715_WRITEBACK=$<BOOL:${P1715_WRITEBACK}>)
target_compile_options(pico1715 PRIVATE -Wall -Wextra -Werror)
target_link_libraries(pico1715 pico_stdlib pico_multicore hardware_spi hardware_sync hardware_gpio)
target_compile_definitions(pico1715 PRIVATE
 PICO_STDIO_USB_ENABLE_RESET_VIA_BAUD_RATE=0
 PICO_STDIO_USB_ENABLE_RESET_VIA_VENDOR_INTERFACE=0
 PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_MS_OS_20_DESCRIPTOR=0
 USBD_PRODUCT="Pico1715 Controller")
pico_enable_stdio_usb(pico1715 1)
pico_enable_stdio_uart(pico1715 0)
pico_add_extra_outputs(pico1715)

add_executable(pico1715_analyzer analyzer_main.c analyzer.c analyzer_usb.c psram.c)
set_target_properties(pico1715_analyzer PROPERTIES LINKER_LANGUAGE C)
target_compile_options(pico1715_analyzer PRIVATE -Wall -Wextra -Werror)
target_link_libraries(pico1715_analyzer pico_stdlib hardware_sync hardware_gpio)
# Reuse SDK CDC descriptors/configuration; main owns TinyUSB task execution.
target_compile_definitions(pico1715_analyzer PRIVATE
 PICO_STDIO_USB_ENABLE_RESET_VIA_BAUD_RATE=0
 PICO_STDIO_USB_ENABLE_RESET_VIA_VENDOR_INTERFACE=0
 PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_MS_OS_20_DESCRIPTOR=0
 USBD_PRODUCT="Pico1715 Analyzer")
pico_enable_stdio_usb(pico1715_analyzer 1)
pico_enable_stdio_uart(pico1715_analyzer 0)
pico_add_extra_outputs(pico1715_analyzer)

option(P1715_RESET_ACCESSORY "EXPERIMENTAL GP22 reset accessory; requires qualified isolated interface" OFF)
target_compile_definitions(pico1715_analyzer PRIVATE P1715_RESET_ACCESSORY=$<BOOL:${P1715_RESET_ACCESSORY}>)
if(P1715_RESET_ACCESSORY)
 pico_generate_pio_header(pico1715_analyzer ${CMAKE_CURRENT_LIST_DIR}/reset_pulse.pio)
 target_link_libraries(pico1715_analyzer hardware_pio hardware_clocks)
endif()

option(P1715_PROTECTED_WRITEBACK "Reserve-gated writeback; requires qualified supervisor and timing budget" OFF)
set(P1715_WORST_BLOCK_US "0" CACHE STRING "Measured worst time for one full 512-byte journal transaction")
set(P1715_RESERVE_MARGIN_US "0" CACHE STRING "Measured reserve for detection, isolation and scheduling")
foreach(budget P1715_WORST_BLOCK_US P1715_RESERVE_MARGIN_US)
 if(NOT "${${budget}}" MATCHES "^[0-9]+$" OR ${budget} GREATER 4294967295)
  message(FATAL_ERROR "${budget} must be an unsigned 32-bit microsecond count")
 endif()
endforeach()
if(P1715_PROTECTED_WRITEBACK AND P1715_WRITEBACK)
 message(FATAL_ERROR "Choose protected or experimental writeback, not both")
endif()
if(P1715_PROTECTED_WRITEBACK AND NOT P1715_WORST_BLOCK_US MATCHES "^[1-9][0-9]*$")
 message(FATAL_ERROR "Protected writeback requires a positive measured P1715_WORST_BLOCK_US")
endif()
target_compile_definitions(pico1715 PRIVATE
 P1715_PROTECTED_WRITEBACK=$<BOOL:${P1715_PROTECTED_WRITEBACK}>
 P1715_WORST_BLOCK_US=${P1715_WORST_BLOCK_US}
 P1715_RESERVE_MARGIN_US=${P1715_RESERVE_MARGIN_US})

option(P1715_CARRIER "Combined carrier A; PIM724 button safe-eject and LED safe status" OFF)
if(P1715_CARRIER AND NOT PICO_BOARD STREQUAL "pimoroni_pico_plus2_rp2350")
 message(FATAL_ERROR "Carrier panel requires PIM724 GPIO45/25; choose the reference board")
endif()
if(P1715_CARRIER AND P1715_RESET_ACCESSORY)
 message(FATAL_ERROR "Carrier GP22 is SD CS; the optional reset accessory conflicts")
endif()
target_compile_definitions(pico1715 PRIVATE P1715_CARRIER=$<BOOL:${P1715_CARRIER}>)
if(P1715_CARRIER)
 target_sources(pico1715 PRIVATE carrier_panel.c)
endif()

option(P1715_COMBINED "Experimental combined controller/capture mailbox" OFF)
if(P1715_COMBINED AND NOT P1715_CARRIER)
 message(FATAL_ERROR "Combined transport requires the carrier profile")
endif()
target_compile_definitions(pico1715 PRIVATE P1715_COMBINED=$<BOOL:${P1715_COMBINED}>)
if(P1715_COMBINED)
 target_sources(pico1715 PRIVATE combined.c analyzer.c)
endif()

option(P1715_RESERVE_SUPERVISOR "Experimental PIM724 SP/CE reserve sensing" OFF)
set(P1715_QUALIFIED_RESERVE_US "0" CACHE STRING "Measured assembly reserve; zero never permits READY")
if(NOT "${P1715_QUALIFIED_RESERVE_US}" MATCHES "^[0-9]+$" OR P1715_QUALIFIED_RESERVE_US GREATER 4294967295)
 message(FATAL_ERROR "P1715_QUALIFIED_RESERVE_US must be an unsigned 32-bit microsecond count")
endif()
if(P1715_RESERVE_SUPERVISOR AND NOT P1715_CARRIER)
 message(FATAL_ERROR "SP/CE supervisor requires the reference PIM724 carrier profile")
endif()
target_compile_definitions(pico1715 PRIVATE
 P1715_RESERVE_SUPERVISOR=$<BOOL:${P1715_RESERVE_SUPERVISOR}>
 P1715_QUALIFIED_RESERVE_US=${P1715_QUALIFIED_RESERVE_US})
if(P1715_RESERVE_SUPERVISOR)
 target_sources(pico1715 PRIVATE reserve.c)
endif()
