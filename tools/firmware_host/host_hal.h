/* SPDX-License-Identifier: MIT. Deterministic host stand-ins for Pico peripherals. */
#ifndef P1715_HOST_HAL_H
#define P1715_HOST_HAL_H
#include <stdint.h>
#include <stdbool.h>
#define GPIO_IN 0
#define GPIO_OUT 1
typedef unsigned critical_section_t;
enum {P1715_COST_POLL, P1715_COST_FIELD, P1715_COST_READ, P1715_COST_WRITE,
      P1715_COST_COMMIT, P1715_COST_SNAPSHOT, P1715_COST_COUNT};
/* Optional deterministic scheduling hooks; null preserves zero-cost fixtures. */
extern void (*host_cost_hook)(unsigned kind);
extern void (*host_lock_hook)(critical_section_t *,bool enter);
static inline void host_cost(unsigned kind){if(host_cost_hook)host_cost_hook(kind);}
extern uint32_t host_inputs,host_outputs,host_directions;
extern uint64_t host_time_us;
extern bool host_worker;
static inline void gpio_init(unsigned p){(void)p;}
static inline void gpio_set_dir_masked(uint32_t m,uint32_t v){host_directions=(host_directions&~m)|(v&m);}
static inline void gpio_set_dir(unsigned p,bool v){gpio_set_dir_masked(1u<<p,v?1u<<p:0);}
static inline void gpio_pull_down(unsigned p){(void)p;}
static inline void gpio_pull_up(unsigned p){(void)p;}
static inline void gpio_put_masked(uint32_t m,uint32_t v){host_outputs=(host_outputs&~m)|(v&m);}
static inline void gpio_put(unsigned p,bool v){gpio_put_masked(1u<<p,v?1u<<p:0);}
static inline uint32_t gpio_get_all(void){return (host_inputs&~host_directions)|(host_outputs&host_directions);}
static inline bool gpio_get(unsigned p){return (gpio_get_all()>>p)&1;}
static inline uint64_t time_us_64(void){return host_time_us;}
static inline void critical_section_init(critical_section_t *s){*s=0;}
static inline void critical_section_enter_blocking(critical_section_t *s){if(host_lock_hook)host_lock_hook(s,true);}
static inline void critical_section_exit(critical_section_t *s){if(host_lock_hook)host_lock_hook(s,false);}
static inline void multicore_launch_core1(void (*f)(void)){(void)f;host_worker=true;}
static inline void sleep_us(unsigned n){(void)n;}
static inline void __dmb(void){}
void host_storage_init(const uint8_t *,bool absent);
const uint8_t *host_storage_image(void);
/* Fault fixture: preserve SD, discard volatile board state on a power cycle. */
void host_storage_power_cycle(void);
const uint8_t *host_storage_block(uint32_t lba);
extern unsigned host_torn_bytes;
/* Called before the block completes, including an injected failing operation.
 * Fixtures may advance the serving core/RTL here while the worker is suspended.
 * Never invoke the storage worker recursively from this hook. */
extern void (*host_io_hook)(bool writing,uint32_t lba);
extern uint64_t host_sd_reads,host_sd_writes,host_fail_read,host_fail_write;
#endif
