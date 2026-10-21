# 08 · Bugs found

## What you'll learn

- Every entry in `docs/bugs.md`, explained in plain words:
  - what went wrong;
  - why, in hardware terms;
  - which test caught it, and how;
  - the fix.
- The difference between a **real bug** and an **injected bug** (a mutation), and why the
  log keeps them apart.
- What the git history can and cannot show about each fix.
- How to tell the "hardest bug" story in an interview, honestly.

---

## 1. A worked example first: the single-cycle core that wasn't

During M4, the first CPI table came out like this (from the bug log, `docs/bugs.md:11`):

| Program | Core | CPI |
|---|---|---|
| bubble_sort | single | **1.595** |

That number is impossible. The single-cycle core finishes one instruction every cycle by
construction (chapter 04), so its CPI must be exactly 1.000. Nobody wrote a test for "CPI is
exactly 1". The bug was caught because a measured number contradicted what the design
guarantees.

**The cause.** The pipelined core's measurements were being filed under the wrong name.
Here's the chain:

1. **The core name came from an environment variable.** The harness learned which core it
   was driving from `CORE`.
2. **pytest passed the right value…** It ran the pipe simulation with `CORE=pipe` passed
   through cocotb's runner (`extra_env`).
3. **…but cocotb overwrote it.** cocotb 1.9's runner builds the simulator's environment
   from `extra_env`, then copies the parent's `os.environ` on top.
4. **Make had already exported an empty `CORE`.** `make` exports `CORE` to its children,
   even when it's empty (`Makefile:6`). So the empty value overwrote `pipe`.
5. **The harness fell back to `single`.** It saw no `CORE`, so it saved the *pipeline's*
   cycle counts and coverage under `single`.

**What was still correct:** the pipelined RTL really was built and really was checked by
the scoreboard. Only the *bookkeeping* was wrong.

That's the pattern of the most dangerous verification bugs. Nothing fails, and the reported
results are quietly wrong.

## 2. Real bugs vs injected bugs

`docs/bugs.md:3-5` defines the split:

- **Real bugs** are mistakes the tests found in the project's own code. That covers RTL,
  testbench or tests.
- **Injected bugs** (**mutations**) are mistakes put in on purpose to prove a test *can*
  fail. They are never counted as real bugs.

Keeping them apart matters for honesty. The headline is **"no RTL bug was found"**
(`docs/bugs.md:14-16`). The pipelined core passed every suite on its first run. Everything
below is either a verification-environment bug or a deliberate mutation.

## 3. Real bug 1: the `CORE` override (testbench, M4)

| | |
|---|---|
| **Symptom** | `make cpi` reported CPI 1.595 for the single-cycle core on bubble sort; no pipeline coverage was recorded |
| **Root cause** | cocotb 1.9's runner applies `os.environ` *over* `extra_env`; `make` exports `CORE` even when empty (`Makefile:6`); so the harness never saw `CORE=pipe` |
| **In hardware terms** | none in the RTL: both simulations were correct. The fault was in labelling the results of the pipelined DUT |
| **Caught by** | sanity-checking a measured result against what the design guarantees (single-cycle CPI must be 1.0) |

**The fix**, three changes that each close one hole:

1. **Pass the core in a way the environment can't override.** The runner now gives the
   simulator the **plusarg** `+CORE=<core>`, a command-line argument to the simulator
   itself (`tests/rtl/cocotb_runner.py:58`). The harness reads it with `cocotb.plusargs`
   (`tb/harness.py:40-45`). The runner's docstring records why
   (`tests/rtl/cocotb_runner.py:31-37`).
2. **Check the label against reality.** `_check_core_identity` looks for a signal only
   `core_pipe` has, and fails if `+CORE` disagrees with the hierarchy that was actually built
   (`tb/harness.py:105-112`).
3. **Turn the sanity check into a test.** Every program run on the single-cycle core must
   have `cycles == instructions`. Every run on the pipeline must match the timing formula
   exactly (`tests/rtl/test_core_programs.py:42-51`).

**What `git log -p` shows:** the plusarg, the identity check and the CPI assertions all
arrive in commit `e6c1b29`, together with the "run every suite on both cores" feature
(`git show e6c1b29 -- tests/rtl/cocotb_runner.py tb/harness.py`). The env-var version was
caught *before* it was committed, so there is no separate "fix" commit and no buggy version
in history. The bug was recorded in `docs/bugs.md` in commit `4385f00`.

**The interview lesson:** verification code is code, and it has bugs. The defence is to
make every measurement checkable against something known. Here: the CPI of a single-cycle
core, the identity of the DUT, and a timing formula that must add up exactly.

## 4. Real bug 2: a gap in the directed tests (M4)

