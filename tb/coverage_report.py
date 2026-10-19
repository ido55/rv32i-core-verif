"""Print functional coverage from build/coverage/*.json as Markdown tables.

Usage (after `make test`):  python -m tb.coverage_report
"""

from tb.coverage import COVERPOINTS, Coverage
from tb.harness import COVERAGE_DIR


def main() -> int:
    files = sorted(COVERAGE_DIR.glob("*.json"))
    if not files:
        print(f"no coverage data in {COVERAGE_DIR}; run `make test` first")
        return 1

    suites = {path.stem: Coverage.load(path) for path in files}
    total = Coverage()
    for cov in suites.values():
        total.merge(cov)

    print("| Suite | Bins hit | Coverage |")
    print("|---|---|---|")
    for name, cov in suites.items():
        hit = sum(h for h, _ in cov.summary().values())
        print(f"| {name} | {hit} / {_total_bins()} | {cov.percent():.1f}% |")
    hit = sum(h for h, _ in total.summary().values())
    print(f"| **all suites** | **{hit} / {_total_bins()}** | **{total.percent():.1f}%** |")

    print("\n| Coverpoint | Bins hit | Coverage |")
    print("|---|---|---|")
    for point, (hit, count) in total.summary().items():
        print(f"| {point} | {hit} / {count} | {100 * hit / count:.1f}% |")

    missing = total.missing()
    print("\nBins never hit:", ", ".join(missing) if missing else "none")
    return 0


def _total_bins() -> int:
    return sum(len(bins) for bins in COVERPOINTS.values())


if __name__ == "__main__":
    raise SystemExit(main())
