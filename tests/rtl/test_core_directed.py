"""Directed tests for the single-cycle core: at least one test per RV32I instruction.

Every test is checked three ways:
- the scoreboard compares each retired instruction with the ISS,
- the final register file and data memory are compared with the ISS,
- `expect` lists hand-computed register values, which do not depend on the ISS at all.
"""

from dataclasses import dataclass, field

import cocotb

from model.encoder import encode as e
from model.encoder import load_immediate as li
from tb.coverage import Coverage
from tb.harness import CORE_SINGLE_SOURCES, COVERAGE_DIR, CoreHarness

from cocotb_runner import run_cocotb

DATA = 0x2000  # data area, well above the code


@dataclass
class Case:
    name: str
    program: list[int]
    data: dict[int, int] = field(default_factory=dict)  # {byte address: word}
    expect: dict[int, int] = field(default_factory=dict)  # {register: value}
    expect_trap: bool = False


def program(*parts: int | list[int]) -> list[int]:
    """Flatten words and word lists into one program, ending with ECALL."""
    words: list[int] = []
    for part in parts:
        words += part if isinstance(part, list) else [part]
    return words + [e("ecall")]


CASES: list[Case] = []

# ---- ALU register-register: each op on edge-value operand pairs ------------------------

R_OPERANDS = [
    (5, 7), (0x8000_0000, 1), (0x7FFF_FFFF, 1), (0xFFFF_FFFF, 0xFFFF_FFFF),
    (0, 0xFFFF_FFFF), (0x1234_5678, 33), (0x8000_0000, 31),
]  # fmt: skip

for _op in ["add", "sub", "sll", "slt", "sltu", "xor", "srl", "sra", "or", "and"]:
    _parts = []
    for _k, (_a, _b) in enumerate(R_OPERANDS):
        _parts += li(1, _a) + li(2, _b) + [e(_op, rd=3 + _k, rs1=1, rs2=2)]
    _parts.append(e(_op, rd=0, rs1=1, rs2=2))  # writing x0 must have no effect
    CASES.append(Case(f"alu_{_op}", program(_parts)))

# ---- ALU immediate: edge immediates on a few rs1 values --------------------------------

I_IMMEDIATES = [0, 1, -1, 2047, -2048, 0x555]
SHIFT_AMOUNTS = [0, 1, 15, 31]
I_RS1_VALUES = [0x8000_0000, 0xFFFF_FFFF, 0x0000_1234]

for _op in ["addi", "slti", "sltiu", "xori", "ori", "andi", "slli", "srli", "srai"]:
    _imms = SHIFT_AMOUNTS if _op in ("slli", "srli", "srai") else I_IMMEDIATES
    _parts, _rd = [], 3
    for _a in I_RS1_VALUES:
        _parts += li(1, _a)
        for _imm in _imms:
            _parts.append(e(_op, rd=_rd, rs1=1, imm=_imm))
            _rd += 1
    CASES.append(Case(f"alu_{_op}", program(_parts)))

# ---- Upper immediates ------------------------------------------------------------------

CASES.append(
    Case(
        "lui",
        program(
            e("lui", rd=1, imm=0),
            e("lui", rd=2, imm=0xFFFFF),
            e("lui", rd=3, imm=0x80000),
            e("lui", rd=4, imm=0x12345),
        ),
        expect={1: 0, 2: 0xFFFF_F000, 3: 0x8000_0000, 4: 0x1234_5000},
    )
)
CASES.append(
    Case(
        "auipc",
        program(
            e("addi", rd=0),  # pc 0
            e("auipc", rd=1, imm=0),  # pc 4
            e("auipc", rd=2, imm=0xFFFFF),  # pc 8: 8 + 0xFFFFF000
            e("auipc", rd=3, imm=1),  # pc 12
        ),
        expect={1: 4, 2: 0xFFFF_F008, 3: 0x100C},
    )
)

# ---- Jumps -----------------------------------------------------------------------------

