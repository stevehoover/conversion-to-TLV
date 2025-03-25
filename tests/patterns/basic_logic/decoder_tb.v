module decoder_tb();

    // Parameters
    parameter IN_WIDTH = 3;
    parameter OUT_WIDTH = 8;

    // Signals
    reg [IN_WIDTH-1:0] in;
    wire [OUT_WIDTH-1:0] out;

    // Instantiate decoder
    decoder #(
        .IN_WIDTH(IN_WIDTH),
        .OUT_WIDTH(OUT_WIDTH)
    ) dut (
        .in(in),
        .out(out)
    );

    // Formal verification properties
    // Input range property
    always @(*) begin
        assert(in < OUT_WIDTH);
    end

    // One-hot output property
    always @(*) begin
        assert($onehot(out));
    end

    // Decoder function property
    always @(*) begin
        assert(out == (1'b1 << in));
    end

    // Initial block for simulation
    initial begin
        // Initialize signals
        in = 0;

        // Test each input value
        for (int i = 0; i < OUT_WIDTH; i++) begin
            #10 in = i;
            #10 assert(out == (1'b1 << i));
        end

        // End simulation
        #100 $finish;
    end

endmodule 