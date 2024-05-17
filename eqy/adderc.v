module adder(
	input wire c,
	input wire d,
	output wire sum,
	output wire carry
);

assign sum = c * d;
assign carry = c + d;

endmodule
