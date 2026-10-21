"""Print the pass counts of the last test run as a Markdown table, and random-program sizes.

Reads the JUnit XML files the runs leave behind:
  build/results/model_tests.xml          pytest tests/model (written by `make results`)
  sim_build/<build>/<test>.None          one per cocotb run (cocotb 1.9's name under pytest)

Usage:  make test-report   (after `make results`, or after `make test` for the RTL rows)
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from tools.mutations import REPO_ROOT

RESULTS_DIR = REPO_ROOT / "build" / "results"
MODEL_XML = RESULTS_DIR / "model_tests.xml"
SIM_BUILD = REPO_ROOT / "sim_build"


def count(path: Path) -> tuple[int, int]:
    """(passed, total) over all <testcase> elements; failures and errors are not passes."""
    cases = ET.parse(path).getroot().iter("testcase")
    total = failed = 0
    for case in cases:
        total += 1
        failed += any(child.tag in ("failure", "error") for child in case)
    return total - failed, total


def random_program_lengths() -> None:
    """Instructions retired per random program, from test_core_random's per-seed record."""
    for path in sorted(RESULTS_DIR.glob("*/random_coverage.json")):
        lengths = [seed["instructions"] for seed in json.loads(path.read_text())]
        print(
            f"Random programs on {path.parent.name}: {len(lengths)} seeds, "
            f"{min(lengths)}-{max(lengths)} instructions, mean {sum(lengths) / len(lengths):.1f}"
        )


def main() -> int:
    rows = []
    if MODEL_XML.exists():
        rows.append(("tests/model (pytest)", "-", *count(MODEL_XML)))
    for path in sorted(SIM_BUILD.glob("*/*.None")):
        # "test_core_directed[pipe].None" -> suite test_core_directed, core pipe
        suite, _, core = path.stem.partition("[")
        rows.append((suite, core.rstrip("]") or "-", *count(path)))
    if not rows:
        print("no test results found: run `make test` first")
        return 1

    print("| Suite | Core | Passed | Total |")
    print("|---|---|---|---|")
    for suite, core, passed, total in rows:
        print(f"| {suite} | {core} | {passed} | {total} |")
    print()
    random_program_lengths()
    all_pass = all(passed == total for *_, passed, total in rows)
    print(f"\nAll passed: {'yes' if all_pass else 'NO'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
