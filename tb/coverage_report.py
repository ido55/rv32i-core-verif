"""Print functional coverage from build/coverage/<core>/*.json as Markdown tables.

Usage (after `make test`):  python -m tb.coverage_report
"""

from tb.coverage import Coverage
from tb.harness import COVERAGE_DIR


def report_core(core: str) -> None:
    files = sorted((COVERAGE_DIR / core).glob("*.json"))
    suites = {path.stem: Coverage.load(path) for path in files}
    total = Coverage(pipelined=core == "pipe")
    for cov in suites.values():
        total.merge(cov)

    print(f"\n### Core: {core}\n")
    print("| Suite | Bins hit | Coverage |")
    print("|---|---|---|")
    for name, cov in suites.items():
        print(f"| {name} | {_hit(cov)} / {_bins(cov)} | {cov.percent():.1f}% |")
    print(f"| **all suites** | **{_hit(total)} / {_bins(total)}** | **{total.percent():.1f}%** |")

    print("\n| Coverpoint | Bins hit | Coverage |")
    print("|---|---|---|")
    for point, (hit, count) in total.summary().items():
        print(f"| {point} | {hit} / {count} | {100 * hit / count:.1f}% |")

    missing = total.missing()
    print("\nBins never hit:", ", ".join(missing) if missing else "none")


def _hit(cov: Coverage) -> int:
    return sum(hit for hit, _ in cov.summary().values())


def _bins(cov: Coverage) -> int:
    return sum(count for _, count in cov.summary().values())


def main() -> int:
    cores = sorted(path.name for path in COVERAGE_DIR.glob("*") if path.is_dir())
    if not cores:
        print(f"no coverage data in {COVERAGE_DIR}; run `make test` first")
        return 1
    for core in cores:
        report_core(core)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
