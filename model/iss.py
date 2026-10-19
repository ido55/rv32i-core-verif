"""RV32I instruction-set simulator (the golden model).

One call to `Iss.step()` executes one instruction and returns a `Retire`
record describing everything it changed. The RTL core exposes the same
fields on its retire port, so the scoreboard can compare them one-to-one.
"""

from dataclasses import dataclass

from model.alu import AluOp, alu
from model.decoder import decode
from model.isa import Fmt, to_s32, to_u32


class MisalignedAccess(Exception):
    """Misaligned load/store/fetch. RV32I allows trapping; this design does not support it."""


class MemoryAccessError(Exception):
    """Access outside the simulated memory."""


class Memory:
    """Flat little-endian byte-addressable memory starting at address `base`."""

    def __init__(self, size: int, base: int = 0):
        self.base = base
        self.data = bytearray(size)

    def _offset(self, addr: int, nbytes: int) -> int:
        offset = addr - self.base
        if offset < 0 or offset + nbytes > len(self.data):
            raise MemoryAccessError(f"access of {nbytes} bytes at 0x{addr:08x} out of range")
        return offset

    def load(self, addr: int, nbytes: int, signed: bool = False) -> int:
        """Read 1, 2 or 4 bytes; returns a 32-bit value (sign- or zero-extended)."""
        offset = self._offset(addr, nbytes)
        value = int.from_bytes(self.data[offset : offset + nbytes], "little", signed=signed)
        return to_u32(value)

    def store(self, addr: int, value: int, nbytes: int) -> None:
        offset = self._offset(addr, nbytes)
        mask = (1 << (8 * nbytes)) - 1
        self.data[offset : offset + nbytes] = (value & mask).to_bytes(nbytes, "little")

    def load_words(self, words: list[int], addr: int) -> None:
        """Copy a program (list of 32-bit words) into memory starting at `addr`."""
        for i, word in enumerate(words):
            self.store(addr + 4 * i, word, 4)


@dataclass(frozen=True)
class Retire:
    """Architectural effects of one retired instruction (mirrors the RTL retire port).

    Conventions (same as the RISC-V Formal Interface):
    - rd = 0 and rd_wdata = 0 when the instruction writes no register (or writes x0).
    - mem_addr is the word-aligned address of a load or store, else 0.
    - mem_rmask / mem_wmask are the bytes read / written (bit i = byte lane i), else 0.
    - For stores, mem_wdata holds the data already shifted into its byte lanes, as on the
      memory bus; else 0.
    """

    pc: int
    insn: int
    next_pc: int
    rd: int = 0
    rd_wdata: int = 0
    mem_addr: int = 0
    mem_rmask: int = 0
    mem_wdata: int = 0
    mem_wmask: int = 0
    halt: bool = False


ALU_OPS = {
    "add": AluOp.ADD, "sub": AluOp.SUB, "sll": AluOp.SLL, "slt": AluOp.SLT,
    "sltu": AluOp.SLTU, "xor": AluOp.XOR, "srl": AluOp.SRL, "sra": AluOp.SRA,
    "or": AluOp.OR, "and": AluOp.AND,
    "addi": AluOp.ADD, "slti": AluOp.SLT, "sltiu": AluOp.SLTU, "xori": AluOp.XOR,
    "ori": AluOp.OR, "andi": AluOp.AND, "slli": AluOp.SLL, "srli": AluOp.SRL,
    "srai": AluOp.SRA,
}  # fmt: skip

BRANCH_TAKEN = {
    "beq": lambda a, b: a == b,
    "bne": lambda a, b: a != b,
    "blt": lambda a, b: to_s32(a) < to_s32(b),
    "bge": lambda a, b: to_s32(a) >= to_s32(b),
    "bltu": lambda a, b: a < b,
    "bgeu": lambda a, b: a >= b,
}

LOADS = {"lb": (1, True), "lh": (2, True), "lw": (4, False), "lbu": (1, False), "lhu": (2, False)}
STORES = {"sb": 1, "sh": 2, "sw": 4}


class Iss:
    def __init__(self, mem: Memory, pc: int = 0):
        self.mem = mem
        self.pc = pc
        self.regs = [0] * 32  # regs[0] is never written, so x0 always reads 0
        self.halted = False

    def step(self) -> Retire:
        if self.halted:
            raise RuntimeError("step() called after the core halted")
        pc = self.pc
        if pc % 4:
            raise MisalignedAccess(f"misaligned fetch at 0x{pc:08x}")
        insn = self.mem.load(pc, 4)
        i = decode(insn)
        rs1 = self.regs[i.rs1]
        rs2 = self.regs[i.rs2]

        next_pc = to_u32(pc + 4)
        result = None  # value written to rd, if any
        mem_addr = mem_rmask = mem_wdata = mem_wmask = 0
        halt = False

        if i.name in ALU_OPS:
            operand_b = rs2 if i.fmt is Fmt.R else to_u32(i.imm)
            result = alu(ALU_OPS[i.name], rs1, operand_b)
        elif i.name == "lui":
            result = to_u32(i.imm << 12)
        elif i.name == "auipc":
            result = to_u32(pc + (i.imm << 12))
        elif i.name == "jal":
            result = to_u32(pc + 4)
            next_pc = to_u32(pc + i.imm)
        elif i.name == "jalr":
            result = to_u32(pc + 4)
            next_pc = to_u32(rs1 + i.imm) & ~1  # spec: clear bit 0 of the target
        elif i.name in BRANCH_TAKEN:
            if BRANCH_TAKEN[i.name](rs1, rs2):
                next_pc = to_u32(pc + i.imm)
        elif i.name in LOADS:
            nbytes, signed = LOADS[i.name]
            addr = to_u32(rs1 + i.imm)
            if addr % nbytes:
                raise MisalignedAccess(f"{i.name} at 0x{addr:08x}")
            result = self.mem.load(addr, nbytes, signed)
            lane = addr % 4
            mem_addr = addr - lane
            mem_rmask = ((1 << nbytes) - 1) << lane
        elif i.name in STORES:
            nbytes = STORES[i.name]
            addr = to_u32(rs1 + i.imm)
            if addr % nbytes:
                raise MisalignedAccess(f"{i.name} at 0x{addr:08x}")
            self.mem.store(addr, rs2, nbytes)
            lane = addr % 4
            mem_addr = addr - lane
            mem_wmask = ((1 << nbytes) - 1) << lane
            mem_wdata = to_u32((rs2 & ((1 << (8 * nbytes)) - 1)) << (8 * lane))
        elif i.name == "fence":
            pass  # single hart, no caches: nothing to order
        elif i.name in ("ecall", "ebreak"):
            halt = True
            next_pc = pc

        if next_pc % 4:
            raise MisalignedAccess(f"{i.name} at 0x{pc:08x} jumps to 0x{next_pc:08x}")

        rd, rd_wdata = 0, 0
        if result is not None and i.rd != 0:
            self.regs[i.rd] = result
            rd, rd_wdata = i.rd, result

        self.pc = next_pc
        self.halted = halt
        return Retire(
            pc, insn, next_pc, rd, rd_wdata, mem_addr, mem_rmask, mem_wdata, mem_wmask, halt
        )

    def run(self, max_steps: int = 100_000) -> list[Retire]:
        """Step until ECALL/EBREAK; returns the full retire trace."""
        trace = []
        while not self.halted:
            if len(trace) >= max_steps:
                raise RuntimeError(f"no halt within {max_steps} instructions")
            trace.append(self.step())
        return trace
