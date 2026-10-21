# 02 · RISC-V basics

## What you'll learn

- What an instruction set architecture (ISA) is, and what "RV32I" means.
- The 32 registers, the program counter, and how memory is addressed.
- The six RV32I instruction formats (R, I, S, B, U, J) and why their bit fields are laid out
  the way they are.
- How to decode a 32-bit instruction by hand, one example per format, using words the
  repo's own tests check.
- Which instructions this project supports, and which it leaves out.

---

## 1. A worked example first

The number `0x002081B3` is an instruction. Written in binary and split at the right places:

```
0000000 00010 00001 000 00011 0110011
funct7   rs2   rs1  f3   rd   opcode
```

Each field, from the right:
- `opcode = 0110011` means "register-register arithmetic".
- `funct3 = 000` and `funct7 = 0000000` together mean "add".
- `rs1 = 1` and `rs2 = 2` are the source registers; `rd = 3` is the destination.

So the instruction is `add x3, x1, x2`: x3 = x1 + x2.

That is all decoding is: cutting 32 bits into fixed fields and looking the fields up in a
table. This repository does it twice:
- in hardware, `rtl/decoder.sv:14-25`;
- in Python, `model/decoder.py:50-100`.

The encoder test checks this exact word (`tests/model/test_encoder.py:17`).

## 2. What an ISA is

An **instruction set architecture (ISA)** is the contract between software and a CPU. It
lists:
- the instructions;
- their binary encodings;
- what each one does to the registers and memory.

It says nothing about *how* the CPU is built. That's why a single-cycle core and a
5-stage pipeline can both be correct RV32I CPUs: the ISA fixes the behaviour, not the
hardware.

**RISC-V** is an open ISA: anyone can implement it without a licence. It is modular: a
small mandatory base plus optional **extensions**. The name **RV32I** reads as:

| Part | Meaning |
|---|---|
| RV | RISC-V |
| 32 | registers and addresses are 32 bits wide (**XLEN** = 32) |
| I | the base **I**nteger instruction set, the minimum every RISC-V CPU must have |

Extensions this project does **not** implement (`ROADMAP.md`, "Scope and non-goals"):
- **M** (multiply/divide). This is why the C programs avoid `*`, `/` and `%`
  (`programs/fibonacci.c:2`).
- **C** (compressed 16-bit instructions).
- **Zicsr** (control and status registers, needed for interrupts and exceptions).
- **Zifencei** (`FENCE.I`).

## 3. Registers and the program counter

A **register** is a small storage slot inside the CPU, the fastest place to keep a value.
RV32I has 32 general-purpose registers, `x0` to `x31`, each 32 bits wide.

- **`x0` always reads as zero.** Writes to it are discarded. This sounds wasteful, but it
  makes many operations free:
  - `addi x5, x0, 7` means "x5 = 7";
  - `add x0, x0, x0` is a do-nothing instruction (**NOP**).

  The RTL implements this in `rtl/regfile.sv:23` (writes to x0 ignored) and
  `rtl/regfile.sv:28-29` (reads of x0 return 0). The model does it in `model/iss.py:103,167`.
- **Software gives registers nicknames**, from the **ABI** (application binary interface,
  the calling convention compilers follow). Four of them appear in this repo:

  | Register | ABI name | Used here for |
  |---|---|---|
  | x1 | `ra` | return address of a function call |
  | x2 | `sp` | stack pointer; `crt0.S` sets it to 0x4000 (`programs/crt0.S:6`) |
  | x3 | `gp` | in riscv-tests: pass/fail result, 1 = pass (`programs/riscv-test-env/riscv_test.h:13`) |
  | x10 | `a0` | first argument and return value; C programs return their result here |

  The hardware treats all of x1–x31 the same. The names are only a software agreement.

The **program counter (pc)** is a separate register holding the address of the current
instruction. Normally it advances by 4 (one instruction is 4 bytes). Jumps and taken
branches set it to something else.

## 4. Memory

Memory is an array of **bytes**, each with a 32-bit address.

- **Words, halfwords, bytes.** A word is 4 bytes, a halfword is 2.
- **Little-endian.** The lowest-addressed byte holds the least significant bits. If
  memory at 0x2000 holds the word `0x80818283`, then:

  | Address | 0x2000 | 0x2001 | 0x2002 | 0x2003 |
  |---|---|---|---|---|
  | Byte | 0x83 | 0x82 | 0x81 | 0x80 |

  `lb` (load byte) from 0x2003 gives 0x80. That's how the directed test `load_lb` expects
  it (`tests/rtl/test_core_directed.py:154-157`).
