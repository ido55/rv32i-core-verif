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
These are added in Milestone 1. Until then, there is nothing to build.
<!-- Filled in with exact, tested commands in Milestone 1. -->
