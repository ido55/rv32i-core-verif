"""Build an RTL top level with Verilator and run a cocotb test module on it, from pytest.

Environment variables:
  SEED=<n>   random seed for cocotb (default 1, so CI runs are reproducible)
  WAVES=1    dump a waveform (sim_build/<toplevel>/dump.vcd)
"""

import os
from pathlib import Path

from cocotb.runner import get_runner

REPO_ROOT = Path(__file__).resolve().parents[2]
RTL_DIR = REPO_ROOT / "rtl"


def run_cocotb(toplevel: str, sources: list[str], test_module: str) -> None:
    build_dir = REPO_ROOT / "sim_build" / toplevel
    waves = os.environ.get("WAVES") == "1"

    runner = get_runner("verilator")
    runner.build(
        sources=[RTL_DIR / name for name in sources],
        hdl_toplevel=toplevel,
        build_dir=build_dir,
        build_args=["-Wall"],  # lint warnings fail the build, same as `make lint`
        waves=waves,
    )
    runner.test(
        hdl_toplevel=toplevel,
        test_module=test_module,
        build_dir=build_dir,
        test_dir=build_dir,
        seed=int(os.environ.get("SEED", "1")),
        waves=waves,
    )
