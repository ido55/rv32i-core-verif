// Load/store unit (combinational). The data memory is word-addressed with byte enables:
// - stores: shift the data into its byte lane(s) and build the byte mask,
// - loads:  pick the addressed byte/halfword out of the word and sign- or zero-extend it.
// Misaligned accesses are out of scope (the golden model raises on them).
module lsu
  import rv32i_pkg::*;
(
  input  logic [2:0]  funct3,       // access width and signedness
  input  logic [1:0]  byte_offset,  // addr[1:0]
  input  logic [31:0] store_data,   // rs2
  input  logic [31:0] mem_rdata,    // word read from data memory
  output logic [3:0]  byte_mask,    // bytes accessed (store byte enables / load read mask)
  output logic [31:0] store_wdata,  // data in its byte lanes
  output logic [31:0] load_data     // value written to rd
);

  logic [4:0]  shift;    // byte_offset * 8
  logic [15:0] shifted;  // low half of the memory word shifted so the addressed byte is in [7:0]

  assign shift   = {byte_offset, 3'b000};
  assign shifted = 16'(mem_rdata >> shift);

  always_comb begin
    unique case (funct3)
      F3_B, F3_BU: byte_mask = 4'b0001 << byte_offset;
      F3_H, F3_HU: byte_mask = 4'b0011 << byte_offset;
      F3_W:        byte_mask = 4'b1111;
      default:     byte_mask = 4'b0000;
    endcase
  end

  always_comb begin
    unique case (funct3)
      F3_B:    store_wdata = {24'b0, store_data[7:0]}  << shift;
      F3_H:    store_wdata = {16'b0, store_data[15:0]} << shift;
      default: store_wdata = store_data;
    endcase
  end

  always_comb begin
    unique case (funct3)
      F3_B:    load_data = {{24{shifted[7]}}, shifted[7:0]};
      F3_H:    load_data = {{16{shifted[15]}}, shifted[15:0]};
      F3_BU:   load_data = {24'b0, shifted[7:0]};
      F3_HU:   load_data = {16'b0, shifted[15:0]};
      default: load_data = mem_rdata;  // LW
    endcase
  end

endmodule
