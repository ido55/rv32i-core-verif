"""Functional coverage: which interesting situations the tests actually exercised.

Coverage is sampled from the retire stream (what the core architecturally did), so the
same coverpoints apply to every core. Each coverpoint is a set of named bins with hit
counts; a bin counts as covered once it has been hit at least once.

Coverpoints:
  opcode       every RV32I instruction (40 bins)
  branch       each branch type taken / not taken (12)
  load_offset  each load width at each legal byte offset (13)
  store_offset each store width at each legal byte offset (7)
  x0           rd = x0 on a writing instruction, rs1 = x0, rs2 = x0 (3)
  imm_sign     negative / positive immediates for I, S, B and J formats (8)
  raw_hazard   rs1/rs2 reads a register written 1, 2 or 3 instructions earlier,
               and a load result used by the very next instruction (7)

Pipelined core only, sampled every clock cycle from core_pipe's hazard logic:
  pipeline     each forwarding path per operand (EX/MEM, MEM/WB, both at once -> newest
               wins), write-before-read bypass per operand, load-use stall, and flushes
               caused by a taken branch, JAL, JALR and ECALL/EBREAK/illegal (13)
"""

import json
from pathlib import Path

from model.decoder import Instr, decode
from model.isa import SPECS, Fmt
from model.iss import Retire

LOAD_WIDTHS = {"lb": 1, "lbu": 1, "lh": 2, "lhu": 2, "lw": 4}
STORE_WIDTHS = {"sb": 1, "sh": 2, "sw": 4}
BRANCHES = ["beq", "bne", "blt", "bge", "bltu", "bgeu"]
WRITES_RD = {Fmt.R, Fmt.I, Fmt.U, Fmt.J}
READS_RS1 = {Fmt.R, Fmt.I, Fmt.S, Fmt.B}
READS_RS2 = {Fmt.R, Fmt.S, Fmt.B}


def _offset_bins(widths: dict[str, int]) -> list[str]:
    return [f"{op}@{offset}" for op, size in widths.items() for offset in range(0, 4, size)]


COVERPOINTS: dict[str, list[str]] = {
    "opcode": [spec.name for spec in SPECS],
    "branch": [f"{op}_{outcome}" for op in BRANCHES for outcome in ("taken", "not_taken")],
    "load_offset": _offset_bins(LOAD_WIDTHS),
    "store_offset": _offset_bins(STORE_WIDTHS),
    "x0": ["rd_x0", "rs1_x0", "rs2_x0"],
    "imm_sign": [f"{fmt}_{sign}" for fmt in ("I", "S", "B", "J") for sign in ("neg", "pos")],
    "raw_hazard": [f"{src}_dist{d}" for src in ("rs1", "rs2") for d in (1, 2, 3)] + ["load_use"],
}


PIPELINE_BINS = [
    "fwd_rs1_exmem", "fwd_rs1_memwb", "fwd_rs1_double",
    "fwd_rs2_exmem", "fwd_rs2_memwb", "fwd_rs2_double",
    "wb_bypass_rs1", "wb_bypass_rs2",
    "stall_load_use",
    "flush_branch", "flush_jal", "flush_jalr", "flush_halt",
]  # fmt: skip

FWD_EXMEM, FWD_MEMWB = 1, 2  # values of core_pipe's fwd_sel_e


