"""cocotb tests for rtl/regfile.sv, checked against a Python list of 32 registers."""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer

from cocotb_runner import run_cocotb


async def start(dut) -> None:
    """Start a 10 ns clock and hold reset for two cycles."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.rst_n.value = 0
    dut.we.value = 0
    dut.rd_addr.value = 0
    dut.rd_data.value = 0
    dut.rs1_addr.value = 0
    dut.rs2_addr.value = 0
    for _ in range(2):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1


async def write(dut, rd: int, value: int) -> None:
    """Drive a write on the falling edge; it takes effect on the next rising edge."""
    dut.we.value = 1
    dut.rd_addr.value = rd
    dut.rd_data.value = value
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.we.value = 0


async def read(dut, rs1: int, rs2: int) -> tuple[int, int]:
    dut.rs1_addr.value = rs1
    dut.rs2_addr.value = rs2
    await Timer(1, units="ns")  # read ports are combinational
    return int(dut.rs1_data.value), int(dut.rs2_data.value)


@cocotb.test()
async def reset_clears_all_registers(dut):
    await start(dut)
    for reg in range(1, 32):
        await write(dut, reg, 0xDEAD_0000 | reg)
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1
    for reg in range(32):
        assert await read(dut, reg, reg) == (0, 0), f"x{reg} not cleared by reset"


@cocotb.test()
async def x0_is_hardwired_to_zero(dut):
    await start(dut)
    await write(dut, 0, 0xFFFF_FFFF)
    assert await read(dut, 0, 0) == (0, 0)


@cocotb.test()
async def read_during_write_returns_old_value(dut):
    await start(dut)
    await write(dut, 5, 0x1111_1111)
    dut.we.value = 1
    dut.rd_addr.value = 5
    dut.rd_data.value = 0x2222_2222
    assert await read(dut, 5, 5) == (0x1111_1111, 0x1111_1111)  # before the edge: old value
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.we.value = 0
    assert await read(dut, 5, 5) == (0x2222_2222, 0x2222_2222)


@cocotb.test()
async def random_reads_and_writes(dut):
    """2000 cycles of random traffic on all three ports, compared every cycle."""
    await start(dut)
    model = [0] * 32
    for cycle in range(2000):
        we = random.random() < 0.7
        rd, value = random.randrange(32), random.getrandbits(32)
        rs1, rs2 = random.randrange(32), random.randrange(32)

        dut.we.value = int(we)
        dut.rd_addr.value = rd
        dut.rd_data.value = value
        got = await read(dut, rs1, rs2)
        assert got == (model[rs1], model[rs2]), (
            f"cycle {cycle}: read x{rs1}, x{rs2} = {got}, expected {(model[rs1], model[rs2])}"
        )

        await RisingEdge(dut.clk)
        if we and rd != 0:
            model[rd] = value
        await FallingEdge(dut.clk)


def test_regfile_rtl():
    run_cocotb("regfile", ["rtl/regfile.sv"], "test_regfile")
