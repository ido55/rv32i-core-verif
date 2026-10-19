// Simulation top: the core plus instruction and data memories (MEM_WORDS x 32 bit each).
// cocotb loads programs by writing imem/dmem directly and watches the retire port,
// which is passed through to the top-level ports.
module tb_top #(
  parameter int MEM_WORDS = 4096  // 16 KiB per memory, addresses 0x0000..0x3FFF
) (
  input  logic        clk,
  input  logic        rst_n,

  output logic        halted,
  output logic        mem_fault,  // an access outside the memories (would silently alias)

  output logic        rvfi_valid,
  output logic [31:0] rvfi_pc,
  output logic [31:0] rvfi_insn,
  output logic [31:0] rvfi_next_pc,
  output logic [4:0]  rvfi_rd,
  output logic [31:0] rvfi_rd_wdata,
  output logic [31:0] rvfi_mem_addr,
  output logic [31:0] rvfi_mem_wdata,
  output logic [3:0]  rvfi_mem_wmask,
  output logic        rvfi_halt,
  output logic        rvfi_trap
);

  localparam int IDX_BITS = $clog2(MEM_WORDS);

  // imem is only written by cocotb (through VPI), never by RTL.
  /* verilator lint_off UNDRIVEN */
  logic [31:0] imem [MEM_WORDS];
  /* verilator lint_on UNDRIVEN */
  logic [31:0] dmem [MEM_WORDS];

  logic [31:0] imem_addr, imem_rdata;
  logic [31:0] dmem_addr, dmem_rdata, dmem_wdata;
  logic        dmem_re;
  logic [3:0]  dmem_wmask;

  core_single u_core (
    .clk            (clk),
    .rst_n          (rst_n),
    .imem_addr      (imem_addr),
    .imem_rdata     (imem_rdata),
    .dmem_addr      (dmem_addr),
    .dmem_re        (dmem_re),
    .dmem_rdata     (dmem_rdata),
    .dmem_wmask     (dmem_wmask),
    .dmem_wdata     (dmem_wdata),
    .halted         (halted),
    .rvfi_valid     (rvfi_valid),
    .rvfi_pc        (rvfi_pc),
    .rvfi_insn      (rvfi_insn),
    .rvfi_next_pc   (rvfi_next_pc),
    .rvfi_rd        (rvfi_rd),
    .rvfi_rd_wdata  (rvfi_rd_wdata),
    .rvfi_mem_addr  (rvfi_mem_addr),
    .rvfi_mem_wdata (rvfi_mem_wdata),
    .rvfi_mem_wmask (rvfi_mem_wmask),
    .rvfi_halt      (rvfi_halt),
    .rvfi_trap      (rvfi_trap)
  );

  // Word index into the memories, and whether the address is inside them.
  logic [IDX_BITS-1:0] imem_idx, dmem_idx;
  logic                imem_in_range, dmem_in_range;

  assign imem_idx      = imem_addr[IDX_BITS+1:2];
  assign dmem_idx      = dmem_addr[IDX_BITS+1:2];
  assign imem_in_range = (imem_addr[31:IDX_BITS+2] == '0);
  assign dmem_in_range = (dmem_addr[31:IDX_BITS+2] == '0);

  assign imem_rdata = imem[imem_idx];
  assign dmem_rdata = dmem[dmem_idx];

  always_ff @(posedge clk) begin
    for (int b = 0; b < 4; b++) begin
      if (dmem_wmask[b]) dmem[dmem_idx][8*b +: 8] <= dmem_wdata[8*b +: 8];
    end
  end

  // Only count data accesses from loads/stores: other instructions drive dmem_addr with
  // an ALU result that is not an address. Both addresses must also be word-aligned.
  logic dmem_access;
  assign dmem_access = dmem_re || (dmem_wmask != 4'b0000);
  assign mem_fault   = rvfi_valid && (
                         !imem_in_range || (imem_addr[1:0] != 2'b00) ||
                         (dmem_access && (!dmem_in_range || dmem_addr[1:0] != 2'b00)));

endmodule
