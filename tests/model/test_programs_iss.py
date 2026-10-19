"""Run the official riscv-tests and the C programs on the ISS (validates the golden model).

Skipped when the RISC-V GCC toolchain is not installed.
"""

import pytest

from model.iss import Iss, Memory
from tb.programs import (
    C_PROGRAMS,
    IMAGE_BYTES,
    build_c_program,
    build_riscv_test,
    riscv_test_names,
    toolchain_available,
)

pytestmark = pytest.mark.skipif(not toolchain_available(), reason="RISC-V GCC not installed")

GP, A0 = 3, 10


def run_image(image: list[int], max_steps: int = 200_000) -> Iss:
    mem = Memory(IMAGE_BYTES)
    mem.load_words(image, 0)
    iss = Iss(mem)
    iss.run(max_steps)
    return iss


@pytest.mark.parametrize("name", riscv_test_names())
def test_riscv_test_on_iss(name):
    iss = run_image(build_riscv_test(name).image)
    gp = iss.regs[GP]
    assert gp == 1, f"rv32ui-{name} failed test case {gp >> 1} (gp={gp})"


def test_riscv_test_list_is_complete():
    names = riscv_test_names()
    assert len(names) == 40  # 42 rv32ui tests minus fence_i and ma_data
    assert "fence_i" not in names and "ma_data" not in names


@pytest.mark.parametrize(("name", "expected"), C_PROGRAMS.items())
def test_c_program_on_iss(name, expected):
    iss = run_image(build_c_program(name).image)
    assert iss.regs[A0] == expected, f"{name}: a0=0x{iss.regs[A0]:08x}, expected 0x{expected:08x}"