| | |
|---|---|
| **Symptom** | the first mutation analysis showed "forwarding from x0" caught by **0 of 45** directed tests and "no load-use stall" by only **1 of 45** |
| **Root cause** | the existing x0 test never put a write to x0 right before a read of x0; its only such pair was separated by a jump, whose flush hid the hazard. No directed test used a load's result in the very next instruction |
| **In hardware terms** | forwarding compares `ex_mem_q.rd == ex_ctrl.rs1`. Without the `rd != 0` check (`rtl/core_pipe.sv:172-173`), a "write" to x0 in MEM would be forwarded to a reader of x0 in EX. A test can only see that if the two instructions are adjacent and the write's value isn't 0 |
| **Caught by** | `make mutation` (`tools/mutation_analysis.py`) |
| **Fix** | 5 directed hazard tests with hand-computed results (`tests/rtl/test_core_directed.py:281-382`). Now 1 of 50 and 2 of 50 directed tests catch those two mutations |

The five tests and what each pins down:

| Test | Lines | Targets |
|---|---|---|
| `hazard_x0_never_forwarded` | `287-307` | writes to x0 at distance 1, 2, 3, plus a load into x0, each followed by a read of x0 |
| `hazard_forwarding_distances` | `308-321` | EX/MEM, MEM/WB and the write-before-read bypass, on rs1 and rs2 |
| `hazard_forwarding_newest_wins` | `322-335` | the same register in both EX/MEM and MEM/WB |
| `hazard_load_use` | `336-359` | load result used as rs1, rs2, store data, load address and branch operand |
| `hazard_branch_and_jump_flush` | `360-382` | wrong-path ALU instructions and a wrong-path store after BEQ, JAL and JALR |

**What `git log -p` shows:** the hazard tests were added in `e6c1b29`. The mutation tool was
committed right after, in `13bd301`. So the "0 of 45" run happened on uncommitted work, and
the history shows only the result: the tests and the tool. The before/after numbers live in
`docs/bugs.md:12`.

**The interview lesson:** good coverage numbers didn't reveal this gap. The directed suite
already hit the x0 coverage bins. Only an experiment that *breaks the design* showed the
tests couldn't see the bug.

## 5. Another fix in the history, not in the bug log

Commit `43ac3b9`, "fix(tools): mutation analysis restores the pipeline's coverage and CPI
data afterwards", is a real bug in a tool.

- **The bug.** `make mutation` runs the test suites on 7 broken designs. Each run rewrote
  `build/coverage/pipe/` and `build/results/pipe/`. After the analysis, `make coverage` and
  `make cpi` would have reported data from the last *mutated* design.
- **The fix.** It backs up both directories first and restores them in a `finally:` block,
  so the restore also happens on Ctrl-C (`git show 43ac3b9`). The logic now lives in
  `tools/mutations.py:57-74`.

It isn't in `docs/bugs.md`, which logs bugs *found by the tests*. This one was found by
checking the files by hand (see Known gaps).

## 6. Injected bugs: the mutation table (M4)

The seven pipeline mutations are exact text substitutions in `rtl/core_pipe.sv`
(`tools/mutations.py:30-53`). Here they are in hardware terms, with how many tests catch
each (failing / run, from `make mutation`):

| Mutation | What breaks in hardware | Directed | Programs | Random |
|---|---|---|---|---|
| No EX/MEM forwarding (rs1) | an instruction needing the previous instruction's result reads the stale register value | 43/50 | 41/42 | 50/50 |
| No MEM/WB forwarding (rs2) | same, at distance 2, for the second operand. Load data can't reach rs2 either | 6/50 | 11/42 | 50/50 |
| Forwarding priority wrong (rs2) | when two in-flight instructions write the same register, the *older* value wins | 9/50 | 27/42 | 49/50 |
| Forwarding from x0 | a write to x0 in MEM is forwarded, so x0 appears non-zero | 1/50 | 16/42 | 9/50 |
| No write-before-read bypass (rs1) | at distance 3, ID reads the register file in the same cycle as its write and gets the old value | 21/50 | 36/42 | 50/50 |
| No load-use stall | the instruction after a load uses the load's address instead of its data | 2/50 | 7/42 | 35/50 |
| Flush squashes only IF, not ID | after a taken branch, the instruction in ID still executes | 50/50 | 42/42 | 50/50 |

The waveform of "No load-use stall" is chapter 05's figure, `docs/img/failing_waveform.png`.

## 7. Injected bugs: earlier milestones

These were applied by hand to a clean tree, the tests were run, and the change was reverted
(`docs/bugs.md:42-51`). They show that each layer of checking works:

