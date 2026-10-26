cmake_minimum_required(VERSION 3.13)
set(PICO_BOARD pimoroni_pico_plus2_rp2350 CACHE STRING "Prototype board")
if(NOT PICO_SDK_PATH)
  set(PICO_SDK_PATH "$ENV{PICO_SDK_PATH}" CACHE PATH "Pico SDK checkout")
endif()
include(${PICO_SDK_PATH}/external/pico_sdk_import.cmake)
project(pico1715 C CXX ASM)
pico_sdk_init()
option(P1715_WRITEBACK "EXPERIMENTAL SD writeback; unqualified on hardware" OFF)
add_executable(pico1715 main.c service.c store.c sd_spi.c psram.c ../model/controller.c)
set_target_properties(pico1715 PROPERTIES LINKER_LANGUAGE C)
target_compile_definitions(pico1715 PRIVATE P1715_WRITEBACK=$<BOOL:${P1715_WRITEBACK}>)
target_compile_options(pico1715 PRIVATE -Wall -Wextra -Werror)
target_link_libraries(pico1715 pico_stdlib pico_multicore hardware_spi hardware_sync hardware_gpio)
pico_enable_stdio_usb(pico1715 0)
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
