"""cocotb tests for rtl/alu.sv, checked against the Python reference ALU (model/alu.py)."""

import random

import cocotb
from cocotb.triggers import Timer

from model.alu import AluOp, alu

from cocotb_runner import run_cocotb

EDGE_VALUES = [
    0x0000_0000, 0x0000_0001, 0x0000_0002, 0x0000_001F, 0x0000_0020, 0x0000_0021,
    0x7FFF_FFFF, 0x8000_0000, 0x8000_0001, 0xFFFF_FFFE, 0xFFFF_FFFF,
    0xAAAA_AAAA, 0x5555_5555,
]  # fmt: skip
RANDOM_PAIRS_PER_OP = 1000


async def check(dut, op: AluOp, a: int, b: int) -> None:
    dut.op.value = int(op)
    dut.a.value = a
    dut.b.value = b
    await Timer(1, units="ns")  # combinational logic: let it settle
    got = int(dut.y.value)
    expected = alu(op, a, b)
    assert got == expected, (
        f"{op.name}(0x{a:08x}, 0x{b:08x}) = 0x{got:08x}, expected 0x{expected:08x}"
    )


@cocotb.test()
async def alu_edge_cases(dut):
    """Every op on every pair of edge values (overflow, sign bit, shift by 31/32/33)."""
    for op in AluOp:
        for a in EDGE_VALUES:
            for b in EDGE_VALUES:
                await check(dut, op, a, b)


@cocotb.test()
async def alu_random_operands(dut):
    """Random operands; the seed is printed by cocotb and set with SEED=<n>."""
    for op in AluOp:
        for _ in range(RANDOM_PAIRS_PER_OP):
            await check(dut, op, random.getrandbits(32), random.getrandbits(32))


@cocotb.test()
async def alu_unused_op_codes_output_zero(dut):
    used = {int(op) for op in AluOp}
    for code in range(16):
        if code in used:
            continue
        dut.op.value = code
        dut.a.value = 0xFFFF_FFFF
        dut.b.value = 0xFFFF_FFFF
        await Timer(1, units="ns")
        assert int(dut.y.value) == 0, f"op code {code:04b} should output 0"


def test_alu_rtl():
    run_cocotb("alu", ["rv32i_pkg.sv", "alu.sv"], "test_alu")
