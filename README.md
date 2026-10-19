# rv32i-core-verif

[![CI](https://github.com/ido55/rv32i-core-verif/actions/workflows/ci.yml/badge.svg)](https://github.com/ido55/rv32i-core-verif/actions/workflows/ci.yml)

A 5-stage pipelined RV32I CPU in SystemVerilog, verified against a Python golden model
using cocotb + Verilator (directed tests, constrained-random streams, scoreboard,
functional coverage).

> **Status:** Milestone 1 of 5 (golden model, ALU, register file, CI). See [ROADMAP.md](ROADMAP.md).
> Results are added here only once measured, together with the command that produced them.

## Quick start

With Docker (no local toolchain needed):

```bash
docker build -t rv32i-core-verif .
docker run --rm rv32i-core-verif          # runs: make lint test
```

Natively on Ubuntu 24.04 / WSL2:

```bash
sudo apt install build-essential python3-venv python3-dev verilator gcc-riscv64-unknown-elf
make venv        # .venv with pinned cocotb / pytest / ruff
make lint        # ruff + verilator --lint-only -Wall
make test        # golden-model tests + cocotb RTL tests
make test-rtl SEED=42 WAVES=1   # different random seed, dump waveforms to sim_build/
```

## Layout

| Path | Contents |
|---|---|
| `model/` | Python golden model: instruction table, encoder/decoder, reference ALU, ISS |
| `rtl/` | SystemVerilog: `rv32i_pkg`, `alu`, `regfile` (cores arrive in M2 and M4) |
| `tests/model/` | pytest for the golden model, incl. an encoder cross-check against GNU `as` |
| `tests/rtl/` | cocotb testbenches, launched from pytest via the cocotb runner |

## Current verification status (M1)

Measured with `make test`:

| Suite | What it checks | Result |
|---|---|---|
| `tests/model` | ISS (every RV32I instruction + edge cases), encoder/decoder round trips, 1,600 random instructions vs GNU `as` | 159 / 159 pass |
| `tests/rtl/test_alu.py` | all 10 ALU ops: 13×13 edge-value pairs + 1,000 random pairs per op, vs `model/alu.py` | 3 / 3 cocotb tests pass |
| `tests/rtl/test_regfile.py` | reset, x0 hard-wired, read-during-write, 2,000 cycles of random traffic | 4 / 4 cocotb tests pass |

## License

[MIT](LICENSE)
