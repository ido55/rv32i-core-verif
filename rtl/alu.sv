// Combinational 32-bit ALU for RV32I.
module alu
  import rv32i_pkg::*;
(
  input  alu_op_e     op,
  input  logic [31:0] a,
  input  logic [31:0] b,
  output logic [31:0] y
);

  // RV32I shifts use only the low 5 bits of the second operand.
  logic [4:0] shamt;
  assign shamt = b[4:0];

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

endmodule
