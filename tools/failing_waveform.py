"""Render the waveform of a failing test: the pipelined core with its load-use stall removed.

1. Injects the "No load-use stall" bug (tools/mutations.py) into rtl/core_pipe.sv.
2. Runs one directed test, directed_hazard_load_use, with WAVES=1 (Verilator VCD dump);
   the scoreboard reports the first mismatching retired instruction.
3. Restores the RTL, reads the VCD and draws the instruction in each pipeline stage, the
   hazard signals and the retire port, with the mismatching cycle marked.

Usage:  make waveform   (writes docs/img/failing_waveform.png; for every signal, open
        sim_build/tb_top_pipe/dump.vcd in GTKWave)
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # render to a file, no display needed
import matplotlib.pyplot as plt  # noqa: E402

from model.decoder import IllegalInstruction, decode, to_asm  # noqa: E402
from tools.mutations import MUTATION_BY_NAME, REPO_ROOT, TARGET, inject, protected_outputs  # noqa: E402

MUTATION = MUTATION_BY_NAME["No load-use stall"]
TESTCASE = "directed_hazard_load_use"
VCD = REPO_ROOT / "sim_build" / "tb_top_pipe" / "dump.vcd"
OUT = REPO_ROOT / "docs" / "img" / "failing_waveform.png"
CORE = "tb_top.u_core."
STAGE_REGS = {"ID": "if_id_q", "EX": "id_ex_q", "MEM": "ex_mem_q", "WB": "mem_wb_q"}
CYCLES_SHOWN = 8
RED, ORANGE = "#d62728", "#e07b00"


def run_failing_test() -> str:
    """Run the test on the mutated core; returns the scoreboard's mismatch report."""
    with protected_outputs():
        inject(MUTATION, TARGET.read_text())
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/rtl/test_core_directed.py", "-q"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env={**os.environ, "CORE": "pipe", "WAVES": "1", "TESTCASE": TESTCASE},
        )
    match = re.search(r"ScoreboardMismatch: (retire #\d+ mismatch.*\n.*)", result.stdout)
    if not match:
        raise SystemExit("expected a scoreboard mismatch, got:\n" + result.stdout[-2000:])
    return match.group(1)


def read_vcd(path: Path, wanted: list[str]) -> tuple[dict, dict]:
    """Minimal VCD reader for what Verilator writes.

    Returns ({name: [(time, value), ...]}, {name: width}) for the wanted dotted names.
    Handles nested $scope blocks, $var lines, '#time', scalar changes like '1!' and
    vector changes like 'b1010 !'. x/z are read as 0.
    """
    scope: list[str] = []
    code_to_name: dict[str, str] = {}
    changes: dict[str, list[tuple[int, int]]] = {name: [] for name in wanted}
    widths: dict[str, int] = {}
    time = 0
    with path.open() as vcd:
        for line in vcd:
            tokens = line.split()
            if not tokens:
                continue
            if tokens[0] == "$scope":
                scope.append(tokens[2])
            elif tokens[0] == "$upscope":
                scope.pop()
            elif tokens[0] == "$var":  # $var wire <width> <code> <name> [range] $end
                name = ".".join([*scope[1:], tokens[4]])  # scope[0]: Verilator's unnamed top
                if name in changes:
                    code_to_name[tokens[3]] = name
                    widths[name] = int(tokens[2])
            elif tokens[0].startswith("#"):
                time = int(tokens[0][1:])
            elif tokens[0][0] == "b" and len(tokens) == 2 and tokens[1] in code_to_name:
                value = int(re.sub("[xz]", "0", tokens[0][1:]), 2)
                changes[code_to_name[tokens[1]]].append((time, value))
            elif tokens[0][0] in "01xz" and tokens[0][1:] in code_to_name:
                changes[code_to_name[tokens[0][1:]]].append((time, int(tokens[0][0] == "1")))
    return changes, widths


def value_at(changes: list[tuple[int, int]], time: int) -> int:
    value = 0
    for t, v in changes:
        if t > time:
            break
        value = v
    return value


def stage_text(reg: int, width: int) -> str:
    """Every pipeline register starts with {valid, pc[31:0], insn[31:0]}."""
    if not reg >> (width - 1):
        return "bubble"
    insn = (reg >> (width - 65)) & 0xFFFF_FFFF
    try:
        return to_asm(decode(insn))
    except IllegalInstruction:
        return f"0x{insn:08x}"


