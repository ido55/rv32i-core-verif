# Resume bullets

Every number is measured and reproduced by `make results` (see README.md), with two
exceptions, both recorded in docs/bugs.md: the 2,000-seed sweeps (command given there), and
the "0/45" figure from the first mutation-analysis run, before the hazard tests existed.

- Designed a 5-stage pipelined RV32I CPU in SystemVerilog (forwarding, load-use stall, branch flush) alongside a single-cycle reference core; passed all 40 applicable official rv32ui riscv-tests and measured CPI 1.159 (fibonacci) and 1.595 (bubble sort), with every lost cycle attributed to fill, stalls or flushes.
- Built a cocotb + Verilator verification environment with a Python ISS golden model and an RVFI-style per-instruction scoreboard; ran 142 directed, compliance and constrained-random tests per core plus 2,000-seed random sweeps on each core with zero mismatches, reaching 103/103 functional coverage bins.
- Validated test quality with automated mutation analysis: all 7 injected pipeline hazard bugs caught by every suite. The analysis exposed a directed-test gap (0/45 detection of x0 forwarding), which I closed with 5 targeted hazard tests.
- Synthesized both cores with Yosys (pipeline: 7,502 generic cells including 1,681 flip-flops) in a Dockerized GitHub Actions CI that runs lint, 720 tests and synthesis on every push.
