# 10 · Results: every number, explained

## What you'll learn

- For every number in `README.md`:
  - what it measures;
  - which code produced it;
  - the command that reproduces it;
  - what it does and doesn't mean.
- How `make results` regenerates them all, and why it runs steps in a particular order.
- Where the numbers are weaker than they look: the honest caveats an interviewer may probe.

---

## 1. A worked example first: tracing one number

The README says the pipelined core runs bubble sort at **CPI 1.595**. Here's the chain
behind that number:

1. `programs/bubble_sort.c` is compiled by GCC (`tb/programs.py:133-137`).
2. `tests/rtl/test_core_programs.py` runs it on `core_pipe` with the scoreboard on. The
   harness counts:
   - `cycles`: falling edges from reset release until the ECALL retires;
   - `retired`: instructions;
   - `stall_cycles` and `flushes` (`tb/harness.py:157-167,196-202`).
3. `record()` asserts that the counts satisfy the timing formula, then writes them to
   `build/results/pipe/programs.json` (`tests/rtl/test_core_programs.py:42-61`).
4. `make cpi` reads that JSON and divides: 5,803 cycles / 3,639 instructions = 1.595
   (`tb/cpi_report.py:31-38`).

To reproduce it: `make test && make cpi`.

**What it means:** the pipeline spends 59.5% more cycles per instruction than the
single-cycle core on this program.

**What it does not mean:** that the pipeline is slower. CPI ignores clock frequency, which
this project doesn't measure (section 7).

Every number below gets the same treatment.

## 2. `make results`: one command for everything

`Makefile:100-112` runs these steps in order:

| Step | Produces | Why this position |
|---|---|---|
| `clean` | — | no stale results from earlier runs |
| `synth` | `build/results/synth.json` | independent of tests |
| `mutation` | `build/results/mutation.json` and the mutation table | injects bugs, so it runs **before** the real tests |
| `waveform` | `docs/img/failing_waveform.png` | injects a bug too |
| `test-model` with `--junitxml` | `build/results/model_tests.xml` | |
| `test-rtl` | `sim_build/*/*.None`, `build/coverage/`, `build/results/<core>/` | the real, unmodified-RTL results |
| `test-report`, `coverage`, `cpi` | tables | read the files from the test run |
| `plots` | `docs/img/cpi_breakdown.png`, `coverage_closure.png` | |

The comment at `Makefile:100-101` states the ordering rule. The bug-injecting steps
restore the RTL and the protected data directories afterwards (`tools/mutations.py:57-74`).
Even so, the real tests run last, so nothing reported can come from a mutated design.

**Measured run time:** 406 s on a clean tree (README).

## 3. Test results

| README number | Measures | Produced by | Reproduce |
|---|---|---|---|
| **429 / 429** model tests | pass count of `pytest tests/model` | JUnit XML from pytest, counted by `tools/test_report.py:21-28` | `make test-model` |
| **289–496** instructions per random program, **mean 382.8** | instructions retired per seed (seeds 1–50), same on both cores | recorded per seed by `tests/rtl/test_core_random.py:41-47`, summarised by `tools/test_report.py:31-38` | `make test-rtl` then `make test-report` |
| **7 / 7** block tests (3 ALU + 4 regfile) | cocotb tests in `tests/rtl/test_alu.py` and `test_regfile.py` | `sim_build/alu/test_alu_rtl.None`, `sim_build/regfile/test_regfile_rtl.None` | `make test-rtl` then `make test-report` |
| **50 / 50** directed, per core | `test_core_directed` cocotb tests | `sim_build/tb_top_<core>/test_core_directed[<core>].None` | same |
| **42 / 42** programs, per core | 40 riscv-tests + 2 C programs | `.../test_core_programs[<core>].None` | same |
| **50 / 50** random, per core | seeds 1–50 | `.../test_core_random[<core>].None` | same |
| **142 / 142** per core | 50 + 42 + 50 | sum of the three | |
| **436** model and block tests | 429 + 7 | sum | |
| **720** tests (RESUME_BULLETS) | 429 + 7 + 2 × 142 | sum | |
| **40 of 42** riscv-tests | the rv32ui suite minus `fence_i`, `ma_data` | `tb/programs.py:40-43,84-86`; asserted to be 40 by `tests/model/test_programs_iss.py:38-41` | `make test-model` |
| **1,600** random instructions vs GNU `as` | 40 instructions × 40 random instances each | `tests/model/test_encoder.py:107-128` | `make test-model` |

**What a pass means here:** every retired instruction matched the model, the final state
matched, and the hand or self-check expectations held (chapter 07, section 3).

## 4. The 2,000-seed sweeps (not part of `make results`)