CASES.append(
    Case(
        "jal",
        program(
            e("jal", rd=1, imm=12),  # 0:  -> 12, x1 = 4
            e("addi", rd=5, imm=1),  # 4:  skipped
            e("jal", rd=0, imm=12),  # 8:  -> 20 (plain jump, no link)
            e("addi", rd=6, imm=2),  # 12
            e("jal", rd=2, imm=-8),  # 16: backwards -> 8, x2 = 20
            e("addi", rd=7, imm=3),  # 20
        ),
        expect={1: 4, 2: 20, 5: 0, 6: 2, 7: 3},
    )
)
CASES.append(
    Case(
        "jalr",
        program(
            e("addi", rd=1, imm=16),  # 0
            e("jalr", rd=2, rs1=1, imm=1),  # 4:  target (16+1) & ~1 = 16, x2 = 8
            e("addi", rd=5, imm=1),  # 8:  skipped
            e("addi", rd=5, imm=2),  # 12: skipped
            e("addi", rd=3, imm=32),  # 16
            e("jalr", rd=3, rs1=3, imm=-4),  # 20: rd == rs1: target 28, x3 = 24
            e("addi", rd=6, imm=1),  # 24: skipped
        ),
        expect={2: 8, 3: 24, 5: 0, 6: 0},
    )
)

# ---- Branches: taken / not taken, hand-computed truth table ----------------------------

BRANCH_OPERANDS = [(7, 7), (7, 8), (0xFFFF_FFFF, 0), (0, 0xFFFF_FFFF), (0x8000_0000, 0x7FFF_FFFF)]
BRANCH_TAKEN = {  # one entry per operand pair above
    "beq": [True, False, False, False, False],
    "bne": [False, True, True, True, True],
    "blt": [False, True, True, False, True],  # signed: -1 < 0, MIN < MAX
    "bge": [True, False, False, True, False],
    "bltu": [False, True, False, True, False],  # unsigned: 0xFFFFFFFF is the largest
    "bgeu": [True, False, True, False, True],
}

for _op, _taken in BRANCH_TAKEN.items():
    _parts, _expect = [], {}
    for _k, (_a, _b) in enumerate(BRANCH_OPERANDS):
        _flag = 10 + _k  # set to 1 only if the branch falls through
        _parts += li(1, _a) + li(2, _b)
        _parts += [e(_op, rs1=1, rs2=2, imm=8), e("addi", rd=_flag, imm=1)]
        _expect[_flag] = 0 if _taken[_k] else 1
    CASES.append(Case(f"branch_{_op}", program(_parts), expect=_expect))

# ---- Loads: every width and byte offset ------------------------------------------------

LOAD_DATA = {DATA: 0x8081_8283, DATA + 4: 0x7F00_FF01}
LOAD_EXPECT = {  # (offset from DATA, expected value)
    "lb": [(0, 0xFFFF_FF83), (1, 0xFFFF_FF82), (2, 0xFFFF_FF81), (3, 0xFFFF_FF80),
           (4, 0x0000_0001), (5, 0xFFFF_FFFF), (6, 0x0000_0000), (7, 0x0000_007F)],
    "lbu": [(0, 0x83), (1, 0x82), (2, 0x81), (3, 0x80), (4, 0x01), (5, 0xFF), (7, 0x7F)],
    "lh": [(0, 0xFFFF_8283), (2, 0xFFFF_8081), (4, 0xFFFF_FF01), (6, 0x0000_7F00)],
    "lhu": [(0, 0x8283), (2, 0x8081), (4, 0xFF01), (6, 0x7F00)],
    "lw": [(0, 0x8081_8283), (4, 0x7F00_FF01)],
}  # fmt: skip

for _op, _cases in LOAD_EXPECT.items():
    _parts, _expect = li(1, DATA), {}
    for _k, (_offset, _value) in enumerate(_cases):
        _parts.append(e(_op, rd=10 + _k, rs1=1, imm=_offset))
        _expect[10 + _k] = _value
    # Negative offset from a base past the data, and a load into x0 (discarded).
    _parts += li(2, DATA + 8) + [e(_op, rd=20, rs1=2, imm=-8), e(_op, rd=0, rs1=1)]
    _expect[20] = _cases[0][1]
    CASES.append(Case(f"load_{_op}", program(_parts), data=dict(LOAD_DATA), expect=_expect))

# ---- Stores: every width and byte offset, read back with LW ---------------------------

STORE_EXPECT = {  # (offset from DATA, word at that offset afterwards); memory starts 0x11111111
    "sb": [(0, 0x1111_11DD), (5, 0x1111_DD11), (10, 0x11DD_1111), (15, 0xDD11_1111)],
    "sh": [(0, 0x1111_CCDD), (6, 0xCCDD_1111)],
    "sw": [(0, 0xAABB_CCDD)],
}

