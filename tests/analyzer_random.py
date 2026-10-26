#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Seeded, independent list-model comparison against the synthesized-source RTL."""
from pathlib import Path
import random
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    rng = random.Random(1715)
    statements = []
    comparisons = 0
    for case in range(160):
        pre = rng.randrange(16)
        post = rng.randrange(16-pre)
        delay = rng.randrange(80)
        stop_at = rng.randrange(delay+post+2) if case % 3 == 0 else None
        history = []
        records = []
        trigger = None
        stopped = False
        statements.append(f'pre_samples=5\'d{pre};post_samples=5\'d{post};arm=1;step;arm=0;')
        for tick in range(delay+post+1):
            if stop_at == tick:
                statements.append('stop=1;step;stop=0;')
                stopped = True
                break
            sample = (rng.getrandbits(38) & ~1) | int(tick == delay)
            statements.append(f'sample=40\'h{sample:010x};step;')
            if trigger is not None:
                records.append((tick, sample))
            elif tick == delay:
                records = history + [(tick, sample)]
                trigger = len(history)
            elif pre:
                history = (history + [(tick, sample)])[-pre:]
        if trigger is None:
            records = history
        # A stop beyond completion was never applied.
        statements.append(f'if(!done || active || count!={len(records)} || triggered!={int(trigger is not None)} || stopped!={int(stopped)}) $fatal(1,"case {case} metadata");')
        if trigger is not None:
            statements.append(f'if(trigger_index!={trigger}) $fatal(1,"case {case} trigger");')
        for index, (tick, sample) in enumerate(records):
            statements.append(f'read_enable=1;read_index=4\'d{index};step;if(!read_valid || read_record!==72\'h{tick:08x}{sample:010x}) $fatal(1,"case {case} record {index}");read_enable=0;')
            comparisons += 1
    bench = '''`timescale 1ns/1ps
module random_tb;
reg clk=0;always #10 clk=~clk;
reg card_reset_n=0,arm=0,stop=0,read_enable=0;
reg [39:0] sample=0;
reg [4:0] pre_samples=0,post_samples=0;
reg [3:0] read_index=0;
wire active,done,triggered,stopped,read_valid;
wire [4:0] count,trigger_index;
wire [71:0] read_record;
wire host_oe,wait_pull_low,int_pull_low,busrq_pull_low,nmi_pull_low,memdi_pull_low,reset_pull_low,ieo;
analyzer_top #(.PTR_BITS(4)) dut(.clk(clk),.card_reset_n(card_reset_n),.arm(arm),.stop(stop),
.sample(sample),.iei(sample[0]),.trigger_mask(40'd1),.trigger_value(40'd1),
.pre_samples(pre_samples),.post_samples(post_samples),.read_enable(read_enable),
.read_index(read_index),.read_valid(read_valid),.read_record(read_record),.active(active),
.done(done),.triggered(triggered),.stopped(stopped),.count(count),.trigger_index(trigger_index),
.host_oe(host_oe),.wait_pull_low(wait_pull_low),.int_pull_low(int_pull_low),
.busrq_pull_low(busrq_pull_low),.nmi_pull_low(nmi_pull_low),.memdi_pull_low(memdi_pull_low),
.reset_pull_low(reset_pull_low),.ieo(ieo));
task step;begin @(posedge clk);#1;
if({host_oe,wait_pull_low,int_pull_low,busrq_pull_low,nmi_pull_low,memdi_pull_low,reset_pull_low}!==0 || ieo!==sample[0]) $fatal(1,"passivity");
@(negedge clk);end endtask
initial begin step;card_reset_n=1;step;
''' + '\n'.join(statements) + '\n$finish;end\nendmodule\n'
    with tempfile.TemporaryDirectory(prefix='p1715-analyzer-') as temp:
        source = Path(temp)/'random_tb.v'
        output = Path(temp)/'sim'
        source.write_text(bench)
        subprocess.run(['iverilog', '-g2012', '-s', 'random_tb', '-o', str(output),
                        str(ROOT/'hardware/rtl/analyzer_top.v'), str(source)], check=True)
        subprocess.run(['vvp', str(output)], check=True, capture_output=True)
    print(f'analyzer randomized PASS: 160 captures, {comparisons} records, seed 1715')


if __name__ == '__main__':
    main()
