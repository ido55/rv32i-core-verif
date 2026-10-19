"""The random program generator must only produce legal, terminating programs."""

from collections import Counter

import pytest

from model.decoder import decode
from model.iss import Iss, Memory
from tb.random_program import DATA_BASE, DATA_BYTES, random_program

MEM_BYTES = 0x4000
SEEDS = range(1, 201)


def run_on_iss(seed: int):
    program = random_program(seed)
    mem = Memory(MEM_BYTES)
    mem.load_words(program.words, 0)
    for addr, word in program.data.items():
        mem.store(addr, word, 4)
    iss = Iss(mem)
    return program, iss.run(max_steps=50_000)


@pytest.mark.parametrize("seed", SEEDS)
def test_program_runs_to_ecall_on_iss(seed):
    """Raises if the program faults, misaligns, leaves memory, or never halts."""
    _, trace = run_on_iss(seed)
    assert trace[-1].halt


def test_loads_and_stores_stay_in_the_data_region():
    for seed in range(1, 51):
        _, trace = run_on_iss(seed)
        for r in trace:
            if r.mem_rmask or r.mem_wmask:
                assert DATA_BASE <= r.mem_addr < DATA_BASE + DATA_BYTES


def test_same_seed_same_program():
    assert random_program(7) == random_program(7)
    assert random_program(7).words != random_program(8).words


def test_every_instruction_appears_across_seeds():
    executed = Counter()
    for seed in range(1, 51):
        _, trace = run_on_iss(seed)
        executed.update(decode(r.insn).name for r in trace)
    expected = {
        "lui", "auipc", "jal", "jalr", "beq", "bne", "blt", "bge", "bltu", "bgeu",
        "lb", "lh", "lw", "lbu", "lhu", "sb", "sh", "sw",
        "addi", "slti", "sltiu", "xori", "ori", "andi", "slli", "srli", "srai",
        "add", "sub", "sll", "slt", "sltu", "xor", "srl", "sra", "or", "and",
        "fence", "ecall",
    }  # fmt: skip
    assert expected <= set(executed), f"never executed: {sorted(expected - set(executed))}"


def test_branches_are_both_taken_and_not_taken():
    taken = not_taken = 0
    for seed in range(1, 21):
        _, trace = run_on_iss(seed)
        for r in trace:
            instr = decode(r.insn)
            if instr.name.startswith("b") and instr.imm != 4:
                if r.next_pc == r.pc + instr.imm:
                    taken += 1
                else:
                    not_taken += 1
    assert taken > 100 and not_taken > 100, (taken, not_taken)
