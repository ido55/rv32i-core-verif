# Glossary

## What you'll learn

- A one- or two-line definition of every term and acronym used in this guide, with the
  chapter where it's explained in depth.

Example of how to use it: you meet "write-before-read bypass" in chapter 05. Look it up
below, read the two-line definition, then follow the chapter link if you need more.

---

| Term | Definition | Ch. |
|---|---|---|
| **`_q` / `_d`** | naming convention: `_q` is a flip-flop's output (current value), `_d` the value it will load at the next edge | [03](03_systemverilog_basics.md) |
| **`$signed`** | SystemVerilog function: treat a value as two's complement for one operation | [03](03_systemverilog_basics.md) |
| **`` `ifdef ``** | preprocessor directive: include code only if a macro is defined (`-DPIPELINED`) | [03](03_systemverilog_basics.md) |
| **7-series** | a Xilinx FPGA family (Artix-7, Kintex-7, …); `synth_xilinx` targets its primitives | [09](09_tooling.md) |
| **ABC** | the logic-optimisation program Yosys calls internally | [09](09_tooling.md) |
| **ABI** | application binary interface: software conventions for register use, e.g. `sp` = x2, `a0` = x10 | [02](02_riscv_basics.md) |
| **Active-low** | a signal that means "true" when 0; marked with `_n`, e.g. `rst_n` | [03](03_systemverilog_basics.md) |
| **Alignment** | an access of N bytes is aligned if its address is a multiple of N; misaligned accesses are out of scope here | [02](02_riscv_basics.md) |
| **ALU** | arithmetic logic unit: computes add, sub, shifts, compares, logic ops (`rtl/alu.sv`) | [04](04_single_cycle_core.md) |
| **`always_comb`** | SystemVerilog block describing combinational logic; uses `=` | [03](03_systemverilog_basics.md) |
| **`always_ff`** | SystemVerilog block describing flip-flops updated on a clock edge; uses `<=` | [03](03_systemverilog_basics.md) |
| **Architectural state** | what software can observe: registers, pc, memory | [06](06_golden_model.md) |
| **Assignment pattern** | `'{field: value, ...}`: sets several struct fields at once | [03](03_systemverilog_basics.md) |
| **AUIPC** | "add upper immediate to pc": rd = pc + (imm << 12) | [02](02_riscv_basics.md) |
| **B-type** | instruction format for branches; 13-bit even offset with scrambled immediate bits | [02](02_riscv_basics.md) |
| **Bin** | one value or situation counted by a coverpoint, e.g. `beq_taken` | [07](07_verification.md) |
| **Blocking assignment** | `=`: takes effect immediately, so later statements see it; used in `always_comb` | [03](03_systemverilog_basics.md) |
| **Branch penalty** | cycles lost when a branch is taken; 2 here | [05](05_pipeline.md) |
| **BTB** | branch target buffer: a small cache that predicts branch targets in IF (not implemented) | [12](12_interview_prep.md) |
| **Bubble** | an empty pipeline slot (`valid = 0`) that changes no state and doesn't retire | [05](05_pipeline.md) |
| **Byte enable / byte mask** | 4 bits saying which bytes of a 32-bit word an access touches | [04](04_single_cycle_core.md) |
| **CARRY4** | Xilinx 7-series fast carry-chain primitive, used for adders and comparators | [10](10_results.md) |
| **CI** | continuous integration: automatic lint, test and synth on every push (GitHub Actions here) | [09](09_tooling.md) |
| **cocotb** | Python framework for writing testbenches that run inside an HDL simulator | [09](09_tooling.md) |
| **Code coverage** | tool-measured coverage of RTL lines, branches or toggles (not used here) | [07](07_verification.md) |
| **Combinational logic** | logic whose output depends only on current inputs, with no memory | [03](03_systemverilog_basics.md) |
| **Constrained-random test** | randomly generated stimulus, restricted by rules that keep it legal and aimed | [07](07_verification.md) |
| **Control** | the part of a CPU that decides what the datapath does for each instruction (the decoder here) | [04](04_single_cycle_core.md) |
| **Control hazard** | the pipeline fetched past a branch/jump before knowing its outcome | [05](05_pipeline.md) |
| **Coverage closure** | reaching the coverage goal; the closure curve tracks bins hit vs tests run | [07](07_verification.md) |
| **Coverpoint** | something to observe for coverage, divided into bins | [07](07_verification.md) |
| **CPI** | cycles per instruction = cycles / instructions retired | [05](05_pipeline.md) |
| **Critical path** | the longest combinational path between flip-flops; it sets the minimum clock period | [04](04_single_cycle_core.md) |
| **Cross coverage** | bins for combinations of two coverpoints (not implemented) | [07](07_verification.md) |
| **CSR / Zicsr** | control and status registers, a RISC-V extension for interrupts, exceptions, counters (not supported) | [02](02_riscv_basics.md) |
| **Data hazard** | an instruction needs a value an older in-flight instruction hasn't written yet | [05](05_pipeline.md) |
| **Datapath** | the hardware that moves and transforms data: register file, ALU, muxes, memory interface | [04](04_single_cycle_core.md) |
| **DFF** | D flip-flop. Yosys's generic flip-flop cells are named after it: `$_SDFFE_…` and `$_SDFFCE_…` are variants with a synchronous reset and an enable | [10](10_results.md) |
| **Decoder** | turns an instruction word into control signals (`rtl/decoder.sv`, `model/decoder.py`) | [04](04_single_cycle_core.md) |
| **Directed test** | a hand-written test aimed at one specific behaviour | [07](07_verification.md) |
| **Docker** | tool for running software in a container built from a fixed image | [09](09_tooling.md) |
| **DUT** | design under test: the core being verified | [07](07_verification.md) |
| **ECALL / EBREAK** | system instructions; in this project both mean "halt" | [02](02_riscv_basics.md) |
| **Enum** | a type whose values have names, e.g. `alu_op_e` | [03](03_systemverilog_basics.md) |
| **EX** | execute stage: forwarding muxes, ALU, branch resolution | [05](05_pipeline.md) |
| **FDRE** | Xilinx 7-series D flip-flop with clock enable and synchronous reset | [10](10_results.md) |
| **FENCE** | memory-ordering instruction; a no-op in this single-core design | [02](02_riscv_basics.md) |
| **Fill (pipeline fill)** | the 4 cycles before the first instruction reaches WB | [05](05_pipeline.md) |
| **Flatten** | synthesis option that merges submodules into one, so counts cover the whole core | [09](09_tooling.md) |
| **Flip-flop** | 1-bit storage that loads its input on a clock edge | [03](03_systemverilog_basics.md) |
| **Flush** | squashing wrong-path instructions after a taken branch, jump or halt | [05](05_pipeline.md) |
| **Fmax** | maximum clock frequency of a design (not measured here) | [10](10_results.md) |
| **Forwarding (bypassing)** | passing a result directly from a later pipeline register to an earlier stage, before it's written to the register file | [05](05_pipeline.md) |
| **FPGA** | field-programmable gate array: a chip of LUTs, flip-flops and wiring configured after manufacture | [09](09_tooling.md) |
| **FST / VCD** | waveform file formats; Verilator writes VCD (value change dump) here | [09](09_tooling.md) |
| **funct3 / funct7** | instruction fields [14:12] and [31:25] that select the exact operation | [02](02_riscv_basics.md) |
| **Generate block** | SystemVerilog construct for conditional or replicated hardware; avoided in `tb_top` because of a cocotb/Verilator limitation | [03](03_systemverilog_basics.md) |
| **GitHub Actions** | GitHub's CI service; workflow in `.github/workflows/ci.yml` | [09](09_tooling.md) |
| **Golden model** | an independent reference implementation that gives the expected results | [06](06_golden_model.md) |
| **GTKWave** | waveform viewer for VCD/FST files | [09](09_tooling.md) |
| **Halt** | here: ECALL/EBREAK/illegal stops the core (`halted = 1`) | [04](04_single_cycle_core.md) |
| **Hazard** | a situation where the next instruction can't safely proceed in the next cycle | [05](05_pipeline.md) |
| **I-type** | instruction format with a 12-bit signed immediate (ALU-immediate, loads, JALR) | [02](02_riscv_basics.md) |
| **IBUF / OBUF / BUFG** | Xilinx input/output/clock buffers inserted on the top-level ports | [10](10_results.md) |
| **ID** | instruction decode stage: decode, register read, load-use check | [05](05_pipeline.md) |
| **IF** | instruction fetch stage | [05](05_pipeline.md) |
| **Illegal instruction** | a word that isn't a supported instruction; the core traps (`rvfi_trap`) and stops | [04](04_single_cycle_core.md) |
| **imem / dmem** | instruction memory and data memory: two 16 KiB arrays in `tb/tb_top.sv`, outside the cores | [04](04_single_cycle_core.md) |
| **Immediate** | a constant encoded inside the instruction | [02](02_riscv_basics.md) |
| **`inside`** | SystemVerilog set-membership operator | [03](03_systemverilog_basics.md) |
| **INV** | Xilinx inverter primitive; reported separately from the LUT count (`make synth`) | [10](10_results.md) |
| **ISA** | instruction set architecture: the contract between software and CPU | [02](02_riscv_basics.md) |
| **ISS** | instruction-set simulator: executes instructions one at a time in software (`model/iss.py`) | [06](06_golden_model.md) |
| **J-type** | instruction format of JAL; 21-bit even offset | [02](02_riscv_basics.md) |
| **JAL / JALR** | jump and link (pc-relative) / jump and link register (rs1 + imm, bit 0 cleared); both write pc + 4 to rd | [02](02_riscv_basics.md) |
| **JUnit XML** | standard test-result file format; cocotb writes `*.None`, pytest writes `--junitxml` | [09](09_tooling.md) |
| **Latch** | level-sensitive storage, usually an accidental bug in `always_comb` | [03](03_systemverilog_basics.md) |
| **Latency vs throughput** | time for one instruction vs instructions finished per unit time | [05](05_pipeline.md) |
| **`li`** | "load immediate" pseudo-instruction: LUI + ADDI | [02](02_riscv_basics.md) |
| **Lint** | static checks of source code with no simulation (`verilator --lint-only`, `ruff`) | [09](09_tooling.md) |
| **Lint waiver** | comment pair `/* verilator lint_off X */ … lint_on X` that silences one intended warning (`UNDRIVEN`, `UNUSEDPARAM`, `UNUSEDSIGNAL`) in a narrow scope | [03](03_systemverilog_basics.md) |
| **Little-endian** | the lowest address holds the least significant byte | [02](02_riscv_basics.md) |
| **Load-use hazard** | a load's result is needed by the very next instruction; costs a 1-cycle stall | [05](05_pipeline.md) |
| **`localparam`** | a constant that can't be overridden from outside the module | [03](03_systemverilog_basics.md) |
| **Lockstep** | here: one model step per retired RTL instruction | [06](06_golden_model.md) |
| **LSU** | load/store unit: byte masks, lane shifting, sign extension (`rtl/lsu.sv`) | [04](04_single_cycle_core.md) |
| **LUI** | "load upper immediate": rd = imm << 12 | [02](02_riscv_basics.md) |
| **LUT** | look-up table: the FPGA's basic logic element (LUT6 = any 6-input function) | [10](10_results.md) |
| **M extension** | RISC-V multiply/divide extension (not implemented; exercise 9 adds MUL) | [13](13_exercises.md) |
| **Make / Makefile** | build tool; the Makefile lists every project command | [09](09_tooling.md) |
| **`mem_fault`** | `tb_top` output flagging a retired access outside the memories or misaligned | [07](07_verification.md) |
| **MEM** | memory stage: data-memory access | [05](05_pipeline.md) |
| **MUXF7 / MUXF8** | Xilinx wide-mux primitives combining LUT outputs | [10](10_results.md) |
| **Mutation analysis** | injecting deliberate bugs to measure whether tests detect them | [07](07_verification.md) |
| **Netlist** | a circuit as a list of cells and the wires connecting them; output of synthesis | [09](09_tooling.md) |
| **Non-blocking assignment** | `<=`: all right-hand sides are evaluated first, then all targets update together; used in `always_ff` | [03](03_systemverilog_basics.md) |
| **NOP** | an instruction that does nothing; canonical form `addi x0, x0, 0` | [02](02_riscv_basics.md) |
| **Opcode** | bits [6:0] of an instruction; selects the instruction class | [02](02_riscv_basics.md) |
| **OP / OP-IMM / MISC-MEM / SYSTEM** | names of opcode classes: register ALU ops, immediate ALU ops, FENCE, ECALL/EBREAK/CSR | [02](02_riscv_basics.md) |
| **Package** | SystemVerilog container for shared types and constants (`rv32i_pkg`) | [03](03_systemverilog_basics.md) |
| **Packed struct** | struct stored as one contiguous bit vector, first field at the MSB | [03](03_systemverilog_basics.md) |
| **Parameter** | a module constant that can be set when the module is instantiated | [03](03_systemverilog_basics.md) |
| **pc** | program counter: the address of the current instruction | [02](02_riscv_basics.md) |
| **Pipeline** | overlapping the stages of several instructions, like an assembly line | [05](05_pipeline.md) |
| **Pipeline register** | the flip-flops between two stages (`if_id_q`, `id_ex_q`, `ex_mem_q`, `mem_wb_q`) | [05](05_pipeline.md) |
| **Place and route** | FPGA/ASIC step after synthesis that places cells and routes wires; gives real timing (not done here) | [10](10_results.md) |
| **Plusarg** | a `+NAME=value` argument to the simulator, read in cocotb via `cocotb.plusargs` | [08](08_bugs_found.md) |
| **Predict not taken** | the simplest branch prediction: always fetch pc + 4 | [05](05_pipeline.md) |
| **Pseudo-instruction** | assembler shorthand that expands to real instructions (`li`, `nop`, `mv`) | [02](02_riscv_basics.md) |
| **pytest** | Python test runner; runs the model tests and launches the cocotb simulations | [09](09_tooling.md) |
| **Questa / VCS / Xcelium / Icarus** | other HDL simulators (three commercial, one open-source); event-driven, unlike Verilator | [09](09_tooling.md) |
| **R-type** | instruction format for register-register ALU operations | [02](02_riscv_basics.md) |
| **RAW** | read-after-write data dependency | [05](05_pipeline.md) |
| **Redirect** | changing the pc to a branch/jump target from EX | [05](05_pipeline.md) |
| **Register file** | the CPU's array of 32 registers (`rtl/regfile.sv`) | [04](04_single_cycle_core.md) |
| **Regression** | the full test suite, re-run on every change | [07](07_verification.md) |
| **Retire** | an instruction completes and its effects become architectural | [04](04_single_cycle_core.md) |
| **Retire port** | the `rvfi_*` outputs that describe each retired instruction | [04](04_single_cycle_core.md) |
| **RISC-V** | an open, modular instruction set architecture | [02](02_riscv_basics.md) |
| **riscv-tests** | the official RISC-V instruction tests; the rv32ui suite is used here | [07](07_verification.md) |
| **ruff** | Python linter and formatter | [09](09_tooling.md) |
| **RV32I** | 32-bit RISC-V base integer instruction set | [02](02_riscv_basics.md) |
| **RVFI** | RISC-V Formal Interface: a standard retire-port format, used by riscv-formal | [06](06_golden_model.md) |
| **riscv-formal** | formal verification framework for RISC-V cores that connects to an RVFI port (next step) | [12](12_interview_prep.md) |
| **S-type** | instruction format for stores; immediate split around the rs fields | [02](02_riscv_basics.md) |
| **Scoreboard** | checker comparing DUT outputs against model predictions, transaction by transaction | [07](07_verification.md) |
| **Seed** | starting value of a random generator; same seed, same program | [07](07_verification.md) |
| **Sign extension** | widening a signed value by copying its sign bit into the new upper bits | [02](02_riscv_basics.md) |
| **Single-cycle core** | CPU that completes every instruction in one clock cycle (CPI = 1) | [04](04_single_cycle_core.md) |
| **`SPECS`** | the instruction table in `model/isa.py`; the encoder, decoder, coverage and tests all read it | [06](06_golden_model.md) |
| **Spike** | the official RISC-V ISS (C++); not used here | [06](06_golden_model.md) |
| **Stall** | holding instructions in place for a cycle while a bubble moves forward | [05](05_pipeline.md) |
| **Stimulus** | the inputs applied to the DUT; for a CPU, the program | [07](07_verification.md) |
| **Structural hazard** | two instructions need the same hardware in one cycle (none in this core) | [05](05_pipeline.md) |
| **Submodule** | a git repository embedded in another at a pinned commit (`third_party/riscv-tests`) | [01](01_big_picture.md) |
| **sv2v** | converter from SystemVerilog to Verilog-2005, used before Yosys | [09](09_tooling.md) |
| **Synchronous reset** | reset that is only acted on at a clock edge | [03](03_systemverilog_basics.md) |
| **Synthesis** | translating RTL into a netlist of real cells | [09](09_tooling.md) |
| **SystemVerilog** | the hardware description and verification language used in `rtl/` | [03](03_systemverilog_basics.md) |
| **Test knobs** | environment variables the tests read: `CORE`, `SEED`, `SEEDS`, `SEED_START`, `WAVES` (exported by the Makefile), `TESTCASE` (cocotb: run one test) | [09](09_tooling.md) |
| **Testbench** | everything around the DUT that drives and checks it | [07](07_verification.md) |
| **Transaction** | the unit a scoreboard compares; here, one retired instruction | [07](07_verification.md) |
| **Two's complement** | the standard binary encoding of signed integers | [02](02_riscv_basics.md) |
| **U-type** | instruction format with a 20-bit upper immediate (LUI, AUIPC) | [02](02_riscv_basics.md) |
| **`unique case`** | `case` whose branches are declared mutually exclusive; tools check it | [03](03_systemverilog_basics.md) |
| **`uses_rs1` / `uses_rs2`** | decoder outputs saying whether rs1/rs2 are really read; prevent false hazards | [05](05_pipeline.md) |
| **`valid` bit** | first field of every pipeline register; 0 = bubble | [05](05_pipeline.md) |
| **venv** | Python virtual environment (`.venv/`) holding the pinned packages | [09](09_tooling.md) |
| **Verilog-2005** | the older Verilog standard that sv2v outputs and Yosys reads fully |  [09](09_tooling.md) |
| **2-state simulation** | signals are only 0 or 1 (no X/Z); Verilator's default, which can hide uninitialised-value bugs | [09](09_tooling.md) |
| **Verilator** | open-source simulator that compiles SystemVerilog into C++; also a linter | [09](09_tooling.md) |
| **VPI** | Verilog Procedural Interface: the C API cocotb uses to read and write signals | [09](09_tooling.md) |
| **Waveform** | a time plot of signal values, dumped by the simulator to VCD | [09](09_tooling.md) |
| **WB** | write-back stage: register write and the retire port | [05](05_pipeline.md) |
| **Word / halfword / byte** | 4 / 2 / 1 bytes | [02](02_riscv_basics.md) |
| **Write-before-read bypass** | ID takes a value being written back in the same cycle straight from WB | [05](05_pipeline.md) |
| **WSL2** | Windows Subsystem for Linux; the development environment | [09](09_tooling.md) |
| **x0** | register 0, always reads zero; writes are ignored | [02](02_riscv_basics.md) |
| **XLEN** | the register width of a RISC-V variant; 32 for RV32 | [02](02_riscv_basics.md) |
| **Yosys** | open-source synthesis tool | [09](09_tooling.md) |
| **Zifencei** | RISC-V extension providing `FENCE.I` (not supported) | [02](02_riscv_basics.md) |

## Check yourself

1. What is the difference between a bubble and a stall?
2. What is RVFI, and how does this repo use the idea?
3. Define "coverpoint" and "bin" with an example from this repo.

<details>
<summary>Answers</summary>

1. A bubble is an empty pipeline slot (`valid = 0`). A stall is the action of holding
   instructions in place for a cycle; it *creates* a bubble in EX.
2. The RISC-V Formal Interface, a standard set of signals describing each retired
   instruction. Both cores expose an RVFI-style retire port that the scoreboard compares
   with the ISS.
3. A coverpoint is something you want to observe, e.g. `branch`. Its bins are the
   situations counted, e.g. `beq_taken` and `beq_not_taken` (`tb/coverage.py:44`).

</details>
