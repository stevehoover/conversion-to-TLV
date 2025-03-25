module full_adder_tb();

    // Signals
    reg a;
    reg b;
    reg cin;
    wire sum;
    wire cout;

    // Instantiate full adder
    full_adder dut (
        .a(a),
        .b(b),
        .cin(cin),
        .sum(sum),
        .cout(cout)
    );

    // Formal verification properties
    // Sum property
    always @(*) begin
        assert(sum == (a ^ b ^ cin));
    end

    // Carry property
    always @(*) begin
        assert(cout == ((a & b) | (b & cin) | (a & cin)));
    end

    // Initial block for simulation
    initial begin
        // Initialize signals
        a = 1'b0;
        b = 1'b0;
        cin = 1'b0;

        // Test all input combinations
        #10 a = 1'b0; b = 1'b0; cin = 1'b0;
        #10 assert(sum == 1'b0 && cout == 1'b0);

        #10 a = 1'b0; b = 1'b0; cin = 1'b1;
        #10 assert(sum == 1'b1 && cout == 1'b0);

        #10 a = 1'b0; b = 1'b1; cin = 1'b0;
        #10 assert(sum == 1'b1 && cout == 1'b0);

        #10 a = 1'b0; b = 1'b1; cin = 1'b1;
        #10 assert(sum == 1'b0 && cout == 1'b1);

        #10 a = 1'b1; b = 1'b0; cin = 1'b0;
        #10 assert(sum == 1'b1 && cout == 1'b0);

        #10 a = 1'b1; b = 1'b0; cin = 1'b1;
        #10 assert(sum == 1'b0 && cout == 1'b1);

        #10 a = 1'b1; b = 1'b1; cin = 1'b0;
        #10 assert(sum == 1'b0 && cout == 1'b1);

        #10 a = 1'b1; b = 1'b1; cin = 1'b1;
        #10 assert(sum == 1'b1 && cout == 1'b1);

        // End simulation
        #100 $finish;
    end

endmodule 