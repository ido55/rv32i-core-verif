# 11 · Code reference

## What you'll learn

- For every source file in the repository:
  - its purpose;
  - its key modules, functions or classes, with line numbers;
  - its inputs and outputs;
  - which other files use it.
- Use it as a lookup table while reading the code, or before an interview when you need to
  find "where does X happen" fast.

A worked example of how to use this chapter: *"Where is the load-use stall decided, and
who reads that signal?"*

1. Look up `rtl/core_pipe.sv` below. "ID" lists `stall_load_use` at lines 145-150.
2. "Used by" lists `tb/harness.py` (stall counting) and `tb/coverage.py` (the
   `stall_load_use` bin).
3. `tools/mutations.py` lists the mutation that disables it.

---

## `rtl/`: hardware

### `rtl/rv32i_pkg.sv`
- **Purpose.** Shared constants and types for both cores.
- **Contents.**
  - opcodes `OPC_*` (`7-17`);
  - `INSN_ECALL`/`INSN_EBREAK` (`19-20`);
  - funct3 values for branches and loads/stores (`23-34`);
  - enums `alu_op_e` (`38-49`), `alu_a_sel_e` (`52-56`) and `wb_sel_e` (`59-63`);
  - the control struct `ctrl_t` (`66-86`).
- **Used by.** Every RTL module except `regfile.sv` (`import rv32i_pkg::*`). Must be
  compiled first (`Makefile:12`, `tb/harness.py:33-37`).
- **Note.** `alu_op_e` values must equal `model/alu.py:AluOp`.

### `rtl/decoder.sv`, module `decoder`
- **Purpose.** Turn one instruction into control signals. Purely combinational.
- **Inputs.** `insn[31:0]`. **Outputs.** `ctrl` (`ctrl_t`).
- **Structure.**
  - field extraction (`14-16`) and the five immediates (`21-25`);
  - defaults (`33-40`);
  - opcode `case` (`42-127`);
  - `uses_rs1`/`uses_rs2` (`131-132`);
  - illegal clean-up (`135-144`).
- **Used by.** `core_single.sv:62-65`, `core_pipe.sv:121-124`.

### `rtl/alu.sv`, module `alu`
- **Purpose.** The 10 RV32I arithmetic/logic operations.
- **Inputs.** `op` (`alu_op_e`), `a`, `b`. **Outputs.** `y`.
- **Key lines.** Shift amount `b[4:0]` (`12-13`); operation `case` (`15-29`).
- **Used by.** Both cores (`core_single.sv:90-95`, `core_pipe.sv:216-221`);
  `tests/rtl/test_alu.py`.

### `rtl/regfile.sv`, module `regfile`
- **Purpose.** 32 × 32-bit registers.
- **Inputs.** `clk`, `rst_n`, `rs1_addr`, `rs2_addr`, `we`, `rd_addr`, `rd_data`.
- **Outputs.** `rs1_data`, `rs2_data`.
- **Behaviour.**
  - synchronous reset clears all registers (`20-26`);
  - writes to x0 are ignored (`23`);
  - x0 reads as 0 (`28-29`);
  - no internal bypass, so a read in the cycle of a write returns the old value.
- **Used by.** Both cores; `tests/rtl/test_regfile.py`; `tb/harness.py:249-253`
  (`read_reg` reads `regs_q` directly).

### `rtl/branch_unit.sv`, module `branch_unit`
- **Purpose.** Decide whether a branch is taken.
- **Inputs.** `funct3`, `a`, `b`. **Outputs.** `taken` (`11-21`).
- **Used by.** `core_single.sv:97-102`, `core_pipe.sv:223-228`.

### `rtl/lsu.sv`, module `lsu`
- **Purpose.** Byte/halfword handling between the core and a word-wide memory.
- **Inputs.** `funct3`, `byte_offset`, `store_data`, `mem_rdata`.
- **Outputs.**
  - `byte_mask` (`23-30`);
  - `store_wdata`, lane-shifted (`32-38`);
  - `load_data`, extracted and sign/zero-extended (`20-21,40-48`).
- **Used by.** `core_single.sv:117-125`, `core_pipe.sv:260-268`.

