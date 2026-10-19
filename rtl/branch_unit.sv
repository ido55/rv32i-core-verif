// Branch condition: is the branch with this funct3 taken for operands a (rs1) and b (rs2)?
module branch_unit
  import rv32i_pkg::*;
(
  input  logic [2:0]  funct3,
  input  logic [31:0] a,
  input  logic [31:0] b,
  output logic        taken
);

  always_comb begin
    unique case (funct3)
      F3_BEQ:  taken = (a == b);
      F3_BNE:  taken = (a != b);
      F3_BLT:  taken = ($signed(a) <  $signed(b));
      F3_BGE:  taken = ($signed(a) >= $signed(b));
      F3_BLTU: taken = (a <  b);
      F3_BGEU: taken = (a >= b);
      default: taken = 1'b0;  // 010 / 011 are illegal; the decoder flags them
    endcase
  end

endmodule
