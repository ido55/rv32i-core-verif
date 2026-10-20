"""Constrained-random programs on the core, checked instruction by instruction against the ISS.

Environment variables:
  SEEDS=<n>        number of random programs (default 50)
  SEED_START=<s>   first program seed (default 1); seeds are SEED_START .. SEED_START+n-1

A failing seed is reproduced exactly with:  make test-random SEED_START=<seed> SEEDS=1
"""

import json
import os

import cocotb
import pytest

from tb.harness import CORE_SOURCES, CoreHarness, coverage_path, new_coverage, results_path
from tb.random_program import random_program

from cocotb_runner import cores_under_test, run_cocotb

# `or`: make exports unset variables as empty strings.
SEEDS = int(os.environ.get("SEEDS") or 50)
SEED_START = int(os.environ.get("SEED_START") or 1)
MAX_CYCLES = 50_000

COVERAGE = new_coverage()
# Coverage closure curve: total bins hit after each seed (plotted by `make plots`).
CLOSURE: list[dict[str, int]] = []


async def run_seed(dut, seed: int) -> None:
    program = random_program(seed)
    harness = CoreHarness(dut, COVERAGE)
    harness.load(program.words, program.data)
    result = await harness.run(max_cycles=MAX_CYCLES)
    COVERAGE.save(coverage_path("random"))
    save_closure(seed)
    dut._log.info("seed %d: %d instructions, %d cycles", seed, result.retired, result.cycles)


def save_closure(seed: int) -> None:
    summary = COVERAGE.summary().values()
    hit, total = sum(h for h, _ in summary), sum(t for _, t in summary)
    CLOSURE.append({"seed": seed, "bins_hit": hit, "bins_total": total})
    path = results_path("random_coverage")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(CLOSURE, indent=1))


def _make_test(seed: int):
    async def test(dut):
        await run_seed(dut, seed)

    test.__name__ = test.__qualname__ = f"random_seed_{seed}"
    return cocotb.test()(test)


for _seed in range(SEED_START, SEED_START + SEEDS):
    globals()[f"random_seed_{_seed}"] = _make_test(_seed)


@pytest.mark.parametrize("core", cores_under_test())
def test_core_random(core):
    run_cocotb("tb_top", CORE_SOURCES, "test_core_random", core)