def main() -> int:
    mismatch = run_failing_test()
    bad_retire = int(re.search(r"retire #(\d+)", mismatch).group(1))
    print("scoreboard:", mismatch.replace("\n", " |"))

    names = ["tb_top.clk", "tb_top.rvfi_valid", "tb_top.rvfi_rd", "tb_top.rvfi_rd_wdata"]
    names += [CORE + n for n in ["pc_q", "stall_load_use", "fwd_a_sel", "ex_rs1"]]
    names += [CORE + reg for reg in STAGE_REGS.values()]
    vcd, widths = read_vcd(VCD, names)

    # One sample per clock cycle, at the falling edge: where the scoreboard samples.
    falling = [t for t, v in vcd["tb_top.clk"] if v == 0][1:]
    retire_times = [t for t in falling if value_at(vcd["tb_top.rvfi_valid"], t)]
    bad_time = retire_times[bad_retire]
    samples = [t for t in falling if t <= bad_time][-CYCLES_SHOWN:]

    def column(name: str) -> list[int]:
        return [value_at(vcd[name], t) for t in samples]

    fwd = {0: "ID value", 1: "EX/MEM", 2: "MEM/WB"}
    retire = zip(column("tb_top.rvfi_valid"), column("tb_top.rvfi_rd"),
                 column("tb_top.rvfi_rd_wdata"), strict=True)  # fmt: skip
    rows = [("IF  pc", [f"0x{v:x}" for v in column(CORE + "pc_q")])]
    for stage, reg in STAGE_REGS.items():
        rows.append((stage, [stage_text(v, widths[CORE + reg]) for v in column(CORE + reg)]))
    rows += [
        ("stall_load_use", column(CORE + "stall_load_use")),
        ("fwd_a_sel", [fwd[v] for v in column(CORE + "fwd_a_sel")]),
        ("EX rs1 value", [f"0x{v:x}" for v in column(CORE + "ex_rs1")]),
        ("retire valid", column("tb_top.rvfi_valid")),
        ("retire rd", [f"x{rd}=0x{data:x}" if valid else "" for valid, rd, data in retire]),
    ]
    # The cycle the bad instruction was in EX, i.e. computed its result with a wrong operand.
    bad_asm = mismatch.split("\n")[0].split(": ", 1)[1]
    ex_column = [i for i, text in enumerate(rows[2][1]) if text == bad_asm][-1]
    draw(rows, mismatch, ex_column)
    print(f"wrote {OUT.relative_to(REPO_ROOT)}")
    return 0


def draw(rows: list[tuple[str, list]], mismatch: str, ex_column: int) -> None:
    """Waveform style: a clock, square waves for 1-bit rows, hexagon segments for buses.
    Each column is one cycle; the last column is the mismatching retire (red), and
    `ex_column` the cycle the failing instruction was in EX (orange)."""
    cycles = len(rows[0][1])
    fig, ax = plt.subplots(figsize=(1.5 * cycles + 1.6, 0.48 * (len(rows) + 1) + 0.9))
    ax.set_xlim(-1.7, cycles + 0.05)
    ax.set_ylim(len(rows) + 0.6, -1.0)
    ax.axis("off")
    ax.axvspan(cycles - 1, cycles, color=RED, alpha=0.10)
    ax.text(cycles - 0.5, -0.65, "scoreboard\nmismatch", ha="center", fontsize=8, color=RED)
    ax.axvspan(ex_column, ex_column + 1, color=ORANGE, alpha=0.12)
    ax.text(ex_column + 0.5, -0.65, "wrong operand\nused in EX", ha="center", fontsize=8,
            color=ORANGE)  # fmt: skip
    h = 0.3  # half height of a trace

    ax.text(-1.65, 0, "clk", va="center", fontsize=9, fontweight="bold")
    for c in range(cycles):
        ax.plot([c, c, c + 0.5, c + 0.5, c + 1], [h, -h, -h, h, h], color="#333", lw=1)
        ax.axvline(c, color="#ccc", lw=0.5, zorder=0)

    for row, (label, values) in enumerate(rows, start=1):
        ax.text(-1.65, row, label, va="center", fontsize=9, fontweight="bold")
        if isinstance(values[0], int):  # 1-bit signal
            xs, ys = [], []
            for c, v in enumerate(values):
                xs += [c, c + 1]
                ys += [row - h if v else row + h] * 2
            ax.plot(xs, ys, color="#1f77b4", lw=1.4)
            continue
        start = 0
        for c in range(1, cycles + 1):  # one hexagon per run of equal values
            if c < cycles and values[c] == values[start]:
                continue
            text, end = values[start], c
            if text:
                d = 0.08
                ax.fill([start, start + d, end - d, end, end - d, start + d],
                        [row, row - h, row - h, row, row + h, row + h],
                        facecolor="#eef4fb", edgecolor="#1f77b4", lw=1)  # fmt: skip
                bad = end == cycles and row == len(rows)
                ax.text((start + end) / 2, row, text, ha="center", va="center", fontsize=7.5,
                        family="monospace", color=RED if bad else "black",
                        fontweight="bold" if bad else "normal")  # fmt: skip
            start = c

    first, second = mismatch.split("\n", 1)
    ax.set_title(
        f"Injected bug: {MUTATION.name} (test {TESTCASE}, pipelined core)\n"
        f"Scoreboard: {first}\n{second.strip()}",
        fontsize=9, loc="left", family="monospace",
    )  # fmt: skip
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=130, bbox_inches="tight")


if __name__ == "__main__":
    raise SystemExit(main())
