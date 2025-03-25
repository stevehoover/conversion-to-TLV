module full_adder(
    // Inputs
    input wire a,
    input wire b,
    input wire cin,

    // Outputs
    output wire sum,
    output wire cout
);

    // Full adder implementation using standard logic gates
    assign sum = a ^ b ^ cin;
    assign cout = (a & b) | (b & cin) | (a & cin);

    // Sum calculation check
    always @(*) begin
        assert(sum == (a ^ b ^ cin));
    end

    // Carry generation check
    always @(*) begin
        assert(cout == ((a & b) | (b & cin) | (a & cin)));
    end

endmodule 