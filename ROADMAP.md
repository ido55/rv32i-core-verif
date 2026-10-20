# Roadmap

Five milestones. Each one is built on its own branch `feat/<milestone>`, lands via a PR with
green CI, and has acceptance criteria that are checked by a command (not by eye).

## Scope and non-goals

**In scope:** the RV32I base integer ISA, 37 instructions:
LUI, AUIPC, JAL, JALR, 6 branches, 5 loads, 3 stores, 9 ALU-immediate, 10 ALU-register.
`FENCE` executes as a no-op. `ECALL`/`EBREAK` halt the core, which is how a test ends.

**Out of scope** (listed as limitations in the README): CSRs/Zicsr, interrupts and exceptions,
misaligned memory accesses, `FENCE.I`, M/C extensions, caches.
The riscv-tests that need these (`fence_i`, `ma_data`, CSR-based env) are excluded or replaced
by a minimal custom test environment.

## Key architecture decisions (apply to all milestones)

| Topic | Decision | Why |
|---|---|---|
| Memories | Separate instruction and data memory (Harvard), as SV arrays in a testbench wrapper `tb_top.sv`, loaded by cocotb | Single-cycle core needs combinational reads; keeps the core itself synthesizable without memories |
| Checking | Core exposes a **retire port** (valid, pc, insn, rd, rd_wdata, mem addr/wdata/wmask), modeled on RISC-V Formal Interface (RVFI) | Scoreboard checks every retired instruction against the ISS, so a bug shows up on the exact instruction, not 1000 cycles later |
| Golden model | Own Python ISS (`model/`), validated independently with pytest and the official riscv-tests | Golden model must itself be trusted ("who verifies the verifier?") |
| Program build | `riscv64-unknown-elf-gcc -march=rv32i -mabi=ilp32` for riscv-tests and C programs; a Python **instruction encoder** for directed and random tests | Toolchain is available, so no hand-written assembler is needed; the encoder is ~100 lines and lets tests build exact instruction streams |
| Coverage | Own small coverage collector in Python (named bins + counters, YAML/JSON report) | No extra dependency, easy to explain; `cocotb-coverage` rejected as overkill for ~10 coverpoints |
| Versions | Verilator 5.020 + Yosys 0.33 from Ubuntu 24.04 apt; cocotb pinned to **1.9.2** | Measured: cocotb 2.x requires Verilator ≥ 5.036 and refuses 5.020; 1.9.2 runs on it. Same versions locally, in Docker and in CI |

---

## M1: Foundation: golden model, toolchain, CI (`feat/m1-foundation`)

**Build:**
- Python ISS `model/iss.py`: fetch/decode/execute for all 37 instructions, 32-bit wraparound, x0 hard-wired to 0.
- Instruction encoder `model/encoder.py` (`add(rd, rs1, rs2) → 0x...`) plus decoder, round-trip tested.
- First RTL blocks: `rtl/alu.sv`, `rtl/regfile.sv`, with cocotb tests against Python reference functions.
- `Makefile` targets: `lint`, `test-model`, `test-rtl`, `test`. `requirements.txt` with pinned versions.
- `Dockerfile` (ubuntu:24.04 + apt toolchain + venv): `docker build -t rv32i . && docker run --rm rv32i make test`.
- GitHub Actions CI: lint (ruff + `verilator --lint-only -Wall`), model tests, RTL tests. CI badge in README.
- `CLAUDE.md` commands section filled in with the exact, tested commands.

**Acceptance criteria:**
- `make test` passes locally, in Docker and in CI.
- pytest covers every one of the 37 instructions in the ISS (incl. edge cases: x0 writes, overflow wrap, sign-extension, shift amounts ≥ 31).
- ALU cocotb test: every ALU op checked against the Python reference on directed edge cases + ≥ 1000 random operand pairs.
- `verilator --lint-only -Wall` reports zero warnings.

## M2: Single-cycle core + scoreboard (`feat/m2-single-cycle`)

