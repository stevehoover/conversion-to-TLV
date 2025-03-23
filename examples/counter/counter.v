// A simple 4-bit counter with synchronous reset
module counter_4bit (
    input wire clk,      // Clock input
    input wire rst,      // Reset input (active high)
    input wire enable,   // Counter enable
    output reg [3:0] count  // 4-bit counter output
);

    // Counter logic
    always @(posedge clk) begin
        if (rst) begin
            // Reset counter to 0
            count <= 4'b0000;
        end else if (enable) begin
            // Increment counter when enabled
            count <= count + 1;
        end
    end

endmodule 