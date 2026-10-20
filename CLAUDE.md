# CLAUDE.md

Guidance for AI assistants (and humans) working in this repo.

## Project
5-stage pipelined RV32I CPU (SystemVerilog) verified against a Python ISS golden model
with cocotb + Verilator. See ROADMAP.md for milestones and acceptance criteria.

## Environment
- Develop inside WSL2 Ubuntu 24.04 (or the Docker image). Never on native Windows.
- System tools (apt): verilator 5.020, yosys 0.33, gcc-riscv64-unknown-elf 13.2, make, gtkwave.
- Python deps live in a project virtualenv `.venv/`, pinned in `requirements.txt`.

## Conventions
- Clarity over cleverness: the author must be able to explain every line in an interview.
- SystemVerilog: `logic` everywhere, `always_ff` / `always_comb`, no latches,
  one module per file in `rtl/`, `snake_case` signals, `_q`/`_d` for flop out/in,
  active-low reset named `rst_n`. Must pass `verilator --lint-only -Wall` with zero warnings.
- Python: PEP 8, type hints on public functions, formatted/linted with `ruff`.
- Every feature lands with tests. Never commit with failing tests.
- Git: branch `feat/<milestone>`, Conventional Commits (feat:, fix:, test:, docs:, ci:, refactor:),
  small commits, PR → green CI → `gh pr merge --merge --delete-branch`.
- Never invent results. Every number in README.md must be reproducible by a command shown next to it.
- Every bug found by random tests goes in docs/bugs.md (symptom, root cause, fix, test that caught it).
- No secrets, large binaries or generated files in git (see .gitignore).

## Commands
Run from the repo root inside WSL. The Makefile uses `.venv/bin/python` if it exists,
otherwise `python3` on PATH (Docker/CI).

```bash
make venv                        # create .venv, install requirements.txt
make lint                        # ruff check + ruff format --check + verilator --lint-only -Wall per top
make format                      # ruff format + ruff check --fix
make test                        # = test-model + test-rtl
make test-model                  # pytest tests/model
make test-rtl                    # pytest tests/rtl (cocotb + Verilator, builds into sim_build/<top>/)
make test-rtl SEED=42 WAVES=1    # other seed; VCD at sim_build/<top>/dump.vcd
make test CORE=pipe              # core-level suites on one core only (default: both)
make test-random SEEDS=200 SEED_START=1   # random programs; reproduce one: SEED_START=<s> SEEDS=1
make coverage                    # merge build/coverage/<core>/*.json and print tables
make cpi                         # CPI table from build/results/<core>/programs.json
make mutation                    # inject 7 pipeline bugs, count failing tests (~5 min)
.venv/bin/python -m pytest tests/model/test_iss.py -k jalr   # one test
make docker-test                 # docker build + run `make lint test` in the image
make clean
```

## Core-level tests
- `tb/harness.py:CoreHarness`: `load(program, data)` writes the same image to imem, dmem and the ISS;
  `run()` samples the retire port on each FALLING edge, steps the ISS, and compares; at halt it
  compares all registers and all of dmem. Use `read_reg(n)` for hand-computed expectations.
- The retire-port fields and conventions are defined once, in `model/iss.py:Retire`; the RTL must match.
- Memory map: 16 KiB imem + 16 KiB dmem at 0x0000; code at 0, test data at 0x2000. `mem_fault`
  in tb_top flags any fetch/load/store outside that range or misaligned.

- Programs: `tb/programs.py` builds rv32ui riscv-tests (pass = gp/x3 == 1) and `programs/*.c`
  (result in a0) with riscv64-unknown-elf-gcc into `build/`. Clone with `--recursive` (submodule).
- Never modify `third_party/` (vendored; excluded from ruff).
- Each core-level suite saves coverage to `build/coverage/<core>/<suite>.json`.
- Two cores, same ports and retire port: `tb_top` instantiates `core_pipe` if built with
  `-DPIPELINED`, else `core_single`; the instance is `u_core` either way. The runner builds
  `sim_build/tb_top_<core>/` and passes `+CORE=<core>` (a plusarg, never an env var: cocotb
  1.9 lets os.environ override extra_env). No generate blocks in tb_top: cocotb 1.9 cannot
  look inside Verilator 5.020 generate scopes.
- Pipeline invariant enforced by test_core_programs:
  `cycles == instructions + 4 + stall_cycles + 2 * (flushes - 1)`.

## Adding an RTL module
1. Add `rtl/<top>.sv`; add `LINT_<top>` (files, packages first) and the name to `LINT_TOPS` in the Makefile.
2. Add `tests/rtl/test_<top>.py` with `@cocotb.test()` coroutines plus a pytest function
   calling `run_cocotb("<top>", [files], "test_<top>")`.
3. cocotb 1.9 under pytest names its results file `sim_build/<top>/<pytest test>.None` (a cocotb quirk; harmless).