### `rtl/core_single.sv`, module `core_single`
- **Purpose.** The single-cycle RV32I core.
- **Ports** (`7-38`).
  - Inputs: `clk`, `rst_n`, `imem_rdata`, `dmem_rdata`.
  - Outputs: `imem_addr`, `dmem_addr`, `dmem_wmask`, `dmem_wdata`, `halted`, and the
    retire port `rvfi_*`.
- **Sections.**
  - fetch/decode (`59-77`);
  - execute (`79-102`);
  - next pc (`104-114`);
  - memory (`116-128`);
  - write-back (`130-137`);
  - state `pc_q`, `halted_q` (`139-148`);
  - retire port (`152-167`).
- **Used by.** `tb/tb_top.sv:52`; `tools/synth_report.py`.

### `rtl/core_pipe.sv`, module `core_pipe`
- **Purpose.** The 5-stage pipelined RV32I core. Same ports as `core_single`.
- **Sections.**
  - header comment summarising the hazards (`1-14`);
  - pipeline-register structs (`48-93`);
  - IF (`112-113`);
  - ID: decoder, regfile, bypass, `stall_load_use` (`115-159`);
  - EX: forwarding select and muxes, ALU, branch, `ex_redirect`, `flush`, `ex_halt`
    (`161-251`);
  - MEM (`253-287`);
  - register update block (`289-323`);
  - retire port (`327-342`);
  - coverage-only signals `cov_*` (`344-361`).
- **Used by.**
  - `tb/tb_top.sv:50`;
  - `tb/harness.py`, which reads `stall_load_use`, `flush` and `u_regfile`;
  - `tb/coverage.py:124-145`, which reads `fwd_*_sel`, `stall_load_use` and `cov_*`;
  - `tools/mutations.py`, which edits it;
  - `tools/failing_waveform.py`, which reads its VCD signals.

---

## `tb/`: testbench

