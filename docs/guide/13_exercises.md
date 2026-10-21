# 13 · Exercises

## What you'll learn

- How to work with the code yourself: read waveforms, add a test, break the pipeline on
  purpose, add coverage, extend the random generator, add an instruction end to end.
- How a change ripples through RTL, golden model, tests, coverage and reports.

**Ground rules:**
- Work on a branch (`git switch -c exercises`), and undo with `git checkout -- .`.
- Every solution at the end was applied to a clean checkout and run against the real test
  suite while writing this guide. The results quoted are those runs.
- Exercises get harder as you go. Hints are inline; full solutions are at the end.

| # | Exercise | Difficulty | Time |
|---|---|---|---|
| 1 | Decode three instructions by hand | ★ | 15 min |
| 2 | Run one test with a waveform and find forwarding in GTKWave | ★ | 20 min |
| 3 | Read the failing-test waveform | ★ | 15 min |
| 4 | Add a directed test | ★★ | 20 min |
| 5 | Break forwarding by hand and read the scoreboard report | ★★ | 20 min |
| 6 | Add your own mutation | ★★ | 20 min |
| 7 | Add a coverpoint | ★★★ | 30 min |
| 8 | Check the timing formula on random programs too | ★★★ | 30 min |
| 9 | Add a random-program block and measure its effect | ★★★ | 45 min |
| 10 | Add the MUL instruction end to end | ★★★★ | 90 min |

---

## Worked example first: the shape of every exercise

Exercise 4 is typical. You will:
1. **Make a change:** add a `Case` to `tests/rtl/test_core_directed.py`.
2. **Predict the result:** both cores should pass, and the directed count goes from 50 to 51.
3. **Run the narrowest command** that shows it:
   `.venv/bin/python -m pytest tests/rtl/test_core_directed.py -q`.
4. **Check the prediction**, and if it's wrong, understand why before moving on.

Predicting first is the habit that makes you useful in a verification team. A test that
does something you didn't expect is information.

---

## Exercise 1 ★: decode three instructions by hand

Decode these three words from the `hazard_load_use` program. Use chapter 02's format
diagrams. Write down the format, every field, and the assembly.

```
0x00548463    0x0080a583    0x0060a423
```

*Hint:* start with bits [6:0] to find the format. For the third one, the immediate's low bits
are where `rd` would be.

Check yourself with the repo's own decoder:

```bash
.venv/bin/python -c "from model.decoder import decode, to_asm; [print(hex(w), to_asm(decode(w))) for w in (0x00548463, 0x0080a583, 0x0060a423)]"
```

## Exercise 2 ★: run one test with a waveform and find forwarding

Run just `directed_hazard_forwarding_distances` on the pipelined core with a VCD dump, then
open it:

```bash
CORE=pipe WAVES=1 TESTCASE=directed_hazard_forwarding_distances \
    .venv/bin/python -m pytest tests/rtl/test_core_directed.py -q
gtkwave sim_build/tb_top_pipe/dump.vcd
```

In GTKWave, add these signals from `TOP.tb_top.u_core`:
- `clk`;
- `fwd_a_sel` and `fwd_b_sel`;
- `stall_load_use`;
- `ex_rs1` and `ex_rs2`;
- `mem_wb_q` (shown as one wide vector).

Then answer:

1. In which cycles is `fwd_a_sel` non-zero, and which value (1 or 2) does each show?
2. In the cycle both operands are forwarded at once, which instruction is in EX?
3. Why is `stall_load_use` never 1 in this test?

*Hint:* count cycles from the first falling edge after `rst_n` rises. Compare with the first
table in chapter 05.

## Exercise 3 ★: read the failing-test waveform

Open `docs/img/failing_waveform.png` (or run `make waveform`, which regenerates it in about
20 seconds). Answer from the image alone:

1. Which instruction is in EX in the orange column, and which is in MEM?
2. What is `fwd_a_sel` in that column, and what value does EX use for rs1?
3. Why does the scoreboard report the problem two cycles later, not in the orange cycle?
4. What should `stall_load_use` have been in the orange column's *previous* cycle?

## Exercise 4 ★★: add a directed test

RV32I has no NOT or NEG instruction. Software uses `xori rd, rs, -1` and `sub rd, x0, rs`.
Add a directed case `not_and_neg` that:
- loads `0x0F0F0F0F` into x1;
- computes NOT x1 into x2 and NEG x1 into x3;
- checks both with **hand-computed** `expect` values.

*Hint:* copy the shape of the `lui` case (`tests/rtl/test_core_directed.py:74-85`). The new
case must be appended *before* the "One cocotb test per case" section, line 385, so the loop
at the end picks it up.

