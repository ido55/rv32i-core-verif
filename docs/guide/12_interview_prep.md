# 12 · Interview prep

## What you'll learn

- 30 questions an interviewer could ask about this project, ordered from easy to hard, each
  with a concise answer you can say out loud and a link to the chapter with the details.
- How to answer the two open-ended classics: "What was the hardest bug?" and "What would you
  improve?"
- Which numbers to know by heart, and the caveats to state before you're asked.

**How to use it:** cover the answer, say yours out loud, then compare. If your answer needs
more than about 30 seconds, it's too long for the first pass; offer the detail as a
follow-up.

---

## 1. A worked example first: answering "Tell me about this project"

> "I built two RISC-V RV32I cores in SystemVerilog: a single-cycle one, then a 5-stage
> pipeline with forwarding, a load-use stall and branch flush. Most of the work was
> verification. I wrote a Python instruction-set simulator as a golden model, validated it
> against the official riscv-tests and GNU `as`, then used cocotb and Verilator to compare
> every retired instruction from the RTL against the model. Stimulus is directed tests, the
> riscv-tests, two C programs and constrained-random programs, with functional coverage and
> mutation analysis to show the tests actually catch pipeline bugs. Both cores pass
> everything, 103 of 103 coverage bins on the pipeline, and all 7 injected pipeline bugs are
> caught. The pipeline's CPI is 1.16 on fibonacci and 1.60 on bubble sort, and I can account
> for every lost cycle."

It covers what you built, how you verified it, and measured results, in about 40 seconds.
Every claim in it is backed by a chapter of this guide.

## 2. Numbers to know by heart

| Fact | Value | Chapter |
|---|---|---|
| Instructions supported | 37 RV32I + FENCE/ECALL/EBREAK = 40 | 02 |
| Tests per core | 50 directed, 42 programs, 50 random = 142 | 07 |
| Model tests | 429 | 06 |
| Random sweep | 2,000 / 2,000 seeds per core | 10 |
| Coverage | 90 / 90 (single), 103 / 103 (pipe) | 07 |
| Mutations caught | 7 / 7, by every suite | 07 |
| CPI pipe | fibonacci 1.159, bubble sort 1.595 | 05 |
| Synthesis (pipe) | 7,502 generic cells, 1,681 flip-flops; 2,155 LUTs (`synth_xilinx`, excluding inverters) | 10 |
| Branch penalty / load-use penalty | 2 cycles / 1 cycle | 05 |

## 3. Questions

### Basics

**Q1. What is RV32I?**
The 32-bit base integer instruction set of RISC-V. It has 32 registers, x0 hard-wired to
zero, and fixed 32-bit instructions in six formats. No multiply, no CSRs. →
[02](02_riscv_basics.md)

**Q2. Why are the register fields in the same bit positions in every format?**
So the register file can be read before decoding finishes. The decoder takes rd, rs1 and
rs2 straight from fixed bits (`rtl/decoder.sv:34-36`). → [02](02_riscv_basics.md)

**Q3. What's the difference between `always_ff` and `always_comb`?**
`always_ff @(posedge clk)` describes flip-flops that update on the clock edge, using `<=`.
`always_comb` describes combinational logic that updates whenever an input changes, using
`=`. → [03](03_systemverilog_basics.md)

**Q4. How do you avoid latches?**
Assign every `always_comb` output on every path: a default at the top of the block
(`rtl/decoder.sv:33-40`) or a `default` branch in every `case` (`rtl/alu.sv:27`). `make
synth` fails if Yosys infers a latch. → [03](03_systemverilog_basics.md)

**Q5. What does the single-cycle core do in one cycle?**
Fetch, decode, read registers, run the ALU, access memory, select write-back data and
compute the next pc, all combinationally. At the rising edge it commits pc, the destination
register and any store. CPI is exactly 1. → [04](04_single_cycle_core.md)

**Q6. What is a golden model?**
An independent, obviously correct implementation that provides the expected results. Here
it's a Python instruction-set simulator, `model/iss.py`, about 180 lines. →
[06](06_golden_model.md)

**Q7. What is a scoreboard?**
A checker that compares the DUT's outputs with the model's predictions, one transaction at a
time. Here a transaction is one retired instruction, compared in 10 fields
(`tb/harness.py:221-236`). → [07](07_verification.md)

### Design

**Q8. Name the five pipeline stages and what each does.**
- IF: fetch at pc.
- ID: decode, read registers, detect load-use.
- EX: forwarding muxes, ALU, resolve branches.
- MEM: data memory access.
- WB: register write and the retire port.

→ [05](05_pipeline.md)

