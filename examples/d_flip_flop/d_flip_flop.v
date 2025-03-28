module d_flip_flop (
    input wire clk,
    input wire rst_n,  // Active low reset
    input wire d,
    output reg q
);

    // D flip-flop with asynchronous reset
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 1'b0;
        else
            q <= d;
    end

endmodule 