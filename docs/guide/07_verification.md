# 07 · Verification

## What you'll learn

- The core vocabulary of hardware verification, each term defined with an example:
  - DUT, testbench, stimulus, checker;
  - golden model, scoreboard;
  - directed vs constrained-random tests, seed;
  - functional coverage (coverpoint, bin, cross), closure;
  - regression, mutation analysis.
- How this repository implements each of those ideas, with file and line references.
- Every way a test in this repo can fail, and what the failure message looks like.
- One test followed from `make test` to PASS. Then the same test with a bug injected,
  followed until the scoreboard reports the mismatch.

---

## 1. A worked example first: one test, end to end

Take `directed_hazard_load_use`, the test from chapters 04 and 05, run on the pipelined
core. Here is everything that happens when you type `make test-rtl CORE=pipe`.

### 1.1 From make to a simulator

1. **Make runs pytest.** `make test-rtl` runs `pytest tests/rtl` (`Makefile:71-72`), and
   `CORE=pipe` is exported to it (`Makefile:6`).
2. **pytest finds the entry function.** In `tests/rtl/test_core_directed.py` it finds
   `test_core_directed(core)`, parametrized by `cores_under_test()`, which returns `["pipe"]`
   (`tests/rtl/test_core_directed.py:414-416`, `tests/rtl/cocotb_runner.py:18-25`).
3. **The function builds and launches the simulator.** It calls
   `run_cocotb("tb_top", CORE_SOURCES, "test_core_directed", "pipe")`
   (`tests/rtl/cocotb_runner.py:28-60`), which:
   - asks **Verilator** to compile all of `rtl/` plus `tb/tb_top.sv`, with `-DPIPELINED` and
     `-Wall`, into a simulator executable in `sim_build/tb_top_pipe/`;
   - starts that executable with the plusarg `+CORE=pipe`.
4. **cocotb takes over inside the simulator.** It imports `test_core_directed.py` again,
   *inside* the simulation. At import time the module builds one cocotb test per `Case`:
   `directed_alu_add`, …, `directed_hazard_load_use` (`tests/rtl/test_core_directed.py:402-411`).
   cocotb runs them one after another on the same simulator.

### 1.2 Inside one cocotb test

`run_case` drives each test (`tests/rtl/test_core_directed.py:391-399`):

```python
harness = CoreHarness(dut, COVERAGE)
harness.load(case.program, case.data)
result = await harness.run(expect_trap=case.expect_trap)
COVERAGE.save(coverage_path("directed"))
for reg, value in case.expect.items():
    got = harness.read_reg(reg)
    assert got == value, f"x{reg} = 0x{got:08x}, expected 0x{value:08x}"
```

1. **`CoreHarness(dut, …)`** checks that `+CORE=pipe` matches what was really built: only
   `core_pipe` has a `stall_load_use` signal (`tb/harness.py:105-112`). This check exists
   because of a real bug (chapter 08, bug 1).
2. **`load()`** builds a 4,096-word image:
   - the program at 0;
   - `mem[0x2000] = 7`, `mem[0x2004] = 9`, `mem[0x200c] = 0x2000`;
   - zeros everywhere else.

   It writes that image into **both** `imem` and `dmem` through the simulator, and into a
   fresh `Iss` (`tb/harness.py:116-134`). Every word is written, so nothing is left over
   from the previous test.
3. **`run()`** first resets the core: `rst_n = 0` for two rising edges, released on a rising
   edge (`tb/harness.py:136-144`). Then it loops on falling edges (`tb/harness.py:158-185`).
   Each falling edge:
   - counts a cycle and enforces `max_cycles`;
   - checks `mem_fault` (an access outside the memories);
   - on the pipe core, adds up stall and flush cycles and samples pipeline coverage;
   - skips the cycle if `rvfi_valid = 0`;
   - fails if `rvfi_trap = 1` and no trap was expected;
   - otherwise reads the retire port, steps the ISS and **compares**;
   - samples instruction coverage;
   - stops after the instruction with `halt = 1`.
4. **After the halt**, the harness waits one more cycle and requires `halted = 1` with
   nothing retiring (`tb/harness.py:190-193`). Then `_check_final_state()` compares x1–x31
   and all 4,096 data-memory words with the ISS (`tb/harness.py:238-247`).
