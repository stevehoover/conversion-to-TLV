# Traffic Light Controller Conversion

This example demonstrates converting a simple state machine from Verilog to TL-Verilog. The traffic light controller manages three states: RED, GREEN, and YELLOW.

## Original Verilog Code

```verilog
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
```

## Conversion Steps

### 1. Three-space Indentation
- Applied standard three-space indentation
- Maintained readability of state machine logic

### 2. Clocking Analysis
- Single global clock input `clk`
- Used with `posedge` trigger
- No internal clock generation
- No gated or divided clocks

### 3. Reset Analysis
- Active-low reset signal `rst_n`
- Used asynchronously
- Will be converted to synchronous reset

### 4. State Machine Analysis
- Three states: RED, GREEN, YELLOW
- Counter-based state transitions
- Clear state encoding
- Well-defined outputs

### 5. Reset Signal Handling
- Convert to synchronous reset
- Maintain state machine functionality
- Preserve timing relationships

## TL-Verilog Version

```tlv
\TLV_version 1d: tl-x.org
\SV
   // State encoding
   localparam RED_STATE    = 2'b00;
   localparam GREEN_STATE  = 2'b01;
   localparam YELLOW_STATE = 2'b10;

   // Convert active-low async reset to active-high sync reset
   logic rst;
   assign rst = ~rst_n;

   // State and counter registers
   logic [1:0] state;
   logic [3:0] counter;

   // Output registers
   logic red, yellow, green;

   // State machine and counter logic
   always_ff @(posedge clk) begin
      if (rst) begin
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
\SV_plus
   // Transaction-level logic can be added here
   // For example, we could add:
   // - State transition monitoring
   // - Timing verification
   // - Safety checks
```

## Key Learnings

1. State machines in TL-Verilog maintain similar structure but with improved clarity
2. Synchronous reset conversion preserves functionality
3. State transitions remain explicit and easy to follow
4. Counter-based timing provides clear state durations

## Verification

The design has been verified using:
- Basic simulation
- State transition checks
- Timing verification
- Reset behavior validation

## Next Steps

Future improvements could include:
- Adding transaction-level monitoring
- Implementing safety checks
- Adding configurable timing parameters
- Including pedestrian crossing logic 