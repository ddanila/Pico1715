/* SPDX-License-Identifier: MIT */
#ifndef P1715_PLATFORM_H
#define P1715_PLATFORM_H
#ifdef P1715_HOST_SIM
#include "host_hal.h"
#define P1715_WORK(kind) host_cost(kind)
#else
#define P1715_WORK(kind) ((void)0)
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "pico/critical_section.h"
#include "hardware/sync.h"
#endif
#endif
