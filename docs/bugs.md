# Bug log

Every bug found by the tests is recorded here: symptom, root cause, fix, and what caught
it, so it can be reproduced. Injected bugs (deliberate mutations used to prove that a test
*can* fail) are kept in separate tables and are never counted as real bugs.

## Real bugs

| # | Where | Symptom | Root cause | Fix | Caught by |
|---|---|---|---|---|---|
| 1 | Testbench (M4) | `make cpi` showed the **single-cycle** core with CPI 1.595 on bubble sort, which is impossible (it must be exactly 1.0); no hazard coverage was recorded for the pipelined core | The harness learned which core it was driving from the env var `CORE`. cocotb 1.9's runner builds the simulator's environment from `extra_env` and then copies `os.environ` over it, and `make` exports `CORE` (empty when unset), so `CORE=pipe` was silently replaced. Pass/fail was still valid (the pipelined RTL was built and checked by the scoreboard), but its coverage and cycle counts were stored as `single` | Pass the core as a plusarg (`+CORE=pipe`), which the environment cannot override; the harness now checks the hierarchy matches `+CORE`; `test_core_programs` asserts single-cycle cycles == instructions, and checks the pipeline's cycle count against its timing model | Sanity check of a measured result (single-cycle CPI must be 1.0) |
| 2 | Directed tests (M4) | Mutation analysis: "forwarding from x0" was caught by **0 / 45** directed tests and "no load-use stall" by only **1 / 45** | The x0 test never placed a write to x0 directly before a read of x0 (the only candidate pair was separated by a jump flush); no directed test used a load result in the next instruction | Added 5 directed hazard tests with hand-computed results (x0 at distance 1/2/3, forwarding distances, newest-value priority, load-use in every operand position, wrong-path squash). Now 1 / 50 and 2 / 50 | `make mutation` |

**RTL:** no RTL bug has been found by the tests so far. The pipelined core passed every
suite on its first run, which is why the mutation analysis below was done: to check the
tests are able to find pipeline bugs at all. Measured:

| Core | CI (`make test`) | One-off sweep |
|---|---|---|
| single | seeds 1-50: 50 / 50 pass | seeds 1000-2999: 2000 / 2000 pass, 157 s, measured in M3 (`make test-random CORE=single SEED_START=1000 SEEDS=2000`) |
| pipe | seeds 1-50: 50 / 50 pass | seeds 1000-2999: 2000 / 2000 pass, 390 s (`make test-random CORE=pipe SEED_START=1000 SEEDS=2000`) |

## Injected bugs: pipeline mutation analysis (M4)

`make mutation` injects each bug into `rtl/core_pipe.sv`, runs the three suites on the
pipelined core and restores the file. Numbers are failing tests / tests run:

| Injected bug | Directed | Programs (riscv-tests + C) | Random (50 seeds) |
|---|---|---|---|
| No EX/MEM forwarding (rs1) | 43 / 50 | 41 / 42 | 50 / 50 |
| No MEM/WB forwarding (rs2) | 6 / 50 | 11 / 42 | 50 / 50 |
| Forwarding priority wrong: MEM/WB beats EX/MEM (rs2) | 9 / 50 | 27 / 42 | 49 / 50 |
| Forwarding from x0 (missing rd != 0 check) | 1 / 50 | 16 / 42 | 9 / 50 |
| No write-before-read bypass (rs1) | 21 / 50 | 36 / 42 | 50 / 50 |
| No load-use stall | 2 / 50 | 7 / 42 | 35 / 50 |
| Flush squashes only IF, not ID | 50 / 50 | 42 / 42 | 50 / 50 |

All 7 are caught by every suite type. The constrained-random suite is the strongest; the
"forwarding from x0" bug is the hardest, because it needs a write to x0 followed closely by
a read of x0, which real code rarely does.

## Injected bugs: earlier milestones

Each mutation was applied to a clean tree, the tests were run, and the change was reverted.

| Mutation | Tests that caught it | First failure reported |
|---|---|---|
| `alu.sv`: SRA as logical shift (M1) | `test_alu` | `SRA(0x80000000, 0x00000001) = 0x40000000, expected 0xc0000000` |
| `lsu.sv`: LB zero-extends (M2) | directed `load_lb` (1 of 45 directed tests) | `retire #1 ... lb x10, 0(x1)`: `rd_wdata core=0x00000083 model=0xffffff83` |
| `model/alu.py`: ISS SRA as logical shift (M3) | riscv-tests on the ISS: `lui`, `sra`, `srai` | `rv32ui-sra failed test case 3 (gp=7)` |
| `branch_unit.sv`: BGE as `>` (M3) | random: 35 of 50 seeds | `retire #287 ... bge x19, x19, .+8`: `next_pc core=0x0000047c model=0x00000480` |

## How to reproduce a random failure

```bash
make test-random CORE=pipe SEED_START=<seed> SEEDS=1          # rerun exactly one program
make test-random CORE=pipe SEED_START=<seed> SEEDS=1 WAVES=1  # plus sim_build/tb_top_pipe/dump.vcd
```
