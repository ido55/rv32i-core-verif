"""Build an RTL top level with Verilator and run a cocotb test module on it, from pytest.

Environment variables:
  CORE=single|pipe  which core(s) the core-level tests run on (default: both)
  SEED=<n>          random seed for cocotb (default 1, so CI runs are reproducible)
  WAVES=1           dump a waveform (sim_build/<build name>/dump.vcd)
"""

import os
from pathlib import Path

from cocotb.runner import get_runner

REPO_ROOT = Path(__file__).resolve().parents[2]
ALL_CORES = ["single", "pipe"]


def cores_under_test() -> list[str]:
    """The cores selected by CORE (`or`: make exports an unset variable as "")."""
    core = os.environ.get("CORE") or ""
    if not core:
        return ALL_CORES
    if core not in ALL_CORES:
        raise ValueError(f"CORE must be one of {ALL_CORES}, got {core!r}")
    return [core]


def run_cocotb(
    toplevel: str, sources: list[str], test_module: str, core: str | None = None
) -> None:
    """`sources` are paths relative to the repo root, packages first.

    With `core`, tb_top is built with that core selected (into its own build directory),
    and the simulation gets the plusarg +CORE=<core> so the harness knows which core it
    drives. (Not an environment variable: cocotb 1.9's runner copies os.environ over
    extra_env, so an exported CORE would silently override it.)
    """
    build_name = f"{toplevel}_{core}" if core else toplevel
    build_dir = REPO_ROOT / "sim_build" / build_name
    defines = {"PIPELINED": 1} if core == "pipe" else {}  # tb_top: `ifdef PIPELINED
    waves = os.environ.get("WAVES") == "1"

    runner = get_runner("verilator")
    runner.build(
        sources=[REPO_ROOT / name for name in sources],
        hdl_toplevel=toplevel,
        build_dir=build_dir,
        build_args=["-Wall"],  # lint warnings fail the build, same as `make lint`
        defines=defines,
        waves=waves,
    )
    runner.test(
        hdl_toplevel=toplevel,
        test_module=test_module,
        build_dir=build_dir,
        test_dir=build_dir,
        seed=int(os.environ.get("SEED") or 1),
        plusargs=[f"+CORE={core}"] if core else [],
        waves=waves,
    )
