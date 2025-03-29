module counter (
    input wire clk,
    input wire rst_n,    // Active low reset
    input wire enable,   // Counter enable
    output reg [3:0] count  // 4-bit counter output
);

    // Counter with enable and reset
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            count <= 4'b0000;
        else if (enable)
            count <= count + 1'b1;
        else
            count <= count;  // Hold current value when disabled
    end

endmodule 