5. **Back in `run_case`**, the hand-computed expectations are checked: x3 = 7, x5 = 9,
   x6 = 7, x8 = 7, x10 = 0, x13 = 14 (`tests/rtl/test_core_directed.py:357`).

All passing: cocotb marks `directed_hazard_load_use` PASS in its JUnit results file. pytest
reads that file, and `test_core_directed[pipe]` passes if all 50 cocotb tests passed.

### 1.3 The same test with a bug

Now remove the load-use stall: `make waveform` does exactly this, using
`tools/mutations.py:46-48`. Here is what happens:

- Retire #0 (`lui x1, 0x2`) matches the model.
- Retire #1 (`lw x2, 0(x1)`) matches the model.
- Retire #2 is `add x3, x2, x0`. The core reports `rd_wdata = 0x2000`; the model says `7`.
  `got == expected` is false, so `_check` lists every differing field and raises
  (`tb/harness.py:221-236`).

This is real output from this repository:

```
tb.harness.ScoreboardMismatch: retire #2 mismatch at pc=0x00000008: add x3, x2, x0
  rd_wdata   core=0x00002000  model=0x00000007
last 2 retired instructions:
  pc=0x00000000  lui x1, 0x2                  x1=0x00002000
  pc=0x00000004  lw x2, 0(x1)                 x2=0x00000007 load mem[0x00002000] mask=1111
```

The report has three parts:
- **Which instruction:** the retire index, pc and disassembly (`tb/harness.py:235`).
- **Which fields differ:** each one with the core value and the model value
  (`tb/harness.py:230-234`).
- **Context:** up to 8 previously retired instructions, formatted by `format_retire`
  (`tb/harness.py:71-79,255-259`).

You can read the bug straight off it: the `add` used x2 = 0x2000, which is the `lw`'s
**address**, before the `lw`'s data existed.

## 2. The vocabulary

| Term | Definition | In this repo |
|---|---|---|
| **DUT** (design under test) | the hardware being verified | `core_single` or `core_pipe`, instance `u_core` (`tb/tb_top.sv:49-53`) |
| **Testbench** | everything around the DUT that drives it and judges it; never synthesized | `tb/tb_top.sv` (memories), `tb/harness.py` (Python driver and checker) |
| **Stimulus** | the inputs applied to the DUT; for a CPU, mostly the program | directed cases, riscv-tests, C programs, random programs |
| **Checker** | code that decides pass/fail | the scoreboard, the final-state compare, `expect` values, program self-checks |
| **Golden model** | an independent implementation that gives the right answer | `model/iss.py` (chapter 06) |
| **Scoreboard** | a checker that compares DUT outputs with the golden model's predictions, transaction by transaction | `CoreHarness._check` (`tb/harness.py:221-236`); the "transaction" is one retired instruction |
| **Directed test** | stimulus written by hand to hit a specific case | 50 `Case`s in `tests/rtl/test_core_directed.py` |
| **Constrained-random test** | stimulus generated randomly, but within rules (constraints) that keep it legal and aim it at interesting areas | `tb/random_program.py` |
| **Seed** | the starting value of a random generator; same seed, same stimulus | `random_program(seed)`; `SEED_START` / `SEEDS` |
| **Functional coverage** | a record of which *specified situations* the stimulus actually caused | `tb/coverage.py` |
| **Coverpoint / bin** | a coverpoint is something you want to observe (e.g. "branch outcome"); bins are its interesting values ("beq taken", "beq not taken") | 8 coverpoints, 103 bins (section 6) |
| **Cross coverage** | bins for *combinations* of two coverpoints | not implemented (Known gaps) |
| **Code coverage** | which RTL lines, branches or toggles were exercised (a tool feature, not hand-written) | not used |
| **Coverage closure** | the process of reaching the coverage goal, e.g. 100% of bins | the closure plot (section 6.4) |
| **Regression** | the full test suite, re-run on every change | `make test`, run by CI on every push (chapter 09) |
| **Mutation analysis** | deliberately inject bugs to measure whether the tests detect them | `make mutation` (section 7) |

## 3. Checking: the four layers in this repo

A test here passes only if **all** of these agree:

