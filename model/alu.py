"""Reference ALU. The op encoding matches rtl/rv32i_pkg.sv: {funct7[5], funct3}."""

from enum import IntEnum

from model.isa import to_s32, to_u32


class AluOp(IntEnum):
    ADD = 0b0000
    SLL = 0b0001
    SLT = 0b0010
    SLTU = 0b0011
    XOR = 0b0100
    SRL = 0b0101
    OR = 0b0110
    AND = 0b0111
    SUB = 0b1000
    SRA = 0b1101


def alu(op: AluOp, a: int, b: int) -> int:
    """Compute one ALU operation on 32-bit operands; returns an unsigned 32-bit result."""
    a, b = to_u32(a), to_u32(b)
    shamt = b & 0x1F  # RV32I uses only the low 5 bits as the shift amount
    match op:
        case AluOp.ADD:
            return to_u32(a + b)
        case AluOp.SUB:
            return to_u32(a - b)
        case AluOp.SLL:
            return to_u32(a << shamt)
        case AluOp.SLT:
            return int(to_s32(a) < to_s32(b))
        case AluOp.SLTU:
            return int(a < b)
        case AluOp.XOR:
            return a ^ b
        case AluOp.SRL:
            return a >> shamt
        case AluOp.SRA:
            return to_u32(to_s32(a) >> shamt)  # Python >> on negative ints is arithmetic
        case AluOp.OR:
            return a | b
        case AluOp.AND:
            return a & b
    raise ValueError(f"unknown ALU op {op!r}")
