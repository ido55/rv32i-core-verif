"""Classic pipeline bugs that can be injected into rtl/core_pipe.sv, one at a time.

Used by tools/mutation_analysis.py (do the tests catch them?) and tools/failing_waveform.py
(what does a caught bug look like?).
"""

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET = REPO_ROOT / "rtl" / "core_pipe.sv"
# Written by every test run; must not be left holding data from a mutated design.
PROTECTED_DIRS = [
    REPO_ROOT / "build" / "coverage" / "pipe",
    REPO_ROOT / "build" / "results" / "pipe",
]


@dataclass(frozen=True)
class Mutation:
    name: str
    old: str  # exact text in core_pipe.sv (must occur once)
    new: str  # its replacement


MUTATIONS = [
    Mutation("No EX/MEM forwarding (rs1)",
     "if (exmem_writes && ex_mem_q.rd == ex_ctrl.rs1)      fwd_a_sel = FWD_EXMEM;",
     "if (1'b0)                                            fwd_a_sel = FWD_EXMEM;"),
    Mutation("No MEM/WB forwarding (rs2)",
     "else if (memwb_writes && mem_wb_q.rd == ex_ctrl.rs2) fwd_b_sel = FWD_MEMWB;",
     "else if (1'b0)                                       fwd_b_sel = FWD_MEMWB;"),
    Mutation("Forwarding priority wrong: MEM/WB beats EX/MEM (rs2)",
     "if (exmem_writes && ex_mem_q.rd == ex_ctrl.rs2)      fwd_b_sel = FWD_EXMEM;",
     "if (exmem_writes && ex_mem_q.rd == ex_ctrl.rs2 && "
     "!(memwb_writes && mem_wb_q.rd == ex_ctrl.rs2)) fwd_b_sel = FWD_EXMEM;"),
    Mutation("Forwarding from x0 (missing rd != 0 check)",
     "assign exmem_writes = ex_mem_q.valid && ex_mem_q.reg_write && (ex_mem_q.rd != 5'd0);",
     "assign exmem_writes = ex_mem_q.valid && ex_mem_q.reg_write;"),
    Mutation("No write-before-read bypass (rs1)",
     "assign wb_bypass_rs1 = wb_we &&",
     "assign wb_bypass_rs1 = 1'b0 && wb_we &&"),
    Mutation("No load-use stall",
     "assign stall_load_use   = if_id_q.valid &&",
     "assign stall_load_use   = 1'b0 && if_id_q.valid &&"),
    Mutation("Flush squashes only IF, not ID",
     "id_ex_q <= (flush || stall_load_use) ? '0 : id_ex_d;",
     "id_ex_q <= stall_load_use ? '0 : id_ex_d;"),
]  # fmt: skip
MUTATION_BY_NAME = {m.name: m for m in MUTATIONS}


@contextmanager
def protected_outputs() -> Iterator[None]:
    """Restore rtl/core_pipe.sv and the pipeline's coverage/results data on exit (also on
    Ctrl-C), so mutated runs leave no trace."""
    original = TARGET.read_text()
    backup = Path(tempfile.mkdtemp(prefix="mutation_backup_"))
    for index, directory in enumerate(PROTECTED_DIRS):
        if directory.exists():
            shutil.copytree(directory, backup / str(index))
    try:
        yield
    finally:
        TARGET.write_text(original)
        for index, directory in enumerate(PROTECTED_DIRS):
            shutil.rmtree(directory, ignore_errors=True)
            if (backup / str(index)).exists():
                shutil.copytree(backup / str(index), directory)
        shutil.rmtree(backup)


def inject(mutation: Mutation, original: str) -> None:
    """Write core_pipe.sv = `original` with this one mutation applied."""
    assert original.count(mutation.old) == 1, f"mutation pattern not found once: {mutation.old}"
    TARGET.write_text(original.replace(mutation.old, mutation.new))