| Layer | What it compares | Catches | Code |
|---|---|---|---|
| 1. Per-instruction scoreboard | core retire record vs `Iss.step()`, all 10 fields | wrong result, wrong branch decision, wrong address/mask/data, missing/extra/reordered instruction | `tb/harness.py:221-236` |
| 2. Final state | registers x1–x31 and all of data memory vs the ISS | wrong state that never appeared on the retire port, e.g. a wrong-path store that wrote memory | `tb/harness.py:238-247` |
| 3. Independent expectations | `expect` register values computed by hand; riscv-tests' gp == 1; C programs' a0 == the value computed in Python | a mistake shared by the core *and* the model | `tests/rtl/test_core_directed.py:396-398`; `tests/rtl/test_core_programs.py:68-69,77-78` |
| 4. Run-level checks | timeout; out-of-range or misaligned access (`mem_fault`); unexpected trap; core not halted after ECALL; `+CORE` mismatch; the cycle-count formula | hangs, runaway pcs, a halt that doesn't stop, measurement errors | `tb/harness.py:105-112,161-164,173-177,190-193`; `tests/rtl/test_core_programs.py:43-51` |

**Why layer 2 is needed on top of layer 1:** suppose a pipeline flush failed to squash a
wrong-path store. The store never retires, so the scoreboard never sees it, but memory is
changed. The final-memory comparison catches it. The test `hazard_branch_and_jump_flush`
places a store on the wrong path for exactly this reason
(`tests/rtl/test_core_directed.py:369`).

## 4. Directed tests: `tests/rtl/test_core_directed.py`

There are 50 cases, each a small program built with the encoder and ending in `ecall`
(`tests/rtl/test_core_directed.py:32-37`):

| Group | Cases | Lines | What they target |
|---|---|---|---|
| ALU register-register | 10 | `44-54` | each op on 7 edge-value pairs (sign bit, overflow, shift by 33/31), plus a write to x0 |
| ALU immediate | 9 | `58-70` | edge immediates (0, ±1, 2047, −2048) and shift amounts (0, 1, 15, 31) |
| `lui`, `auipc` | 2 | `74-97` | upper-immediate edges, pc-relative values; hand-computed `expect` |
| `jal`, `jalr` | 2 | `101-129` | forward and backward jumps, link values, `jalr` bit-0 clearing, rd == rs1 |
| Branches | 6 | `133-150` | a truth table per branch on 5 operand pairs, with flag registers set only on fall-through |
| Loads | 5 | `154-172` | every width at every legal byte offset, negative offset, load into x0 |
| Stores | 3 | `176-193` | every width and offset, read back with `lw` |
| System | 4 | `197-213` | `fence`; `ecall` and `ebreak` halt (the instruction after must not run); illegal word traps |
| x0 | 1 | `217-233` | every instruction class with rd = x0 |
| Small programs | 3 | `237-278` | sum 1..10, fib(20) = 6765, a dependency chain |
| Pipeline hazards | 5 | `285-382` | added in M4 after mutation analysis (chapter 08) |

Total: 10 + 9 + 2 + 2 + 6 + 5 + 3 + 4 + 1 + 3 + 5 = **50**. The same 50 run on both cores.

**The weakness of directed tests:** they only test what someone thought of. Mutation
analysis measured this. Before the hazard tests existed, no directed test caught
"forwarding from x0" (0 of 45; chapter 08).

## 5. Program tests and random tests

### 5.1 `tests/rtl/test_core_programs.py`: real software

- **The 40 rv32ui riscv-tests.** These are the official RISC-V compliance-style tests, one
  assembly file per instruction. Each one checks itself: on failure it puts
  `2 × test number + 1` in gp (x3); on success, 1. They normally need CSRs for their
  environment. This repo replaces that environment with a bare one,
  `programs/riscv-test-env/riscv_test.h`, so they run on a core without CSRs.
  - **Built by:** `tb/programs.py:89-101` (GCC, linked at 0x0 by `programs/link.ld`).
  - **Two excluded:** `fence_i` and `ma_data`, with the reasons in code
    (`tb/programs.py:40-43`).
- **Two C programs.** `programs/fibonacci.c` (recursive fib(15) = 610) and
  `programs/bubble_sort.c` (sort 32 pseudo-random words, return a checksum). Their expected
  results are computed by a separate Python copy (`tb/programs.py:107-130`).

