"""Synthesize both cores with Yosys and print their resource counts.

Flow per core: sv2v (SystemVerilog -> Verilog-2005) -> Yosys, twice:
  - `synth`         technology-independent gates and flip-flops
  - `synth_xilinx`  Xilinx 7-series LUTs / flip-flops (no vendor tools needed)
The memories are outside the cores (in tb/tb_top.sv), so they are not counted.

Usage:  make synth   (sv2v: tools/install_sv2v.sh; writes build/synth/ and build/results/synth.json)
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "build" / "synth"
RESULTS_FILE = REPO_ROOT / "build" / "results" / "synth.json"
COMMON = ["rv32i_pkg.sv", "alu.sv", "regfile.sv", "decoder.sv", "branch_unit.sv", "lsu.sv"]
CORES = {"single": "core_single", "pipe": "core_pipe"}
FLOWS = {"generic": "synth -flatten", "xilinx": "synth_xilinx -flatten"}


def find_sv2v() -> str:
    candidates = [os.environ.get("SV2V"), shutil.which("sv2v"), Path.home() / ".local/bin/sv2v"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise SystemExit("sv2v not found: run tools/install_sv2v.sh (or set SV2V=<path>)")


def cell_counts(stat_text: str) -> dict[str, int]:
    """Parse Yosys `stat` output: lines like '     $_DFF_P_     12'."""
    return {name: int(n) for name, n in re.findall(r"^\s+(\S+)\s+(\d+)$", stat_text, re.M)}


def synthesize(top: str, sv2v: str) -> dict[str, dict[str, int]]:
    verilog = OUT_DIR / f"{top}.v"
    sources = [str(REPO_ROOT / "rtl" / name) for name in [*COMMON, f"{top}.sv"]]
    converted = subprocess.run(
        [sv2v, *sources, f"--top={top}"], check=True, capture_output=True, text=True
    )
    verilog.write_text(converted.stdout)
    counts = {}
    for flow, command in FLOWS.items():
        stat = OUT_DIR / f"{top}_{flow}_stat.txt"
        log = OUT_DIR / f"{top}_{flow}.log"
        script = f"read_verilog {verilog}; {command} -top {top}; tee -q -o {stat} stat"
        subprocess.run(["yosys", "-q", "-l", str(log), "-p", script], check=True)
        # Yosys's own warnings start the line; ABC's log lines ("ABC: Warning: The network
        # is combinational") are informational.
        warnings = [line for line in log.read_text().splitlines() if line.startswith("Warning")]
        if warnings:  # e.g. an inferred latch or a multiply-driven net: treat as an error
            raise SystemExit(f"{top} ({flow}): Yosys warnings:\n" + "\n".join(warnings))
        counts[flow] = cell_counts(stat.read_text())
    return counts


def summarize(counts: dict[str, dict[str, int]]) -> dict[str, int]:
    generic, xilinx = counts["generic"], counts["xilinx"]
    assert not any("DLATCH" in name for name in generic), "latch inferred"
    return {
        "generic_cells": sum(generic.values()),
        "generic_flops": sum(n for name, n in generic.items() if "DFF" in name),
        "xilinx_luts": sum(n for name, n in xilinx.items() if name.startswith("LUT")),
        "xilinx_flops": sum(n for name, n in xilinx.items() if name.startswith("FD")),
        "xilinx_carry4": xilinx.get("CARRY4", 0),
        "xilinx_muxf": xilinx.get("MUXF7", 0) + xilinx.get("MUXF8", 0),
    }


def main() -> int:
    sv2v = find_sv2v()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {core: summarize(synthesize(top, sv2v)) for core, top in CORES.items()}
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(results, indent=2))

    print("| Core | Generic cells | Flip-flops | 7-series LUTs | 7-series FFs | CARRY4 | MUXF7/8 |")
    print("|---|---|---|---|---|---|---|")
    for core, r in results.items():
        print(
            f"| {core} | {r['generic_cells']:,} | {r['generic_flops']:,} | {r['xilinx_luts']:,} "
            f"| {r['xilinx_flops']:,} | {r['xilinx_carry4']} | {r['xilinx_muxf']} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