**Predict, then run:** `.venv/bin/python -m pytest tests/rtl/test_core_directed.py -q`. How
many directed tests run now?

## Exercise 5 ★★: break forwarding by hand

In `rtl/core_pipe.sv:178`, change

```systemverilog
      if (exmem_writes && ex_mem_q.rd == ex_ctrl.rs1)      fwd_a_sel = FWD_EXMEM;
```

to `if (1'b0)` so EX/MEM forwarding never happens for rs1. Then:

1. **Predict:** will `make test-rtl CORE=single` fail? And `make test-rtl CORE=pipe`?
2. Run `.venv/bin/python -m pytest tests/rtl/test_core_directed.py -q` with `CORE=pipe`. Read
   the first `ScoreboardMismatch` in the output.
3. Explain the reported instruction and both values from the program text. The failing test
   is `directed_alu_add`; its program is built at `tests/rtl/test_core_directed.py:49-54`.
4. Restore the file: `git checkout -- rtl/core_pipe.sv`.

*Hint:* `li(1, 0x12345678)` expands to two instructions (chapter 02).

## Exercise 6 ★★: add your own mutation

Add an eighth mutation to `tools/mutations.py`: **"JALR does not redirect"**. Remove
`ex_ctrl.is_jalr ||` from the `ex_redirect` expression (`rtl/core_pipe.sv:231-232`).

1. **Predict** which directed tests fail on the pipelined core.
2. Check the substitution matches exactly once: `inject()` asserts that
   (`tools/mutations.py:77-80`).
3. Run only the directed suite with the mutation (faster than `make mutation`):

   ```bash
   .venv/bin/python - <<'EOF'
   import os, subprocess, sys
   from tools.mutations import MUTATION_BY_NAME, TARGET, inject, protected_outputs
   with protected_outputs():
       inject(MUTATION_BY_NAME["JALR does not redirect"], TARGET.read_text())
       subprocess.run([sys.executable, "-m", "pytest", "tests/rtl/test_core_directed.py", "-q"],
                      env={**os.environ, "CORE": "pipe"})
   EOF
   ```

4. Which retire-port field reports the bug, and why that one?

## Exercise 7 ★★★: add a coverpoint

Add a coverpoint `shift_imm` with two bins: `shamt_0` and `shamt_31`. They count immediate
shifts (`slli`, `srli`, `srai`) by 0 and by 31, the two edge amounts.

*Hints:*
- Bins are declared in `COVERPOINTS` (`tb/coverage.py:42-50`).
- Sampling happens in `sample()`. The variable `is_shift` already exists
  (`tb/coverage.py:100`).
- `tests/model/test_coverage.py:24` asserts the total bin count. Update it, and add a small
  test in the style of `test_x0_and_immediate_sign` (`tests/model/test_coverage.py:58-60`).
- Run `make test` and then `make coverage`. Which suites hit both new bins?

## Exercise 8 ★★★: check the timing formula on random programs

`test_core_programs.py` asserts the cycle formula for the C programs and riscv-tests
(`tests/rtl/test_core_programs.py:43-51`). The random suite doesn't check it. Add the same
assertion to `run_seed` in `tests/rtl/test_core_random.py`:
- `cycles == instructions` on the single-cycle core;
- `cycles == instructions + 4 + stalls + 2 × (flushes − 1)` on the pipeline.

*Hints:*
- `core_name()` is in `tb/harness.py:40-45`.
- **Predict:** will it hold for random programs, which jump forward by as little as 4 bytes
  (a "taken" branch to pc + 4)? Why?

## Exercise 9 ★★★: a random block that targets load-use

The mutation table shows "No load-use stall" caught by only 35 of 50 random seeds. Random
programs rarely use a loaded value in the very next instruction.

1. Add a block `load_use` to `tb/random_program.py`:
   - set a base register to an aligned data address with `emit_li`;
   - `lw` into a non-zero register;
   - immediately use that register in an `add`.
2. Give it weight 5 in `BLOCK_WEIGHTS` (`tb/random_program.py:42-51`).
3. Run `make test-model`. `tests/model/test_random_program.py` proves your programs are
   still legal on the ISS.
4. Run `make test-random`.
5. Re-measure: with your block, how many of the 50 seeds catch "No load-use stall"? Use
   the script from exercise 6 with that mutation and `tests/rtl/test_core_random.py`.

*Hint:* `self.dest(exclude=(0,))` gives a destination other than x0. Why must the load's
destination not be x0 here?

