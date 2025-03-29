# Counter Conversion

This example demonstrates converting a 4-bit counter from Verilog to TL-Verilog. The counter includes synchronous reset and enable functionality.

## Original Verilog Code

```verilog
module counter (
   input wire clk,
   input wire rst_n,
   input wire enable,
   output reg [3:0] count
);

   // Counter logic
   always @(posedge clk or negedge rst_n) begin
      if (!rst_n)
         count <= 4'b0;
      else if (enable)
         count <= count + 1;
   end

endmodule
```

## Conversion Steps

### 1. Three-space Indentation
- Applied standard three-space indentation
- Maintained readability of control logic

### 2. Clocking Analysis
- Single global clock input `clk`
- Used with `posedge` trigger
- No internal clock generation
- No gated or divided clocks

### 3. Reset Analysis
- Active-low reset signal `rst_n`
- Used asynchronously
- Will be converted to synchronous reset

### 4. Control Signal Analysis
- Two control signals: reset and enable
- Clear priority: reset takes precedence
- No conflicting conditions

### 5. Reset Signal Handling
- Convert to synchronous reset
- Maintain counter functionality
- Preserve timing relationships

## TL-Verilog Version

```tlv
\TLV_version 1d: tl-x.org
\SV
   module counter (
      input wire clk,
      input wire rst_n,
      input wire enable,
      output reg [3:0] count
   );
\TLV
   // Connect inputs:
   $reset = ~ *rst_n;
   $enable = *enable;
   
   // Counter logic using ternary operator
   $Count[3:0] = 
        $reset  ? 4'b0 :
        $enable ? $Count[3:0] + 1 :
        //default
                  $RETAIN;
   
   // Connect outputs (immediate)
   *count = $Count;
\SV
   endmodule
```