- **Alignment.** A word access must be at an address divisible by 4; a halfword at an even
  address. The RISC-V spec allows misaligned access, but this project leaves it out:
  - the model raises `MisalignedAccess` (`model/iss.py:141-142,150-151`);
  - the testbench flags it as a fault (`tb/tb_top.sv:74-82`).
- **Load/store architecture.** Arithmetic only works on registers. Memory is touched only
  by **loads** (memory → register) and **stores** (register → memory).

In this project:
- code lives at 0x0000–0x1FFF;
- data lives at 0x2000–0x3FFF;
- the C programs' stack starts at 0x4000 and grows down (`programs/link.ld:1-5`).

## 5. The six instruction formats

Every RV32I instruction is 32 bits. The **format** decides how those bits are split into
fields. Every format agrees on a few things:

- `opcode` is **always bits [6:0]**. It picks the instruction class.
- `rd`, the destination register, is **always bits [11:7]** when it exists.
- `rs1` is **always [19:15]** and `rs2` **always [24:20]** when they exist.
- `funct3` is **always [14:12]**, and `funct7` is [31:25]. They pick the exact operation
  within a class.
- The **immediate**, a constant encoded inside the instruction, has its sign bit
  **always at bit 31**.

Keeping these positions fixed is a hardware decision. The CPU can read the registers
*before* it knows which instruction it has, because the register numbers are always in the
same place. `rtl/decoder.sv:34-36` takes `rd`, `rs1` and `rs2` straight from the bits for
every instruction.

Bits are numbered 31 (left) to 0 (right):

```
        31        25 24    20 19    15 14  12 11       7 6      0
R-type  |  funct7   |  rs2   |  rs1   |funct3|    rd    | opcode |   add x3, x1, x2
I-type  |     imm[11:0]      |  rs1   |funct3|    rd    | opcode |   addi, lw, jalr
S-type  | imm[11:5] |  rs2   |  rs1   |funct3| imm[4:0] | opcode |   sw, sb, sh
B-type  |i[12|10:5] |  rs2   |  rs1   |funct3|i[4:1|11] | opcode |   beq, bne, ...
U-type  |            imm[31:12]                |    rd    | opcode |   lui, auipc
J-type  |    imm[20|10:1|11|19:12]             |    rd    | opcode |   jal
```

### Why S, B and J immediates look scrambled

They are scrambled so the other fields never move:
- In S-type, the immediate's low 5 bits sit where `rd` would be, because a store has no
  destination register.
- B-type is S-type with the bits shuffled once more: branch offsets are always even, so
  bit 0 is not stored, and bit 11 moves into the free slot.
- J-type does the same thing on top of U-type.

The payoff is in hardware: every immediate bit comes from a small, fixed set of positions,
so each bit of the immediate is just a small mux. The decoder rebuilds the five immediates
in five lines (`rtl/decoder.sv:21-25`):

```systemverilog
assign imm_i = {{20{insn[31]}}, insn[31:20]};
assign imm_s = {{20{insn[31]}}, insn[31:25], insn[11:7]};
assign imm_b = {{19{insn[31]}}, insn[31], insn[7], insn[30:25], insn[11:8], 1'b0};
assign imm_u = {insn[31:12], 12'b0};
assign imm_j = {{11{insn[31]}}, insn[31], insn[19:12], insn[20], insn[30:21], 1'b0};
```

`{20{insn[31]}}` means "20 copies of bit 31". That is **sign extension**: a negative 12-bit
number like -4 (`0xFFC`) becomes the 32-bit -4 (`0xFFFFFFFC`). Chapter 03 explains
the syntax.

### The opcodes this project uses

From `rtl/rv32i_pkg.sv:7-17` (the same values as `model/isa.py:44-55`):

| Opcode (bits 6:0) | Name | Format | Instructions |
|---|---|---|---|
| `0110111` | LUI | U | `lui` |
| `0010111` | AUIPC | U | `auipc` |
| `1101111` | JAL | J | `jal` |
| `1100111` | JALR | I | `jalr` |
| `1100011` | BRANCH | B | `beq bne blt bge bltu bgeu` |
| `0000011` | LOAD | I | `lb lh lw lbu lhu` |
| `0100011` | STORE | S | `sb sh sw` |
| `0010011` | OP-IMM | I | `addi slti sltiu xori ori andi slli srli srai` |
| `0110011` | OP | R | `add sub sll slt sltu xor srl sra or and` |
| `0001111` | MISC-MEM | — | `fence` |
| `1110011` | SYSTEM | — | `ecall ebreak` |