class Coverage:
    def __init__(self, pipelined: bool = False) -> None:
        points = dict(COVERPOINTS)
        if pipelined:
            points["pipeline"] = PIPELINE_BINS
        self.bins = {point: dict.fromkeys(names, 0) for point, names in points.items()}
        self._history: list[Instr] = []  # last 3 retired instructions, oldest first

    def hit(self, point: str, name: str) -> None:
        self.bins[point][name] += 1

    def reset_history(self) -> None:
        """Call between programs, so hazards are not counted across two programs."""
        self._history = []

    def sample(self, retire: Retire) -> None:
        instr = decode(retire.insn)
        name, fmt = instr.name, instr.fmt
        self.hit("opcode", name)

        if name in BRANCHES and instr.imm != 4:  # offset 4: taken looks like not taken
            taken = retire.next_pc == (retire.pc + instr.imm) & 0xFFFF_FFFF
            self.hit("branch", f"{name}_{'taken' if taken else 'not_taken'}")

        if name in LOAD_WIDTHS:
            self.hit("load_offset", f"{name}@{_lowest_lane(retire.mem_rmask)}")
        if name in STORE_WIDTHS:
            self.hit("store_offset", f"{name}@{_lowest_lane(retire.mem_wmask)}")

        if fmt in WRITES_RD and instr.rd == 0:
            self.hit("x0", "rd_x0")
        if fmt in READS_RS1 and instr.rs1 == 0:
            self.hit("x0", "rs1_x0")
        if fmt in READS_RS2 and instr.rs2 == 0:
            self.hit("x0", "rs2_x0")

        is_shift = name in ("slli", "srli", "srai")  # shamt is unsigned, so no sign to cover
        if fmt in (Fmt.I, Fmt.S, Fmt.B, Fmt.J) and instr.imm != 0 and not is_shift:
            self.hit("imm_sign", f"{fmt.name}_{'neg' if instr.imm < 0 else 'pos'}")

        self._sample_hazards(instr, fmt)
        self._history = (self._history + [instr])[-3:]

    def _sample_hazards(self, instr: Instr, fmt: Fmt) -> None:
        sources = []
        if fmt in READS_RS1:
            sources.append(("rs1", instr.rs1))
        if fmt in READS_RS2:
            sources.append(("rs2", instr.rs2))
        for src_name, reg in sources:
            if reg == 0:
                continue  # x0 never creates a dependency
            # Nearest earlier writer of this register, 1 = the previous instruction.
            for distance, older in enumerate(reversed(self._history), start=1):
                if older.fmt in WRITES_RD and older.rd == reg:
                    self.hit("raw_hazard", f"{src_name}_dist{distance}")
                    if distance == 1 and older.name in LOAD_WIDTHS:
                        self.hit("raw_hazard", "load_use")
                    break

    def sample_pipeline(self, core) -> None:
        """Sample core_pipe's hazard signals (a cocotb handle to the core) for one cycle."""
        for operand, sel in (("rs1", core.fwd_a_sel), ("rs2", core.fwd_b_sel)):
            value = int(sel.value)
            if value == FWD_EXMEM:
                self.hit("pipeline", f"fwd_{operand}_exmem")
            elif value == FWD_MEMWB:
                self.hit("pipeline", f"fwd_{operand}_memwb")
        signals = {
            "fwd_rs1_double": core.cov_fwd_a_double,
            "fwd_rs2_double": core.cov_fwd_b_double,
            "wb_bypass_rs1": core.cov_wb_bypass_rs1,
            "wb_bypass_rs2": core.cov_wb_bypass_rs2,
            "stall_load_use": core.stall_load_use,
            "flush_branch": core.cov_flush_branch,
            "flush_jal": core.cov_flush_jal,
            "flush_jalr": core.cov_flush_jalr,
            "flush_halt": core.cov_flush_halt,
        }
        for name, signal in signals.items():
            if signal.value == 1:
                self.hit("pipeline", name)

    # ---- Reporting --------------------------------------------------------------------

    def merge(self, other: "Coverage") -> None:
        for point, bins in other.bins.items():
            self.bins.setdefault(point, dict.fromkeys(bins, 0))
            for name, count in bins.items():
                self.bins[point][name] += count

    def summary(self) -> dict[str, tuple[int, int]]:
        """{coverpoint: (bins hit, bins total)}"""
        return {
            point: (sum(1 for c in bins.values() if c), len(bins))
            for point, bins in self.bins.items()
        }

    def percent(self) -> float:
        hit = sum(h for h, _ in self.summary().values())
        total = sum(t for _, t in self.summary().values())
        return 100.0 * hit / total

    def missing(self) -> list[str]:
        return [f"{p}.{n}" for p, bins in self.bins.items() for n, c in bins.items() if not c]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.bins, indent=1))

    @classmethod
    def load(cls, path: Path) -> "Coverage":
        data = json.loads(path.read_text())
        cov = cls(pipelined="pipeline" in data)
        for point, bins in data.items():
            for name, count in bins.items():
                cov.bins[point][name] += count
        return cov


def _lowest_lane(mask: int) -> int:
    """Byte offset of an access = index of the lowest set bit of its byte mask."""
    return (mask & -mask).bit_length() - 1
