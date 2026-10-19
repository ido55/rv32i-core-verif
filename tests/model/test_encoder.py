"""Encoder/decoder tests: known words, round trips, range checks and a GNU as cross-check."""

import random
import shutil
import subprocess

import pytest

from model.decoder import IllegalInstruction, Instr, decode, to_asm
from model.encoder import encode
from model.isa import SHIFT_IMM_NAMES, SPECS, Fmt

# Hand-checked against the RISC-V spec encoding tables.
KNOWN_WORDS = [
    (("addi", 1, 0, 0, 1), 0x00100093),
    (("addi", 0, 0, 0, 0), 0x00000013),  # canonical NOP
    (("add", 3, 1, 2, 0), 0x002081B3),
    (("sub", 3, 1, 2, 0), 0x402081B3),
    (("lui", 5, 0, 0, 0x12345), 0x123452B7),
    (("sw", 0, 1, 2, 8), 0x0020A423),
    (("lw", 4, 2, 0, -4), 0xFFC12203),
    (("srai", 1, 2, 0, 3), 0x40315093),
    (("jal", 1, 0, 0, 8), 0x008000EF),
    (("beq", 0, 1, 2, -4), 0xFE208EE3),
    (("ecall", 0, 0, 0, 0), 0x00000073),
    (("ebreak", 0, 0, 0, 0), 0x00100073),
]


def random_instr(rng: random.Random, name: str) -> Instr:
    """A random legal instance of instruction `name` (fields a format ignores are 0)."""
    spec = next(s for s in SPECS if s.name == name)
    rd, rs1, rs2 = (rng.randrange(32) for _ in range(3))
    if spec.fmt is Fmt.R:
        return Instr(name, spec.fmt, rd=rd, rs1=rs1, rs2=rs2)
    if spec.fmt is Fmt.I:
        imm = rng.randrange(32) if name in SHIFT_IMM_NAMES else rng.randint(-2048, 2047)
        return Instr(name, spec.fmt, rd=rd, rs1=rs1, imm=imm)
    if spec.fmt is Fmt.S:
        return Instr(name, spec.fmt, rs1=rs1, rs2=rs2, imm=rng.randint(-2048, 2047))
    if spec.fmt is Fmt.B:
        return Instr(name, spec.fmt, rs1=rs1, rs2=rs2, imm=2 * rng.randint(-2048, 2047))
    if spec.fmt is Fmt.U:
        return Instr(name, spec.fmt, rd=rd, imm=rng.randrange(1 << 20))
    if spec.fmt is Fmt.J:
        return Instr(name, spec.fmt, rd=rd, imm=2 * rng.randint(-(1 << 19), (1 << 19) - 1))
    return Instr(name, spec.fmt)


def encode_instr(i: Instr) -> int:
    return encode(i.name, rd=i.rd, rs1=i.rs1, rs2=i.rs2, imm=i.imm)


@pytest.mark.parametrize(("fields", "word"), KNOWN_WORDS, ids=lambda x: str(x))
def test_known_encodings(fields, word):
    name, rd, rs1, rs2, imm = fields
    assert encode(name, rd=rd, rs1=rs1, rs2=rs2, imm=imm) == word
    assert decode(word) == Instr(name, decode(word).fmt, rd=rd, rs1=rs1, rs2=rs2, imm=imm)


@pytest.mark.parametrize("name", [s.name for s in SPECS])
def test_round_trip(name):
    rng = random.Random(name)  # deterministic per instruction
    for _ in range(200):
        instr = random_instr(rng, name)
        assert decode(encode_instr(instr)) == instr


@pytest.mark.parametrize(
    ("name", "imm"),
    [
        ("addi", 2048), ("addi", -2049), ("slli", 32), ("sw", 2048),
        ("beq", 3), ("beq", 4096), ("jal", 1), ("jal", 1 << 20), ("lui", 1 << 20), ("lui", -1),
    ],
)  # fmt: skip
def test_immediate_out_of_range(name, imm):
    with pytest.raises(ValueError):
        encode(name, imm=imm)


def test_register_out_of_range():
    with pytest.raises(ValueError):
        encode("add", rd=32)


@pytest.mark.parametrize(
    "word",
    [
        0x00000000,  # all zeros is defined as illegal
        0xFFFFFFFF,
        0x022081B3,  # mul x3, x1, x2 (M extension, not supported)
        0x30001073,  # csrrw (Zicsr, not supported)
        0x0000B083,  # ld (RV64 only)
        0x40209093,  # slli with imm[11:5] != 0
        0x00001067,  # jalr with funct3 != 0
    ],
)
def test_illegal_words(word):
    with pytest.raises(IllegalInstruction):
        decode(word)


GCC = "riscv64-unknown-elf-gcc"
OBJCOPY = "riscv64-unknown-elf-objcopy"


@pytest.mark.skipif(shutil.which(GCC) is None, reason="RISC-V GCC toolchain not installed")
def test_encoder_matches_gnu_as(tmp_path):
    """Assemble 40 random instances of every instruction with GNU as and compare words."""
    rng = random.Random(2026)
    instrs = [random_instr(rng, s.name) for s in SPECS for _ in range(40)]
    rng.shuffle(instrs)

    src = tmp_path / "prog.S"
    src.write_text(".option norelax\n.text\n" + "\n".join(to_asm(i) for i in instrs) + "\n")
    elf, binary = tmp_path / "prog.elf", tmp_path / "prog.bin"
    subprocess.run(
        [GCC, "-march=rv32i", "-mabi=ilp32", "-nostdlib", "-Wl,-Ttext=0x80000000",
         "-Wl,--no-warn-rwx-segments", "-o", elf, src],
        check=True,
    )  # fmt: skip
    subprocess.run([OBJCOPY, "-O", "binary", "-j", ".text", elf, binary], check=True)

    data = binary.read_bytes()
    gnu_words = [int.from_bytes(data[k : k + 4], "little") for k in range(0, len(data), 4)]
    assert len(gnu_words) == len(instrs)
    for instr, gnu in zip(instrs, gnu_words, strict=True):
        assert encode_instr(instr) == gnu, f"{to_asm(instr)}: ours 0x{encode_instr(instr):08x}"