That gives 37 instructions plus `fence`, `ecall` and `ebreak`: the 40 entries of `SPECS`
in `model/isa.py:67-114`.

## 6. What the instructions do

| Group | Instructions | Effect |
|---|---|---|
| Register-register ALU | `add sub sll slt sltu xor srl sra or and` | rd = rs1 op rs2 |
| Immediate ALU | `addi slti sltiu xori ori andi slli srli srai` | rd = rs1 op imm (no `subi`: use `addi` with a negative immediate) |
| Upper immediate | `lui`, `auipc` | `lui`: rd = imm << 12. `auipc`: rd = pc + (imm << 12) |
| Loads | `lb lh lw lbu lhu` | rd = memory[rs1 + imm]; `b/h` sign-extend, `bu/hu` zero-extend |
| Stores | `sb sh sw` | memory[rs1 + imm] = low 1/2/4 bytes of rs2 |
| Branches | `beq bne blt bge bltu bgeu` | if (rs1 cmp rs2) pc = pc + imm; `u` = unsigned compare |
| Jumps | `jal`, `jalr` | rd = pc + 4 (the return address). `jal`: pc = pc + imm. `jalr`: pc = (rs1 + imm) with bit 0 cleared |
| System | `fence`, `ecall`, `ebreak` | Here: `fence` does nothing, `ecall`/`ebreak` halt the core |

**Details that tests check on purpose:**
- **Shifts use only the low 5 bits** of the shift amount. `sll` by 35 shifts by 3
  (`tests/model/test_iss.py:36`; `rtl/alu.sv:11-13`).
- **`slt` compares as signed, `sltu` as unsigned.** 0xFFFFFFFF is -1 to `slt` but the
  largest number to `sltu` (`tests/model/test_iss.py:37-38`).
- **`sra` copies the sign bit in from the left; `srl` shifts in zeros**
  (`tests/model/test_alu_model.py:27-30`).
- **`jalr` clears bit 0 of its target** (`model/iss.py:134`; `rtl/core_single.sv:111`).
- **Overflow wraps silently.** There are no overflow exceptions in RV32I
  (`tests/model/test_alu_model.py:13`).

### The `li` pseudo-instruction

There is no instruction that loads an arbitrary 32-bit constant: an immediate has at most
20 bits. Assemblers provide `li rd, value`, a **pseudo-instruction**: one line of assembly
that expands to `lui` + `addi`.

Take `0x12345678`: `lui x1, 0x12345` sets x1 = 0x12345000, then `addi x1, x1, 0x678`
adds the rest (`tests/model/test_iss.py:85-88`).

There is one trap. `addi` *sign-extends* its 12-bit immediate. If bit 11 of the low part
is 1, the low part acts as a negative number, so the upper part must be rounded up by
one. `model/encoder.py:103-117` handles exactly this, and `tests/model/test_iss.py:256-265`
tests the edge cases (0x800, 0xFFFFF800, …).

## 7. Hand-decoding one instruction of each format

Every word below is in the encoder's known-answer list (`tests/model/test_encoder.py:14-27`).
That test asserts both directions, encode and decode, so these decodings are checked by
`make test`.

### R-type: `0x002081B3`

Done in section 1: `add x3, x1, x2`.

### I-type: `0xFFC12203`

```
111111111100 00010 010 00100 0000011
 imm[11:0]    rs1  f3   rd   opcode
```

1. `opcode = 0000011` is a LOAD.
2. `funct3 = 010` means a word load, `lw` (`rtl/rv32i_pkg.sv:32`).
3. `rd = 00100` is x4, and `rs1 = 00010` is x2.
4. The immediate `111111111100` has its top bit set, so it is negative: 0xFFC - 0x1000 = **-4**.

Result: **`lw x4, -4(x2)`**, meaning x4 = memory word at (x2 - 4).

### S-type: `0x0020A423`

```
0000000 00010 00001 010 01000 0100011
imm[11:5] rs2  rs1  f3 imm[4:0] opcode
```

1. `opcode = 0100011` is a STORE, and `funct3 = 010` means `sw`.
2. `rs1 = x1` is the base address and `rs2 = x2` is the data to store.
3. The immediate is `0000000` ++ `01000` = 8.

Result: **`sw x2, 8(x1)`**, meaning memory word at (x1 + 8) = x2. Notice the immediate's
low bits sit in the slot `rd` uses in other formats.

