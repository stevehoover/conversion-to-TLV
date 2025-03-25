module d_flipflop #(
    parameter WIDTH = 1
)(
    // Clock and reset
    input wire clk,
    input wire rst_n,

    // Control signals
    input wire enable,

    // Data signals
    input wire [WIDTH-1:0] d,
    output reg [WIDTH-1:0] q
);

    // My D Flip-Flop implementation with enable and async reset
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            q <= {WIDTH{1'b0}};
        end
        else begin
            if (enable) begin
                q <= d;
            end
        end
    end

    // Checking if reset works correctly
    always @(posedge clk) begin
        if (!rst_n) begin
            assert(q == {WIDTH{1'b0}});
        end
    end

    // Making sure data is captured only when enabled
    always @(posedge clk) begin
        if (!rst_n) begin
            assert(q == {WIDTH{1'b0}});
        end
        else if (enable) begin
            assert(q == d);
        end
    end

endmodule 