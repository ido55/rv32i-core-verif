"""Mutation analysis of the pipelined core: are the tests able to find hazard bugs?

Injects one classic pipeline bug at a time into rtl/core_pipe.sv, runs the directed,
program and random suites on the pipelined core, and counts the failing tests. The RTL
file, and the coverage/CPI data of the last real `make test` (which the mutated runs would
otherwise overwrite), are restored at the end, also on Ctrl-C.

Usage:  make mutation      (about 4-5 minutes)
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET = REPO_ROOT / "rtl" / "core_pipe.sv"
# Written by every test run; must not be left holding data from a mutated design.
PROTECTED_DIRS = [
    REPO_ROOT / "build" / "coverage" / "pipe",
    REPO_ROOT / "build" / "results" / "pipe",
]
SUITES = ["test_core_directed", "test_core_programs", "test_core_random"]

# (description, exact text in core_pipe.sv, replacement)
MUTATIONS = [
    ("No EX/MEM forwarding (rs1)",
     "if (exmem_writes && ex_mem_q.rd == ex_ctrl.rs1)      fwd_a_sel = FWD_EXMEM;",
     "if (1'b0)                                            fwd_a_sel = FWD_EXMEM;"),
    ("No MEM/WB forwarding (rs2)",
     "else if (memwb_writes && mem_wb_q.rd == ex_ctrl.rs2) fwd_b_sel = FWD_MEMWB;",
     "else if (1'b0)                                       fwd_b_sel = FWD_MEMWB;"),
    ("Forwarding priority wrong: MEM/WB beats EX/MEM (rs2)",
     "if (exmem_writes && ex_mem_q.rd == ex_ctrl.rs2)      fwd_b_sel = FWD_EXMEM;",
     "if (exmem_writes && ex_mem_q.rd == ex_ctrl.rs2 && "
     "!(memwb_writes && mem_wb_q.rd == ex_ctrl.rs2)) fwd_b_sel = FWD_EXMEM;"),
    ("Forwarding from x0 (missing rd != 0 check)",
     "assign exmem_writes = ex_mem_q.valid && ex_mem_q.reg_write && (ex_mem_q.rd != 5'd0);",
     "assign exmem_writes = ex_mem_q.valid && ex_mem_q.reg_write;"),
    ("No write-before-read bypass (rs1)",
     "assign wb_bypass_rs1 = wb_we &&",
     "assign wb_bypass_rs1 = 1'b0 && wb_we &&"),
    ("No load-use stall",
     "assign stall_load_use   = if_id_q.valid &&",
     "assign stall_load_use   = 1'b0 && if_id_q.valid &&"),
    ("Flush squashes only IF, not ID",
     "id_ex_q <= (flush || stall_load_use) ? '0 : id_ex_d;",
     "id_ex_q <= stall_load_use ? '0 : id_ex_d;"),
]  # fmt: skip


def results_file(suite: str) -> Path:
    return REPO_ROOT / "sim_build" / "tb_top_pipe" / f"{suite}[pipe].None"


def run_suite(suite: str) -> tuple[int, int]:
    """Run one suite on the pipelined core; returns (failing tests, total tests)."""
    results_file(suite).unlink(missing_ok=True)
    subprocess.run(
        [sys.executable, "-m", "pytest", f"tests/rtl/{suite}.py", "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        env={**os.environ, "CORE": "pipe"},
    )
    if not results_file(suite).exists():
        return (-1, -1)  # did not even build or start
    text = results_file(suite).read_text()
    return (len(re.findall(r"<failure", text)), len(re.findall(r"<testcase", text)))


def main() -> int:
    original = TARGET.read_text()
    backup = Path(tempfile.mkdtemp(prefix="mutation_backup_"))
    for index, directory in enumerate(PROTECTED_DIRS):
        if directory.exists():
            shutil.copytree(directory, backup / str(index))

    print("| Injected bug | Directed fail | Programs fail | Random fail |")
    print("|---|---|---|---|")
    missed = 0
    try:
        for name, old, new in MUTATIONS:
            assert original.count(old) == 1, f"mutation pattern not found once: {old}"
            TARGET.write_text(original.replace(old, new))
            counts = [run_suite(suite) for suite in SUITES]
            missed += all(failed == 0 for failed, _ in counts)
            cells = " | ".join(f"{failed} / {total}" for failed, total in counts)
            print(f"| {name} | {cells} |", flush=True)
    finally:
        TARGET.write_text(original)
        for index, directory in enumerate(PROTECTED_DIRS):
            shutil.rmtree(directory, ignore_errors=True)
            if (backup / str(index)).exists():
                shutil.copytree(backup / str(index), directory)
        shutil.rmtree(backup)
    print(f"\nMutations not caught by any suite: {missed} of {len(MUTATIONS)}")
    return 1 if missed else 0


if __name__ == "__main__":
    raise SystemExit(main())
