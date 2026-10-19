"""ISS tests: one or more directed cases per RV32I instruction, expected values by hand."""

import pytest

from model.encoder import encode as e
from model.encoder import load_immediate
from model.isa import SPEC_BY_NAME, Fmt
from model.iss import Iss, Memory, MemoryAccessError, MisalignedAccess

MEM_SIZE = 0x1000
DATA = 0x800  # data area used by load/store tests


def make_iss(program: list[int], regs: dict[int, int] | None = None) -> Iss:
    """Load `program` at address 0, followed by ECALL, and preset some registers."""
    mem = Memory(MEM_SIZE)
    mem.load_words(program + [e("ecall")], 0)
    iss = Iss(mem)
    for reg, value in (regs or {}).items():
        iss.regs[reg] = value
    return iss


def run(program: list[int], regs: dict[int, int] | None = None) -> Iss:
    iss = make_iss(program, regs)
    iss.run()
    return iss


# ---- ALU register-register and immediate ---------------------------------------------

ALU_CASES = [
    # (instruction, rs1 value, rs2 value or immediate, expected rd)
    ("add", 5, 7, 12),
    ("sub", 5, 7, 0xFFFF_FFFE),
    ("sll", 1, 35, 8),  # shift amount is rs2[4:0] = 3
    ("slt", 0xFFFF_FFFF, 1, 1),
    ("sltu", 0xFFFF_FFFF, 1, 0),
    ("xor", 0b1100, 0b1010, 0b0110),
    ("srl", 0x8000_0000, 4, 0x0800_0000),
    ("sra", 0x8000_0000, 4, 0xF800_0000),
    ("or", 0b1100, 0b1010, 0b1110),
    ("and", 0b1100, 0b1010, 0b1000),
    ("addi", 5, -7, 0xFFFF_FFFE),
    ("slti", 0xFFFF_FFFE, -1, 1),  # -2 < -1
    ("sltiu", 5, -1, 1),  # imm -1 sign-extends to 0xFFFFFFFF, then compares unsigned
    ("xori", 0x0F, -1, 0xFFFF_FFF0),  # xori rd, rs1, -1 is bitwise NOT
    ("ori", 0x100, 0x0FF, 0x1FF),
    ("andi", 0xFFFF_FFFF, -16, 0xFFFF_FFF0),
    ("slli", 1, 31, 0x8000_0000),
    ("srli", 0xFFFF_FFFF, 31, 1),
    ("srai", 0xFFFF_FFFF, 31, 0xFFFF_FFFF),
]


@pytest.mark.parametrize(("name", "a", "b", "expected"), ALU_CASES)
def test_alu_instructions(name, a, b, expected):
    if SPEC_BY_NAME[name].fmt is Fmt.R:
        iss = run([e(name, rd=3, rs1=1, rs2=2)], {1: a, 2: b})
    else:
        iss = run([e(name, rd=3, rs1=1, imm=b)], {1: a})
    assert iss.regs[3] == expected


def test_write_to_x0_is_ignored():
    iss = make_iss([e("addi", rd=0, rs1=0, imm=123)])
    retire = iss.step()
    assert iss.regs[0] == 0
    assert (retire.rd, retire.rd_wdata) == (0, 0)  # RVFI convention: no write reported


def test_rd_equals_rs1():
    iss = run([e("addi", rd=1, rs1=1, imm=1), e("addi", rd=1, rs1=1, imm=1)], {1: 10})
    assert iss.regs[1] == 12


# ---- Upper immediates -------------------------------------------------------------------


def test_lui():
    iss = run([e("lui", rd=1, imm=0xFFFFF)])
    assert iss.regs[1] == 0xFFFF_F000


def test_lui_addi_builds_constant():
    # 0x12345678 = lui 0x12345 + addi 0x678
    iss = run([e("lui", rd=1, imm=0x12345), e("addi", rd=1, rs1=1, imm=0x678)])
    assert iss.regs[1] == 0x1234_5678


def test_auipc():
    iss = run([e("addi", rd=0), e("auipc", rd=1, imm=0x1)])  # auipc at pc=4
    assert iss.regs[1] == 0x1004


