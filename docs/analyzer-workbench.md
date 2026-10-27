# Analyzer workbench artifacts

The DAC analyzer page consumes the existing raw v1 and compact v1/v2 contracts.
It has no firmware protocol changes. `tools/build_analyzer_workbench.py` builds
original directed decoder vectors, Python expected results, a differential
validation corpus, a standalone Z80 disassembler and a **test-only** WASM build
of the actual analyzer USB C handler/receiver. The device seam is not a second
firmware implementation. Original notices travel with the artifacts.

For the native RTL examples, first run the existing generator without private
ROMs or disk inputs:

```
python3 tools/check_cycle_analyzer.py --dac ../dac-emulation --out local/workbench-cosim
python3 tools/build_analyzer_workbench.py --cosim local/workbench-cosim
```

Use a new cosimulation output directory. The builder copies only `synthetic-all`
and `synthetic-io-only` captures and records their generator/tool provenance.
The small raw example is a clearly labeled directed sampled pattern, not a bench
measurement. The other examples isolate decoder/transport cases, not CPU execution.

The output manifest pins source revisions, exact source hashes, compiler and all
artifact hashes. Build after committing; dirty builds are marked. DAC's
`scripts/sync-analyzer.mjs` rejects dirty builds unless a development override is
explicitly supplied. Its independent JS decoder and transport tests compare against
these Python results and exercise the shared C USB handler. Existing native Python
USB/RTL tests remain necessary; browser tests do not qualify electrical operation,
USB throughput, or the optional reset accessory.
