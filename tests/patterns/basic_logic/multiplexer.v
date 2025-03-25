module multiplexer #(
    parameter WIDTH = 8,
    parameter SEL_WIDTH = 3,
    parameter NUM_INPUTS = 8
)(
    // Select signal
    input wire [SEL_WIDTH-1:0] sel,

    // Input data
    input wire [WIDTH-1:0] data_in [NUM_INPUTS-1:0],

    // Output
    output wire [WIDTH-1:0] data_out
);

    // Multiplexer implementation using array indexing
    assign data_out = data_in[sel];

    // Select signal range check
    always @(*) begin
        assert(sel < NUM_INPUTS);
    end

endmodule 