module aliases(
	input wire C,
	input wire D,
	output wire sum,
	output wire carry
);

assign sum = C ^ D;
assign carry = C & D;

endmodule

