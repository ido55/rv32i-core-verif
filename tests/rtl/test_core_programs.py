"""Official riscv-tests (rv32ui) and the C programs on the core, with the ISS scoreboard on.

Each program passes only if (1) every retired instruction matches the ISS, (2) the final
registers and memory match, and (3) the program's own self-check passes:
riscv-tests leave gp == 1, C programs return the expected value in a0.

Instruction and cycle counts of every program are saved to build/results/<core>/programs.json
(used for the CPI table: `make cpi`).
"""

import json

import cocotb
import pytest

from tb.harness import (
    CORE_SOURCES,
    CoreHarness,
    RunResult,
    core_name,
    coverage_path,
    new_coverage,
    results_path,
)
from tb.programs import (
    C_PROGRAMS,
    build_c_program,
    build_riscv_test,
    riscv_test_names,
    toolchain_available,
)

from cocotb_runner import cores_under_test, run_cocotb

GP, A0 = 3, 10
MAX_CYCLES = 200_000

COVERAGE = new_coverage()
RESULTS: dict[str, dict[str, int]] = {}


def record(name: str, result: RunResult) -> None:
    if core_name() == "single":
        # Sanity check of the cycle counting itself: one instruction per cycle, exactly.
        assert result.cycles == result.retired, f"{name}: single-cycle CPI is {result.cpi}"
    else:
        # Every lost cycle must be explained: 4 cycles to fill the pipeline, 1 per load-use
        # stall, 2 per flush. The final ECALL's own flush is not counted, because the run
        # ends when the ECALL retires.
        expected = result.retired + 4 + result.stall_cycles + 2 * (result.flushes - 1)
        assert result.cycles == expected, f"{name}: {result.cycles} cycles, model {expected}"
    COVERAGE.save(coverage_path("programs"))
    RESULTS[name] = {
        "instructions": result.retired,
        "cycles": result.cycles,
        "stall_cycles": result.stall_cycles,
        "flushes": result.flushes,
    }
    path = results_path("programs")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(RESULTS, indent=1))


async def run_riscv_test(dut, name: str) -> None:
    harness = CoreHarness(dut, COVERAGE)
    harness.load(build_riscv_test(name).image)
    result = await harness.run(max_cycles=MAX_CYCLES)
    gp = harness.read_reg(GP)
    assert gp == 1, f"rv32ui-{name} failed test case {gp >> 1} (gp={gp})"
    record(f"rv32ui-{name}", result)


async def run_c_program(dut, name: str, expected: int) -> None:
    harness = CoreHarness(dut, COVERAGE)
    harness.load(build_c_program(name).image)
    result = await harness.run(max_cycles=MAX_CYCLES)
    a0 = harness.read_reg(A0)
    assert a0 == expected, f"{name}: a0=0x{a0:08x}, expected 0x{expected:08x}"
    record(name, result)
    dut._log.info("%s: %d instructions, %d cycles", name, result.retired, result.cycles)


def _named_test(name: str, coroutine, *args):
    async def test(dut):
        await coroutine(dut, *args)

    test.__name__ = test.__qualname__ = name
    return cocotb.test()(test)


if toolchain_available():
    for _name in riscv_test_names():
        globals()[f"rv32ui_{_name}"] = _named_test(f"rv32ui_{_name}", run_riscv_test, _name)
    for _name, _expected in C_PROGRAMS.items():
        globals()[f"program_{_name}"] = _named_test(
            f"program_{_name}", run_c_program, _name, _expected
        )


@pytest.mark.skipif(not toolchain_available(), reason="RISC-V GCC not installed")
@pytest.mark.parametrize("core", cores_under_test())
def test_core_programs(core):
    run_cocotb("tb_top", CORE_SOURCES, "test_core_programs", core)
