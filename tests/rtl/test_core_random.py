"""Constrained-random programs on the core, checked instruction by instruction against the ISS.

Environment variables:
  SEEDS=<n>        number of random programs (default 50)
  SEED_START=<s>   first program seed (default 1); seeds are SEED_START .. SEED_START+n-1

A failing seed is reproduced exactly with:  make test-random SEED_START=<seed> SEEDS=1
"""

import os

import cocotb

from tb.coverage import Coverage
from tb.harness import CORE_SINGLE_SOURCES, COVERAGE_DIR, CoreHarness
from tb.random_program import random_program

from cocotb_runner import run_cocotb

# `or`: make exports unset variables as empty strings.
SEEDS = int(os.environ.get("SEEDS") or 50)
SEED_START = int(os.environ.get("SEED_START") or 1)
MAX_CYCLES = 50_000

COVERAGE = Coverage()


async def run_seed(dut, seed: int) -> None:
    program = random_program(seed)
    harness = CoreHarness(dut, COVERAGE)
    harness.load(program.words, program.data)
    result = await harness.run(max_cycles=MAX_CYCLES)
    COVERAGE.save(COVERAGE_DIR / "random.json")
    dut._log.info("seed %d: %d instructions, %d cycles", seed, result.retired, result.cycles)


def _make_test(seed: int):
    async def test(dut):
        await run_seed(dut, seed)

    test.__name__ = test.__qualname__ = f"random_seed_{seed}"
    return cocotb.test()(test)


for _seed in range(SEED_START, SEED_START + SEEDS):
    globals()[f"random_seed_{_seed}"] = _make_test(_seed)


def test_core_single_random():
    run_cocotb("tb_top", CORE_SINGLE_SOURCES, "test_core_random")
