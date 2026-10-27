// SPDX-License-Identifier: MIT
// One cooperative scheduler, with native and browser context implementations.
#ifndef P1715_CONTEXT_H
#define P1715_CONTEXT_H
#ifdef __EMSCRIPTEN__
#include <emscripten/fiber.h>
#include <cstdlib>
struct p1715_context {
    emscripten_fiber_t fiber;
    alignas(16) unsigned char async_stack[128*1024];
    void (*entry)();
};
static void context_entry(void *p){((p1715_context*)p)->entry();std::abort();}
static void context_current(p1715_context *c){
    emscripten_fiber_init_from_current_context(&c->fiber,c->async_stack,sizeof(c->async_stack));
}
static void context_init(p1715_context *c,void *stack,size_t size,void (*entry)()){
    c->entry=entry;emscripten_fiber_init(&c->fiber,context_entry,c,stack,size,c->async_stack,sizeof(c->async_stack));
}
static void context_swap(p1715_context *a,p1715_context *b){emscripten_fiber_swap(&a->fiber,&b->fiber);}
#else
#include <ucontext.h>
#include <cstdlib>
typedef ucontext_t p1715_context;
static void context_current(p1715_context *){}
static void context_init(p1715_context *c,void *stack,size_t size,void (*entry)()){
    if(getcontext(c))std::abort();
    c->uc_stack.ss_sp=stack;c->uc_stack.ss_size=size;c->uc_link=nullptr;makecontext(c,entry,0);
}
static void context_swap(p1715_context *a,p1715_context *b){if(swapcontext(a,b))std::abort();}
#endif
#endif
