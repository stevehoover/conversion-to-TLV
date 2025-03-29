module shift_register (
   input wire clk,
   input wire rst_n,
   input wire load_en,    // Enable parallel loading
   input wire shift_en,   // Enable shifting
   input wire serial_in,  // Serial input
   input wire [7:0] data_in,  // Parallel input
   output reg [7:0] data_out  // Parallel output
);

   // Shift register logic
   always @(posedge clk or negedge rst_n) begin
      if (!rst_n)
         data_out <= 8'b0;
      else begin
         if (load_en)
            data_out <= data_in;
         else if (shift_en)
            data_out <= {serial_in, data_out[7:1]};
      end
   end

endmodule 