Each program also records its instruction and cycle counts, and asserts the cycle formula
(`tests/rtl/test_core_programs.py:42-61`). Those numbers become the CPI table.

### 5.2 `tb/random_program.py`: constrained-random programs

**Random stimulus finds the cases nobody thought of.** Pure randomness would produce
illegal programs: jumps into data, misaligned loads, infinite loops. So each part of a
program comes from a **block** with one constraint that keeps it legal
(`tb/random_program.py:3-16`):

| Block (weight) | What it emits | Constraint that keeps it legal | Lines |
|---|---|---|---|
| alu (40) | one R, I or shift instruction | none needed | `105-117`, `126-127` |
| memory (20) | `li base, addr - offset`, 0–2 ALU instructions, then a load/store | the address is aligned and inside 0x2000–0x27FF by construction; the ALU instructions never write `base` | `134-148` |
| branch (15) | a branch that skips 0–3 ALU instructions | forward only | `150-156` |
| upper (5) | `lui`/`auipc` | none | `129-132` |
| jal (5) | `jal` skipping 0–3 | forward only | `158-162` |
| jalr (5) | `auipc base, 0` + `jalr` | forward only; sometimes bit 0 set (JALR must clear it) | `164-173` |
| loop (5) | counter = 1..4, a 1–4 instruction body, decrement, `bne` back | the only backward branch; the body never writes the counter | `175-183` |
| fence (1) | `fence` | none | `185-186` |

**Aiming the randomness:**
- **Dependency bias.** Half of all source registers are taken from the last three
  destinations (`tb/random_program.py:89-93`). That creates the read-after-write
  dependencies forwarding must handle.
- **Edge-value bias.** Half of all 32-bit values are edge cases such as 0x7FFFFFFF and
  0x80000000 (`tb/random_program.py:36-40,71-75`).
- **Random start.** Half the registers begin with random values (`tb/random_program.py:191-193`).

**A real excerpt of seed 1** (from `random_program(1)`):

```
0x0088: lui x14, 0x2              # memory block: li x14, 0x2332 ...
0x008c: addi x14, x14, 818
0x0090: ori x0, x14, 2            #   ... one ALU instruction (never writes x14) ...
0x0094: lhu x18, 874(x14)         #   ... load: 0x2332 + 874 = 0x269C, halfword-aligned
0x0098: lui x3, 0x2               # memory block: li x3, 0x2413
0x009c: addi x3, x3, 1043
0x00a0: sw x3, 1(x3)              #   base used right after it is written: 0x2414
0x00a4: sltu x20, x18, x18        # alu block
0x00a8: bgeu x29, x3, .+4         # branch block that skips 0 instructions
0x00ac: sub x26, x20, x13         # alu block
0x00b0: addi x14, x0, 1           # loop block: counter x14 = 1
0x00b4: sll x0, x14, x14          #   body
0x00b8: ori x21, x14, 1187        #   body
0x00bc: addi x14, x14, -1         #   decrement
0x00c0: bne x14, x0, .-12         #   back to 0x00b4
0x00c4: blt x27, x27, .+12        # branch block with equal operands, skips 2
```

A program has 150 blocks plus the register setup (`tb/random_program.py:62,190-198`).
Measured over seeds 1–50, programs retire between 289 and 496 instructions, with a mean
of 382.8.

**Two guarantees:**
- **Reproducibility.** The same seed always gives the same program
  (`tests/model/test_random_program.py:40-42`). A failing seed is rerun exactly with
  `make test-random SEED_START=<seed> SEEDS=1` (`tests/rtl/test_core_random.py:7`).
- **Legality is tested, not assumed.** 200 seeds are run on the ISS in `tests/model`; every
  one must reach ECALL with all loads and stores inside the data region
  (`tests/model/test_random_program.py:25-37`).

## 6. Functional coverage: `tb/coverage.py`

### 6.1 Example first

The coverpoint `branch` has 12 bins: `beq_taken`, `beq_not_taken`, …, `bgeu_not_taken`.
Each time a branch retires, the collector works out whether it was taken
(`next_pc == pc + imm`) and increments one bin (`tb/coverage.py:84-86`). After a run:
- `bne_taken: 3, bne_not_taken: 0` means the tests **never** saw a `bne` fall through;
- if a bug only affects not-taken `bne`, no test could have found it.

