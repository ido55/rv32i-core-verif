# Bug log

Every RTL bug found by the tests is recorded here: symptom, root cause, fix, and the test
that caught it, so it can be reproduced. Injected bugs (deliberate mutations used to prove
that a test *can* fail) are kept in a separate table and are never counted as real bugs.

## Real bugs

| # | Found in | Symptom | Root cause | Fix | Caught by |
|---|---|---|---|---|---|
| — | — | none yet | — | — | — |

**Single-cycle core (M2-M3):** the random tests have not found an RTL bug. Measured:

- CI: seeds 1-50 on every push (`make test-random`), 50 / 50 pass.
- One-off sweep: seeds 1000-2999, 2000 / 2000 pass, 157 s wall time
  (`make test-random SEED_START=1000 SEEDS=2000`).

The directed tests (45), the official rv32ui suite (40 tests) and the two C programs also
pass, so this is a reasonable but not a complete result: random testing can only show the
bugs it happens to reach. The pipelined core (M4) is where hazards make bugs likely.

## Injected bugs (test-quality checks, not real bugs)

Each mutation was applied to a clean tree, the tests were run, and the change was reverted
with `git checkout`.

| Mutation | Tests that caught it | First failure reported |
|---|---|---|
| `alu.sv`: SRA as logical shift (M1) | `test_alu` | `SRA(0x80000000, 0x00000001) = 0x40000000, expected 0xc0000000` |
| `lsu.sv`: LB zero-extends (M2) | directed `load_lb` (1 of 45 directed tests) | `retire #1 ... lb x10, 0(x1)`: `rd_wdata core=0x00000083 model=0xffffff83` |
| `model/alu.py`: ISS SRA as logical shift (M3) | riscv-tests on the ISS: `lui`, `sra`, `srai` | `rv32ui-sra failed test case 3 (gp=7)` |
| `branch_unit.sv`: BGE as `>` (M3) | random: 35 of 50 seeds | `retire #287 ... bge x19, x19, .+8`: `next_pc core=0x0000047c model=0x00000480` |

## How to reproduce a random failure

```bash
make test-random SEED_START=<seed> SEEDS=1          # rerun exactly one program
make test-random SEED_START=<seed> SEEDS=1 WAVES=1  # plus a waveform in sim_build/tb_top/dump.vcd
```
