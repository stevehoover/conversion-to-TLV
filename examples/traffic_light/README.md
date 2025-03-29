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
   module traffic_light (
      input wire clk,
      input wire rst_n,
      output reg red,
      output reg yellow,
      output reg green
   );
\TLV
   // Connect inputs:
   $reset = ~ *rst_n;
   
   // State machine logic using |state_machine: notation
   |state_machine: RED_STATE, GREEN_STATE, YELLOW_STATE
   
   // State and counter logic
   $State[1:0] =
        $reset ? RED_STATE :
        // State transitions
        ($State == RED_STATE && $Counter == 4'd10) ? GREEN_STATE :
        ($State == GREEN_STATE && $Counter == 4'd15) ? YELLOW_STATE :
        ($State == YELLOW_STATE && $Counter == 4'd5) ? RED_STATE :
        //default
        $RETAIN;
   
   // Counter logic
   $Counter[3:0] =
        $reset ? 4'b0 :
        ($State == RED_STATE && $Counter == 4'd10) ? 4'b0 :
        ($State == GREEN_STATE && $Counter == 4'd15) ? 4'b0 :
        ($State == YELLOW_STATE && $Counter == 4'd5) ? 4'b0 :
        //default
        $Counter + 1;
   
   // Output logic
   $Red = ($State == RED_STATE);
   $Yellow = ($State == YELLOW_STATE);
   $Green = ($State == GREEN_STATE);
   
   // Connect outputs (immediate)
   *red = $Red;
   *yellow = $Yellow;
   *green = $Green;
\SV
   endmodule
```