Coverage turns "I think I tested branches" into a measured statement.

### 6.2 The coverpoints

| Coverpoint | Bins | Sampled from | Code |
|---|---|---|---|
| `opcode` | 40 | every retired instruction | `tb/coverage.py:43,82` |
| `branch` | 12 | each branch: taken / not taken | `44, 84-86` |
| `load_offset` | 13 | each load width × legal byte offset | `45, 88-89` |
| `store_offset` | 7 | each store width × legal byte offset | `46, 90-91` |
| `x0` | 3 | rd = x0 on a writing instruction; rs1 = x0; rs2 = x0 | `47, 93-98` |
| `imm_sign` | 8 | negative/positive immediate for I, S, B, J | `48, 100-102` |
| `raw_hazard` | 7 | rs1/rs2 written 1, 2 or 3 instructions earlier; load-use | `49, 107-122` |
| `pipeline` (pipe only) | 13 | every cycle: each forwarding path per operand, both-at-once (newest wins), bypass per operand, stall, flush by branch/JAL/JALR/halt | `53-59, 124-145` |

That's 90 bins for the single-cycle core and 103 for the pipeline
(`tests/model/test_coverage.py:23-27`).

### 6.3 Where coverage is sampled

- **Architectural bins come from the retire stream**, not from inside the core, so the same
  bins apply to both cores. The harness calls `coverage.sample(retire)` after each
  successful comparison (`tb/harness.py:182-183`).
- **Pipeline bins come from inside `core_pipe`**, every cycle, through cocotb handles to its
  signals (`tb/harness.py:168-169`, `tb/coverage.py:124-145`). Some of them read the helper
  signals `cov_*` in `rtl/core_pipe.sv:344-361`.
- **Each suite saves its own JSON file**, `build/coverage/<core>/<suite>.json`
  (`tb/harness.py:52-53`). `make coverage` merges the files and prints the tables
  (`tb/coverage_report.py`).

### 6.4 Measured results and what they mean

Measured with `make test && make coverage`:

| Suite | single (of 90) | pipe (of 103) |
|---|---|---|
| directed | 90 | 103 |
| programs | 89 | 102 |
| random | 88 | 101 |
| **all suites** | **90 (100%)** | **103 (100%)** |

**What random misses, by design:** `ebreak` (programs end with `ecall`) and a negative
J-type immediate (jumps only go forward).

**The closure curve** records the random suite's total bins hit after each seed
(`tests/rtl/test_core_random.py:41-47`). On both cores it reaches its maximum after
**3 seeds** and then stays flat:

| After seed | 1 | 2 | 3 | … 50 |
|---|---|---|---|---|
| single (of 90) | 77 | 86 | 88 | 88 |
| pipe (of 103) | 90 | 99 | 101 | 101 |

![coverage closure](../img/coverage_closure.png)

**The honest reading:** the coverage model is coarse. After 3 programs, more random
programs add nothing to the coverage number. Yet the mutation analysis (section 7) shows
bugs that only 9 of 50 seeds catch. So more random programs *do* add bug-finding power that
these bins don't measure. **100% coverage means every listed event happened, not that every
bug was found.** Cross coverage would close part of that gap (Known gaps).

## 7. Mutation analysis: do the tests work?

**The idea:** if you break the design and no test fails, your tests are blind to that kind
of bug.

`tools/mutations.py:30-53` lists 7 realistic pipeline bugs. Each one is an exact text
replacement in `rtl/core_pipe.sv`. `tools/mutation_analysis.py` then, for each bug:
1. applies the replacement;
2. runs the directed, program and random suites on the pipelined core;
3. counts failing tests.

Afterwards it restores the RTL and the coverage/CPI data, even on Ctrl-C
(`tools/mutations.py:57-74`).

Measured with `make mutation` (failing / run):

| Injected bug | Directed | Programs | Random |
|---|---|---|---|
| No EX/MEM forwarding (rs1) | 43 / 50 | 41 / 42 | 50 / 50 |
| No MEM/WB forwarding (rs2) | 6 / 50 | 11 / 42 | 50 / 50 |
| Forwarding priority wrong (MEM/WB beats EX/MEM) | 9 / 50 | 27 / 42 | 49 / 50 |
| Forwarding from x0 | 1 / 50 | 16 / 42 | 9 / 50 |
| No write-before-read bypass | 21 / 50 | 36 / 42 | 50 / 50 |
| No load-use stall | 2 / 50 | 7 / 42 | 35 / 50 |
| Flush squashes only IF, not ID | 50 / 50 | 42 / 42 | 50 / 50 |

