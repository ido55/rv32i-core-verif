"""Encode RV32I instructions into 32-bit machine words.

Immediates follow assembly-language conventions:
- I/S: signed 12-bit, -2048..2047 (shift-immediates: shamt 0..31)
- B:   signed byte offset, even, -4096..4094
- J:   signed byte offset, even, -1048576..1048574
- U:   the 20-bit upper immediate, 0..0xFFFFF (as in `lui x1, 0x12345`)
"""

from model.isa import (
    EBREAK_WORD,
    ECALL_WORD,
    FENCE_WORD,
    SHIFT_IMM_NAMES,
    SPEC_BY_NAME,
    Fmt,
)


def _check_reg(reg: int) -> None:
    if not 0 <= reg <= 31:
        raise ValueError(f"register x{reg} out of range")


def _check_range(name: str, imm: int, lo: int, hi: int, even: bool = False) -> None:
    if not lo <= imm <= hi:
        raise ValueError(f"{name}: immediate {imm} outside [{lo}, {hi}]")
    if even and imm % 2:
        raise ValueError(f"{name}: offset {imm} must be even")


def encode(name: str, rd: int = 0, rs1: int = 0, rs2: int = 0, imm: int = 0) -> int:
    """Return the machine word for one instruction.

    >>> hex(encode("addi", rd=1, rs1=0, imm=1))
    '0x100093'
    """
    spec = SPEC_BY_NAME[name]
    for reg in (rd, rs1, rs2):
        _check_reg(reg)
    op, f3, f7 = int(spec.opcode), spec.funct3, spec.funct7

    if spec.fmt is Fmt.R:
        return (f7 << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op

    if spec.fmt is Fmt.I:
        if name in SHIFT_IMM_NAMES:
            _check_range(name, imm, 0, 31)
            imm12 = (f7 << 5) | imm
        else:
            _check_range(name, imm, -2048, 2047)
            imm12 = imm & 0xFFF
        return (imm12 << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op

    if spec.fmt is Fmt.S:
        _check_range(name, imm, -2048, 2047)
        imm12 = imm & 0xFFF
        return (
            ((imm12 >> 5) << 25)
            | (rs2 << 20)
            | (rs1 << 15)
            | (f3 << 12)
            | ((imm12 & 0x1F) << 7)
            | op
        )

    if spec.fmt is Fmt.B:
        _check_range(name, imm, -4096, 4094, even=True)
        imm13 = imm & 0x1FFF
        return (
            (((imm13 >> 12) & 0x1) << 31)
            | (((imm13 >> 5) & 0x3F) << 25)
            | (rs2 << 20)
            | (rs1 << 15)
            | (f3 << 12)
            | (((imm13 >> 1) & 0xF) << 8)
            | (((imm13 >> 11) & 0x1) << 7)
            | op
        )

    if spec.fmt is Fmt.U:
        _check_range(name, imm, 0, 0xFFFFF)
        return (imm << 12) | (rd << 7) | op

    if spec.fmt is Fmt.J:
        _check_range(name, imm, -(1 << 20), (1 << 20) - 2, even=True)
        imm21 = imm & 0x1FFFFF
        return (
            (((imm21 >> 20) & 0x1) << 31)
            | (((imm21 >> 1) & 0x3FF) << 21)
            | (((imm21 >> 11) & 0x1) << 20)
            | (((imm21 >> 12) & 0xFF) << 12)
            | (rd << 7)
            | op
        )

    # Fmt.SYS: fixed words, operands are ignored.
    return {"fence": FENCE_WORD, "ecall": ECALL_WORD, "ebreak": EBREAK_WORD}[name]
