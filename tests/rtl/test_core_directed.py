"""Directed tests for the single-cycle core: at least one test per RV32I instruction.

Every test is checked three ways:
- the scoreboard compares each retired instruction with the ISS,
- the final register file and data memory are compared with the ISS,
- `expect` lists hand-computed register values, which do not depend on the ISS at all.
"""

from dataclasses import dataclass, field

import cocotb
import pytest

from model.encoder import encode as e
from model.encoder import load_immediate as li
from tb.harness import CORE_SOURCES, CoreHarness, coverage_path, new_coverage

from cocotb_runner import cores_under_test, run_cocotb

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


# ---- Pipeline hazards (added in M4 after mutation analysis showed directed-test gaps) ----
# Each case puts the dependent instruction at an exact distance from the producer.
# On the single-cycle core they are ordinary programs; on core_pipe they hit one hazard path.

NOP = e("addi", rd=0, rs1=0, imm=0)

CASES.append(
    Case(
        "hazard_x0_never_forwarded",  # writes to x0 must not be forwarded or bypassed
        program(
            e("addi", rd=0, rs1=0, imm=5),
            e("add", rd=1, rs1=0, rs2=0),  # distance 1 (EX/MEM path)
            e("addi", rd=0, rs1=0, imm=6),
            NOP,
            e("add", rd=2, rs1=0, rs2=0),  # distance 2 (MEM/WB path)
            e("addi", rd=0, rs1=0, imm=7),
            NOP,
            NOP,
            e("add", rd=3, rs1=0, rs2=0),  # distance 3 (write-before-read in ID)
            li(5, DATA),
            e("lw", rd=0, rs1=5, imm=0),
            e("add", rd=4, rs1=0, rs2=0),  # a load into x0 must not be forwarded either
        ),
        data={DATA: 0x1234_5678},
        expect={1: 0, 2: 0, 3: 0, 4: 0},
    )
)
CASES.append(
    Case(
        "hazard_forwarding_distances",
        program(
            e("addi", rd=1, imm=10),
            e("addi", rd=2, rs1=1, imm=1),  # x1 written 1 back: EX/MEM -> 11
            e("addi", rd=3, rs1=1, imm=2),  # x1 written 2 back: MEM/WB -> 12
            e("addi", rd=4, rs1=1, imm=3),  # x1 written 3 back: write-before-read -> 13
            e("add", rd=5, rs1=3, rs2=2),  # x3 2 back (MEM/WB), x2 3 back (bypass) -> 23
            e("sub", rd=6, rs1=4, rs2=5),  # x4 2 back, x5 1 back on rs2 (EX/MEM) -> 13 - 23
        ),
        expect={2: 11, 3: 12, 4: 13, 5: 23, 6: 0xFFFF_FFF6},
    )
)
CASES.append(
    Case(
        "hazard_forwarding_newest_wins",  # x1 in both EX/MEM and MEM/WB: take the newer one
        program(
            e("addi", rd=1, imm=1),
            e("addi", rd=1, imm=2),
            e("add", rd=2, rs1=1, rs2=1),  # must be 2 + 2, not 1 + 1 or 1 + 2
            e("addi", rd=3, imm=5),
            e("addi", rd=3, rs1=3, imm=1),  # 6, depends on the previous one
            e("add", rd=4, rs1=0, rs2=3),  # rs2: newest x3 = 6
        ),
        expect={1: 2, 2: 4, 3: 6, 4: 6},
    )
)
CASES.append(
    Case(
        "hazard_load_use",  # load result used by the very next instruction, every operand kind
        program(
            li(1, DATA),
            e("lw", rd=2, rs1=1, imm=0),
            e("add", rd=3, rs1=2, rs2=0),  # rs1 load-use -> 7
            e("lw", rd=4, rs1=1, imm=4),
            e("add", rd=5, rs1=0, rs2=4),  # rs2 load-use -> 9
            e("lw", rd=6, rs1=1, imm=0),
            e("sw", rs1=1, rs2=6, imm=8),  # store data from the load -> mem[DATA+8] = 7
            e("lw", rd=7, rs1=1, imm=12),
            e("lw", rd=8, rs1=7, imm=0),  # load address from the load (pointer chasing) -> 7
            e("lw", rd=9, rs1=1, imm=4),
            e("beq", rs1=9, rs2=5, imm=8),  # branch on the load: 9 == 9, taken
            e("addi", rd=10, imm=1),  # skipped
            e("lw", rd=11, rs1=1, imm=8),
            e("lw", rd=12, rs1=1, imm=8),  # rd 11 is not read: no stall needed, still correct
            e("add", rd=13, rs1=11, rs2=12),  # 7 + 7
        ),
        data={DATA: 7, DATA + 4: 9, DATA + 12: DATA},
        expect={3: 7, 5: 9, 6: 7, 8: 7, 10: 0, 13: 14},
    )
)
CASES.append(
    Case(
        "hazard_branch_and_jump_flush",  # wrong-path instructions after a redirect must vanish
        program(
            li(7, DATA),  # 0
            e("addi", rd=1, imm=3),  # 4
            e("addi", rd=2, imm=3),  # 8
            e("beq", rs1=1, rs2=2, imm=12),  # 12: operands forwarded; taken -> 24
            e("addi", rd=10, imm=1),  # 16: wrong path
            e("sw", rs1=7, rs2=1, imm=0),  # 20: wrong path, must not write memory
            e("jal", rd=3, imm=12),  # 24: -> 36, x3 = 28
            e("addi", rd=11, imm=1),  # 28: wrong path
            e("addi", rd=12, imm=1),  # 32: wrong path
            e("auipc", rd=4, imm=0),  # 36: x4 = 36
            e("jalr", rd=5, rs1=4, imm=16),  # 40: rs1 forwarded from auipc -> 52, x5 = 44
            e("addi", rd=13, imm=1),  # 44: wrong path
            e("addi", rd=14, imm=1),  # 48: wrong path
            e("addi", rd=6, imm=6),  # 52
        ),
        data={DATA: 0},
        expect={10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 3: 28, 5: 44, 6: 6},
    )
)


# ---- One cocotb test per case ------------------------------------------------------------


COVERAGE = new_coverage()


async def run_case(dut, case: Case) -> None:
    harness = CoreHarness(dut, COVERAGE)
    harness.load(case.program, case.data)
    result = await harness.run(expect_trap=case.expect_trap)
    COVERAGE.save(coverage_path("directed"))
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


@pytest.mark.parametrize("core", cores_under_test())
def test_core_directed(core):
    run_cocotb("tb_top", CORE_SOURCES, "test_core_directed", core)
