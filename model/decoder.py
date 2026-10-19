"""Decode 32-bit RV32I machine words, and format them as assembly text.

The decoded immediate uses the same convention as the encoder, so
`decode(encode(name, ...))` returns the same fields. Operand fields that a
format does not use are reported as 0.
"""

from dataclasses import dataclass

from model.isa import (
    EBREAK_WORD,
    ECALL_WORD,
    SHIFT_IMM_NAMES,
    SPECS,
    Fmt,
    Opcode,
    sign_extend,
)


class IllegalInstruction(ValueError):
    """Raised for a word that is not a supported RV32I instruction."""


@dataclass(frozen=True)
class Instr:
    name: str
    fmt: Fmt
    rd: int = 0
    rs1: int = 0
    rs2: int = 0
    imm: int = 0


# Lookup key: (opcode, funct3, funct7). funct3/funct7 are None where the
# format does not use them, so e.g. every JAL word maps to (JAL, None, None).
def _key(opcode: int, fmt: Fmt, funct3: int, funct7: int, name: str) -> tuple:
    if fmt in (Fmt.U, Fmt.J):
        return (opcode, None, None)
    if fmt is Fmt.R or name in SHIFT_IMM_NAMES:
        return (opcode, funct3, funct7)
    return (opcode, funct3, None)


_LOOKUP = {
    _key(int(s.opcode), s.fmt, s.funct3, s.funct7, s.name): s for s in SPECS if s.fmt is not Fmt.SYS
}


def decode(word: int) -> Instr:
    opcode = word & 0x7F
    rd = (word >> 7) & 0x1F
    funct3 = (word >> 12) & 0x7
    rs1 = (word >> 15) & 0x1F
    rs2 = (word >> 20) & 0x1F
    funct7 = (word >> 25) & 0x7F

    # System instructions have fixed encodings (FENCE fields are ignored).
    if opcode == Opcode.MISC_MEM and funct3 == 0:
        return Instr("fence", Fmt.SYS)
    if word == ECALL_WORD:
        return Instr("ecall", Fmt.SYS)
    if word == EBREAK_WORD:
        return Instr("ebreak", Fmt.SYS)

    spec = (
        _LOOKUP.get((opcode, None, None))
        or _LOOKUP.get((opcode, funct3, funct7))
        or _LOOKUP.get((opcode, funct3, None))
    )
    if spec is None:
        raise IllegalInstruction(f"illegal instruction 0x{word:08x}")

    if spec.fmt is Fmt.R:
        return Instr(spec.name, spec.fmt, rd=rd, rs1=rs1, rs2=rs2)
    if spec.fmt is Fmt.I:
        if spec.name in SHIFT_IMM_NAMES:
            return Instr(spec.name, spec.fmt, rd=rd, rs1=rs1, imm=rs2)  # shamt = bits 24:20
        return Instr(spec.name, spec.fmt, rd=rd, rs1=rs1, imm=sign_extend(word >> 20, 12))
    if spec.fmt is Fmt.S:
        imm = (funct7 << 5) | rd
        return Instr(spec.name, spec.fmt, rs1=rs1, rs2=rs2, imm=sign_extend(imm, 12))
    if spec.fmt is Fmt.B:
        imm = (
            (((word >> 31) & 0x1) << 12)
            | (((word >> 7) & 0x1) << 11)
            | (((word >> 25) & 0x3F) << 5)
            | (((word >> 8) & 0xF) << 1)
        )
        return Instr(spec.name, spec.fmt, rs1=rs1, rs2=rs2, imm=sign_extend(imm, 13))
    if spec.fmt is Fmt.U:
        return Instr(spec.name, spec.fmt, rd=rd, imm=word >> 12)
    # Fmt.J
    imm = (
        (((word >> 31) & 0x1) << 20)
        | (((word >> 12) & 0xFF) << 12)
        | (((word >> 20) & 0x1) << 11)
        | (((word >> 21) & 0x3FF) << 1)
    )
    return Instr(spec.name, spec.fmt, rd=rd, imm=sign_extend(imm, 21))


def to_asm(instr: Instr) -> str:
    """Format a decoded instruction as GNU assembler syntax.

    Branch/jump targets are written relative to the current address (`.+8`),
    which GNU as accepts; this lets tests cross-check the encoder against it.
    """
    n, rd, rs1, rs2, imm = instr.name, instr.rd, instr.rs1, instr.rs2, instr.imm
    if instr.fmt is Fmt.SYS:
        return n
    if instr.fmt is Fmt.R:
        return f"{n} x{rd}, x{rs1}, x{rs2}"
    if instr.fmt is Fmt.U:
        return f"{n} x{rd}, 0x{imm:x}"
    if instr.fmt is Fmt.J:
        return f"{n} x{rd}, .{imm:+d}"
    if instr.fmt is Fmt.B:
        return f"{n} x{rs1}, x{rs2}, .{imm:+d}"
    if instr.fmt is Fmt.S:
        return f"{n} x{rs2}, {imm}(x{rs1})"
    if n in ("jalr", "lb", "lh", "lw", "lbu", "lhu"):
        return f"{n} x{rd}, {imm}(x{rs1})"
    return f"{n} x{rd}, x{rs1}, {imm}"
