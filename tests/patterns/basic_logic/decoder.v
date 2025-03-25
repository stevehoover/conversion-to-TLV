module decoder #(
    parameter IN_WIDTH = 3,
    parameter OUT_WIDTH = 8
)(
    // Input
    input wire [IN_WIDTH-1:0] in,

    // Output
    output wire [OUT_WIDTH-1:0] out
);

    // Binary to one-hot decoder using shift operation
    assign out = (1'b1 << in);

    // Input range check
    always @(*) begin
        assert(in < OUT_WIDTH);
    end

    // One-hot output check
    always @(*) begin
        assert($onehot(out));
    end

endmodule 