"""Constrained-random RV32I program generator.

A program is a sequence of *blocks*. Each block type has one constraint that keeps the
whole program legal, so every generated program runs to its final ECALL:

- alu / upper: any ALU, LUI or AUIPC instruction; no constraint needed.
- memory:      the base register is loaded with `li` right before the load/store, so the
               address is always aligned and inside the data region.
- branch/jal:  forward only; they skip 0-3 ALU instructions.
- jalr:        AUIPC + JALR, also forward only (sometimes with bit 0 set, which JALR clears).
- loop:        the only backward branch: a counter register set to 1..4, decremented in the
               loop and never written by the loop body, so the loop always ends.

Register choice is biased towards registers written in the last three instructions, to
create read-after-write dependencies (what the pipeline's forwarding must handle in M4).
The same seed always produces the same program.
"""

import random
from dataclasses import dataclass

from model.encoder import encode as e
from model.encoder import load_immediate as li

DATA_BASE = 0x2000
DATA_BYTES = 0x800  # loads/stores stay inside 0x2000..0x27FF
MAX_CODE_WORDS = DATA_BASE // 4  # code must stay below the data region

ALU_R = ["add", "sub", "sll", "slt", "sltu", "xor", "srl", "sra", "or", "and"]
ALU_I = ["addi", "slti", "sltiu", "xori", "ori", "andi"]
SHIFT_I = ["slli", "srli", "srai"]
BRANCHES = ["beq", "bne", "blt", "bge", "bltu", "bgeu"]
LOADS = {"lb": 1, "lh": 2, "lw": 4, "lbu": 1, "lhu": 2}
STORES = {"sb": 1, "sh": 2, "sw": 4}

INTERESTING_VALUES = [
    0x0000_0000, 0x0000_0001, 0x0000_0002, 0x0000_001F, 0x0000_0020,
    0x7FFF_FFFF, 0x8000_0000, 0x8000_0001, 0xFFFF_FFFE, 0xFFFF_FFFF,
]  # fmt: skip
INTERESTING_IMMEDIATES = [0, 1, -1, 2, 31, 2047, -2048, 0x400, -0x400]

BLOCK_WEIGHTS = {
    "alu": 40,
    "memory": 20,
    "branch": 15,
    "upper": 5,
    "jal": 5,
    "jalr": 5,
    "loop": 5,
    "fence": 1,
}


@dataclass(frozen=True)
class RandomProgram:
    seed: int
    words: list[int]  # code, starting at address 0, ending with ECALL
    data: dict[int, int]  # initial data memory {byte address: word}


