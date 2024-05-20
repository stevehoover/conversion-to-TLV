module aliases(
  input wire C,
  input wire D,

  output wire sum,
  output wire carry
);

assign sum = C ^ D; // XOR gate
assign carry = C & D; // AND gate

endmodule