# ---- Jumps ------------------------------------------------------------------------------


def test_jal_links_and_jumps():
    # 0: jal x1, +8 ; 4: addi x2, x0, 1 (skipped) ; 8: ecall
    iss = make_iss([e("jal", rd=1, imm=8), e("addi", rd=2, imm=1)])
    retire = iss.step()
    assert (retire.next_pc, retire.rd, retire.rd_wdata) == (8, 1, 4)
    iss.run()
    assert iss.regs[2] == 0


def test_jal_backwards():
    # 0: jal x0, +8 ; 4: ecall ; 8: jal x0, -4  -> ends at the ecall at 4
    mem = Memory(MEM_SIZE)
    mem.load_words([e("jal", imm=8), e("ecall"), e("jal", imm=-4)], 0)
    iss = Iss(mem)
    trace = iss.run()
    assert [r.pc for r in trace] == [0, 8, 4]


def test_jalr_clears_bit0_and_handles_rd_equals_rs1():
    # jalr x1, 1(x1) with x1 = 8: target = (8 + 1) & ~1 = 8, link = 4
    iss = make_iss([e("jalr", rd=1, rs1=1, imm=1)], {1: 8})
    retire = iss.step()
    assert retire.next_pc == 8
    assert iss.regs[1] == 4


# ---- Branches ---------------------------------------------------------------------------

BRANCH_CASES = [
    # (branch, rs1, rs2, taken)
    ("beq", 7, 7, True),
    ("beq", 7, 8, False),
    ("bne", 7, 8, True),
    ("bne", 7, 7, False),
    ("blt", 0xFFFF_FFFF, 0, True),  # -1 < 0 signed
    ("blt", 0, 0xFFFF_FFFF, False),
    ("bge", 0, 0xFFFF_FFFF, True),
    ("bge", 5, 5, True),  # equal counts as >=
    ("bge", 0xFFFF_FFFF, 0, False),
    ("bltu", 0, 0xFFFF_FFFF, True),
    ("bltu", 0xFFFF_FFFF, 0, False),
    ("bgeu", 0xFFFF_FFFF, 0, True),
    ("bgeu", 0, 1, False),
]


@pytest.mark.parametrize(("name", "a", "b", "taken"), BRANCH_CASES)
def test_branches(name, a, b, taken):
    iss = make_iss([e(name, rs1=1, rs2=2, imm=12)], {1: a, 2: b})
    retire = iss.step()
    assert retire.next_pc == (12 if taken else 4)
    assert retire.rd == 0  # branches never write a register


# ---- Loads and stores -------------------------------------------------------------------


def _iss_with_data(program: list[int], word: int) -> Iss:
    iss = make_iss(program, {1: DATA})
    iss.mem.store(DATA, word, 4)
    return iss


@pytest.mark.parametrize(
    ("name", "offset", "expected"),
    [
        ("lw", 0, 0x8081_8283),
        ("lb", 0, 0xFFFF_FF83),  # byte 0 = 0x83, sign-extended
        ("lb", 3, 0xFFFF_FF80),
        ("lbu", 0, 0x0000_0083),
        ("lh", 0, 0xFFFF_8283),
        ("lh", 2, 0xFFFF_8081),
        ("lhu", 2, 0x0000_8081),
    ],
)
def test_loads(name, offset, expected):
    iss = _iss_with_data([e(name, rd=2, rs1=1, imm=offset)], 0x8081_8283)
    retire = iss.step()
    assert iss.regs[2] == expected
    width = {"lw": 4, "lh": 2, "lhu": 2}.get(name, 1)
    assert retire.mem_addr == DATA  # word-aligned
    assert retire.mem_rmask == ((1 << width) - 1) << offset
    assert retire.mem_wmask == 0


def test_load_with_negative_offset():
    iss = make_iss([e("lw", rd=2, rs1=1, imm=-4)], {1: DATA + 4})
    iss.mem.store(DATA, 0xCAFE_F00D, 4)
    iss.run()
    assert iss.regs[2] == 0xCAFE_F00D


