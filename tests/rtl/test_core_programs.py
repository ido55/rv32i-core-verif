"""Official riscv-tests (rv32ui) and the C programs on the core, with the ISS scoreboard on.

Each program passes only if (1) every retired instruction matches the ISS, (2) the final
registers and memory match, and (3) the program's own self-check passes:
riscv-tests leave gp == 1, C programs return the expected value in a0.
"""

import cocotb
import pytest

from tb.coverage import Coverage
from tb.harness import CORE_SINGLE_SOURCES, COVERAGE_DIR, CoreHarness
from tb.programs import (
    C_PROGRAMS,
    build_c_program,
    build_riscv_test,
    riscv_test_names,
    toolchain_available,
)

from cocotb_runner import run_cocotb

GP, A0 = 3, 10
MAX_CYCLES = 200_000

COVERAGE = Coverage()


async def run_riscv_test(dut, name: str) -> None:
    harness = CoreHarness(dut, COVERAGE)
    harness.load(build_riscv_test(name).image)
    result = await harness.run(max_cycles=MAX_CYCLES)
    COVERAGE.save(COVERAGE_DIR / "programs.json")
    gp = harness.read_reg(GP)
    assert gp == 1, f"rv32ui-{name} failed test case {gp >> 1} (gp={gp})"
    dut._log.info("rv32ui-%s: %d instructions, %d cycles", name, result.retired, result.cycles)


async def run_c_program(dut, name: str, expected: int) -> None:
    harness = CoreHarness(dut, COVERAGE)
    harness.load(build_c_program(name).image)
    result = await harness.run(max_cycles=MAX_CYCLES)
    COVERAGE.save(COVERAGE_DIR / "programs.json")
    a0 = harness.read_reg(A0)
    assert a0 == expected, f"{name}: a0=0x{a0:08x}, expected 0x{expected:08x}"
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
def test_core_single_programs():
    run_cocotb("tb_top", CORE_SINGLE_SOURCES, "test_core_programs")
