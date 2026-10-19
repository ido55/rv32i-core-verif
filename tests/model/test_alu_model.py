"""Reference ALU tests with hand-computed expected values."""

import pytest

from model.alu import AluOp, alu

MAX_POS = 0x7FFF_FFFF
MIN_NEG = 0x8000_0000
ALL_ONES = 0xFFFF_FFFF

CASES = [
    (AluOp.ADD, 1, 2, 3),
    (AluOp.ADD, MAX_POS, 1, MIN_NEG),  # signed overflow wraps
    (AluOp.ADD, ALL_ONES, 1, 0),  # unsigned carry-out is dropped
    (AluOp.SUB, 0, 1, ALL_ONES),
    (AluOp.SUB, MIN_NEG, 1, MAX_POS),
    (AluOp.SLL, 1, 31, MIN_NEG),
    (AluOp.SLL, 1, 32, 1),  # only b[4:0] is used: shift by 0
    (AluOp.SLL, 1, 33, 2),
    (AluOp.SLT, ALL_ONES, 0, 1),  # -1 < 0 signed
    (AluOp.SLT, 0, ALL_ONES, 0),
    (AluOp.SLT, MIN_NEG, MAX_POS, 1),
    (AluOp.SLT, 5, 5, 0),
    (AluOp.SLTU, ALL_ONES, 0, 0),  # 0xFFFFFFFF > 0 unsigned
    (AluOp.SLTU, 0, ALL_ONES, 1),
    (AluOp.XOR, 0xF0F0_F0F0, 0xFF00_FF00, 0x0FF0_0FF0),
    (AluOp.SRL, MIN_NEG, 31, 1),
    (AluOp.SRL, MIN_NEG, 1, 0x4000_0000),  # zero fill
    (AluOp.SRA, MIN_NEG, 1, 0xC000_0000),  # sign fill
    (AluOp.SRA, MIN_NEG, 31, ALL_ONES),
    (AluOp.SRA, 0x4000_0000, 30, 1),  # positive: same as SRL
    (AluOp.OR, 0xF0F0_0000, 0x0000_0F0F, 0xF0F0_0F0F),
    (AluOp.AND, 0xF0F0_F0F0, 0xFF00_FF00, 0xF000_F000),
]


@pytest.mark.parametrize(("op", "a", "b", "expected"), CASES)
def test_alu(op, a, b, expected):
    assert alu(op, a, b) == expected


def test_operands_are_wrapped_to_32_bits():
    assert alu(AluOp.ADD, -1, 0) == ALL_ONES