@pytest.mark.parametrize(
    ("name", "offset", "mask", "lane_data", "memory_after"),
    [
        ("sw", 0, 0b1111, 0xAABB_CCDD, 0xAABB_CCDD),
        ("sh", 0, 0b0011, 0x0000_CCDD, 0x1111_CCDD),
        ("sh", 2, 0b1100, 0xCCDD_0000, 0xCCDD_1111),
        ("sb", 0, 0b0001, 0x0000_00DD, 0x1111_11DD),
        ("sb", 1, 0b0010, 0x0000_DD00, 0x1111_DD11),
        ("sb", 3, 0b1000, 0xDD00_0000, 0xDD11_1111),
    ],
)
def test_stores(name, offset, mask, lane_data, memory_after):
    iss = make_iss([e(name, rs1=1, rs2=2, imm=offset)], {1: DATA, 2: 0xAABB_CCDD})
    iss.mem.store(DATA, 0x1111_1111, 4)
    retire = iss.step()
    assert (retire.mem_addr, retire.mem_wmask, retire.mem_wdata) == (DATA, mask, lane_data)
    assert retire.rd == 0
    assert retire.mem_rmask == 0
    assert iss.mem.load(DATA, 4) == memory_after


@pytest.mark.parametrize(
    ("name", "offset"), [("lw", 2), ("lh", 1), ("lhu", 3), ("sw", 1), ("sh", 3)]
)
def test_misaligned_access_raises(name, offset):
    instr = e(name, rd=2, rs1=1, imm=offset) if name[0] == "l" else e(name, rs1=1, imm=offset)
    with pytest.raises(MisalignedAccess):
        run([instr], {1: DATA})


def test_out_of_range_access_raises():
    with pytest.raises(MemoryAccessError):
        run([e("lw", rd=2, rs1=1)], {1: MEM_SIZE})


# ---- System -----------------------------------------------------------------------------


def test_fence_is_nop():
    iss = make_iss([e("fence")])
    retire = iss.step()
    assert (retire.next_pc, retire.rd, retire.mem_wmask) == (4, 0, 0)


@pytest.mark.parametrize("name", ["ecall", "ebreak"])
def test_halt(name):
    mem = Memory(MEM_SIZE)
    mem.load_words([e(name)], 0)
    iss = Iss(mem)
    retire = iss.step()
    assert retire.halt and iss.halted
    with pytest.raises(RuntimeError):
        iss.step()


def test_run_without_halt_raises():
    mem = Memory(MEM_SIZE)
    mem.load_words([e("jal", imm=0)], 0)  # jump-to-self forever
    with pytest.raises(RuntimeError):
        Iss(mem).run(max_steps=100)


# ---- load_immediate (li pseudo-instruction) --------------------------------------------


@pytest.mark.parametrize(
    "value",
    [0, 1, -1, 2047, 2048, -2048, -2049, 0x800, 0xFFF, 0x1000, 0x7FFF_FFFF, 0x8000_0000,
     0x8000_0800, 0xFFFF_F800, 0xFFFF_F7FF, 0x1234_5678, 0xDEAD_BEEF],
)  # fmt: skip
def test_load_immediate(value):
    program = load_immediate(5, value)
    iss = run(program)
    assert iss.regs[5] == value & 0xFFFF_FFFF
    assert len(program) <= 2


# ---- A small program --------------------------------------------------------------------


def test_sum_1_to_10_loop():
    #   addi x1, x0, 10      # counter
    #   addi x2, x0, 0       # sum
    # loop:
    #   add  x2, x2, x1
    #   addi x1, x1, -1
    #   bne  x1, x0, loop    # -8
    program = [
        e("addi", rd=1, imm=10),
        e("addi", rd=2, imm=0),
        e("add", rd=2, rs1=2, rs2=1),
        e("addi", rd=1, rs1=1, imm=-1),
        e("bne", rs1=1, rs2=0, imm=-8),
    ]
    iss = make_iss(program)
    trace = iss.run()
    assert iss.regs[2] == 55
    assert len(trace) == 2 + 3 * 10 + 1  # setup + 10 iterations + ecall
