// 32 x 32-bit register file: two combinational read ports, one synchronous write port.
// x0 always reads as zero. A read in the same cycle as a write to the same register
// returns the OLD value (no internal bypass); the pipeline adds forwarding in M4.
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