**Think about it:** adding a block changes `rng.choices` for every seed, so *every* random
program changes. What does that mean for reproducing an old failing seed after this change?

## Exercise 10 ★★★★: add MUL end to end

Add `mul rd, rs1, rs2` (M extension: the low 32 bits of rs1 × rs2) to both cores and the
golden model. Encoding: R-type, opcode `0110011`, funct3 `000`, funct7 `0000001`.

**Plan before typing.** List every file that must change. There are more than you think:
- the ISA table;
- the reference ALU and the ISS's operation map;
- the RTL enum, ALU and decoder;
- a directed test;
- and three existing tests that will *break* because they assumed RV32I only.

*Hints:*
- `alu_op_e` is `{funct7[5], funct3}`. MUL's funct7[5] is 0 and its funct3 is 000, so the
  existing formula would decode it as ADD. Pick an unused code (`4'b1001` is free) and
  special-case funct7 = `0000001` in the decoder.
- The decoder currently flags MUL as illegal. Find where (`rtl/decoder.sv:110-115`).
- Search the tests for the word `mul` and for `-march=rv32i`.
- The opcode coverpoint is built from `SPECS` (`tb/coverage.py:43`). What happens to the
  bin count, and which test checks it?
- Finish with `make lint && make test && make coverage`. Everything must pass, at 100%
  coverage.

---

## Solutions

### Solution 1

| Word | Format | Fields | Assembly |
|---|---|---|---|
| `0x00548463` | B | opcode 1100011, funct3 000 (BEQ), rs1 = 9, rs2 = 5, imm = 8 | `beq x9, x5, .+8` |
| `0x0080a583` | I | opcode 0000011, funct3 010 (LW), rd = 11, rs1 = 1, imm = 8 | `lw x11, 8(x1)` |
| `0x0060a423` | S | opcode 0100011, funct3 010 (SW), rs1 = 1, rs2 = 6, imm = 0000000 ++ 01000 = 8 | `sw x6, 8(x1)` |

All three appear in the real trace of `hazard_load_use`, at pc 0x28, 0x30 and 0x18 (chapter 04).

### Solution 2

From the real run (chapter 05, first table):

1. **Cycles 4, 5, 7 and 8.** Cycle 4 shows 1 (EX/MEM); cycles 5 and 7 show 2 (MEM/WB). In
   cycle 8, a = 2 (MEM/WB) and b = 1 (EX/MEM).
2. **Cycle 8:** `sub x6, x4, x5`. x4 comes from MEM/WB, two instructions back; x5 comes from
   EX/MEM, one back.
3. **The program has no loads**, and `stall_load_use` requires a load in EX
   (`rtl/core_pipe.sv:147`).

### Solution 3

1. **EX:** `add x3, x2, x0`. **MEM:** `lw x2, 0(x1)`.
2. **`fwd_a_sel` = EX/MEM** and **rs1 = 0x2000**. That's the `lw`'s address, held in
   `ex_mem_q.result`, not its data.
3. **The scoreboard only sees instructions when they retire,** in WB. The `add` reaches WB
   two cycles after leaving EX.
4. **1.** The `add` was in ID with the `lw` in EX: a load-use pair. The mutation forces the
   stall to 0.

### Solution 4

Insert before `# ---- One cocotb test per case` (`tests/rtl/test_core_directed.py:385`):

```python
CASES.append(
    Case(
        "not_and_neg",  # NOT and NEG have no instruction of their own in RV32I
        program(
            li(1, 0x0F0F_0F0F),
            e("xori", rd=2, rs1=1, imm=-1),  # NOT x1
            e("sub", rd=3, rs1=0, rs2=1),  # NEG x1 = 0 - x1
        ),
        expect={2: 0xF0F0_F0F0, 3: 0xF0F0_F0F1},
    )
)
```

