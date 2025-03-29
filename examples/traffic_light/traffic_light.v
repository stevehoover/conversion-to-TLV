module traffic_light (
   input wire clk,
   input wire rst_n,
   output reg red,
   output reg yellow,
   output reg green
);

   // State encoding
   localparam RED_STATE    = 2'b00;
   localparam GREEN_STATE  = 2'b01;
   localparam YELLOW_STATE = 2'b10;

   reg [1:0] state;
   reg [3:0] counter;

   // State machine and counter logic
   always @(posedge clk or negedge rst_n) begin
      if (!rst_n) begin
         state <= RED_STATE;
         counter <= 4'b0;
         red <= 1'b1;
         yellow <= 1'b0;
         green <= 1'b0;
      end
      else begin
         case (state)
            RED_STATE: begin
               if (counter == 4'd10) begin
                  state <= GREEN_STATE;
                  counter <= 4'b0;
                  red <= 1'b0;
                  green <= 1'b1;
               end
               else
                  counter <= counter + 1;
            end

            GREEN_STATE: begin
               if (counter == 4'd15) begin
                  state <= YELLOW_STATE;
                  counter <= 4'b0;
                  green <= 1'b0;
                  yellow <= 1'b1;
               end
               else
                  counter <= counter + 1;
            end

            YELLOW_STATE: begin
               if (counter == 4'd5) begin
                  state <= RED_STATE;
                  counter <= 4'b0;
                  yellow <= 1'b0;
                  red <= 1'b1;
               end
               else
                  counter <= counter + 1;
            end
         endcase
      end
   end

endmodule 