| README number | Command | Measured |
|---|---|---|
| single: **2,000 / 2,000**, 157 s | `make test-random CORE=single SEED_START=1000 SEEDS=2000` | in M3 |
| pipe: **2,000 / 2,000**, 390 s | `make test-random CORE=pipe SEED_START=1000 SEEDS=2000` | in M4 |

These were one-off runs, recorded in `docs/bugs.md:18-21`. Seeds 1000–2999 don't overlap
the CI seeds 1–50.

**What this means:** about 2,000 more distinct programs per core, each roughly 380
instructions long (section 8), all matching the model.

**What it doesn't mean:** proof of correctness. Random testing samples the input space; it
doesn't cover all of it.

## 5. CPI

Reproduce with `make test && make cpi` (table) and `make plots` (figure).

| Program | Core | Instructions | Cycles | CPI | Stall cycles | Flushes |
|---|---|---|---|---|---|---|
| fibonacci | single | 14,799 | 14,799 | 1.000 | - | - |
| fibonacci | pipe | 14,799 | 17,147 | 1.159 | 0 | 1,173 |
| bubble_sort | single | 3,639 | 3,639 | 1.000 | - | - |
| bubble_sort | pipe | 3,639 | 5,803 | 1.595 | 496 | 833 |

![CPI breakdown](../img/cpi_breakdown.png)

| Number | Meaning |
|---|---|
| **instructions** | instructions retired, including the final ECALL (`tb/harness.py:84,197`) |
| **cycles** | falling edges counted from reset release until the ECALL retires (`tb/harness.py:85,159-160`); this includes the pipeline's 4 fill cycles |
| **1.000** for single | asserted exactly, for every program (`tests/rtl/test_core_programs.py:43-45`); it's also a check on the cycle counting itself |
| **stall cycles** | cycles with `stall_load_use = 1` (`tb/harness.py:166`) |
| **flushes** | cycles with `flush = 1`: each taken branch, JAL, JALR, and the final ECALL (`tb/harness.py:167`) |
| **2 × 832 = 1,664** | bubble sort cycles lost to flushes (the README's design-decision table) |
| **the formula** | `cycles = instructions + 4 + stalls + 2 × (flushes − 1)`, asserted for every program (`tests/rtl/test_core_programs.py:46-51`) and re-checked by the plot script (`tools/plot_results.py:43-44`) |

**How the stacked bars are built.** Each bar is split into four layers: 1.0 for the
instructions themselves, then fill, stalls and flushes, each divided by the instruction
count (`tools/plot_results.py:31-63`).

For bubble sort on the pipeline:
- 4 / 3,639 = 0.001 fill;
- 496 / 3,639 = 0.136 stalls;
- 1,664 / 3,639 = 0.457 flushes.

That adds up to 1.595.

**The caveat:** CPI here is per clock cycle. A real pipeline runs at a higher clock
frequency than a single-cycle design. This project doesn't measure frequency, so it can't
say which core is faster in seconds.

## 6. Functional coverage

Reproduce with `make test && make coverage` and `make plots`.

| Number | Meaning | Code |
|---|---|---|
| **90** bins (single) | 7 architectural coverpoints | `tb/coverage.py:42-50`; asserted in `tests/model/test_coverage.py:24` |
| **103** bins (pipe) | 90 + 13 pipeline bins | `tb/coverage.py:53-59`; asserted in `tests/model/test_coverage.py:26` |
| **90 / 90**, **103 / 103** | every bin hit at least once, across all suites | `tb/coverage_report.py:10-30` |
| **88 / 90**, **101 / 103** | the random suite alone; misses `ebreak` and a negative J immediate | |
| **within 3 programs** | the random suite's total stops growing after seed 3 (77 → 86 → 88 single; 90 → 99 → 101 pipe) | `build/results/<core>/random_coverage.json`, written by `tests/rtl/test_core_random.py:41-47` |

![coverage closure](../img/coverage_closure.png)

**What the numbers mean:** every situation listed in `tb/coverage.py` happened at least
once.

**What they don't mean:** "fully verified". Chapter 07 explains why a flat closure curve
next to a 9/50 mutation result shows the bins are too coarse.

## 7. Mutation analysis

Reproduce with `make mutation`, about 4–5 minutes (`tools/mutation_analysis.py:8`).

| Number | Meaning |
|---|---|
| **7 / 7** caught | for each of the 7 mutations in `tools/mutations.py:30-53`, at least one test failed in *every* suite type |
| a cell like **9 / 50** | 9 of the 50 random-seed tests failed with "forwarding from x0" injected |
| `-1 / -1` (if it ever appears) | the suite didn't build or start (`tools/mutation_analysis.py:37-38`) |

The table counts failing **cocotb tests** by searching the JUnit file for `<failure`
(`tools/mutation_analysis.py:39-40`).

## 8. Synthesis

Reproduce with `make synth`. It needs sv2v; see chapter 09.

| Core | Generic cells | Flip-flops | 7-series LUTs | 7-series INV | 7-series FFs | CARRY4 | MUXF7/8 |
|---|---|---|---|---|---|---|---|
| single | 6,438 | 1,057 | 1,946 | 1,071 | 1,037 | 50 | 254 |
| pipe | 7,502 | 1,681 | 2,155 | 1,328 | 1,681 | 58 | 511 |

| Column | Computed as (`tools/synth_report.py:61-72`) | Meaning |
|---|---|---|
| Generic cells | sum of all cells after `synth -flatten` | technology-independent gates and flip-flops |
| Flip-flops | cells whose name contains `DFF` | single: 1,024 `$_SDFFCE_` (32 × 32: the register file) + 33 `$_SDFFE_`, which matches `pc_q` (32 bits) + `halted_q` (inferred from the widths, not traced in the netlist) |
| 7-series LUTs | cells named `LUT1`…`LUT6` after `synth_xilinx` | look-up tables, the FPGA's logic blocks |
| 7-series INV | cells named `INV` | inverters that `synth_xilinx` leaves as separate cells; place-and-route typically absorbs many into LUTs or flip-flop inputs |
| 7-series FFs | cells named `FD*` | all `FDRE` here |
| CARRY4 | fast carry chains | used by adders and comparators |
| MUXF7/8 | wide multiplexers built from LUT pairs | single 254, pipe 511 |

Derived numbers in the README:

| Number | Arithmetic |
|---|---|
| **624** more flip-flops | 1,681 − 1,057 |
| **+17%** generic cells | 7,502 / 6,438 = 1.165 |
| **+11%** LUTs | 2,155 / 1,946 = 1.107 |
| **1,024** register-file flip-flops | 32 registers × 32 bits, all reset (`rtl/regfile.sv:21-22`) |

**The caveats.** All measured from `build/synth/*_stat.txt`; see Known gaps for details.

- **These are counts after synthesis, not after FPGA place-and-route.** Vivado would
  optimise further.
- **The Xilinx flow also creates inverter cells,** reported in their own column (1,071 for
  single, 1,328 for pipe) rather than inside the LUT count. The post-implementation LUT
  count would be somewhere between the LUT column and LUTs + INV. It hasn't been measured.
- **The retire port is part of the synthesized core.** It adds 208 output bits, part of the
  309 `OBUF` cells. A product core would drop it.
- **The two flows count different flip-flop totals for the single core** (1,057 vs 1,037),
  while the pipeline's two counts agree (1,681 = 1,681). This wasn't investigated.

## 9. Known gaps

- **No post-implementation LUT count.** `tools/synth_report.py:67` counts `LUT1`–`LUT6`, and
  the `INV` cells are reported separately (`tools/synth_report.py:71`). How many inverters
  survive place-and-route is unknown until the design is implemented (e.g. in Vivado).
  This was originally a gap in the README too: the guide found it, and the README's
  synthesis section now states it.
- **The single core's flip-flop count differs between flows** (1,057 generic vs 1,037
  Xilinx). The cause wasn't investigated.
