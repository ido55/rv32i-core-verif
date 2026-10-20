// Instruction decoder: turns one 32-bit instruction into the control struct ctrl_t.
// Purely combinational, so the single-cycle and pipelined cores can both use it.
module decoder
  import rv32i_pkg::*;
(
  input  logic [31:0] insn,
  output ctrl_t       ctrl
);

  logic [6:0] opcode;
  logic [2:0] funct3;
  logic [6:0] funct7;

  assign opcode = insn[6:0];
  assign funct3 = insn[14:12];
  assign funct7 = insn[31:25];

  // Immediates for each format (RISC-V spec, Figure 2.4). insn[31] is always the sign bit.
  logic [31:0] imm_i, imm_s, imm_b, imm_u, imm_j;

  assign imm_i = {{20{insn[31]}}, insn[31:20]};
  assign imm_s = {{20{insn[31]}}, insn[31:25], insn[11:7]};
  assign imm_b = {{19{insn[31]}}, insn[31], insn[7], insn[30:25], insn[11:8], 1'b0};
  assign imm_u = {insn[31:12], 12'b0};
  assign imm_j = {{11{insn[31]}}, insn[31], insn[19:12], insn[20], insn[30:21], 1'b0};

  // funct7 must be 0000000, or 0100000 for SUB / SRA / SRAI.
  logic funct7_ok;
  assign funct7_ok = (funct7 == 7'b0000000) || (funct7 == 7'b0100000);

  always_comb begin
    // Defaults: an instruction that does nothing. Each case turns on what it needs.
    ctrl           = '0;
    ctrl.rd        = insn[11:7];
    ctrl.rs1       = insn[19:15];
    ctrl.rs2       = insn[24:20];
    ctrl.funct3    = funct3;
    ctrl.alu_op    = ALU_ADD;
    ctrl.alu_a_sel = ALU_A_RS1;
    ctrl.wb_sel    = WB_ALU;

    unique case (opcode)
      OPC_LUI: begin
        ctrl.reg_write = 1'b1;
        ctrl.alu_a_sel = ALU_A_ZERO;
        ctrl.alu_b_imm = 1'b1;
        ctrl.imm       = imm_u;
      end

      OPC_AUIPC: begin
        ctrl.reg_write = 1'b1;
        ctrl.alu_a_sel = ALU_A_PC;
        ctrl.alu_b_imm = 1'b1;
        ctrl.imm       = imm_u;
      end

      OPC_JAL: begin
        ctrl.reg_write = 1'b1;
        ctrl.wb_sel    = WB_PC4;
        ctrl.is_jal    = 1'b1;
        ctrl.imm       = imm_j;
      end

      OPC_JALR: begin
        ctrl.reg_write = 1'b1;
        ctrl.wb_sel    = WB_PC4;
        ctrl.is_jalr   = 1'b1;
        ctrl.alu_b_imm = 1'b1;  // target = rs1 + imm, computed by the ALU
        ctrl.imm       = imm_i;
        ctrl.illegal   = (funct3 != 3'b000);
      end

      OPC_BRANCH: begin
        ctrl.is_branch = 1'b1;
        ctrl.imm       = imm_b;
        ctrl.illegal   = (funct3 == 3'b010) || (funct3 == 3'b011);
      end

      OPC_LOAD: begin
        ctrl.reg_write = 1'b1;
        ctrl.wb_sel    = WB_MEM;
        ctrl.mem_read  = 1'b1;
        ctrl.alu_b_imm = 1'b1;  // address = rs1 + imm
        ctrl.imm       = imm_i;
        ctrl.illegal   = !(funct3 inside {F3_B, F3_H, F3_W, F3_BU, F3_HU});
      end

      OPC_STORE: begin
        ctrl.mem_write = 1'b1;
        ctrl.alu_b_imm = 1'b1;
        ctrl.imm       = imm_s;
        ctrl.illegal   = !(funct3 inside {F3_B, F3_H, F3_W});
      end

      OPC_OP_IMM: begin
        ctrl.reg_write = 1'b1;
        ctrl.alu_b_imm = 1'b1;
        ctrl.imm       = imm_i;
        if (funct3 == 3'b001) begin            // SLLI: imm[11:5] must be 0
          ctrl.alu_op  = ALU_SLL;
          ctrl.illegal = (funct7 != 7'b0000000);
        end else if (funct3 == 3'b101) begin   // SRLI / SRAI: imm[10] selects arithmetic
          ctrl.alu_op  = alu_op_e'({funct7[5], funct3});
          ctrl.illegal = !funct7_ok;
        end else begin                         // ADDI, SLTI, ... have no funct7 field
          ctrl.alu_op  = alu_op_e'({1'b0, funct3});
        end
      end

      OPC_OP: begin
        ctrl.reg_write = 1'b1;
        ctrl.alu_op    = alu_op_e'({funct7[5], funct3});
        // funct7 = 0100000 is only valid for SUB (000) and SRA (101).
        ctrl.illegal   = !funct7_ok || (funct7[5] && funct3 != 3'b000 && funct3 != 3'b101);
      end

      OPC_MISC_MEM: begin
        ctrl.illegal = (funct3 != 3'b000);  // FENCE is a no-op here; FENCE.I unsupported
      end

      OPC_SYSTEM: begin
        ctrl.halt    = (insn == INSN_ECALL) || (insn == INSN_EBREAK);
        ctrl.illegal = !ctrl.halt;          // CSR instructions are not supported
      end

      default: ctrl.illegal = 1'b1;
    endcase

    // Which source registers are really read. In LUI/AUIPC/JAL those bits are part of
    // the immediate; a pipeline must not treat them as a dependency.
    ctrl.uses_rs1 = opcode inside {OPC_JALR, OPC_BRANCH, OPC_LOAD, OPC_STORE, OPC_OP_IMM, OPC_OP};
    ctrl.uses_rs2 = opcode inside {OPC_BRANCH, OPC_STORE, OPC_OP};

    // An illegal instruction must not change any state.
    if (ctrl.illegal) begin
      ctrl.uses_rs1  = 1'b0;
      ctrl.uses_rs2  = 1'b0;
      ctrl.reg_write = 1'b0;
      ctrl.mem_read  = 1'b0;
      ctrl.mem_write = 1'b0;
      ctrl.is_branch = 1'b0;
      ctrl.is_jal    = 1'b0;
      ctrl.is_jalr   = 1'b0;
    end
  end

endmodule
