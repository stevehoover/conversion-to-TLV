module multiplexer_tb();

    // Parameters
    parameter WIDTH = 8;
    parameter SEL_WIDTH = 3;
    parameter NUM_INPUTS = 8;

    // Signals
    reg [SEL_WIDTH-1:0] sel;
    reg [WIDTH-1:0] data_in [NUM_INPUTS-1:0];
    wire [WIDTH-1:0] data_out;

    // Instantiate multiplexer
    multiplexer #(
        .WIDTH(WIDTH),
        .SEL_WIDTH(SEL_WIDTH),
        .NUM_INPUTS(NUM_INPUTS)
    ) dut (
        .sel(sel),
        .data_in(data_in),
        .data_out(data_out)
    );

    // Formal verification properties
    // Select range property
    always @(*) begin
        assert(sel < NUM_INPUTS);
    end

    // Data selection property
    always @(*) begin
        assert(data_out == data_in[sel]);
    end

    // Initial block for simulation
    initial begin
        // Initialize signals
        sel = 0;
        for (int i = 0; i < NUM_INPUTS; i++) begin
            data_in[i] = i;
        end

        // Test each input
        for (int i = 0; i < NUM_INPUTS; i++) begin
            #10 sel = i;
            #10 assert(data_out == data_in[i]);
        end

        // Test with different data
        #10 data_in[0] = 8'hAA;
        #10 sel = 0;
        #10 assert(data_out == 8'hAA);

        #10 data_in[4] = 8'h55;
        #10 sel = 4;
        #10 assert(data_out == 8'h55);

        // End simulation
        #100 $finish;
    end

endmodule 