for _op, _cases in STORE_EXPECT.items():
    _data = {DATA + 4 * k: 0x1111_1111 for k in range(8)}
    _parts = li(1, DATA) + li(2, 0xAABB_CCDD)
    for _offset, _ in _cases:
        _parts.append(e(_op, rs1=1, rs2=2, imm=_offset))
    # Negative offset: store relative to DATA + 32 into the word at DATA + 28.
    _parts += li(3, DATA + 32) + [e(_op, rs1=3, rs2=2, imm=-4)]
    _expect = {}
    for _k, (_offset, _word) in enumerate(_cases):
        _parts.append(e("lw", rd=10 + _k, rs1=1, imm=_offset & ~3))
        _expect[10 + _k] = _word
    CASES.append(Case(f"store_{_op}", program(_parts), data=_data, expect=_expect))

# ---- System ----------------------------------------------------------------------------

CASES.append(Case("fence", program(e("fence"), e("addi", rd=1, imm=1)), expect={1: 1}))
for _op in ("ecall", "ebreak"):
    CASES.append(
        Case(
            f"halt_{_op}",
            [e("addi", rd=1, imm=5), e(_op), e("addi", rd=1, imm=6)],  # the last one never runs
            expect={1: 5},
        )
    )
CASES.append(
    Case(
        "illegal_instruction_traps",
        [e("addi", rd=1, imm=1), 0xFFFF_FFFF, e("addi", rd=1, imm=2), e("ecall")],
        expect={1: 1},
        expect_trap=True,
    )
)

# ---- x0 as destination of every instruction class --------------------------------------

CASES.append(
    Case(
        "x0_is_never_written",
        program(
            li(1, DATA),
            e("addi", rd=0, imm=123),
            e("lui", rd=0, imm=0xFFFFF),
            e("auipc", rd=0, imm=1),
            e("add", rd=0, rs1=1, rs2=1),
            e("lw", rd=0, rs1=1),
            e("jal", rd=0, imm=4),
            e("addi", rd=2, rs1=0, imm=0),  # x2 = x0 must still be 0
        ),
        data={DATA: 0xFFFF_FFFF},
        expect={0: 0, 2: 0},
    )
)

# ---- Small programs --------------------------------------------------------------------

CASES.append(
    Case(
        "program_sum_1_to_10",
        program(
            e("addi", rd=1, imm=10),
            e("addi", rd=2, imm=0),
            e("add", rd=2, rs1=2, rs2=1),  # loop:
            e("addi", rd=1, rs1=1, imm=-1),
            e("bne", rs1=1, rs2=0, imm=-8),  # -> loop
        ),
        expect={2: 55},
    )
)
CASES.append(
    Case(
        "program_fibonacci_20",
        program(
            e("addi", rd=1, imm=0),  # fib(i)
            e("addi", rd=2, imm=1),  # fib(i+1)
            e("addi", rd=3, imm=20),  # counter
            e("add", rd=4, rs1=1, rs2=2),  # loop:
            e("addi", rd=1, rs1=2, imm=0),
            e("addi", rd=2, rs1=4, imm=0),
            e("addi", rd=3, rs1=3, imm=-1),
            e("bne", rs1=3, rs2=0, imm=-16),  # -> loop
        ),
        expect={1: 6765},  # fib(20)
    )
)
CASES.append(
    Case(
        "program_dependency_chain",  # back-to-back read-after-write, matters for M4
        program(
            li(1, DATA),
            [e("addi", rd=2, rs1=2, imm=1)] * 10,
            e("sw", rs1=1, rs2=2),
            e("lw", rd=3, rs1=1),
            e("add", rd=4, rs1=3, rs2=3),
        ),
        expect={2: 10, 3: 10, 4: 20},
    )
)


# ---- One cocotb test per case ------------------------------------------------------------


COVERAGE = Coverage()


async def run_case(dut, case: Case) -> None:
    harness = CoreHarness(dut, COVERAGE)
    harness.load(case.program, case.data)
    result = await harness.run(expect_trap=case.expect_trap)
    COVERAGE.save(COVERAGE_DIR / "directed.json")
    for reg, value in case.expect.items():
        got = harness.read_reg(reg)
        assert got == value, f"x{reg} = 0x{got:08x}, expected 0x{value:08x}"
    dut._log.info("%s: %d instructions in %d cycles", case.name, result.retired, result.cycles)


def _make_test(case: Case):
    async def test(dut):
        await run_case(dut, case)

    test.__name__ = test.__qualname__ = f"directed_{case.name}"
    return cocotb.test()(test)


for _case in CASES:
    globals()[f"directed_{_case.name}"] = _make_test(_case)


def test_core_single_directed():
    run_cocotb("tb_top", CORE_SINGLE_SOURCES, "test_core_directed")
