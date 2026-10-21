# 03 · SystemVerilog basics (only what this repo uses)

## What you'll learn

- What a hardware description language is, and how it differs from a program.
- Every SystemVerilog construct used in `rtl/` and `tb/tb_top.sv`, each shown with a real
  snippet from this repo:
  - modules and ports;
  - `logic` and vectors;
  - `assign`;
  - `always_comb` vs `always_ff`;
  - blocking vs non-blocking assignment;
  - `case`;
  - concatenation;
  - parameters;
  - packages;
  - enums;
  - packed structs;
  - module instances;
  - `` `ifdef ``.
- The rules the repo follows to avoid the classic beginner bug, the accidental latch.

---

## 1. A worked example first: the register file

Here is the complete register file, `rtl/regfile.sv:4-31`:

```systemverilog
module regfile (
  input  logic        clk,
  input  logic        rst_n,     // synchronous, active-low: clears all registers

  input  logic [4:0]  rs1_addr,
  output logic [31:0] rs1_data,
  input  logic [4:0]  rs2_addr,
  output logic [31:0] rs2_data,

  input  logic        we,
  input  logic [4:0]  rd_addr,
  input  logic [31:0] rd_data
);

  logic [31:0] regs_q [32];

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      for (int i = 0; i < 32; i++) regs_q[i] <= 32'b0;
    end else if (we && rd_addr != 5'd0) begin
      regs_q[rd_addr] <= rd_data;
    end
  end

  assign rs1_data = (rs1_addr == 5'd0) ? 32'b0 : regs_q[rs1_addr];
  assign rs2_data = (rs2_addr == 5'd0) ? 32'b0 : regs_q[rs2_addr];

endmodule
```

Here is how it maps to digital logic you already know:

- **The `regs_q` array** is 32 registers of 32 flip-flops each: 1,024 flip-flops.
  Synthesis confirms it: the `$_SDFFCE_` count in chapter 10 is exactly 1,024.
- **The `always_ff @(posedge clk)` block** describes what those flip-flops load on each
  rising clock edge:
  - zeros during reset;
  - otherwise `rd_data` into one register, when `we` is set and the target isn't x0.
- **The two `assign` lines** are read ports: two 32-to-1 multiplexers, each with an
  "is it x0?" override that forces the output to 0.

**SystemVerilog describes a circuit.** It is not a sequence of steps. Every `assign` and
every `always` block exists all the time, in parallel. They are all wires and gates at once.

## 2. Modules and ports

A **module** is a hardware block with **ports**, its input and output wires. It's like a
chip with pins. A **port** declaration has a direction, a type and a width:

```systemverilog
  input  logic [4:0]  rs1_addr,
  output logic [31:0] rs1_data,
```

`rs1_addr` is a 5-bit input, a register number 0–31. `rs1_data` is a 32-bit output.
`[4:0]` means bits 4 down to 0, 5 bits in total. Bit 4 is the most significant. This
"high:low" order is the convention throughout the repo.

Two modules here use a different header style, importing a package between the name and
the port list (`rtl/alu.sv:2-9`):

```systemverilog
module alu
  import rv32i_pkg::*;
(
  input  alu_op_e     op,
  input  logic [31:0] a,
  input  logic [31:0] b,
  output logic [31:0] y
);
```

The `import` makes the package's types, such as `alu_op_e`, usable *in the port list
itself*. Section 9 covers packages. This exact line is what Yosys 0.33 cannot parse,
which is why synthesis goes through sv2v (chapter 09).

## 3. `logic`, vectors and arrays

- **`logic`** is a signal that holds 0, 1, X (unknown) or Z (undriven). The repo uses
  `logic` for everything, as `CLAUDE.md:21` requires. Older Verilog distinguished `wire` and
  `reg`; SystemVerilog's `logic` replaces both.
- **`logic [31:0] x`** is a 32-bit **vector**. `x[3]` is one bit. `x[31:2]` is a
  **part-select** of 30 bits.
- **`logic [31:0] regs_q [32]`** is an **unpacked array**: 32 separate 32-bit elements.
  Read the declaration in two parts:
  - the bits per element come before the name;
  - the number of elements comes after it.
- **`logic [31:0] imem [MEM_WORDS]`** (`tb/tb_top.sv:36`) is how the testbench models a
  memory.

**Number literals** give a width, a base and a value:
- `32'b0` is 32 zero bits;
- `5'd0` is the 5-bit decimal 0;
- `4'b0001` is a 4-bit binary value;
- `7'b0110111` is an opcode;
- `'0` means "all zeros, whatever width is needed" (`rtl/core_pipe.sv:295`).

## 4. `assign`: continuous combinational logic

```systemverilog
assign shamt = b[4:0];                                   // rtl/alu.sv:13
assign imem_addr = pc_q;                                 // rtl/core_single.sv:60
assign dmem_addr  = {alu_y[31:2], 2'b00};                // rtl/core_single.sv:127
```

`assign y = expr;` means y is *always* equal to expr. It's a wire connected to some gates.
It has no memory and no clock.

**The ternary `c ? a : b` is a 2-to-1 multiplexer.** For example,
`assign alu_b = ctrl.alu_b_imm ? ctrl.imm : rs2_data;` (`rtl/core_single.sv:88`) chooses
the ALU's second operand.

## 5. `always_comb` vs `always_ff`

Both describe hardware. They describe *different kinds* of hardware:

| | `always_comb` | `always_ff @(posedge clk)` |
|---|---|---|
| Describes | combinational logic: gates, muxes | flip-flops: state |
| Updates when | any input changes | only at the rising clock edge |
| Assignment operator | `=` (blocking) | `<=` (non-blocking) |
| Example | `rtl/alu.sv:15-29` | `rtl/regfile.sv:20-26` |

**`always_comb`** is like an `assign` that's too big for one line: `case` statements,
`if` chains, defaults. Here is the ALU (`rtl/alu.sv:15-29`):

```systemverilog
always_comb begin
  unique case (op)
    ALU_ADD:  y = a + b;
    ALU_SUB:  y = a - b;
    ALU_SLL:  y = a << shamt;
    ALU_SLT:  y = {31'b0, $signed(a) < $signed(b)};
    ALU_SLTU: y = {31'b0, a < b};
    ALU_XOR:  y = a ^ b;
    ALU_SRL:  y = a >> shamt;
    ALU_SRA:  y = $unsigned($signed(a) >>> shamt);
    ALU_OR:   y = a | b;
    ALU_AND:  y = a & b;
    default:  y = 32'b0;  // unused encodings; also prevents a latch
  endcase
end
```

In hardware, all ten results are computed at once by ten circuits, and `op` drives a mux
that picks one. There is no "if this then compute that".

**`always_ff`** describes flip-flops. Here is the single-cycle core's state
(`rtl/core_single.sv:140-148`):

```systemverilog
always_ff @(posedge clk) begin
  if (!rst_n) begin
    pc_q     <= 32'b0;
    halted_q <= 1'b0;
  end else if (active) begin
    pc_q <= pc_next;
    if (ctrl.halt || ctrl.illegal) halted_q <= 1'b1;
  end
end
```

**Reset is synchronous.** `if (!rst_n)` is checked only at the clock edge. **Active-low**
means `rst_n = 0` *is* reset (the `_n` suffix means "negated"). Both conventions come from
`CLAUDE.md:21-23`.

### Blocking `=` vs non-blocking `<=`

This is the one rule that trips everyone up:

- **Inside `always_ff`, use `<=`.** All the right-hand sides are evaluated with the values
  from *before* the edge, then every flip-flop updates together. That's how real
  flip-flops behave.
- **Inside `always_comb`, use `=`.** The statements run top to bottom, and later lines see
  earlier results, like normal code. That's how the decoder sets defaults first and then
  overrides them (section 7).

**Worked example.** At each edge, the pipeline moves every instruction one stage forward
(`rtl/core_pipe.sv:317-318`):

```systemverilog
ex_mem_q <= ex_mem_d;
mem_wb_q <= mem_wb_d;
```

`mem_wb_d` is computed from the *old* `ex_mem_q`. With `<=`, the instruction that was in
EX/MEM moves into MEM/WB, and the one from EX moves into EX/MEM, all at the same instant.

With `=`, the first line would change `ex_mem_q` immediately. The second line would then
see the new value, and the simulation could skip a stage. The result would disagree with
the synthesized hardware.

### Naming: `_q` and `_d`

- **`_q`** is the output of a flip-flop: `pc_q`, `id_ex_q`.
- **`_d`** is the next value about to be loaded into it: `id_ex_d`, `ex_mem_d`.

The names come from the classic D flip-flop's D (input) and Q (output) pins. The
convention is in `CLAUDE.md:22`, and `rtl/core_pipe.sv:95-99` uses it for every pipeline
register.

## 6. `case`, `unique case`, `if`, and the latch rule

**`unique case`** (`rtl/alu.sv:16`) tells tools that exactly one branch matches. A
simulator warns if none or two match. Synthesis may build a parallel mux rather than a
priority chain.

**The latch rule.** In `always_comb`, every output must be assigned on *every* path.
Otherwise the signal has to "remember" its old value, and synthesis builds a **latch**, a
level-sensitive storage element. That is almost always a bug. The repo avoids it two ways:

1. **A `default` branch in every `case`.** For example, `default: y = 32'b0;  // ... also
   prevents a latch` (`rtl/alu.sv:27`).
2. **Assign defaults at the top, then override.** The decoder starts every instruction as
   "do nothing" (`rtl/decoder.sv:31-40`):

   ```systemverilog
   always_comb begin
     // Defaults: an instruction that does nothing. Each case turns on what it needs.
     ctrl           = '0;
     ctrl.rd        = insn[11:7];
     ...
   ```

`make synth` checks this: it fails if Yosys reports any warning or infers any latch
(`tools/synth_report.py:52-56,63`).

## 7. Operators the repo relies on

| Syntax | Meaning | Example |
|---|---|---|
| `{a, b}` | concatenation: a's bits, then b's bits | `{alu_y[31:2], 2'b00}` clears the low 2 bits (`rtl/core_single.sv:127`) |
| `{N{x}}` | replication: x repeated N times | `{{20{insn[31]}}, insn[31:20]}` is sign extension (`rtl/decoder.sv:21`) |
| `$signed(x)` | treat x as two's complement for this operation | signed compare in `slt` (`rtl/alu.sv:20`) |
| `>>>` | arithmetic shift right, which copies the sign bit (needs a signed operand) | `sra` (`rtl/alu.sv:24`) |
| `x inside {a, b, c}` | set membership: x equals any of them | `opcode inside {OPC_BRANCH, OPC_STORE, OPC_OP}` (`rtl/decoder.sv:132`) |
| `16'(expr)` | size cast: keep the low 16 bits | `16'(mem_rdata >> shift)` (`rtl/lsu.sv:21`) |
| `alu_op_e'(bits)` | cast bits to an enum type | `alu_op_e'({funct7[5], funct3})` (`rtl/decoder.sv:112`) |
| `x[8*b +: 8]` | indexed part-select: 8 bits starting at bit 8·b | byte write enables (`tb/tb_top.sv:67`) |
| `^{a, b}` | reduction XOR of all bits | the "consume unused bits" trick (`rtl/core_single.sv:57`) |

## 8. Parameters and `localparam`

A **parameter** is a constant that can be set when the module is instantiated, so one
design serves several sizes:

```systemverilog
module tb_top #(
  parameter int MEM_WORDS = 4096  // 16 KiB per memory, addresses 0x0000..0x3FFF
) (                                                       // tb/tb_top.sv:9-11
...
localparam int IDX_BITS = $clog2(MEM_WORDS);              // tb/tb_top.sv:32
```

A **`localparam`** is a constant that *cannot* be overridden from outside. `$clog2(4096)`
is 12, the number of address bits needed to index the memory.

Note one thing: the Python side keeps its own copy, `MEM_WORDS = 4096  # must match tb_top's
MEM_WORDS parameter` (`tb/harness.py:29`). The two copies are only tied together by
that comment. Chapter 07 lists it under Known gaps.

## 9. Packages

A **package** holds definitions shared by many modules: constants, types and enums.
`rtl/rv32i_pkg.sv:4-88` is the only one in the repo:

```systemverilog
package rv32i_pkg;
  localparam logic [6:0] OPC_LUI      = 7'b0110111;
  ...
endpackage
```

A module uses it with `import rv32i_pkg::*;` (section 2). The package must be compiled
*before* the modules that import it. That's why every source list in the repo starts with
it ("packages first", `Makefile:11-13`; `tb/harness.py:33-37`).

## 10. Enums

An **enum** gives names to the values of a small field (`rtl/rv32i_pkg.sv:38-49`):

```systemverilog
typedef enum logic [3:0] {
  ALU_ADD  = 4'b0000,
  ALU_SLL  = 4'b0001,
  ...
  ALU_SUB  = 4'b1000,
  ALU_SRA  = 4'b1101
} alu_op_e;
```

- **`typedef`** creates a new type name. The `_e` suffix marks an enum.
- **`logic [3:0]`** says the enum is stored in 4 bits.
- **The values are chosen on purpose:** each one is `{funct7[5], funct3}` of the
  instruction. The decoder can then build the ALU operation straight from instruction
  bits, with no lookup table (`rtl/decoder.sv:112`). The Python model uses the same
  numbers (`model/alu.py:8-18`), and a comment in each file says they must match
  (`rtl/rv32i_pkg.sv:36-37`).

There are two more enums:
- `alu_a_sel_e`, the ALU's first operand: rs1, pc or zero (`rtl/rv32i_pkg.sv:52-56`);
- `wb_sel_e`, what gets written back: ALU result, load data or pc+4
  (`rtl/rv32i_pkg.sv:59-63`).

The pipeline defines one inside the module, `fwd_sel_e` (`rtl/core_pipe.sv:162-166`).

## 11. Packed structs

A **struct** groups named fields. A **packed** struct stores them back to back in one
long bit vector. The first field is at the most significant end, so it can be assigned,
cleared or stored in a flip-flop as a single value.

The decoder's whole output is one struct, `ctrl_t` (`rtl/rv32i_pkg.sv:66-86`):

```systemverilog
typedef struct packed {
  logic [4:0]  rd;
  logic [4:0]  rs1;
  logic [4:0]  rs2;
  logic        uses_rs1;   // the instruction really reads rs1 (for hazard detection)
  logic        uses_rs2;   // the instruction really reads rs2
  logic [2:0]  funct3;     // branch condition / load-store width
  logic [31:0] imm;        // already sign-extended and shifted for its format
  alu_op_e     alu_op;
  ...
  logic        halt;       // ECALL / EBREAK
  logic        illegal;    // not a supported RV32I instruction
} ctrl_t;
```

**Why this matters in the pipeline.** A pipeline register has to carry an instruction's
whole control state from one stage to the next. With a struct, that's one line:
`id_ex_d.ctrl = id_ctrl;` (`rtl/core_pipe.sv:156`). Each pipeline register is its own
struct (`rtl/core_pipe.sv:48-93`).

**How structs are used:**
- **Field access** uses a dot: `id_ex_q.ctrl.rd`.
- **Clearing all fields** at once uses `'0`: `if_id_q <= '0;` turns a stage into a
  **bubble**, an empty slot (`rtl/core_pipe.sv:305`).
- **Assigning several fields** at once uses an assignment pattern
  (`rtl/core_pipe.sv:310`):

  ```systemverilog
  if_id_q <= '{valid: 1'b1, pc: pc_q, insn: imem_rdata};
  ```

Because a packed struct is "just bits", waveform dumps show it as one wide vector. The
waveform tool relies on the first fields of every pipeline register being
`{valid, pc, insn}` so it can pull them out (`tools/failing_waveform.py:99-107`).

## 12. Instantiating modules

To use a module inside another, write an **instance**: the module name, an instance name,
then the port connections (`rtl/core_single.sv:62-65`):

```systemverilog
decoder u_decoder (
  .insn (imem_rdata),
  .ctrl (ctrl)
);
```

`.port (signal)` connects by name. The repo's convention is `u_` + module name for
instances.

The testbench uses the shortcut **`.*`**, which means "connect every port to the signal of
the same name in this scope" (`tb/tb_top.sv:48-53`):

```systemverilog
  // .* connects every port to the signal of the same name declared above.
`ifdef PIPELINED
  core_pipe u_core (.*);
`else
  core_single u_core (.*);
`endif
```

## 13. `` `ifdef ``: compile-time selection

`` `ifdef PIPELINED `` is a **preprocessor** directive, like C's `#ifdef`. It's resolved
before compilation. When the simulator is built with `-DPIPELINED`, `tb_top` contains
`core_pipe`; otherwise it contains `core_single`. Either way the instance is named
`u_core`, so Python can always reach `dut.u_core`.

The runner sets the define (`tests/rtl/cocotb_runner.py:40`). Using a parameter plus a
`generate` block would be more idiomatic, but cocotb 1.9 cannot look inside generate
blocks in Verilator 5.020, as the comment in `tb/tb_top.sv:5-6` records.

## 14. Functions and loops

A **function** is reusable combinational logic (`tb/tb_top.sv:74-76`):

```systemverilog
function automatic logic out_of_range(logic [31:0] addr);
  return (addr[31:IDX_BITS+2] != '0) || (addr[1:0] != 2'b00);
endfunction
```

`automatic` gives each call its own variables, the safe default.

A **`for` loop** in hardware is unrolled at compile time into copies of the logic.
`for (int b = 0; b < 4; b++) if (dmem_wmask[b]) dmem[...][8*b +: 8] <= ...;`
(`tb/tb_top.sv:65-69`) becomes four independent byte-write circuits. `rtl/regfile.sv:22`
likewise becomes 32 parallel resets.

## 15. Lint waivers

`verilator --lint-only -Wall` (chapter 09) must report zero warnings (`CLAUDE.md:23`).
When a warning is intended, the code waives it explicitly, in the narrowest scope, with
the reason next to it. For example (`tb/tb_top.sv:34-37`):

```systemverilog
// imem is only written by cocotb (through VPI), never by RTL.
/* verilator lint_off UNDRIVEN */
logic [31:0] imem [MEM_WORDS];
/* verilator lint_on UNDRIVEN */
```

The other waivers are:
- `UNUSEDPARAM` around the package (`rtl/rv32i_pkg.sv:3,89`);
- `UNUSEDSIGNAL` around the pipeline's coverage-only signals
  (`rtl/core_pipe.sv:345,361`);
- `UNUSEDSIGNAL` around the memory address bits the testbench ignores on purpose
  (`tb/tb_top.sv:42-44,73-77`).

## 16. Synthesizable vs simulation-only

**Synthesizable code** is everything that maps to gates and flip-flops: all of `rtl/`.
`make synth` turns it into gates (chapter 09).

`tb/tb_top.sv` is **simulation-only** in spirit. Its memories are written by Python through
the simulator, and it exists to wrap the core for testing. It is never synthesized.

## Known gaps

- `rtl/regfile.sv:3` says "the pipeline adds forwarding in M4". That was true when it
  was written, during M1. The comment is now historical.
- `rtl/core_single.sv:54-57` uses a reduction-XOR "unused" signal so Verilator doesn't
  warn that `uses_rs1` and `uses_rs2` are unused. It works, but it's a lint workaround,
  not logic. The comment says so.

## Check yourself

1. What hardware does `assign y = s ? a : b;` describe?
2. Why must `always_ff` blocks use `<=`? What could go wrong with `=`?
3. What is a latch, and name the two techniques this repo uses to avoid one.
4. Why does the decoder output a packed struct instead of 20 separate signals?
5. How does the same `tb_top.sv` end up containing either core?

<details>
<summary>Answers</summary>

1. A 2-to-1 multiplexer: `s` selects `a` or `b`. It's purely combinational.
2. With `<=`, every flip-flop samples its input from *before* the clock edge and they all
   update together, like real flip-flops. With `=`, a later statement in the same block
   would see an already-updated value. A pipeline could then skip a stage in simulation
   and disagree with the synthesized hardware.
3. A latch is level-sensitive storage. Synthesis infers one when an `always_comb` output
   isn't assigned on every path. The repo avoids it with a `default` branch in every `case`
   (`rtl/alu.sv:27`) and with defaults assigned at the top of the block
   (`rtl/decoder.sv:33-40`).
4. One struct carries every control field through the pipeline registers with a single
   assignment (`rtl/core_pipe.sv:156`) and can be cleared with `'0`. Both cores consume
   the same type.
5. `` `ifdef PIPELINED `` (`tb/tb_top.sv:49-53`). The runner builds the pipe simulation
   with `-DPIPELINED` (`tests/rtl/cocotb_runner.py:40`).

</details>
