"""Mutation analysis of the pipelined core: are the tests able to find hazard bugs?

Injects one classic pipeline bug at a time (tools/mutations.py) into rtl/core_pipe.sv,
runs the directed, program and random suites on the pipelined core, and counts the failing
tests. The RTL file, and the coverage/CPI data of the last real `make test` (which the
mutated runs would otherwise overwrite), are restored at the end, also on Ctrl-C.

Usage:  make mutation      (about 4-5 minutes)
"""

import json
import os
import re
import subprocess
import sys

from tools.mutations import MUTATIONS, REPO_ROOT, TARGET, inject, protected_outputs

SUITES = ["test_core_directed", "test_core_programs", "test_core_random"]
# Machine-readable copy of the table. Outside build/results/pipe, which is restored afterwards.
RESULTS_FILE = REPO_ROOT / "build" / "results" / "mutation.json"


def results_file(suite: str):
    return REPO_ROOT / "sim_build" / "tb_top_pipe" / f"{suite}[pipe].None"


def run_suite(suite: str, extra_env: dict[str, str] | None = None) -> tuple[int, int]:
    """Run one suite on the pipelined core; returns (failing tests, total tests)."""
    results_file(suite).unlink(missing_ok=True)
    subprocess.run(
        [sys.executable, "-m", "pytest", f"tests/rtl/{suite}.py", "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        env={**os.environ, "CORE": "pipe", **(extra_env or {})},
    )
    if not results_file(suite).exists():
        return (-1, -1)  # did not even build or start
    text = results_file(suite).read_text()
    return (len(re.findall(r"<failure", text)), len(re.findall(r"<testcase", text)))


def main() -> int:
    print("| Injected bug | Directed fail | Programs fail | Random fail |")
    print("|---|---|---|---|")
    table = {}
    with protected_outputs():
        original = TARGET.read_text()
        for mutation in MUTATIONS:
            inject(mutation, original)
            counts = [run_suite(suite) for suite in SUITES]
            table[mutation.name] = dict(zip(SUITES, counts, strict=True))
            cells = " | ".join(f"{failed} / {total}" for failed, total in counts)
            print(f"| {mutation.name} | {cells} |", flush=True)
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(table, indent=2))

    missed = sum(all(failed == 0 for failed, _ in row.values()) for row in table.values())
    print(f"\nMutations not caught by any suite: {missed} of {len(MUTATIONS)}")
    return 1 if missed else 0


if __name__ == "__main__":
    raise SystemExit(main())
