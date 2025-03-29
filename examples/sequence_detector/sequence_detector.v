module sequence_detector (
   input wire clk,
   input wire rst_n,
   input wire in,
   output reg match
);

   // State encoding
   localparam IDLE    = 3'b000;  // Initial state
   localparam S1      = 3'b001;  // Found '1'
   localparam S10     = 3'b010;  // Found '10'
   localparam S101    = 3'b011;  // Found '101'
   localparam S10_1   = 3'b100;  // Found '10' and current input is '1'

   reg [2:0] state;
   reg [2:0] next_state;

   // State machine logic
   always @(posedge clk or negedge rst_n) begin
      if (!rst_n)
         state <= IDLE;
      else
         state <= next_state;
   end

   // Next state logic
   always @(*) begin
      case (state)
         IDLE:    next_state = in ? S1 : IDLE;
         S1:      next_state = in ? S1 : S10;
         S10:     next_state = in ? S101 : IDLE;
         S101:    next_state = in ? S10_1 : IDLE;
         S10_1:   next_state = in ? S10_1 : S10;
      endcase
   end

   // Output logic
   always @(posedge clk or negedge rst_n) begin
      if (!rst_n)
         match <= 1'b0;
      else
         match <= (state == S101);
   end

endmodule 