- **The retire port inflates area.** The core is synthesized as the top level, so all 309
  output bits stay, including the 208-bit retire port and its gating logic.
- **No timing.** Neither flow reports a clock frequency, so the speed benefit of pipelining
  isn't measured. Yosys's `ltp` command can give a logic-depth estimate, but the README
  doesn't report one: with the memories outside the core, the single-cycle core's critical
  path is split across the ports, so the comparison would mislead.
- **Run time of `make results`.** `make help` says ~10 min, the README says ~7 min, and the
  measured run took 406 s (`Makefile:39`).

## Check yourself

1. Which file does `make cpi` read, and which test wrote it?
2. Why does `make results` run `mutation` and `waveform` before the real tests?
3. Break down bubble sort's 5,803 pipeline cycles into the four terms of the formula.
4. What exactly is counted in the "7-series LUTs" column, and what's left out?
5. Why can't the README claim the pipeline is faster than the single-cycle core?

<details>
<summary>Answers</summary>

1. `build/results/<core>/programs.json`, written by `record()` in
   `tests/rtl/test_core_programs.py:42-61`.
2. They modify the RTL temporarily. Running the real tests afterwards guarantees every
   reported test, coverage and CPI number comes from the unmodified design
   (`Makefile:100-112`).
3. 3,639 instructions + 4 fill + 496 stall cycles + 2 × 832 flush cycles = 5,803.
4. Only cells named `LUT1`–`LUT6` in the `synth_xilinx` netlist
   (`tools/synth_report.py:67`). `INV` cells (1,328 for pipe) are left out of it and
   reported in their own column. I/O buffers and carry/mux primitives are left out too.
5. Only CPI was measured. Pipelining pays off through a higher clock frequency, and no
   timing analysis was done.

</details>
