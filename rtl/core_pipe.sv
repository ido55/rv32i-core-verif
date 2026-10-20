// 5-stage pipelined RV32I core: IF -> ID -> EX -> MEM -> WB.
// Same ports and retire-port conventions as core_single, so the same testbench runs on both.
//
// Hazards:
//   - Data, ALU result needed by the next 1-2 instructions: forwarded into EX from the
//     EX/MEM or MEM/WB pipeline register (EX/MEM wins: it holds the newer value).
//   - Data, value being written back while ID reads it: bypassed inside ID (write-before-read).
//   - Load-use, load result needed by the very next instruction: the data only exists at
//     the end of MEM, so ID is stalled for one cycle and a bubble goes into EX; the value
//     then arrives through MEM/WB forwarding.
//   - Control, branches and jumps are resolved in EX. The pipeline always fetches pc + 4
//     (predict not taken); a taken branch or jump flushes the 2 younger instructions.
//   - ECALL / EBREAK / illegal in EX also flush the younger instructions and stop fetch,
//     so nothing after the halting instruction can write memory or registers.
module core_pipe
  import rv32i_pkg::*;
(
  input  logic        clk,
  input  logic        rst_n,          // synchronous, active-low

  output logic [31:0] imem_addr,
  input  logic [31:0] imem_rdata,

  output logic [31:0] dmem_addr,      // word-aligned
  input  logic [31:0] dmem_rdata,
  output logic [3:0]  dmem_wmask,
  output logic [31:0] dmem_wdata,

  output logic        halted,

  output logic        rvfi_valid,
  output logic [31:0] rvfi_pc,
  output logic [31:0] rvfi_insn,
  output logic [31:0] rvfi_next_pc,
  output logic [4:0]  rvfi_rd,
  output logic [31:0] rvfi_rd_wdata,
  output logic [31:0] rvfi_mem_addr,
  output logic [3:0]  rvfi_mem_rmask,
  output logic [31:0] rvfi_mem_wdata,
  output logic [3:0]  rvfi_mem_wmask,
  output logic        rvfi_halt,
  output logic        rvfi_trap
);

  // ---- Pipeline registers ------------------------------------------------------------
  // valid = 0 is a bubble: it changes no state and does not retire.

  typedef struct packed {
    logic        valid;
    logic [31:0] pc;
    logic [31:0] insn;
  } if_id_t;

  typedef struct packed {
    logic        valid;
    logic [31:0] pc;
    logic [31:0] insn;
    ctrl_t       ctrl;
    logic [31:0] rs1_val;      // register values read in ID (may be overridden by forwarding)
    logic [31:0] rs2_val;
  } id_ex_t;

  typedef struct packed {
    logic        valid;
    logic [31:0] pc;
    logic [31:0] insn;
    logic [31:0] next_pc;
    logic [4:0]  rd;
    logic        reg_write;
    logic        mem_read;
    logic        mem_write;
    logic [2:0]  funct3;
    logic [31:0] result;       // ALU result, or pc + 4 for JAL/JALR; for loads/stores the address
    logic [31:0] store_data;   // rs2 after forwarding
    logic        halt;
    logic        illegal;
  } ex_mem_t;

  typedef struct packed {
    logic        valid;
    logic [31:0] pc;
    logic [31:0] insn;
    logic [31:0] next_pc;
    logic [4:0]  rd;
    logic        reg_write;
    logic [31:0] wb_data;      // value written to rd
    logic [31:0] mem_addr;     // the rest is only for the retire port
    logic [3:0]  mem_rmask;
    logic [31:0] mem_wdata;
    logic [3:0]  mem_wmask;
    logic        halt;
    logic        illegal;
  } mem_wb_t;

  logic [31:0] pc_q;
  if_id_t      if_id_q;
  id_ex_t      id_ex_q,  id_ex_d;
  ex_mem_t     ex_mem_q, ex_mem_d;
  mem_wb_t     mem_wb_q, mem_wb_d;
  logic        fetch_stopped_q;  // a halting instruction reached EX: fetch nothing more
  logic        halted_q;

  ctrl_t       ex_ctrl;          // control of the instruction in EX (used by ID's hazard check too)
  assign ex_ctrl = id_ex_q.ctrl;

  // Hazard control, computed below.
  logic        stall_load_use;   // hold IF and ID, insert a bubble into EX
  logic        flush;            // squash the instructions in IF and ID
  logic        ex_redirect;      // taken branch / jump in EX: fetch from ex_redirect_pc
  logic [31:0] ex_redirect_pc;

  // ---- IF ----------------------------------------------------------------------------
  assign imem_addr = pc_q;

  // ---- ID: decode, read registers, detect load-use -------------------------------------
  ctrl_t       id_ctrl;
  logic [31:0] rf_rs1_data, rf_rs2_data;
  logic        wb_we;
  logic        wb_bypass_rs1, wb_bypass_rs2;

  decoder u_decoder (
    .insn (if_id_q.insn),
    .ctrl (id_ctrl)
  );

  assign wb_we = mem_wb_q.valid && mem_wb_q.reg_write;

  regfile u_regfile (
    .clk      (clk),
    .rst_n    (rst_n),
    .rs1_addr (id_ctrl.rs1),
    .rs1_data (rf_rs1_data),
    .rs2_addr (id_ctrl.rs2),
    .rs2_data (rf_rs2_data),
    .we       (wb_we),
    .rd_addr  (mem_wb_q.rd),
    .rd_data  (mem_wb_q.wb_data)
  );

  // Write-before-read: the register file is written at the END of this cycle, so a value
  // being written back right now is taken from WB directly.
  assign wb_bypass_rs1 = wb_we && (mem_wb_q.rd != 5'd0) && (mem_wb_q.rd == id_ctrl.rs1);
  assign wb_bypass_rs2 = wb_we && (mem_wb_q.rd != 5'd0) && (mem_wb_q.rd == id_ctrl.rs2);

  // Load-use: the instruction in EX is a load whose result the instruction in ID needs.
  logic ex_is_load_to_rd;
  assign ex_is_load_to_rd = id_ex_q.valid && ex_ctrl.mem_read && (ex_ctrl.rd != 5'd0);
  assign stall_load_use   = if_id_q.valid && ex_is_load_to_rd && (
                              (id_ctrl.uses_rs1 && id_ctrl.rs1 == ex_ctrl.rd) ||
                              (id_ctrl.uses_rs2 && id_ctrl.rs2 == ex_ctrl.rd));

  always_comb begin
    id_ex_d.valid   = if_id_q.valid;
    id_ex_d.pc      = if_id_q.pc;
    id_ex_d.insn    = if_id_q.insn;
    id_ex_d.ctrl    = id_ctrl;
    id_ex_d.rs1_val = wb_bypass_rs1 ? mem_wb_q.wb_data : rf_rs1_data;
    id_ex_d.rs2_val = wb_bypass_rs2 ? mem_wb_q.wb_data : rf_rs2_data;
  end

  // ---- EX: forwarding, ALU, branch resolution ----------------------------------------
  typedef enum logic [1:0] {
    FWD_NONE  = 2'd0,  // value read in ID
    FWD_EXMEM = 2'd1,  // result of the previous instruction
    FWD_MEMWB = 2'd2   // result of the instruction before that (incl. load data)
  } fwd_sel_e;

  fwd_sel_e    fwd_a_sel, fwd_b_sel;
  logic [31:0] ex_rs1, ex_rs2;
  logic        exmem_writes, memwb_writes;

  assign exmem_writes = ex_mem_q.valid && ex_mem_q.reg_write && (ex_mem_q.rd != 5'd0);
  assign memwb_writes = mem_wb_q.valid && mem_wb_q.reg_write && (mem_wb_q.rd != 5'd0);

  always_comb begin
    fwd_a_sel = FWD_NONE;
    if (id_ex_q.valid && ex_ctrl.uses_rs1) begin
      if (exmem_writes && ex_mem_q.rd == ex_ctrl.rs1)      fwd_a_sel = FWD_EXMEM;
      else if (memwb_writes && mem_wb_q.rd == ex_ctrl.rs1) fwd_a_sel = FWD_MEMWB;
    end
    fwd_b_sel = FWD_NONE;
    if (id_ex_q.valid && ex_ctrl.uses_rs2) begin
      if (exmem_writes && ex_mem_q.rd == ex_ctrl.rs2)      fwd_b_sel = FWD_EXMEM;
      else if (memwb_writes && mem_wb_q.rd == ex_ctrl.rs2) fwd_b_sel = FWD_MEMWB;
    end
  end

  always_comb begin
    unique case (fwd_a_sel)
      FWD_EXMEM: ex_rs1 = ex_mem_q.result;
      FWD_MEMWB: ex_rs1 = mem_wb_q.wb_data;
      default:   ex_rs1 = id_ex_q.rs1_val;
    endcase
    unique case (fwd_b_sel)
      FWD_EXMEM: ex_rs2 = ex_mem_q.result;
      FWD_MEMWB: ex_rs2 = mem_wb_q.wb_data;
      default:   ex_rs2 = id_ex_q.rs2_val;
    endcase
  end

  logic [31:0] alu_a, alu_b, alu_y;
  logic        branch_taken;
  logic [31:0] ex_pc_plus4;
  logic        ex_halt;

  always_comb begin
    unique case (ex_ctrl.alu_a_sel)
      ALU_A_PC:   alu_a = id_ex_q.pc;
      ALU_A_ZERO: alu_a = 32'b0;
      default:    alu_a = ex_rs1;
    endcase
  end

  assign alu_b = ex_ctrl.alu_b_imm ? ex_ctrl.imm : ex_rs2;

  alu u_alu (
    .op (ex_ctrl.alu_op),
    .a  (alu_a),
    .b  (alu_b),
    .y  (alu_y)
  );

  branch_unit u_branch (
    .funct3 (ex_ctrl.funct3),
    .a      (ex_rs1),
    .b      (ex_rs2),
    .taken  (branch_taken)
  );

  assign ex_pc_plus4    = id_ex_q.pc + 32'd4;
  assign ex_redirect    = id_ex_q.valid &&
                          (ex_ctrl.is_jal || ex_ctrl.is_jalr || (ex_ctrl.is_branch && branch_taken));
  assign ex_redirect_pc = ex_ctrl.is_jalr ? {alu_y[31:1], 1'b0} : (id_ex_q.pc + ex_ctrl.imm);
  assign ex_halt        = id_ex_q.valid && (ex_ctrl.halt || ex_ctrl.illegal);
  assign flush          = ex_redirect || ex_halt;

  always_comb begin
    ex_mem_d.valid      = id_ex_q.valid;
    ex_mem_d.pc         = id_ex_q.pc;
    ex_mem_d.insn       = id_ex_q.insn;
    ex_mem_d.next_pc    = ex_halt ? id_ex_q.pc : (ex_redirect ? ex_redirect_pc : ex_pc_plus4);
    ex_mem_d.rd         = ex_ctrl.rd;
    ex_mem_d.reg_write  = ex_ctrl.reg_write;
    ex_mem_d.mem_read   = ex_ctrl.mem_read;
    ex_mem_d.mem_write  = ex_ctrl.mem_write;
    ex_mem_d.funct3     = ex_ctrl.funct3;
    ex_mem_d.result     = (ex_ctrl.wb_sel == WB_PC4) ? ex_pc_plus4 : alu_y;
    ex_mem_d.store_data = ex_rs2;
    ex_mem_d.halt       = ex_ctrl.halt;
    ex_mem_d.illegal    = ex_ctrl.illegal;
  end

  // ---- MEM ---------------------------------------------------------------------------
  logic [3:0]  byte_mask;
  logic [31:0] load_data;
  logic        mem_access;

  assign dmem_addr = {ex_mem_q.result[31:2], 2'b00};

  lsu u_lsu (
    .funct3      (ex_mem_q.funct3),
    .byte_offset (ex_mem_q.result[1:0]),
    .store_data  (ex_mem_q.store_data),
    .mem_rdata   (dmem_rdata),
    .byte_mask   (byte_mask),
    .store_wdata (dmem_wdata),
    .load_data   (load_data)
  );

  assign dmem_wmask = (ex_mem_q.valid && ex_mem_q.mem_write) ? byte_mask : 4'b0000;
  assign mem_access = ex_mem_q.mem_read || ex_mem_q.mem_write;

  always_comb begin
    mem_wb_d.valid     = ex_mem_q.valid;
    mem_wb_d.pc        = ex_mem_q.pc;
    mem_wb_d.insn      = ex_mem_q.insn;
    mem_wb_d.next_pc   = ex_mem_q.next_pc;
    mem_wb_d.rd        = ex_mem_q.rd;
    mem_wb_d.reg_write = ex_mem_q.reg_write;
    mem_wb_d.wb_data   = ex_mem_q.mem_read ? load_data : ex_mem_q.result;
    mem_wb_d.mem_addr  = mem_access ? dmem_addr : 32'b0;
    mem_wb_d.mem_rmask = ex_mem_q.mem_read ? byte_mask : 4'b0000;
    mem_wb_d.mem_wdata = ex_mem_q.mem_write ? dmem_wdata : 32'b0;
    mem_wb_d.mem_wmask = ex_mem_q.mem_write ? byte_mask : 4'b0000;
    mem_wb_d.halt      = ex_mem_q.halt;
    mem_wb_d.illegal   = ex_mem_q.illegal;
  end

  // ---- Pipeline register updates -------------------------------------------------------
  // A stall and a flush never happen in the same cycle: both are decided by the single
  // instruction in EX (a stall needs a load there, a flush a branch/jump/halt).
  always_ff @(posedge clk) begin
    if (!rst_n) begin
      pc_q            <= 32'b0;
      if_id_q         <= '0;
      id_ex_q         <= '0;
      ex_mem_q        <= '0;
      mem_wb_q        <= '0;
      fetch_stopped_q <= 1'b0;
      halted_q        <= 1'b0;
    end else begin
      // PC and IF/ID
      if (ex_redirect) begin
        pc_q    <= ex_redirect_pc;
        if_id_q <= '0;
      end else if (ex_halt || fetch_stopped_q) begin
        if_id_q <= '0;                       // fetch nothing more
      end else if (!stall_load_use) begin
        pc_q    <= pc_q + 32'd4;
        if_id_q <= '{valid: 1'b1, pc: pc_q, insn: imem_rdata};
      end                                    // stall: keep pc_q and if_id_q

      // ID/EX
      id_ex_q <= (flush || stall_load_use) ? '0 : id_ex_d;

      // EX/MEM and MEM/WB always advance.
      ex_mem_q <= ex_mem_d;
      mem_wb_q <= mem_wb_d;

      if (ex_halt) fetch_stopped_q <= 1'b1;
      if (mem_wb_q.valid && (mem_wb_q.halt || mem_wb_q.illegal)) halted_q <= 1'b1;
    end
  end

  assign halted = halted_q;

  // ---- WB and retire port ------------------------------------------------------------
  logic writes_rd;
  assign writes_rd = mem_wb_q.reg_write && (mem_wb_q.rd != 5'd0);

  assign rvfi_valid     = mem_wb_q.valid;
  assign rvfi_pc        = mem_wb_q.pc;
  assign rvfi_insn      = mem_wb_q.insn;
  assign rvfi_next_pc   = mem_wb_q.next_pc;
  assign rvfi_rd        = writes_rd ? mem_wb_q.rd : 5'd0;
  assign rvfi_rd_wdata  = writes_rd ? mem_wb_q.wb_data : 32'b0;
  assign rvfi_mem_addr  = mem_wb_q.mem_addr;
  assign rvfi_mem_rmask = mem_wb_q.mem_rmask;
  assign rvfi_mem_wdata = mem_wb_q.mem_wdata;
  assign rvfi_mem_wmask = mem_wb_q.mem_wmask;
  assign rvfi_halt      = mem_wb_q.halt;
  assign rvfi_trap      = mem_wb_q.illegal;

  // ---- Hazard events for functional coverage (read by the testbench only) -------------
  /* verilator lint_off UNUSEDSIGNAL */
  logic cov_flush_branch, cov_flush_jal, cov_flush_jalr, cov_flush_halt;
  logic cov_fwd_a_double, cov_fwd_b_double;
  logic cov_wb_bypass_rs1, cov_wb_bypass_rs2;

  // Only count a write-before-read bypass when ID holds a real instruction that reads it.
  assign cov_wb_bypass_rs1 = if_id_q.valid && id_ctrl.uses_rs1 && wb_bypass_rs1;
  assign cov_wb_bypass_rs2 = if_id_q.valid && id_ctrl.uses_rs2 && wb_bypass_rs2;

  assign cov_flush_branch = id_ex_q.valid && ex_ctrl.is_branch && branch_taken;
  assign cov_flush_jal    = id_ex_q.valid && ex_ctrl.is_jal;
  assign cov_flush_jalr   = id_ex_q.valid && ex_ctrl.is_jalr;
  assign cov_flush_halt   = ex_halt;
  // Both EX/MEM and MEM/WB hold the register: the newer value (EX/MEM) must be used.
  assign cov_fwd_a_double = (fwd_a_sel == FWD_EXMEM) && memwb_writes && mem_wb_q.rd == ex_ctrl.rs1;
  assign cov_fwd_b_double = (fwd_b_sel == FWD_EXMEM) && memwb_writes && mem_wb_q.rd == ex_ctrl.rs2;
  /* verilator lint_on UNUSEDSIGNAL */

endmodule