**Q9. What is forwarding, and which paths does this core have?**
Feeding a result to a dependent instruction before it's written to the register file. Here:
- EX/MEM → EX, for distance 1;
- MEM/WB → EX, for distance 2;
- a write-before-read bypass in ID, for distance 3 (`rtl/core_pipe.sv:140-199`).

→ [05](05_pipeline.md)

**Q10. If both EX/MEM and MEM/WB write the register an instruction needs, which wins and why?**
EX/MEM, because it holds the younger instruction, whose value is the architecturally
correct one. The if/else order encodes the priority (`rtl/core_pipe.sv:178-179`), and
`hazard_forwarding_newest_wins` tests it. → [05](05_pipeline.md)

**Q11. Why does a load-use need a stall even with forwarding?**
The load's data only appears at the end of MEM. In that same cycle the next instruction is
in EX, and the EX/MEM register holds the load's *address*, not its data. So the pipeline
holds IF and ID for one cycle, inserts a bubble, and then forwards from MEM/WB. →
[05](05_pipeline.md)

**Q12. How are branches handled, and what does a taken branch cost?**
Predict not taken: always fetch pc + 4. Branches resolve in EX. A taken branch or any jump
redirects the pc and squashes the two younger instructions in IF and ID, costing 2 cycles
(`rtl/core_pipe.sv:230-235,303-314`). → [05](05_pipeline.md)

**Q13. Why can't a stall and a flush happen in the same cycle?**
Both are decided by the single instruction in EX. A stall needs a load there; a flush needs
a branch, jump or halt there (`rtl/core_pipe.sv:290-291`). → [05](05_pipeline.md)

**Q14. Why does the decoder output `uses_rs1`/`uses_rs2`?**
In LUI, AUIPC and JAL, bits 19:15 and 24:20 are immediate bits, not register numbers.
Without the flags, the hazard logic would see false dependencies and stall or forward for
nothing (`rtl/decoder.sv:129-132`). → [05](05_pipeline.md)

**Q15. Why must forwarding check `rd != 0`?**
x0 always reads 0. If a write to x0 were forwarded, the consumer would see a non-zero x0.
That's the hardest mutation for the tests to catch (9 of 50 random seeds). →
[05](05_pipeline.md), [08](08_bugs_found.md)

**Q16. Explain the pipeline's CPI of 1.595 on bubble sort.**
3,639 instructions + 4 fill cycles + 496 load-use stall cycles + 2 × 832 flush cycles
= 5,803 cycles, and 5,803 / 3,639 = 1.595. A test asserts that formula for every program.
→ [05](05_pipeline.md), [10](10_results.md)

### Verification

**Q17. Why compare every retired instruction instead of the final state?**
A wrong value can be overwritten, or can surface thousands of cycles later. Per-instruction
comparison reports the first wrong instruction, with context. The final-state check is kept
too, for effects that never retire, such as a wrong-path store. → [07](07_verification.md)

**Q18. How does the same testbench verify both cores?**
Both expose an identical RVFI-style retire port. The harness skips cycles with no retired
instruction and steps the model once per retirement, so timing differences don't matter. →
[06](06_golden_model.md)

**Q19. How do you know the golden model is right?**
Four independent checks:
- hand-computed unit tests;
- the encoder against GNU `as` on 1,600 random instructions;
- the 40 official rv32ui tests on the ISS;
- C program results recomputed in plain Python.

An injected SRA bug in the model was caught by the riscv-tests. → [06](06_golden_model.md)

**Q20. Directed vs constrained-random: why both?**
Directed tests hit specific known cases with hand-checked answers. Random tests find
combinations nobody thought of. In the mutation table, random tests catch most bugs on
nearly every seed, while directed tests pin each bug with 1–2 targeted cases. →
[07](07_verification.md)

**Q21. How do you keep random programs legal?**
They're built from blocks, each with one constraint:
- loads and stores set their base register with `li` right before the access;
- branches and jumps only go forward;
- the only backward branch is a counted loop whose counter the body never writes.

200 seeds are run on the ISS to prove legality. → [07](07_verification.md)

**Q22. What is functional coverage, and what's yours?**
A record of which specified situations happened: 90 architectural bins plus 13 pipeline
bins, all hit. Architectural bins are sampled from the retire stream; pipeline bins from
the hazard logic every cycle. → [07](07_verification.md)

**Q23. You have 100% coverage. Are you done?**
No. Random coverage saturates after 3 programs, yet one injected bug is caught by only 9 of
50 seeds. The bins don't capture combinations. Cross coverage and mutation analysis address
that. → [07](07_verification.md)

