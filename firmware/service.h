/* SPDX-License-Identifier: MIT */
#ifndef P1715_SERVICE_H
#define P1715_SERVICE_H
#include <stdbool.h>
#include "../model/controller.h"
typedef struct {uint32_t state,dirty_blocks,storage_error,max_service_us;uint64_t requests;} p1715_diagnostics;
extern volatile p1715_diagnostics p1715_status;
int p1715_service_init(pico1715_controller *,bool writable);
void p1715_service_step(void);
void p1715_storage_step(void);
#endif
