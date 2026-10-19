"""RV32I instruction set definitions shared by the encoder, decoder and ISS.

Every instruction is described once, in SPECS. The encoder, decoder and
tests all read from this table, so adding or fixing an instruction is a
one-line change.
"""

from dataclasses import dataclass
from enum import Enum, IntEnum

MASK32 = 0xFFFF_FFFF


def to_u32(value: int) -> int:
    """Wrap any Python int to an unsigned 32-bit value (what a register holds)."""
    return value & MASK32


def to_s32(value: int) -> int:
    """Interpret a 32-bit value as a signed two's-complement number."""
    value &= MASK32
    return value - (1 << 32) if value & 0x8000_0000 else value


def sign_extend(value: int, bits: int) -> int:
    """Interpret the low `bits` bits of `value` as a signed number."""
    sign_bit = 1 << (bits - 1)
    value &= (1 << bits) - 1
    return (value ^ sign_bit) - sign_bit


class Fmt(Enum):
    """Instruction formats from the RISC-V spec (Volume I, chapter 2)."""

    R = "R"
    I = "I"  # noqa: E741 - the spec's name for the format
    S = "S"
    B = "B"
    U = "U"
    J = "J"
    SYS = "SYS"  # FENCE / ECALL / EBREAK: fixed encodings, no operands


class Opcode(IntEnum):
    LUI = 0b0110111
    AUIPC = 0b0010111
    JAL = 0b1101111
    JALR = 0b1100111
    BRANCH = 0b1100011
    LOAD = 0b0000011
    STORE = 0b0100011
    OP_IMM = 0b0010011
    OP = 0b0110011
    MISC_MEM = 0b0001111
    SYSTEM = 0b1110011


@dataclass(frozen=True)
class InstrSpec:
    name: str
    fmt: Fmt
    opcode: Opcode
    funct3: int = 0
    funct7: int = 0  # for shift-immediates this is imm[11:5]


SPECS: list[InstrSpec] = [
    # Upper immediates and jumps
    InstrSpec("lui", Fmt.U, Opcode.LUI),
    InstrSpec("auipc", Fmt.U, Opcode.AUIPC),
    InstrSpec("jal", Fmt.J, Opcode.JAL),
    InstrSpec("jalr", Fmt.I, Opcode.JALR, 0b000),
    # Branches
    InstrSpec("beq", Fmt.B, Opcode.BRANCH, 0b000),
    InstrSpec("bne", Fmt.B, Opcode.BRANCH, 0b001),
    InstrSpec("blt", Fmt.B, Opcode.BRANCH, 0b100),
    InstrSpec("bge", Fmt.B, Opcode.BRANCH, 0b101),
    InstrSpec("bltu", Fmt.B, Opcode.BRANCH, 0b110),
    InstrSpec("bgeu", Fmt.B, Opcode.BRANCH, 0b111),
    # Loads and stores
    InstrSpec("lb", Fmt.I, Opcode.LOAD, 0b000),
    InstrSpec("lh", Fmt.I, Opcode.LOAD, 0b001),
    InstrSpec("lw", Fmt.I, Opcode.LOAD, 0b010),
    InstrSpec("lbu", Fmt.I, Opcode.LOAD, 0b100),
    InstrSpec("lhu", Fmt.I, Opcode.LOAD, 0b101),
    InstrSpec("sb", Fmt.S, Opcode.STORE, 0b000),
    InstrSpec("sh", Fmt.S, Opcode.STORE, 0b001),
    InstrSpec("sw", Fmt.S, Opcode.STORE, 0b010),
    # ALU with immediate
    InstrSpec("addi", Fmt.I, Opcode.OP_IMM, 0b000),
    InstrSpec("slti", Fmt.I, Opcode.OP_IMM, 0b010),
    InstrSpec("sltiu", Fmt.I, Opcode.OP_IMM, 0b011),
    InstrSpec("xori", Fmt.I, Opcode.OP_IMM, 0b100),
    InstrSpec("ori", Fmt.I, Opcode.OP_IMM, 0b110),
    InstrSpec("andi", Fmt.I, Opcode.OP_IMM, 0b111),
    InstrSpec("slli", Fmt.I, Opcode.OP_IMM, 0b001, 0b0000000),
    InstrSpec("srli", Fmt.I, Opcode.OP_IMM, 0b101, 0b0000000),
    InstrSpec("srai", Fmt.I, Opcode.OP_IMM, 0b101, 0b0100000),
    # ALU register-register
    InstrSpec("add", Fmt.R, Opcode.OP, 0b000, 0b0000000),
    InstrSpec("sub", Fmt.R, Opcode.OP, 0b000, 0b0100000),
    InstrSpec("sll", Fmt.R, Opcode.OP, 0b001, 0b0000000),
    InstrSpec("slt", Fmt.R, Opcode.OP, 0b010, 0b0000000),
    InstrSpec("sltu", Fmt.R, Opcode.OP, 0b011, 0b0000000),
    InstrSpec("xor", Fmt.R, Opcode.OP, 0b100, 0b0000000),
    InstrSpec("srl", Fmt.R, Opcode.OP, 0b101, 0b0000000),
    InstrSpec("sra", Fmt.R, Opcode.OP, 0b101, 0b0100000),
    InstrSpec("or", Fmt.R, Opcode.OP, 0b110, 0b0000000),
    InstrSpec("and", Fmt.R, Opcode.OP, 0b111, 0b0000000),
    # System: fixed encodings
    InstrSpec("fence", Fmt.SYS, Opcode.MISC_MEM),
    InstrSpec("ecall", Fmt.SYS, Opcode.SYSTEM),
    InstrSpec("ebreak", Fmt.SYS, Opcode.SYSTEM),
]

SPEC_BY_NAME: dict[str, InstrSpec] = {spec.name: spec for spec in SPECS}

SHIFT_IMM_NAMES = {"slli", "srli", "srai"}

# FENCE with pred=succ=iorw (what `fence` assembles to), ECALL, EBREAK.
FENCE_WORD = 0x0FF0000F
ECALL_WORD = 0x00000073
EBREAK_WORD = 0x00100073
