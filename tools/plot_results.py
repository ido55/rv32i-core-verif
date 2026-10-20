"""Draw the README plots from the measurements of the last `make test`.

  docs/img/cpi_breakdown.png     where the pipelined core's cycles go, per C program
  docs/img/coverage_closure.png  functional coverage vs number of random programs

Usage (after `make test`):  make plots
"""

import json

import matplotlib

matplotlib.use("Agg")  # render to a file, no display needed
import matplotlib.pyplot as plt  # noqa: E402

from tb.harness import RESULTS_DIR  # noqa: E402
from tb.programs import C_PROGRAMS  # noqa: E402
from tools.mutations import REPO_ROOT  # noqa: E402

IMG_DIR = REPO_ROOT / "docs" / "img"
PIPELINE_FILL = 4  # cycles before the first instruction retires on the pipelined core


def load(core: str, name: str):
    path = RESULTS_DIR / core / f"{name}.json"
    if not path.exists():
        raise SystemExit(f"{path} missing: run `make test` first")
    return json.loads(path.read_text())


def cpi_breakdown() -> None:
    """Stacked CPI bars. The pipelined core's extra cycles are split exactly (the test suite
    asserts cycles == instructions + fill + stall cycles + 2 x (flushes - 1))."""
    single, pipe = load("single", "programs"), load("pipe", "programs")
    labels, parts = [], {"1 cycle / instruction": [], "pipeline fill": [],
                         "load-use stalls": [], "branch / jump flushes": []}  # fmt: skip
    for program in C_PROGRAMS:
        for core, r in (("single", single[program]), ("pipe", pipe[program])):
            n = r["instructions"]
            fill = PIPELINE_FILL if core == "pipe" else 0
            stalls = r["stall_cycles"] if core == "pipe" else 0
            flush_cycles = r["cycles"] - n - fill - stalls
            if core == "pipe":
                assert flush_cycles == 2 * (r["flushes"] - 1), f"{program}: timing model broken"
            labels.append(f"{program}\n{core}")
            parts["1 cycle / instruction"].append(1.0)
            parts["pipeline fill"].append(fill / n)
            parts["load-use stalls"].append(stalls / n)
            parts["branch / jump flushes"].append(flush_cycles / n)

    fig, ax = plt.subplots(figsize=(7, 4))
    bottom = [0.0] * len(labels)
    for (name, values), color in zip(parts.items(), ["#9ecae1", "#bbbbbb", "#fd8d3c", "#e6550d"],
                                     strict=True):  # fmt: skip
        ax.bar(labels, values, bottom=bottom, label=name, color=color, width=0.6)
        bottom = [b + v for b, v in zip(bottom, values, strict=True)]
    for x, total in enumerate(bottom):
        ax.text(x, total + 0.02, f"CPI {total:.3f}", ha="center", fontsize=9)
    ax.set_ylabel("cycles per instruction")
    ax.set_ylim(0, max(bottom) * 1.15)
    ax.set_title("CPI of the C programs: single-cycle vs 5-stage pipeline (measured)")
    ax.legend(loc="upper left", fontsize=8)
    save(fig, "cpi_breakdown.png")


def coverage_closure() -> None:
    fig, ax = plt.subplots(figsize=(7, 3.6))
    for core in ("single", "pipe"):
        points = load(core, "random_coverage")
        programs = range(1, len(points) + 1)
        percent = [100 * p["bins_hit"] / p["bins_total"] for p in points]
        last = points[-1]
        label = f"{core}: {last['bins_hit']}/{last['bins_total']} bins after {len(points)}"
        ax.plot(programs, percent, marker=".", label=label)
    ax.set_xlabel("random programs run (seeds 1, 2, ...)")
    ax.set_ylabel("functional coverage (%)")
    ax.set_title("Coverage closure of the constrained-random suite alone")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right", fontsize=8)
    save(fig, "coverage_closure.png")


def save(fig, name: str) -> None:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMG_DIR / name, dpi=130, bbox_inches="tight")
    print(f"wrote {(IMG_DIR / name).relative_to(REPO_ROOT)}")


def main() -> int:
    cpi_breakdown()
    coverage_closure()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
