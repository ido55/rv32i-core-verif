// Shared types and constants for the RV32I cores.
// Not every module uses every constant, so UNUSEDPARAM is waived for this package only.
/* verilator lint_off UNUSEDPARAM */
package rv32i_pkg;

  // ---- Opcodes (insn[6:0]) ---------------------------------------------------------
  localparam logic [6:0] OPC_LUI      = 7'b0110111;
  localparam logic [6:0] OPC_AUIPC    = 7'b0010111;
  localparam logic [6:0] OPC_JAL      = 7'b1101111;
  localparam logic [6:0] OPC_JALR     = 7'b1100111;
  localparam logic [6:0] OPC_BRANCH   = 7'b1100011;
  localparam logic [6:0] OPC_LOAD     = 7'b0000011;
  localparam logic [6:0] OPC_STORE    = 7'b0100011;
  localparam logic [6:0] OPC_OP_IMM   = 7'b0010011;
  localparam logic [6:0] OPC_OP       = 7'b0110011;
  localparam logic [6:0] OPC_MISC_MEM = 7'b0001111;
  localparam logic [6:0] OPC_SYSTEM   = 7'b1110011;

  localparam logic [31:0] INSN_ECALL  = 32'h0000_0073;
  localparam logic [31:0] INSN_EBREAK = 32'h0010_0073;

  // ---- funct3 values for branches and loads/stores ------------------------------------
  localparam logic [2:0] F3_BEQ  = 3'b000;
  localparam logic [2:0] F3_BNE  = 3'b001;
  localparam logic [2:0] F3_BLT  = 3'b100;
  localparam logic [2:0] F3_BGE  = 3'b101;
  localparam logic [2:0] F3_BLTU = 3'b110;
  localparam logic [2:0] F3_BGEU = 3'b111;

  localparam logic [2:0] F3_B  = 3'b000;  // LB / SB
  localparam logic [2:0] F3_H  = 3'b001;  // LH / SH
  localparam logic [2:0] F3_W  = 3'b010;  // LW / SW
  localparam logic [2:0] F3_BU = 3'b100;  // LBU
  localparam logic [2:0] F3_HU = 3'b101;  // LHU

  // ALU operation = {funct7[5], funct3}, so the decoder can build it straight
  // from the instruction bits. Must match model/alu.py (AluOp).
  typedef enum logic [3:0] {
    ALU_ADD  = 4'b0000,
    ALU_SLL  = 4'b0001,
    ALU_SLT  = 4'b0010,
    ALU_SLTU = 4'b0011,
    ALU_XOR  = 4'b0100,
    ALU_SRL  = 4'b0101,
    ALU_OR   = 4'b0110,
    ALU_AND  = 4'b0111,
    ALU_SUB  = 4'b1000,
    ALU_SRA  = 4'b1101
  } alu_op_e;

  // First ALU operand. LUI uses zero (0 + imm), AUIPC uses the pc.
  typedef enum logic [1:0] {
    ALU_A_RS1  = 2'd0,
    ALU_A_PC   = 2'd1,
    ALU_A_ZERO = 2'd2
  } alu_a_sel_e;

  // What gets written to rd.
  typedef enum logic [1:0] {
    WB_ALU = 2'd0,  // ALU result
    WB_MEM = 2'd1,  // load data
    WB_PC4 = 2'd2   // return address for JAL/JALR
  } wb_sel_e;

  // Everything the datapath needs to know about one instruction, produced by decoder.sv.
  typedef struct packed {
    logic [4:0]  rd;
    logic [4:0]  rs1;
    logic [4:0]  rs2;
    logic        uses_rs1;   // the instruction really reads rs1 (for hazard detection)
    logic        uses_rs2;   // the instruction really reads rs2
    logic [2:0]  funct3;     // branch condition / load-store width
    logic [31:0] imm;        // already sign-extended and shifted for its format
    alu_op_e     alu_op;
    alu_a_sel_e  alu_a_sel;
    logic        alu_b_imm;  // 1: second ALU operand is imm, 0: rs2
    logic        reg_write;
    wb_sel_e     wb_sel;
    logic        mem_read;
    logic        mem_write;
    logic        is_branch;
    logic        is_jal;
    logic        is_jalr;
    logic        halt;       // ECALL / EBREAK
    logic        illegal;    // not a supported RV32I instruction
  } ctrl_t;

endpackage
/* verilator lint_on UNUSEDPARAM */
