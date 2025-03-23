// Testbench for 4-bit counter
module counter_tb;
    // Testbench signals
    reg clk;
    reg rst;
    reg enable;
    wire [3:0] count;

    // Instantiate the counter
    counter_4bit dut (
        .clk(clk),
        .rst(rst),
        .enable(enable),
        .count(count)
    );

    // Clock generation
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    // Test stimulus
    initial begin
        // Initialize
        rst = 1;
        enable = 0;
        
        // Wait for 2 clock cycles
        @(posedge clk);
        @(posedge clk);
        
        // Release reset
        rst = 0;
        enable = 1;
        
        // Let it count for a while
        repeat(20) @(posedge clk);
        
        // Disable counting
        enable = 0;
        repeat(5) @(posedge clk);
        
        // Enable and reset
        enable = 1;
        rst = 1;
        repeat(3) @(posedge clk);
        rst = 0;
        
        // Let it count again
        repeat(5) @(posedge clk);
        
        $finish;
    end

    // Monitor changes
    initial begin
        $monitor("Time=%0t rst=%b enable=%b count=%b", 
                 $time, rst, enable, count);
    end

endmodule 