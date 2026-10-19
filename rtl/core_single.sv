// Single-cycle RV32I core: every instruction is fetched, executed and written back in
// one clock cycle (CPI = 1). Instruction and data memories are outside the core and
// read combinationally; data memory is written on the rising edge.
//
// The retire port (rvfi_*) describes the instruction completing in the current cycle,
// using the same fields and conventions as model/iss.py:Retire.
module core_single
  import rv32i_pkg::*;
(
  input  logic        clk,
  input  logic        rst_n,          // synchronous, active-low

  // Instruction memory
  output logic [31:0] imem_addr,
  input  logic [31:0] imem_rdata,

  // Data memory (word address + byte enables)
  output logic [31:0] dmem_addr,      // word-aligned
  output logic        dmem_re,        // load this cycle
  input  logic [31:0] dmem_rdata,
  output logic [3:0]  dmem_wmask,     // non-zero = write these bytes
  output logic [31:0] dmem_wdata,

  output logic        halted,         // set after ECALL/EBREAK or an illegal instruction

  // Retire port
  output logic        rvfi_valid,
  output logic [31:0] rvfi_pc,
  output logic [31:0] rvfi_insn,
  output logic [31:0] rvfi_next_pc,
  output logic [4:0]  rvfi_rd,        // 0 if no register is written
  output logic [31:0] rvfi_rd_wdata,  // 0 if no register is written
  output logic [31:0] rvfi_mem_addr,  // loads and stores (word-aligned), else 0
  output logic [3:0]  rvfi_mem_rmask, // loads only, else 0
  output logic [31:0] rvfi_mem_wdata, // stores only, else 0
  output logic [3:0]  rvfi_mem_wmask, // stores only, else 0
  output logic        rvfi_halt,
  output logic        rvfi_trap       // illegal instruction
);

  logic [31:0] pc_q;
  logic        halted_q;
  logic        active;  // executing an instruction this cycle

  ctrl_t       ctrl;
  logic [31:0] rs1_data, rs2_data;
  logic [31:0] alu_a, alu_b, alu_y;
  logic        branch_taken;
  logic [31:0] pc_plus4, pc_target, pc_next;
  logic [3:0]  byte_mask;
  logic [31:0] load_data, rd_wdata;

  assign active = rst_n && !halted_q;

  // ---- Fetch and decode -------------------------------------------------------------
  assign imem_addr = pc_q;

  decoder u_decoder (
    .insn (imem_rdata),
    .ctrl (ctrl)
  );

  regfile u_regfile (
    .clk      (clk),
    .rst_n    (rst_n),
    .rs1_addr (ctrl.rs1),
    .rs1_data (rs1_data),
    .rs2_addr (ctrl.rs2),
    .rs2_data (rs2_data),
    .we       (active && ctrl.reg_write),
    .rd_addr  (ctrl.rd),
    .rd_data  (rd_wdata)
  );

  // ---- Execute -----------------------------------------------------------------------
  always_comb begin
    unique case (ctrl.alu_a_sel)
      ALU_A_PC:   alu_a = pc_q;
      ALU_A_ZERO: alu_a = 32'b0;
      default:    alu_a = rs1_data;
    endcase
  end

  assign alu_b = ctrl.alu_b_imm ? ctrl.imm : rs2_data;

  alu u_alu (
    .op (ctrl.alu_op),
    .a  (alu_a),
    .b  (alu_b),
    .y  (alu_y)
  );

  branch_unit u_branch (
    .funct3 (ctrl.funct3),
    .a      (rs1_data),
    .b      (rs2_data),
    .taken  (branch_taken)
  );

  // ---- Next pc -----------------------------------------------------------------------
  assign pc_plus4  = pc_q + 32'd4;
  assign pc_target = pc_q + ctrl.imm;  // JAL and branch target

  always_comb begin
    if (ctrl.halt || ctrl.illegal)                   pc_next = pc_q;  // stop here
    else if (ctrl.is_jal)                            pc_next = pc_target;
    else if (ctrl.is_jalr)                           pc_next = {alu_y[31:1], 1'b0};
    else if (ctrl.is_branch && branch_taken)         pc_next = pc_target;
    else                                             pc_next = pc_plus4;
  end

  // ---- Memory ------------------------------------------------------------------------
  lsu u_lsu (
    .funct3      (ctrl.funct3),
    .byte_offset (alu_y[1:0]),
    .store_data  (rs2_data),
    .mem_rdata   (dmem_rdata),
    .byte_mask   (byte_mask),
    .store_wdata (dmem_wdata),
    .load_data   (load_data)
  );

  assign dmem_addr  = {alu_y[31:2], 2'b00};
  assign dmem_re    = active && ctrl.mem_read;
  assign dmem_wmask = (active && ctrl.mem_write) ? byte_mask : 4'b0000;

  // ---- Write back --------------------------------------------------------------------
  always_comb begin
    unique case (ctrl.wb_sel)
      WB_MEM:  rd_wdata = load_data;
      WB_PC4:  rd_wdata = pc_plus4;
      default: rd_wdata = alu_y;
    endcase
  end

  // ---- State -------------------------------------------------------------------------
  always_ff @(posedge clk) begin
    if (!rst_n) begin
      pc_q     <= 32'b0;
      halted_q <= 1'b0;
    end else if (active) begin
      pc_q <= pc_next;
      if (ctrl.halt || ctrl.illegal) halted_q <= 1'b1;
    end
  end

  assign halted = halted_q;

  // ---- Retire port -------------------------------------------------------------------
  logic writes_rd;
  assign writes_rd = ctrl.reg_write && (ctrl.rd != 5'd0);

  assign rvfi_valid     = active;
  assign rvfi_pc        = pc_q;
  assign rvfi_insn      = imem_rdata;
  assign rvfi_next_pc   = pc_next;
  assign rvfi_rd        = writes_rd ? ctrl.rd : 5'd0;
  assign rvfi_rd_wdata  = writes_rd ? rd_wdata : 32'b0;
  assign rvfi_mem_addr  = (ctrl.mem_read || ctrl.mem_write) ? dmem_addr : 32'b0;
  assign rvfi_mem_rmask = ctrl.mem_read  ? byte_mask  : 4'b0000;
  assign rvfi_mem_wdata = ctrl.mem_write ? dmem_wdata : 32'b0;
  assign rvfi_mem_wmask = ctrl.mem_write ? byte_mask  : 4'b0000;
  assign rvfi_halt      = ctrl.halt;
  assign rvfi_trap      = ctrl.illegal;

endmodule