class Generator:
    def __init__(self, seed: int, blocks: int = 150):
        self.seed = seed
        self.rng = random.Random(seed)
        self.blocks = blocks
        self.words: list[int] = []
        self.recent: list[int] = []  # destination registers of the last few instructions

    # ---- Random choices ---------------------------------------------------------------

    def value(self) -> int:
        """A 32-bit value: half the time an edge case, otherwise uniform."""
        if self.rng.random() < 0.5:
            return self.rng.choice(INTERESTING_VALUES)
        return self.rng.getrandbits(32)

    def imm12(self) -> int:
        if self.rng.random() < 0.4:
            return self.rng.choice(INTERESTING_IMMEDIATES)
        return self.rng.randint(-2048, 2047)

    def dest(self, exclude: tuple[int, ...] = ()) -> int:
        """A destination register; occasionally x0, whose writes must be discarded."""
        while True:
            reg = 0 if self.rng.random() < 0.03 else self.rng.randrange(1, 32)
            if reg not in exclude:
                return reg

    def source(self) -> int:
        """A source register, often one of the last three destinations (a RAW hazard)."""
        if self.recent and self.rng.random() < 0.5:
            return self.rng.choice(self.recent)
        return self.rng.randrange(32)

    # ---- Emitting instructions ----------------------------------------------------------

    def emit(self, word: int, rd: int = 0) -> None:
        self.words.append(word)
        self.recent = (self.recent + [rd])[-3:] if rd else self.recent

    def emit_li(self, rd: int, value: int) -> None:
        for word in li(rd, value):
            self.emit(word, rd)

    def alu_instruction(self, exclude: tuple[int, ...] = ()) -> None:
        """One ALU instruction (register, immediate or shift) not writing `exclude`."""
        rd = self.dest(exclude)
        kind = self.rng.random()
        if kind < 0.45:
            op = self.rng.choice(ALU_R)
            self.emit(e(op, rd=rd, rs1=self.source(), rs2=self.source()), rd)
        elif kind < 0.8:
            op = self.rng.choice(ALU_I)
            self.emit(e(op, rd=rd, rs1=self.source(), imm=self.imm12()), rd)
        else:
            op = self.rng.choice(SHIFT_I)
            self.emit(e(op, rd=rd, rs1=self.source(), imm=self.rng.randrange(32)), rd)

    def skipped_instructions(self, count: int) -> None:
        """Instructions that a forward branch or jump may skip over."""
        for _ in range(count):
            self.alu_instruction()

    # ---- Blocks -------------------------------------------------------------------------

    def block_alu(self) -> None:
        self.alu_instruction()

    def block_upper(self) -> None:
        rd = self.dest()
        op = self.rng.choice(["lui", "auipc"])
        self.emit(e(op, rd=rd, imm=self.rng.getrandbits(20)), rd)

    def block_memory(self) -> None:
        is_load = self.rng.random() < 0.5
        op = self.rng.choice(list(LOADS if is_load else STORES))
        size = (LOADS if is_load else STORES)[op]
        addr = DATA_BASE + size * self.rng.randrange(DATA_BYTES // size)
        offset = self.imm12()
        base = self.rng.randrange(1, 32)
        self.emit_li(base, addr - offset)  # so that base + offset == addr
        for _ in range(self.rng.randint(0, 2)):  # 0 = base is used right after it is written
            self.alu_instruction(exclude=(base,))
        if is_load:
            rd = self.dest()
            self.emit(e(op, rd=rd, rs1=base, imm=offset), rd)
        else:
            self.emit(e(op, rs1=base, rs2=self.source(), imm=offset))

    def block_branch(self) -> None:
        op = self.rng.choice(BRANCHES)
        rs1 = self.source()
        rs2 = rs1 if self.rng.random() < 0.2 else self.source()  # equal operands
        skip = self.rng.randint(0, 3)
        self.emit(e(op, rs1=rs1, rs2=rs2, imm=4 * (skip + 1)))
        self.skipped_instructions(skip)

    def block_jal(self) -> None:
        rd = self.dest()
        skip = self.rng.randint(0, 3)
        self.emit(e("jal", rd=rd, imm=4 * (skip + 1)), rd)
        self.skipped_instructions(skip)

    def block_jalr(self) -> None:
        # auipc base, 0      <- base = address of this instruction (P)
        # jalr  rd, off(base)   target = P + 8 + 4 * skip, i.e. just past the skipped ones
        base = self.rng.randrange(1, 32)
        rd = self.dest()
        skip = self.rng.randint(0, 3)
        offset = 8 + 4 * skip + (1 if self.rng.random() < 0.3 else 0)  # bit 0 is cleared
        self.emit(e("auipc", rd=base, imm=0), base)
        self.emit(e("jalr", rd=rd, rs1=base, imm=offset), rd)
        self.skipped_instructions(skip)

    def block_loop(self) -> None:
        counter = self.rng.randrange(1, 32)
        self.emit_li(counter, self.rng.randint(1, 4))
        body_start = len(self.words)
        for _ in range(self.rng.randint(1, 4)):
            self.alu_instruction(exclude=(counter,))
        self.emit(e("addi", rd=counter, rs1=counter, imm=-1), counter)
        back = 4 * (len(self.words) - body_start)
        self.emit(e("bne", rs1=counter, rs2=0, imm=-back))

    def block_fence(self) -> None:
        self.emit(e("fence"))

    # ---- Whole program ------------------------------------------------------------------

    def generate(self) -> RandomProgram:
        for reg in range(1, 32):  # start from random register values, not all zeros
            if self.rng.random() < 0.5:
                self.emit_li(reg, self.value())
        names = list(BLOCK_WEIGHTS)
        weights = list(BLOCK_WEIGHTS.values())
        for _ in range(self.blocks):
            getattr(self, f"block_{self.rng.choices(names, weights)[0]}")()
        self.emit(e("ecall"))
        assert len(self.words) <= MAX_CODE_WORDS, "program too long for the code region"

        data = {DATA_BASE + 4 * k: self.value() for k in range(DATA_BYTES // 4)}
        return RandomProgram(self.seed, self.words, data)


def random_program(seed: int, blocks: int = 150) -> RandomProgram:
    return Generator(seed, blocks).generate()
