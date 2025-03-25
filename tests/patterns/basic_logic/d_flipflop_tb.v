// Testbench for D Flip-Flop RTL and TLV comparison
module d_flipflop_tb;

    // Parameters
    parameter WIDTH = 4;
    
    // Signals
    reg clk;
    reg rst_n;
    reg enable;
    reg [WIDTH-1:0] d;
    wire [WIDTH-1:0] q_rtl;
    wire [WIDTH-1:0] q_tlv;
    
    // Clock generation
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end
    
    // Instantiate both versions
    d_flipflop #(.WIDTH(WIDTH)) dff_rtl (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .d(d),
        .q(q_rtl)
    );
    
    d_flipflop_tlv #(.WIDTH(WIDTH)) dff_tlv (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .d(d),
        .q(q_tlv)
    );
    
    // Test stimulus
    initial begin
        // Initialize signals
        rst_n = 1;
        enable = 1;
        d = 0;
        
        // Reset test
        #10 rst_n = 0;
        #10 rst_n = 1;
        
        // Test data capture
        #10 d = 4'hA;
        #10 d = 4'h5;
        
        // Test enable/disable
        #10 enable = 0;
        #10 d = 4'hF;
        #10 enable = 1;
        
        // Test multiple values
        repeat(5) begin
            #10 d = $random;
        end
        
        // End simulation
        #100 $finish;
    end
    
    // Monitor outputs
    initial begin
        $monitor("Time=%0t rst_n=%b enable=%b d=%h q_rtl=%h q_tlv=%h",
                 $time, rst_n, enable, d, q_rtl, q_tlv);
    end
    
    // Compare outputs
    always @(posedge clk) begin
        if (q_rtl !== q_tlv) begin
            $error("Mismatch at time %0t: RTL=%h TLV=%h",
                   $time, q_rtl, q_tlv);
        end
    end
    
endmodule 