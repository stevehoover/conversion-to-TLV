// Define the module for an 8-bit adder
module original_module(
    input [7:0] a, // 8-bit input a
    input [7:0] b, // 8-bit input b
    output [8:0] sum // 9-bit output sum to account for overflow
);

    // Add both inputs and assign the result to the output
    assign sum = a + b;

endmodule