**The expected values by hand:**
- NOT flips every bit: `0x0F0F0F0F` → `0xF0F0F0F0`.
- NEG is NOT + 1 (two's complement): `0xF0F0F0F1`.

**Verified run:** pytest reports `2 passed`, one per core, and the pipelined core's results
file now lists **51** directed tests.

### Solution 5

1. **The single-cycle core still passes:** `core_single.sv` has no forwarding. **The pipeline
   fails.**
2. **43 of 50 directed tests fail** on the pipeline in the verified run. The first report:

   ```
   ScoreboardMismatch: retire #17 mismatch at pc=0x00000044: addi x1, x1, 1656
     rd_wdata   core=0x00000678  model=0x12345678
   last 8 retired instructions:
     ...
     pc=0x00000040  lui x1, 0x12345              x1=0x12345000
   ```

3. **Why:** `li(1, 0x12345678)` is `lui x1, 0x12345` then `addi x1, x1, 0x678` (1656). The
   `addi` needs x1 from the instruction right before it, the EX/MEM path. Without that path,
   EX uses the stale x1 (0, from earlier in the program), so the result is 0 + 0x678 =
   `0x678` instead of `0x12345678`.

   This shows how common distance-1 dependencies are: the `li` pseudo-instruction alone
   creates one.

### Solution 6

Append a new entry at the end of the `MUTATIONS` list in `tools/mutations.py`:

```python
MUTATIONS = [
    # ... the 7 existing entries ...
    Mutation(
        "JALR does not redirect",
        "(ex_ctrl.is_jal || ex_ctrl.is_jalr || (ex_ctrl.is_branch && branch_taken))",
        "(ex_ctrl.is_jal || (ex_ctrl.is_branch && branch_taken))",
    ),
]
```

**Verified run:** exactly **2 of 50** directed tests fail, `directed_jalr` and
`directed_hazard_branch_and_jump_flush`. The first report:

```
ScoreboardMismatch: retire #1 mismatch at pc=0x00000004: jalr x2, 1(x1)
  next_pc    core=0x00000008  model=0x00000010
```

**The field is `next_pc`.** The JALR still writes its link register correctly
(`rd_wdata = 8` matches), but the core falls through to pc + 4 instead of jumping to 16. Only
`next_pc` reveals where execution goes next. That's why it's on the retire port (chapter 04).

### Solution 7

In `tb/coverage.py`, add the bins:

```python
    "raw_hazard": [f"{src}_dist{d}" for src in ("rs1", "rs2") for d in (1, 2, 3)] + ["load_use"],
    "shift_imm": ["shamt_0", "shamt_31"],
}
```

…and sample them right after the `imm_sign` block:

```python
            self.hit("imm_sign", f"{fmt.name}_{'neg' if instr.imm < 0 else 'pos'}")
        if is_shift and instr.imm in (0, 31):
            self.hit("shift_imm", f"shamt_{instr.imm}")
```

In `tests/model/test_coverage.py`, change `== 90` to `== 92` and add:

```python
def test_shift_amount_edges():
    cov = covered([e("slli", rd=1, rs1=1, imm=0), e("srai", rd=1, rs1=1, imm=31)])
    assert {"shift_imm.shamt_0", "shift_imm.shamt_31"} <= hits(cov)
```

**Verified run:**
- `test_coverage.py`: 7 passed.
- `make test-rtl`: passed.
- `make coverage`:
  - single: directed 92/92, programs 91/92, random 90/92, all suites **92/92**;
  - pipe: **105/105** in total.
  - `shift_imm` is 2/2 in every suite. Directed hits it through `SHIFT_AMOUNTS = [0, 1, 15, 31]`
    (`tests/rtl/test_core_directed.py:59`); random through `randrange(32)`.

### Solution 8

In `tests/rtl/test_core_random.py`, import `core_name` from `tb.harness` and add after
`result = await harness.run(...)`:

```python
    if core_name() == "pipe":
        expected = result.retired + 4 + result.stall_cycles + 2 * (result.flushes - 1)
    else:
        expected = result.retired
    assert result.cycles == expected, f"seed {seed}: {result.cycles} cycles, model {expected}"
```

**Verified run:** both cores pass all 50 seeds, and ruff is clean.

**It holds even for "taken to pc + 4" branches.** The hardware doesn't compare the target
with pc + 4: a taken branch always redirects and flushes (`rtl/core_pipe.sv:231-235`). So it
costs 2 cycles and counts as a flush, exactly as the formula assumes.

### Solution 9

In `tb/random_program.py`, add `"load_use": 5,` to `BLOCK_WEIGHTS`, and this method before
`block_fence`:

```python
    def block_load_use(self) -> None:
        """A word load whose result is used by the very next instruction."""
        addr = DATA_BASE + 4 * self.rng.randrange(DATA_BYTES // 4)
        base = self.rng.randrange(1, 32)
        rd = self.dest(exclude=(0,))
        self.emit_li(base, addr)
        self.emit(e("lw", rd=rd, rs1=base, imm=0), rd)
        consumer = self.dest()
        self.emit(e("add", rd=consumer, rs1=rd, rs2=self.source()), consumer)
```

**Why the destination must not be x0:** a load into x0 creates no dependency, because the
pipeline never stalls or forwards for x0 (`rtl/core_pipe.sv:147`).

**Verified run:**
- `test_random_program.py`: 204 passed.
- `test_core_random.py` on both cores: passed.
- Random coverage unchanged: 88/90 and 101/103.
- **"No load-use stall" now caught by 50 of 50 seeds**, up from 35 of 50 measured on the
  unmodified generator in the same session.

**This is the coverage lesson from chapter 07 in action:** the coverage number didn't
change at all, but the suite's bug-finding power did.

**On reproducibility:** after this change, seed N produces a different program than
before. A failing seed recorded with the old generator can only be reproduced on the old
commit. Note the commit hash together with the seed.

### Solution 10

These are the changes, all verified together (`make lint`: clean; `tests/model`: 430 passed;
`tests/rtl`: all passed; coverage **91/91** single and **104/104** pipe).

| File | Change |
|---|---|
| `model/isa.py` | after the `and` entry: `InstrSpec("mul", Fmt.R, Opcode.OP, 0b000, 0b0000001),  # M extension` |
| `model/alu.py` | `MUL = 0b1001` in `AluOp`; `case AluOp.MUL: return to_u32(a * b)` |
| `model/iss.py` | `"mul": AluOp.MUL` in `ALU_OPS` |
| `rtl/rv32i_pkg.sv` | `ALU_MUL  = 4'b1001,` after `ALU_SUB` |
| `rtl/alu.sv` | `ALU_MUL:  y = a * b;  // low 32 bits` |
| `rtl/decoder.sv` | OP case, shown below |
| `tests/rtl/test_core_directed.py` | add `"mul"` to the R-type op list (`49`), giving a new `alu_mul` case checked by the scoreboard |
| `tests/model/test_encoder.py` | the illegal-word list used `0x022081B3` (mul) as an example of an *unsupported* instruction; replace it with `0x022091B3` (mulh, still unsupported) |
| `tests/model/test_encoder.py` | the GNU `as` cross-check assembles every `SPECS` entry with `-march=rv32i`, which rejects `mul`; change it to `-march=rv32im` |
| `tests/model/test_coverage.py` | bin count `90` → `91` (the opcode coverpoint gains a bin automatically) |

The decoder's OP case:

```systemverilog
      OPC_OP: begin
        ctrl.reg_write = 1'b1;
        if (funct7 == 7'b0000001) begin            // M extension: only MUL is supported
          ctrl.alu_op  = ALU_MUL;
          ctrl.illegal = (funct3 != 3'b000);
        end else begin
          ctrl.alu_op  = alu_op_e'({funct7[5], funct3});
          // funct7 = 0100000 is only valid for SUB (000) and SRA (101).
          ctrl.illegal = !funct7_ok || (funct7[5] && funct3 != 3'b000 && funct3 != 3'b101);
        end
      end
```

**What didn't need changing**, and is worth noticing:
- **The pipeline:** MUL is just another ALU operation, with the same forwarding and hazards.
- **The scoreboard and the retire port.**
- **`model/decoder.py`:** its lookup is built from `SPECS`, and R-type keys include funct7.
- **The ALU unit test:** it iterates over `AluOp`, so it now tests MUL on edge values and
  1,000 random pairs automatically.

**The lesson:** three *existing* tests broke because they encoded the assumption "RV32I only".
That is normal, and it's why "list every file first" is the real first step.

**What a real design would think about:** a 32 × 32 multiplier in one cycle is large and slow.
Real cores pipeline it or take several cycles. Running `make synth` before and after would
show the cost; this guide didn't measure it.

## Check yourself

1. In exercise 5, why does the single-cycle core still pass?
2. In exercise 6, why is `next_pc` the field that exposes the bug?
3. In exercise 9, coverage stayed the same but detection rose from 35/50 to 50/50. What does that say about the coverage model?
4. In exercise 10, which three existing tests had to change, and why?

<details>
<summary>Answers</summary>

1. It has no forwarding logic: each instruction reads registers that were written at the
   end of the previous cycle. The edited line exists only in `core_pipe.sv`.
2. The JALR's register write is still correct. Only its control-flow effect, where execution
   continues, is wrong, and `next_pc` is the field that reports control flow.
3. The bins measure whether load-use pairs occur at least once, not how often or in which
   combinations. Bug-finding power depends on that, so the coverage model is too coarse to
   track it (chapter 07).
4. Here are the three:
   - `test_encoder.py`'s illegal-word list, which used MUL as an unsupported example;
   - its GNU `as` cross-check, which assembled with `-march=rv32i`;
   - `test_coverage.py`'s bin count.

   All three hard-coded "RV32I only".

</details>