### `tb/tb_top.sv`, module `tb_top`
- **Purpose.** The simulation top: one core plus two 4,096-word memories.
- **Parameter.** `MEM_WORDS = 4096` (`9-11`).
- **Ports.** `clk`, `rst_n` in. `halted`, `mem_fault` and `rvfi_*` out (`12-30`).
- **Contents.**
  - memories (`36-38`);
  - core selection by `` `ifdef PIPELINED `` (`49-53`);
  - combinational reads (`62-63`);
  - byte-enabled writes (`65-69`);
  - `mem_fault` (`74-82`).
- **Used by.** `tb/harness.py` (`CORE_SOURCES`, `33-37`); `Makefile` lint (`18`).

### `tb/harness.py`
- **Purpose.** Load, run and check a core. This is the scoreboard.
- **Constants.**
  - `COVERAGE_DIR`, `RESULTS_DIR` (`27-28`);
  - `MEM_WORDS` (`29`);
  - `CLOCK_PERIOD_NS = 10` (`31`);
  - `CORE_SOURCES` (`33-37`).
- **Functions.**
  - `core_name()` (`40-45`), `new_coverage()` (`48-49`), `coverage_path()` (`52-53`),
    `results_path()` (`56-57`);
  - `disasm()` (`64-68`), `format_retire()` (`71-79`).
- **Classes.**
  - `ScoreboardMismatch(AssertionError)` (`60-61`);
  - `RunResult` (`82-92`): `retired`, `cycles`, `trace`, `stall_cycles`, `flushes`, `cpi`;
  - `CoreHarness` (`95-259`), described below.
- **`CoreHarness` methods.**

  | Method | Lines | Does |
  |---|---|---|
  | `__init__` / `_check_core_identity` | `96-112` | stores the DUT handle, checks `+CORE` matches the hierarchy |
  | `load(program, data)` | `116-134` | same image into imem, dmem and a new `Iss` |
  | `_reset()` | `136-144` | starts the clock once, holds `rst_n` low 2 cycles |
  | `run(max_cycles, expect_trap)` | `148-202` | the per-cycle loop; returns a `RunResult` |
  | `_read_retire()` | `206-219` | retire-port signals → `Retire` |
  | `_check(got, trace)` | `221-236` | `iss.step()` and field-by-field comparison |
  | `_check_final_state()` | `238-247` | x1–x31 and all of dmem |
  | `read_reg(n)` | `249-253` | a register straight from the RTL |
  | `_report(...)` | `255-259` | message plus the last 8 retired instructions |

- **Used by.** All three `tests/rtl/test_core_*.py`; `tb/coverage_report.py`,
  `tb/cpi_report.py` and `tools/plot_results.py` (directory constants).

### `tb/coverage.py`
- **Purpose.** The functional coverage collector.
- **Data.**
  - `COVERPOINTS`, 7 points / 90 bins (`42-50`);
  - `PIPELINE_BINS`, 13 bins (`53-59`);
  - `FWD_EXMEM`, `FWD_MEMWB` (`61`).
- **Class `Coverage`.**
  - `__init__(pipelined)` (`65-70`), `hit` (`72-73`), `reset_history` (`75-77`);
  - `sample(retire)` (`79-105`) and `_sample_hazards` (`107-122`);
  - `sample_pipeline(core)` (`124-145`);
  - `merge`, `summary`, `percent`, `missing`, `save`, `load` (`149-181`).
- **Used by.** `tb/harness.py` (sampling), `tb/coverage_report.py`,
  `tests/model/test_coverage.py`, and the three core test modules (via `new_coverage`).

### `tb/coverage_report.py`
- **Purpose.** `make coverage`: merge `build/coverage/<core>/*.json` and print Markdown tables.
- **Functions.** `report_core` (`10-30`), `main` (`41-48`).

### `tb/cpi_report.py`
- **Purpose.** `make cpi`: read `build/results/<core>/programs.json` and print the CPI
  table (`15-39`).

### `tb/programs.py`
- **Purpose.** Build test programs with GCC into word lists.
- **Constants.** `COMMON_FLAGS`, `C_FLAGS` (`25-37`); `RISCV_TESTS_EXCLUDED` (`40-43`);
  `IMAGE_BYTES` (`23`).
- **Functions.**
  - `toolchain_available` (`46-47`);
  - `_rebuild_needed` (`50-53`), `_link` (`56-60`), `elf_to_image` (`63-72`);
  - `riscv_test_names` (`84-86`), `build_riscv_test` (`89-101`);
  - `_expected_fibonacci` (`107-111`), `_expected_bubble_sort` (`114-126`);
  - `C_PROGRAMS` (`130`), `build_c_program` (`133-137`).
- **Used by.** `tests/rtl/test_core_programs.py`, `tests/model/test_programs_iss.py`,
  `tb/cpi_report.py`, `tools/plot_results.py`.

### `tb/random_program.py`
- **Purpose.** Seeded constrained-random program generator.
- **Data.**
  - `DATA_BASE = 0x2000`, `DATA_BYTES = 0x800` (`25-27`);
  - `INTERESTING_VALUES`/`IMMEDIATES` (`36-40`);
  - `BLOCK_WEIGHTS` (`42-51`).
- **Class `Generator`** (`61-202`).
  - random choices: `value`, `imm12`, `dest`, `source` (`71-93`);
  - emitting: `emit`, `emit_li`, `alu_instruction`, `skipped_instructions` (`97-122`);
  - blocks: `block_*` (`126-186`);
  - `generate` (`190-202`).
- **Function.** `random_program(seed, blocks=150)` (`205-206`).
- **Used by.** `tests/rtl/test_core_random.py`, `tests/model/test_random_program.py`.

---

## `model/`: golden model

### `model/isa.py`
- **Purpose.** The single source of truth for the instruction set.
- **Contents.**
  - `MASK32`, `to_u32`, `to_s32`, `sign_extend` (`11-29`);
  - `Fmt` (`32-41`) and `Opcode` (`44-55`);
  - `InstrSpec` (`58-64`);
  - `SPECS`, 40 entries (`67-114`);
  - `SPEC_BY_NAME`, `SHIFT_IMM_NAMES` and the fixed words `FENCE_WORD`, `ECALL_WORD`,
    `EBREAK_WORD` (`116-123`).
- **Used by.** `encoder.py`, `decoder.py`, `alu.py`, `iss.py`, `tb/coverage.py`, the tests.

### `model/encoder.py`
- **Purpose.** Assembly fields → 32-bit word.
- **Functions.** `encode(name, rd, rs1, rs2, imm)` (`34-100`) and
  `load_immediate(rd, value)` (`103-117`), plus `_check_reg` and `_check_range`
  (`22-31`).
- **Used by.** Directed tests, `tb/random_program.py`, the model tests.

### `model/decoder.py`
- **Purpose.** 32-bit word → fields → assembly text.
- **Contents.**
  - `IllegalInstruction` (`21-22`) and `Instr` (`25-32`);
  - `_LOOKUP` (`45-47`);
  - `decode(word)` (`50-100`) and `to_asm(instr)` (`103-124`).
- **Used by.** `model/iss.py`, `tb/coverage.py`, `tb/harness.py` (`disasm`),
  `tools/failing_waveform.py`, the tests.

### `model/alu.py`
- **Purpose.** The reference ALU.
- **Contents.** `AluOp` (`8-18`), the same codes as `alu_op_e`; `alu(op, a, b)` (`21-46`).
- **Used by.** `model/iss.py`, `tests/rtl/test_alu.py`, `tests/model/test_alu_model.py`.

### `model/iss.py`
- **Purpose.** The instruction-set simulator.
- **Contents.**
  - exceptions `MisalignedAccess` and `MemoryAccessError` (`15-20`);
  - `Memory`, with `load`, `store` and `load_words` (`23-50`);
  - the frozen dataclass `Retire` (`53-74`);
  - `ALU_OPS`, `BRANCH_TAKEN`, `LOADS`, `STORES` (`77-96`);
  - `Iss`, with `step()` (`106-175`) and `run(max_steps)` (`177-184`).
- **Used by.** `tb/harness.py`, `tb/coverage.py` (`Retire`), the model tests.

---

## `tests/`

### `tests/rtl/cocotb_runner.py`
- **Purpose.** Build with Verilator, run a cocotb module from pytest.
- **Functions.** `cores_under_test()` (`18-25`) and
  `run_cocotb(toplevel, sources, test_module, core)` (`28-60`).
- **Reads.** The environment variables `CORE`, `SEED`, `WAVES`.
- **Used by.** Every `tests/rtl/test_*.py`.

### `tests/rtl/test_alu.py` and `tests/rtl/test_regfile.py`
- **`test_alu.py`.**
  - 3 cocotb tests: edge pairs, 1,000 random pairs per op, unused codes output 0
    (`32-59`);
  - pytest entry point `test_alu_rtl` (`62-63`).
- **`test_regfile.py`.**
  - 4 cocotb tests: reset clears all, x0 hard-wired, read-during-write gives the old value,
    2,000 random cycles (`44-99`);
  - entry point `test_regfile_rtl` (`102-103`).

### `tests/rtl/test_core_directed.py`
- **Purpose.** The 50 directed cases.
- **Contents.**
  - `Case` dataclass (`23-29`) and the `program()` helper (`32-37`);
  - case groups (`42-382`, table in chapter 07);
  - `run_case` (`391-399`) and the generated cocotb tests (`402-411`);
  - entry point `test_core_directed(core)` (`414-416`).

### `tests/rtl/test_core_programs.py`
- **Purpose.** riscv-tests and the C programs on the cores.
- **Contents.**
  - `record()`, with the CPI and timing assertions plus the `programs.json` output (`42-61`);
  - `run_riscv_test` (`64-70`) and `run_c_program` (`73-80`);
  - test generation (`91-97`);
  - entry point (`100-103`).

### `tests/rtl/test_core_random.py`
- **Purpose.** Random programs on the cores.
- **Contents.**
  - `SEEDS`, `SEED_START` from the environment (`22-23`);
  - `run_seed` (`31-38`) and `save_closure` (`41-47`), which writes
    `random_coverage.json`;
  - entry point (`62-64`).

### `tests/model/*.py`
- **What they check:** ISS (`test_iss.py`, 82 tests), ALU (`test_alu_model.py`, 23),
  encoder/decoder (`test_encoder.py`, 71), programs on the ISS (`test_programs_iss.py`, 43),
  the random generator (`test_random_program.py`, 204) and the coverage collector
  (`test_coverage.py`, 6). The total is 429. Chapter 06 has the details.

---

## `tools/`

| File | Purpose | Key items | Writes |
|---|---|---|---|
| `tools/mutations.py` | the 7 injectable bugs, plus safe restore | `Mutation` (`23-27`), `MUTATIONS` (`30-53`), `protected_outputs()` (`57-74`), `inject()` (`77-80`) | temporarily `rtl/core_pipe.sv` |
| `tools/mutation_analysis.py` | `make mutation` | `run_suite` (`28-40`), `main` (`43-60`) | `build/results/mutation.json` |
| `tools/failing_waveform.py` | `make waveform` | `run_failing_test` (`37-51`), `read_vcd` (`54-87`), `stage_text` (`99-107`), `draw` (`150-203`) | `docs/img/failing_waveform.png` |
| `tools/synth_report.py` | `make synth` | `find_sv2v` (`26-31`), `synthesize` (`39-58`), `summarize` (`61-71`) | `build/synth/*`, `build/results/synth.json` |
| `tools/install_sv2v.sh` | install the pinned sv2v | version + SHA-256 (`10-11`) | `~/.local/bin/sv2v` |
| `tools/plot_results.py` | `make plots` | `cpi_breakdown` (`31-63`), `coverage_closure` (`66-80`) | `docs/img/cpi_breakdown.png`, `coverage_closure.png` |
| `tools/test_report.py` | `make test-report` | `count` (`19-26`), `main` (`29-47`) | stdout |

---

## `programs/`, configuration and infrastructure

| File | Purpose |
|---|---|
| `programs/crt0.S` | `_start`: `li sp, 0x4000`; `call main`; `ecall` (`5-8`) |
| `programs/link.ld` | code at 0x0, `.data`/`.bss` at 0x2000, and an assertion that code fits below 0x2000 (`9-20`) |
| `programs/fibonacci.c` | recursive `fib(15)` = 610 |
| `programs/bubble_sort.c` | xorshift32 data, bubble sort, sortedness check, rotate-XOR checksum |
| `programs/riscv-test-env/riscv_test.h` | bare-metal replacements for the riscv-tests macros; pass = gp = 1 at ECALL (`24-28`), fail = gp = 2n+1 (`30-36`) |
| `Makefile` | all commands (chapter 09) |
| `requirements.txt`, `pyproject.toml` | pinned Python packages; pytest and ruff config |
| `Dockerfile`, `.dockerignore` | the reproducible image |
| `.github/workflows/ci.yml` | the two CI jobs |
| `.gitmodules` | the `third_party/riscv-tests` submodule URL |
| `ROADMAP.md`, `CLAUDE.md`, `README.md`, `RESUME_BULLETS.md`, `docs/bugs.md` | plans, conventions, results, bug log |

## Known gaps

- **`tools/plot_results.py` and `tools/test_report.py` import `REPO_ROOT` from
  `tools/mutations.py`** (`tools/plot_results.py:18`, `tools/test_report.py:13`). That's a
  convenient import, but it makes two unrelated tools depend on the mutation module. A
  small shared `paths` module would be cleaner.
- **`tools/synth_report.py:18` and `tb/harness.py:26` compute `REPO_ROOT` separately.** It
  works, but it's duplicated.

## Check yourself

1. Which file defines the retire record's fields, and which two files must match it?
2. Where would you add a new coverpoint?
3. Which function writes `build/results/<core>/programs.json`?
4. Which files does `tools/mutations.py` modify, and how does it guarantee restoration?
5. Where is the list of excluded riscv-tests, and why is it there?

<details>
<summary>Answers</summary>

1. `model/iss.py:53-74` defines `Retire`. `rtl/core_single.sv:152-167` and
   `rtl/core_pipe.sv:327-342` drive the same fields. `tb/harness.py:206-219` reads them.
2. In `tb/coverage.py`: add bins to `COVERPOINTS` (`42-50`) and a `hit` call in `sample`
   (`79-105`). Then update the bin-count test in `tests/model/test_coverage.py:23-27`.
3. `record()` in `tests/rtl/test_core_programs.py:42-61`.
4. `rtl/core_pipe.sv` (and the contents of `build/coverage/pipe` and `build/results/pipe`).
   `protected_outputs()` restores all of them in a `finally:` block, which also runs on
   Ctrl-C (`tools/mutations.py:57-74`).
5. `tb/programs.py:40-43`, `RISCV_TESTS_EXCLUDED`. It sits next to the code that builds the
   tests, with the reason for each exclusion, and `riscv_test_names()` filters on it.

</details>