### B-type: `0xFE208EE3`

```
1 111111 00010 00001 000 1110 1 1100011
12 10:5   rs2   rs1  f3  4:1 11  opcode
```

1. `opcode = 1100011` is a BRANCH, and `funct3 = 000` means `beq`.
2. The registers are `rs1 = x1` and `rs2 = x2`.
3. Reassemble the immediate in order, bit 12 down to bit 1, and append a 0 for bit 0:

   | imm bit | 12 | 11 | 10:5 | 4:1 | 0 |
   |---|---|---|---|---|---|
   | value | 1 | 1 | 111111 | 1110 | 0 (implicit) |

   That is `1111111111100` (13 bits). The top bit is 1, so it's negative: **-4**.

Result: **`beq x1, x2, -4`**: if x1 == x2, jump back one instruction. The code's
version is `rtl/decoder.sv:23` and `model/decoder.py:83-90`.

### U-type: `0x123452B7`

```
00010010001101000101 00101 0110111
     imm[31:12]        rd   opcode
```

1. `opcode = 0110111` is LUI.
2. `rd = x5`.
3. The upper immediate is `0x12345`.

Result: **`lui x5, 0x12345`**, so x5 = 0x12345000. The low 12 bits are zero
(`rtl/decoder.sv:24`).

### J-type: `0x008000EF`

```
0 0000000100 0 00000000 00001 1101111
20  10:1     11  19:12    rd   opcode
```

1. `opcode = 1101111` is JAL, and `rd = x1`.
2. The immediate: bit 20 = 0, bits 10:1 = `0000000100` (= 4), bit 11 = 0, bits 19:12 = 0.
   Shift left once for the implicit bit 0: 4 × 2 = **8**.

Result: **`jal x1, 8`**: x1 = pc + 4, then pc = pc + 8.

## 8. ECALL and EBREAK in this project

On a real system, `ecall` asks an operating system for a service and `ebreak` hands control
to a debugger. Here there is no operating system. Both are treated as **"the program is
finished"**:
- the RTL decoder sets `halt` for them (`rtl/decoder.sv:121-124`);
- the model sets `halt = True` (`model/iss.py:159-161`).

Every test program ends with `ecall`.

Anything else in the SYSTEM opcode is a CSR instruction, which the core doesn't support.
The decoder flags it as **illegal**, and the core stops with `rvfi_trap` set. One directed
test checks that path on purpose (`tests/rtl/test_core_directed.py:206-213`).

## Known gaps

- `ROADMAP.md` counts "37 instructions" while `model/isa.py` has 40 entries. Both are
  right: 37 plus `fence`, `ecall` and `ebreak`. The coverage report counts the 40 `SPECS`
  entries as 40 opcode bins (`tb/coverage.py:43`).
- `ecall`/`ebreak` halting the core is a project convention, not RISC-V behaviour. A real
  core would raise an exception and jump to a trap handler. Here, without CSRs, there is
  nowhere to jump to.

## Check yourself

1. Why does RISC-V put `rs1`, `rs2` and `rd` in the same bit positions in every format?
2. Decode `0x00100093` by hand.
3. What value does `lb` return from address 0x2000 if the word there is `0x80818283`? And `lbu`?
4. Why can't a single `addi` load the constant `0x12345678`, and why is `li` of `0x00000800` two instructions?
5. Why do B-type and J-type immediates not store bit 0?

<details>
<summary>Answers</summary>

1. So the hardware can read the register file before decoding is finished. The register
   numbers are always at the same bits (`rtl/decoder.sv:34-36`).
2. Here are the fields:
   - opcode `0010011` is OP-IMM;
   - funct3 `000` is `addi`;
   - rd = 1, rs1 = 0;
   - imm = 1.

   So it's `addi x1, x0, 1`. It's the first entry of `tests/model/test_encoder.py:15`.
3. Byte 0 is `0x83`. `lb` sign-extends it to `0xFFFFFF83`; `lbu` zero-extends it to `0x83`
   (`tests/model/test_iss.py:166,168`).
4. `addi` holds only a 12-bit signed immediate (-2048 to 2047). For `0x800`, the low 12 bits
   on their own would mean -2048, so `li` uses `lui 1` (giving 0x1000) plus `addi -2048`
   (`model/encoder.py:109-117`).
5. Instructions are always at even addresses (multiples of 4 in RV32I without C). So bit 0
   of an offset is always 0, and storing it would waste a bit.

</details>