| Mutation | Hardware meaning | Caught by | First report |
|---|---|---|---|
| `alu.sv`: SRA as a logical shift (M1) | sign bit not copied in from the left | the ALU unit test, edge values | `SRA(0x80000000, 0x00000001) = 0x40000000, expected 0xc0000000` |
| `lsu.sv`: LB zero-extends (M2) | a loaded byte ≥ 0x80 becomes positive | directed `load_lb`, 1 of 45 tests | `retire #1 ... lb x10, 0(x1)`: `rd_wdata core=0x00000083 model=0xffffff83` |
| `model/alu.py`: ISS SRA as a logical shift (M3) | **the golden model is wrong** | the official riscv-tests run on the ISS: `lui`, `sra`, `srai` | `rv32ui-sra failed test case 3 (gp=7)` |
| `branch_unit.sv`: BGE as `>` (M3) | `bge` with equal operands falls through | random tests, 35 of 50 seeds | `retire #287 ... bge x19, x19, .+8`: `next_pc core=0x0000047c model=0x00000480` |

**Two of these deserve a closer look:**

- **The ISS mutation** answers "who verifies the verifier?" (chapter 06). A wrong model is
  caught by tests that don't depend on the model.
- **The BGE mutation** shows why `next_pc` is on the retire port (chapter 04). The branch
  went to `0x47c` (fall-through) instead of `0x480` (taken), and the scoreboard flagged the
  exact instruction, number 287 of the program.

## 8. Reproducing a failure

From `docs/bugs.md:53-59`:

```bash
make test-random CORE=pipe SEED_START=<seed> SEEDS=1          # rerun exactly one program
make test-random CORE=pipe SEED_START=<seed> SEEDS=1 WAVES=1  # plus sim_build/tb_top_pipe/dump.vcd
gtkwave sim_build/tb_top_pipe/dump.vcd                        # every signal
```

`make waveform` does the whole loop for one mutation: inject, run, dump, restore, render
(`tools/failing_waveform.py:37-51`).

## 9. The "hardest bug" answer for interviews

Tell the `CORE` override story (section 3). It has everything interviewers look for:

- **A symptom that looked like success:** all tests passed.
- **A sanity check that caught it:** single-cycle CPI must be 1.0.
- **A root cause in a tool's subtle behaviour,** worth knowing: cocotb's environment
  precedence plus make's `export`.
- **A fix that removes the class of bug, not just the instance:** a plusarg, an identity
  check, and an exact cycle-count assertion.

Be honest that it was a testbench bug, not an RTL bug. Say why that's still the scarier
kind: wrong numbers with green tests.

## Known gaps

- **The bug log doesn't list everything that was fixed.** Commit `43ac3b9` (section 5) and
  commit `1e7ed00` aren't in it. `1e7ed00`, "report load address and read mask on the
  retire port so the scoreboard checks loads", closed a checking gap: before it, the
  scoreboard did not compare a load's address or byte mask. The log's rule, "every bug
  found by random tests goes in docs/bugs.md" (`CLAUDE.md:29`), is narrower than "every bug".
- **No before/after commits for the two real bugs.** Both were fixed before they were
  committed. The evidence for them is the bug log and the PR #4 description, not a diff.
- **The earlier-milestone mutations were applied by hand.** Their numbers ("35 of 50 seeds",
  "1 of 45") were measured at the time and can't be regenerated by a command. Only the M4
  mutation table is reproducible (`make mutation`).

## Check yourself

1. What was the symptom of the `CORE` override bug, and why was it impossible on its face?
2. Why did fixing it with a plusarg work where the environment variable didn't?
3. Why couldn't a directed test catch "forwarding from x0" before M4's hazard tests?
4. Which injected bug shows that the golden model is itself checked, and by what?
5. What's the difference between a real bug and an injected bug in this repo's log?

<details>
<summary>Answers</summary>

1. The single-cycle core was reported at CPI 1.595. It completes one instruction per cycle
   by construction, so its CPI must be exactly 1.0.
2. A plusarg is passed on the simulator's command line (`+CORE=pipe`,
   `tests/rtl/cocotb_runner.py:58`), so the environment-merging order in cocotb's runner
   can't overwrite it. The harness also verifies it against the built hierarchy
   (`tb/harness.py:105-112`).
3. No directed test put a write to x0 *immediately* before a read of x0. The only such
   pair was split by a jump whose flush hid the hazard.
4. The ISS SRA mutation (`model/alu.py`). The official riscv-tests run on the ISS caught it
   (`rv32ui-sra failed test case 3`).
5. Real bugs are mistakes found in the project's own code (here, verification code).
   Injected bugs are deliberate mutations used to prove tests can fail, and they're never
   counted as real bugs (`docs/bugs.md:3-5`).

</details>
