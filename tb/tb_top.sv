// Simulation top: one core plus instruction and data memories (MEM_WORDS x 32 bit each).
// Define PIPELINED (verilator -DPIPELINED) to use core_pipe, otherwise core_single. Both
// have identical ports and the instance is called u_core either way, so the testbench
// works with both unchanged.
// (A define, not a parameter + generate block: cocotb 1.9 cannot look inside generate
// scopes in Verilator 5.020 - "VPI: Not able to map type vpiScope".)
// cocotb loads programs by writing imem/dmem directly and watches the retire port,
// which is passed through to the top-level ports.
module tb_top #(
  parameter int MEM_WORDS = 4096  // 16 KiB per memory, addresses 0x0000..0x3FFF
) (
  input  logic        clk,
  input  logic        rst_n,

  output logic        halted,
  output logic        mem_fault,  // a retired access outside the memories (would silently alias)

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

  localparam int IDX_BITS = $clog2(MEM_WORDS);

  // imem is only written by cocotb (through VPI), never by RTL.
  /* verilator lint_off UNDRIVEN */
  logic [31:0] imem [MEM_WORDS];
  /* verilator lint_on UNDRIVEN */
  logic [31:0] dmem [MEM_WORDS];

  // The memories use only the index bits of each address; range and alignment are
  // checked on the retire port instead (mem_fault below).
  /* verilator lint_off UNUSEDSIGNAL */
  logic [31:0] imem_addr, dmem_addr;
  /* verilator lint_on UNUSEDSIGNAL */
  logic [31:0] imem_rdata, dmem_rdata, dmem_wdata;
  logic [3:0]  dmem_wmask;

  // .* connects every port to the signal of the same name declared above.
`ifdef PIPELINED
  core_pipe u_core (.*);
`else
  core_single u_core (.*);
`endif

  // Memories. Addresses are word-aligned; bits above the memory size are ignored here,
  // and checked by mem_fault below. A wrong-path fetch in the pipeline may alias, which is
  // harmless because that instruction never retires.
  logic [IDX_BITS-1:0] imem_idx, dmem_idx;
  assign imem_idx = imem_addr[IDX_BITS+1:2];
  assign dmem_idx = dmem_addr[IDX_BITS+1:2];

  assign imem_rdata = imem[imem_idx];
  assign dmem_rdata = dmem[dmem_idx];

  always_ff @(posedge clk) begin
    for (int b = 0; b < 4; b++) begin
      if (dmem_wmask[b]) dmem[dmem_idx][8*b +: 8] <= dmem_wdata[8*b +: 8];
    end
  end

  // Checked on the retire port, so it is exact for both cores: the retired instruction's
  // pc and (for loads/stores) its address must be word-aligned and inside the memories.
  /* verilator lint_off UNUSEDSIGNAL */  // the index bits are what is allowed to vary
  function automatic logic out_of_range(logic [31:0] addr);
    return (addr[31:IDX_BITS+2] != '0) || (addr[1:0] != 2'b00);
  endfunction
  /* verilator lint_on UNUSEDSIGNAL */

  logic retired_mem_access;
  assign retired_mem_access = (rvfi_mem_rmask != 4'b0000) || (rvfi_mem_wmask != 4'b0000);
  assign mem_fault = rvfi_valid &&
                     (out_of_range(rvfi_pc) || (retired_mem_access && out_of_range(rvfi_mem_addr)));

endmodule