**Q24. What is mutation analysis, and what did it find?**
Injecting realistic bugs to check that the tests fail. All 7 pipeline mutations are caught
by every suite type. The first run showed the directed tests catching "forwarding from x0"
in 0 of 45, so I added 5 targeted hazard tests. → [07](07_verification.md),
[08](08_bugs_found.md)

**Q25. How do you reproduce a failing random test?**
`make test-random CORE=pipe SEED_START=<seed> SEEDS=1 WAVES=1`. The same seed always gives
the same program, and `WAVES=1` writes a VCD for GTKWave. → [07](07_verification.md)

### Tools

**Q26. Why Verilator and cocotb?**
Both are free and fast. Verilator compiles the RTL to C++. cocotb lets the testbench reuse
the Python golden model directly. cocotb is pinned at 1.9.2 because 2.x needs Verilator ≥
5.036, and Ubuntu 24.04 has 5.020; that was measured. → [09](09_tooling.md)

**Q27. Why does synthesis go through sv2v?**
Yosys 0.33's SystemVerilog parser rejects package imports in module headers and `inside`.
sv2v converts the RTL to Verilog-2005 for synthesis only; simulation uses the original. →
[09](09_tooling.md)

### Hard

**Q28. What was the hardest bug?**
A testbench bug. The pipeline's measurements were filed under the single-cycle core, so the
single-cycle core showed CPI 1.595, which is impossible.

- **Cause:** the core name came from an environment variable that cocotb 1.9's runner
  overwrote with make's exported empty value.
- **What was still right:** pass/fail was correct the whole time; only the coverage and
  cycle counts were mislabelled.
- **The fix, three parts:**
  - pass the core as a plusarg, which the environment can't override;
  - check it against the hierarchy that was actually built;
  - assert single-cycle CPI == 1 and the pipeline timing formula on every program.

**The lesson:** the scariest bugs are green tests with wrong numbers, so make every
measurement checkable. → [08](08_bugs_found.md)

**Q29. Is your pipeline faster than your single-cycle core?**
I can't claim that from my data. CPI is higher (1.159 and 1.595 vs 1.000). The benefit of
pipelining is a shorter clock period, and I only measured area, not timing. The next step is
synchronous memories plus FPGA place-and-route to get a measured Fmax per core. →
[10](10_results.md)

**Q30. What would you improve?**
In order of value:
1. **Formal verification** with riscv-formal. The retire port is already RVFI-shaped.
2. **Cross coverage**, e.g. forwarding path × consuming instruction, so coverage tracks
   bug-finding power.
3. **Synchronous block-RAM memories and place-and-route**, for a real Fmax and LUT count.
   The current LUT figure excludes inverter cells and includes the retire port.
4. **A cheaper branch penalty** (resolve in ID, or a BTB), measured with the same CPI
   breakdown.
5. **Small cleanups:** stall-free store-data forwarding, and comparing against Spike to
   remove the shared-author risk in the golden model.

→ [05](05_pipeline.md), [07](07_verification.md), [10](10_results.md)

## 4. Caveats to volunteer before you're asked

Interviewers trust candidates who state the limits of their own numbers:

- "No RTL bug was found. The bugs I found were in the verification setup. That's why I did
  mutation analysis." ([08](08_bugs_found.md))
- "The memories are combinational, so the single-cycle design works but isn't
  FPGA-realistic." ([04](04_single_cycle_core.md))
- "The LUT counts come from `synth_xilinx` and exclude about 1,300 inverter cells, so
  they're estimates, not implementation results." ([10](10_results.md))
- "The model and the RTL share an author. The official riscv-tests and GNU `as`
  cross-checks are what make the model trustworthy." ([06](06_golden_model.md))

## Check yourself

1. Give the 40-second project summary from memory.
2. Explain, without notes, why a load-use pair costs one cycle.
3. Explain bubble sort's CPI in one sentence with the four numbers.
4. Tell the hardest-bug story in under a minute.
5. Name three improvements and why each matters.

<details>
<summary>Answers</summary>

1. See section 1.
2. See Q11. The data exists only at the end of MEM, and EX/MEM holds the address in that
   cycle, so the pipeline waits one cycle and then forwards from MEM/WB.
3. 3,639 instructions plus 4 fill, 496 stall and 1,664 flush cycles make 5,803 cycles;
   5,803 / 3,639 = 1.595.
4. See Q28.
5. See Q30. Formal verification (exhaustive proofs on the existing RVFI port), cross
   coverage (makes coverage track bug-finding), and place-and-route (gives a real Fmax
   comparison).

</details>
