/* SPDX-License-Identifier: MIT */
#ifndef P1715_ANALYZER_BRIDGE_H
#define P1715_ANALYZER_BRIDGE_H
#include "common/trace/trace.h"
#ifdef __cplusplus
extern "C" {
#endif
void analyzer_init(void *machine, const char *output_dir);
void analyzer_event(const dac_trace_event *event);
void analyzer_observe(void);
void analyzer_finish(void);
#ifdef __cplusplus
}
#endif
#endif
