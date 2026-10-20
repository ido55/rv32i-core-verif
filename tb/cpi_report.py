"""Print a CPI table for the C programs from build/results/<core>/programs.json.

Usage (after `make test`):  python -m tb.cpi_report

cycles = clock cycles from reset release until the final ECALL retires, so the pipelined
core's 4-cycle fill time is included (it matters little for programs this long).
"""

import json

from tb.harness import RESULTS_DIR
from tb.programs import C_PROGRAMS


def main() -> int:
    rows = []
    for core in ("single", "pipe"):
        path = RESULTS_DIR / core / "programs.json"
        if not path.exists():
            continue
        results = json.loads(path.read_text())
        for name in C_PROGRAMS:
            if name in results:
                rows.append((name, core, results[name]))
    if not rows:
        print(f"no results in {RESULTS_DIR}; run `make test` first")
        return 1

    print("| Program | Core | Instructions | Cycles | CPI | Load-use stall cycles | Flushes |")
    print("|---|---|---|---|---|---|---|")
    for name, core, r in sorted(rows):
        cpi = r["cycles"] / r["instructions"]
        stalls = r["stall_cycles"] if core == "pipe" else "-"
        flushes = r["flushes"] if core == "pipe" else "-"
        print(
            f"| {name} | {core} | {r['instructions']:,} | {r['cycles']:,} | {cpi:.3f} "
            f"| {stalls} | {flushes} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
