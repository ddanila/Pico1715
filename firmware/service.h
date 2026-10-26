/* SPDX-License-Identifier: MIT */
#ifndef P1715_SERVICE_H
#define P1715_SERVICE_H
#include <stdbool.h>
#include "../model/controller.h"
/* Bounded receive elasticity for index/mark interrupt overlap. The standalone
   controller reference still defaults to a single-byte latch. */
enum {P1715_RX_FIFO_DEPTH=2};
enum {P1715_RUNNING, P1715_DRAINING, P1715_SAFE, P1715_UNSAFE};
enum {P1715_BACKUP_ABSENT, P1715_BACKUP_CHARGING, P1715_BACKUP_READY,
      P1715_BACKUP_EXHAUSTED, P1715_BACKUP_FAILED};
enum {P1715_READ_ONLY, P1715_WRITE_EXPERIMENTAL, P1715_WRITE_PROTECTED};
enum {P1715_EJECT=1, P1715_POWER_FAIL=2};
enum {P1715_SHUTDOWN_OK, P1715_SHUTDOWN_STORAGE, P1715_SHUTDOWN_RESERVE,
      P1715_SHUTDOWN_DEADLINE};
typedef struct {
 uint32_t state,dirty_blocks,storage_error,max_service_us;
 uint64_t requests;
 uint32_t shutdown,shutdown_reason,backup,write_policy,dirty_limit,storage_busy;
 uint64_t reserve_us,shutdown_deadline;
} p1715_diagnostics;
/* Core 0 API. Status and the command mailbox are SWD-visible; no new host ports.
   A board-specific power supervisor may call these on the serving core. */
extern volatile uint32_t p1715_shutdown_command;
int p1715_shutdown_request(unsigned command);
int p1715_write_policy(unsigned policy,uint32_t worst_block_us,uint32_t margin_us);
int p1715_backup_update(unsigned state,uint64_t reserve_us);
extern volatile p1715_diagnostics p1715_status;
int p1715_service_init(pico1715_controller *,bool writable);
int p1715_service_init_protected(pico1715_controller *,uint32_t worst_block_us,uint32_t margin_us);
void p1715_service_step(void);
void p1715_storage_step(void);
#endif