**Build:**
- `rtl/core_single.sv`: single-cycle datapath (decoder, immediate gen, ALU, branch compare, load/store unit) + retire port.
- `tb/tb_top.sv` with instruction/data memory; halts on ECALL/EBREAK.
- cocotb scoreboard: on every retire, step the ISS and compare pc, insn, rd write and memory write; at the end, compare the full register file and data memory.
- Directed tests: ≥ 1 test per instruction (37+), plus edge cases (x0 as destination, load sign/zero-extension, byte/halfword store masks, branch to self-offset, JALR LSB clearing).

**Acceptance criteria:**
- All directed tests pass with zero scoreboard mismatches.
- A deliberately injected bug (e.g. SRA treated as SRL) is caught by the scoreboard; shown in the PR description, then reverted.

## M3: Real programs, random tests, coverage (`feat/m3-random-coverage`)

**Build:**
- riscv-tests as a git submodule pinned to a commit, with a minimal custom env (`riscv_test.h`, no CSRs).
  The rv32ui suite runs on **both** the ISS and the RTL.
- Sample C/asm programs: fibonacci, bubble sort (built with GCC, results checked against expected values).
- Constrained-random instruction stream generator (seeded): weighted opcode mix, register reuse
  to create dependencies, branches/jumps constrained to stay inside the program, loads/stores
  constrained to aligned addresses inside data memory, guaranteed termination.
- Functional coverage: opcodes, rd/rs1/rs2 = x0, branch taken / not taken per branch type,
  load/store widths, sign of immediates. Report written per run.
- `docs/bugs.md` started: every bug the random tests find is logged (symptom, root cause, fix, seed/test).

**Acceptance criteria:**
- All applicable rv32ui tests pass on ISS and RTL (excluded tests listed with the reason).
- fibonacci and bubble sort produce correct results on the RTL.
- `make test-random SEEDS=N` passes (N chosen and stated in README); failing seed reproducible with `SEED=<n>`.
- Coverage report generated by a command; the measured % is recorded, not assumed.

## M4: 5-stage pipeline (`feat/m4-pipeline`)

**Build:**
- `rtl/core_pipe.sv`: IF / ID / EX / MEM / WB with pipeline registers.
- Forwarding EX/MEM→EX and MEM/WB→EX; register file write-before-read for WB→ID.
- Hazard unit: 1-cycle stall on load-use; branches/jumps resolved in EX with predict-not-taken and a 2-instruction flush.
- Same retire port, so the **same** scoreboard, directed, riscv-tests and random tests run unchanged against both cores (selected by a `CORE=single|pipe` make variable).
- Hazard coverage: forward from EX/MEM vs MEM/WB, per source operand; load-use stalls; flushes from taken branches and jumps.
- CPI measured from cycle and retire counts on fibonacci and bubble sort.
- Bugs found during pipelining logged in `docs/bugs.md`.

**Acceptance criteria:**
- Every test from M2–M3 passes on `CORE=pipe`.
- Every hazard coverage bin is hit at least once, as reported by the coverage command.
- CPI measured for both programs and both cores via a command (single-cycle CPI = 1.0 is a sanity check).

## M5: Synthesis, results, final README (`feat/m5-results`)

**Build:**
- Yosys script: `synth -top core_pipe` (generic cells) and the same for `core_single`; cell/flop counts table.
  Also `synth_xilinx` for 7-series LUT/FF counts. Yosys 0.33 cannot parse parts of the SV used, so sv2v converts first.
- One failing-test waveform: `make waveform` injects a bug from the mutation table in `docs/bugs.md`
  (instead of a throwaway branch), dumps a VCD, restores the RTL and renders the failing cycles to a PNG.
- `make results` regenerates every number in the README (pass rate, coverage %, CPI, cell counts) and the plots (matplotlib, added here and justified in the PR).
- Final README: motivation, Mermaid architecture diagram, copy-paste commands, results tables + plots, design decisions and tradeoffs, limitations and next steps, CI badge.
- `RESUME_BULLETS.md`: 3–4 bullets using only measured numbers.

**Acceptance criteria:**
- `make results` reproduces every number in the README.
- All milestones merged, CI green on `main`.
