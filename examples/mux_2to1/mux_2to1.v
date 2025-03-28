module mux_2to1 (
    input wire [7:0] in0,    // First input
    input wire [7:0] in1,    // Second input
    input wire sel,          // Select signal
    output wire [7:0] out    // Output
);

    // 2-to-1 multiplexer implementation
    assign out = sel ? in1 : in0;

endmodule 