**What this table tells you:**
- **Every suite type catches every bug.** The constrained-random suite is the strongest,
  catching most bugs on nearly every seed.
- **"Forwarding from x0" is the hardest.** It needs a write to x0 followed closely by a read
  of x0, which real code rarely does. The directed hazard test was added specifically for it.
- **The directed suite catches each bug with only 1–2 targeted tests.** That's fine. One
  failing test is enough to stop a merge.

## 8. Running and reproducing

| Want to | Command |
|---|---|
| Everything | `make test` |
| One core | `make test CORE=pipe` |
| More random programs | `make test-random CORE=pipe SEED_START=1000 SEEDS=500` |
| Rerun exactly one random program, with a waveform | `make test-random CORE=pipe SEED_START=<seed> SEEDS=1 WAVES=1` |
| Change cocotb's own random seed (used by the ALU/regfile random tests) | `make test-rtl SEED=42` |
| Coverage tables / CPI table | `make coverage`, `make cpi` |
| Mutation table | `make mutation` |

## Known gaps

- **No cross coverage.** There are no bins for combinations, such as "forwarded value used
  by a store" or "stall immediately followed by a flush". The closure curve flattening after
  3 seeds is the visible symptom.
- **No code coverage.** Verilator can report line and toggle coverage, but it isn't
  enabled. Line coverage would show RTL never exercised, for example illegal-instruction
  paths per opcode.
- **Instruction memory isn't compared at the end.** That's fine, because nothing writes it
  (self-modifying code is out of scope).
- **`mem_fault` only checks retired accesses** (`tb/tb_top.sv:79-82`). A wrong-path fetch
  outside the memory is ignored on purpose (`tb/tb_top.sv:55-57`).
- **cocotb's own seed is fixed at 1 by default** (`tests/rtl/cocotb_runner.py:57`). The ALU
  and register-file random tests therefore run the same operands on every CI run. That's
  reproducible, but not exploring.
- **The README's "~360 instructions each" for random programs is off.** Measured over seeds
  1–50 (the CI seeds), the mean is 382.8 retired instructions, ranging from 289 to 496.
- **Two stale comments:**
  - `tests/rtl/test_core_directed.py:1` says "for the single-cycle core";
  - `CLAUDE.md:43` says the waveform is at `sim_build/<top>/dump.vcd`. With two cores the
    directory is `sim_build/tb_top_<core>/`, as `tests/rtl/cocotb_runner.py:6,38-39`
    correctly describes.

## Check yourself

1. Name the four checking layers, and give a bug that only layer 2 would catch.
2. What is the difference between directed and constrained-random tests? Give the constraint that keeps random loads aligned.
3. What does a coverage bin record, and why can 100% coverage still miss bugs here?
4. In the mismatch report, how do you tell which instruction failed, and what the core did wrong?
5. What does mutation analysis measure that coverage does not?

<details>
<summary>Answers</summary>

1. The four layers:
   - the per-instruction scoreboard;
   - the final registers and memory;
   - independent expectations (hand `expect`, gp, a0);
   - run-level checks (timeout, `mem_fault`, trap, halt, cycle formula).

   A wrong-path store that the flush failed to squash never retires, so only the
   final-memory compare sees it.
2. Directed tests are hand-written for a specific case. Constrained-random tests are
   generated from a seed within rules. For loads: the base register is set with
   `li base, addr - offset` right before the load, where `addr` is an aligned address
   inside the data region (`tb/random_program.py:134-148`).
3. A bin records how many times a specific situation happened. The bins here don't capture
   *combinations*. Random coverage is flat after 3 seeds, while some injected bugs are
   caught by only 9 of 50 seeds.
4. The header line gives the retire index, pc and disassembly. The following lines list
   each differing field with the core and model values (`tb/harness.py:230-235`).
5. Whether the tests can *detect* bugs. Coverage measures what was *exercised*, not whether
   a wrong result would be noticed.

</details>
